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


def fetch_entity_id_map() -> dict:
    entities = cg_get("entities/list")
    out = {}
    for e in entities if isinstance(entities, list) else entities.get("entities", []):
        symbol = (e.get("symbol") or "").strip().upper()
        entity_id = e.get("entity_id") or e.get("id")
        if symbol and entity_id and symbol not in out:
            out[symbol] = entity_id
    return out


def fetch_transaction_history(entity_id: str) -> list[dict]:
    data = cg_get(
        f"public_treasury/{entity_id}/transaction_history",
        {"coin_ids": "bitcoin", "per_page": 250},
    )
    txs = data.get("transactions", data) if isinstance(data, dict) else data
    if not isinstance(txs, list):
        return []
    return txs


def parse_tx_date(raw) -> str | None:
    if not raw:
        return None
    text = str(raw)[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


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
    return sorted(by_date.items())


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

    entity_map = fetch_entity_id_map()
    time.sleep(REQUEST_SLEEP_SECONDS)

    company_series = {}  # name -> [(date, balance, avg_cost), ...]
    for c in companies:
        symbol = (c.get("symbol") or "").strip().upper()
        entity_id = entity_map.get(symbol)
        if not entity_id:
            log.warning(f"Sin entity_id para {c.get('name')} ({symbol}) - se omite")
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

    upsert_rows(rows)
    log.info(f"{len(rows)} dias actualizados a partir de {len(company_series)} empresas")


if __name__ == "__main__":
    main()
