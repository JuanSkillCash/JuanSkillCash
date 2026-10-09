"""
Actualizacion diaria del costo base institucional de Bitcoin (solo empresas con BTC en su
balance corporativo - Fase 1 del indicador "Costo Base Institucional"; los ETFs spot quedan
para una Fase 2 aparte).

Fuente: API publica de CoinGecko (Public Treasury). Reconstruye el historico completo en cada
corrida (no solo "los ultimos dias"): la API gratuita no permite pedir solo lo nuevo, y repetir
todo el calculo cada dia es mas simple y se autocorrige si CoinGecko ajusta datos retroactivos.

Pasos:
  1. companies/public_treasury/bitcoin -> lista de empresas con total_holdings y
     total_entry_value_usd (filtra las que no reportan costo base) y las ordena por tenencia.
  2. entities/list -> mapa symbol -> entity_id (CoinGecko no expone el entity_id en el paso 1).
  3. Para las N empresas con mas BTC: public_treasury/{entity_id}/transaction_history
     (coin_ids=bitcoin, per_page=250 cabe en una sola pagina gratuita para cualquier empresa
     del top, incluida Strategy con ~120 transacciones) -> serie de holding_balance /
     average_entry_value_usd por fecha.
  4. Para cada dia (desde la primera transaccion encontrada hasta hoy) se arrastra el ultimo
     valor conocido de cada empresa (forward-fill) y se agrega:
       total_btc_held      = suma de holding_balance de todas las empresas ese dia
       avg_cost_basis_usd   = suma(holding_balance_i * average_entry_value_usd_i) / total_btc_held

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import re
import sys
import time
import logging
from datetime import date, timedelta, datetime, timezone

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_treasury_cost_basis_daily")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "treasury_cost_basis_daily"

# Mismo API key "Demo" de CoinGecko que ya se usa del lado del cliente en index.html (es publico,
# no requiere mantenerlo en secreto - CoinGecko lo trata como identificador de tasa de uso, no
# como credencial).
COINGECKO_API_KEY = "CG-B17Pfy5LygHBnhQCoxkh2U2W"
CG_BASE = "https://api.coingecko.com/api/v3"
TOP_N_COMPANIES = 20
REQUEST_SLEEP_SECONDS = 1.5


def cg_get(path: str, params: dict | None = None) -> dict:
    params = dict(params or {})
    params["x_cg_demo_api_key"] = COINGECKO_API_KEY
    resp = requests.get(f"{CG_BASE}/{path}", params=params, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"CoinGecko respondio {resp.status_code} en {path}: {resp.text[:300]}")
    return resp.json()


def fetch_top_companies() -> list[dict]:
    data = cg_get("companies/public_treasury/bitcoin")
    companies = [
        c for c in data.get("companies", [])
        if c.get("total_entry_value_usd") and c.get("total_holdings")
    ]
    companies.sort(key=lambda c: c["total_holdings"], reverse=True)
    return companies[:TOP_N_COMPANIES]


def normalize_symbol(symbol: str) -> str:
    # companies/public_treasury/bitcoin devuelve tickers tipo "MSTR.US"/"3350.T"/"SWC.L" (con
    # sufijo de bolsa) mientras que entities/list los da "pelados" (solo "MSTR") - sin esto casi
    # ninguna empresa calza (confirmado al correr el robot: 14 de 20 quedaban sin entity_id)
    return (symbol or "").strip().upper().split(".")[0]


_NAME_SUFFIXES = (" inc", " corp", " corporation", " co", " ltd", " plc", " group",
                   " holdings", " holding", " technologies", " technology", " llc", " sa", " ag")


def normalize_name(name: str) -> str:
    n = (name or "").lower()
    n = re.sub(r"[^a-z0-9 ]", "", n)
    for suf in _NAME_SUFFIXES:
        if n.endswith(suf):
            n = n[: -len(suf)]
    return n.strip()


def fetch_entity_id_map() -> tuple[dict, dict]:
    raw = cg_get("entities/list")
    entities = raw if isinstance(raw, list) else raw.get("entities", raw.get("data", []))
    by_symbol, by_name = {}, {}
    for e in entities:
        entity_id = e.get("entity_id") or e.get("id")
        if not entity_id:
            continue
        symbol = normalize_symbol(e.get("symbol") or "")
        if symbol and symbol not in by_symbol:
            by_symbol[symbol] = entity_id
        name = normalize_name(e.get("name") or "")
        if name and name not in by_name:
            by_name[name] = entity_id
    # diagnostico temporal: la primera corrida real solo calzo 1 de 20 empresas (ni Strategy ni
    # Tesla aparecieron) - esto confirma si entities/list de verdad trae esos nombres y bajo que
    # campos exactos, en vez de seguir adivinando el formato a ciegas
    log.info(f"entities/list: {len(entities)} entidades, {len(by_symbol)} con symbol, {len(by_name)} con name")
    if entities:
        log.info(f"ejemplo crudo de una entidad: {entities[0]}")
    needles = ("strateg", "tesla", "metaplanet")
    for e in entities:
        n = (e.get("name") or "").lower()
        if any(x in n for x in needles):
            log.info(f"match por nombre en entities/list: {e}")
    return by_symbol, by_name


def fetch_transaction_history(entity_id: str) -> list[dict]:
    data = cg_get(
        f"public_treasury/{entity_id}/transaction_history",
        {"coin_ids": "bitcoin", "per_page": 250},
    )
    txs = data.get("transactions", data) if isinstance(data, dict) else data
    if not isinstance(txs, list):
        return []
    return txs


COVERAGE_START = date(2020, 8, 1)  # CoinGecko documenta historico desde agosto 2020


def parse_tx_date(raw) -> str | None:
    if not raw:
        return None
    text = str(raw)[:10]
    try:
        d = date.fromisoformat(text)
    except ValueError:
        return None
    # defensa contra fechas basura del API (sentinelas tipo "0001-01-01" o fechas futuras) que
    # de otro modo arman un rango de dias absurdo en el forward-fill (ya paso una vez: una sola
    # fecha mala produjo "90323 dias actualizados")
    today = datetime.now(timezone.utc).date()
    if d < COVERAGE_START or d > today:
        return None
    return d.isoformat()


def build_company_series(txs: list[dict]) -> list[tuple]:
    rows = []
    for tx in txs:
        d = parse_tx_date(tx.get("date"))
        balance = tx.get("holding_balance")
        avg_cost = tx.get("average_entry_value_usd")
        if d is None or balance is None or avg_cost is None:
            continue
        rows.append((d, float(balance), float(avg_cost)))
    rows.sort(key=lambda r: r[0])
    # si hay varias transacciones el mismo dia, nos quedamos con la ultima (balance ya acumulado)
    by_date = {}
    for d, balance, avg_cost in rows:
        by_date[d] = (balance, avg_cost)
    return [(d, balance, avg_cost) for d, (balance, avg_cost) in sorted(by_date.items())]


def delete_all_rows():
    # la tabla la llena solo este robot y se reconstruye completa cada corrida - se borra todo
    # antes de insertar en vez de solo hacer upsert, para que un run anterior con datos malos
    # (ej. el bug de fechas que una vez dejo 90323 dias de basura) no deje filas huerfanas que un
    # upsert nunca borra
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?date=gte.1900-01-01"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "return=minimal",
    }
    resp = requests.delete(url, headers=headers, timeout=60)
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase (delete) respondio {resp.status_code}: {resp.text[:500]}")


def upsert_rows(rows: list[dict]):
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=date"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    BATCH = 2000
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        resp = requests.post(url, json=batch, headers=headers, timeout=60)
        if resp.status_code >= 300:
            raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text[:500]}")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    companies = fetch_top_companies()
    log.info(f"{len(companies)} empresas candidatas (top {TOP_N_COMPANIES} por tenencia con costo base reportado)")

    entity_by_symbol, entity_by_name = fetch_entity_id_map()
    time.sleep(REQUEST_SLEEP_SECONDS)

    company_series = {}  # name -> [(date, balance, avg_cost), ...]
    for c in companies:
        symbol = normalize_symbol(c.get("symbol") or "")
        entity_id = entity_by_symbol.get(symbol) or entity_by_name.get(normalize_name(c.get("name") or ""))
        if not entity_id:
            log.warning(f"Sin entity_id para {c.get('name')} ({c.get('symbol')}) - se omite")
            continue
        try:
            txs = fetch_transaction_history(entity_id)
        except RuntimeError as err:
            log.warning(f"Fallo transaction_history de {c.get('name')} ({entity_id}): {err}")
            continue
        series = build_company_series(txs)
        if series:
            company_series[c["name"]] = series
        time.sleep(REQUEST_SLEEP_SECONDS)

    if not company_series:
        log.error("No se pudo construir ninguna serie de empresas - no se actualiza Supabase")
        sys.exit(1)

    first_dates = [series[0][0] for series in company_series.values()]
    start = min(date.fromisoformat(d) for d in first_dates)
    today = datetime.now(timezone.utc).date()

    # puntero de forward-fill por empresa: indice del ultimo elemento <= dia actual
    pointers = {name: -1 for name in company_series}
    last_known = {name: (0.0, 0.0) for name in company_series}

    rows = []
    d = start
    while d <= today:
        iso = d.isoformat()
        total_btc = 0.0
        weighted_sum = 0.0
        for name, series in company_series.items():
            idx = pointers[name]
            while idx + 1 < len(series) and series[idx + 1][0] <= iso:
                idx += 1
                last_known[name] = (series[idx][1], series[idx][2])
            pointers[name] = idx
            if idx >= 0:
                balance, avg_cost = last_known[name]
                total_btc += balance
                weighted_sum += balance * avg_cost
        if total_btc > 0:
            rows.append({
                "date": iso,
                "total_btc_held": round(total_btc, 4),
                "avg_cost_basis_usd": round(weighted_sum / total_btc, 2),
            })
        d += timedelta(days=1)

    delete_all_rows()
    upsert_rows(rows)
    log.info(f"{len(rows)} dias actualizados a partir de {len(company_series)} empresas")


if __name__ == "__main__":
    main()
