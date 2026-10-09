"""
Costo base de ETFs spot de Bitcoin (Fase 2 del indicador "Costo Base Institucional" - ver
update_treasury_cost_basis_daily.py para la Fase 1, treasuries corporativas).

Fuente: tabla publica de flujos diarios de Farside Investors (en millones de USD por ETF),
convertida a BTC comprado/vendido cada dia con el precio de cierre de ese dia (blockchain.info,
la misma fuente que ya usa el sitio para el historico completo - CoinGecko en su tier gratis
solo da 365 dias). Se calcula el costo promedio ponderado (VWAC) acumulado por ETF y se agregan
todos entre si.

Farside esta detras de un challenge JS real de Cloudflare ("Just a moment...", confirmado
corriendo el robot de verdad - un simple requests.get con headers de navegador no basta, por
mas realistas que sean, porque no hay motor JS que lo resuelva). Por eso fetch_farside_table usa
Playwright (Chromium headless) en vez de requests: un navegador de verdad SI puede resolver ese
challenge solo, con tal de esperar a que la pagina real cargue.

GBTC se excluye del agregado: traia BTC desde antes de convertirse en ETF (enero 2024) y su
historial de flujos post-conversion es casi puro de salida - tratarlo solo con flujos post-
conversion daria un balance/costo sin sentido (negativo o indefinido).

Formula VWAC por ETF (se reconstruye el historico completo en cada corrida, igual que el resto
de robots del repo - Farside no tiene paginacion/limite de tasa documentado y el calculo entero
es barato):
  - entrada ese dia (flow > 0 USD): btc += flow/precio ; costo += flow
  - salida ese dia (flow < 0 USD): btc_out = min(|flow|/precio, btc) ; costo -= btc_out*(costo/btc)
    ; btc -= btc_out   (el costo promedio por moneda NO cambia en una salida, solo el total)
  - costo base del ETF en cualquier momento = costo / btc

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import re
import sys
import logging
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_etf_cost_basis_daily")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "etf_cost_basis_daily"

FARSIDE_URL = "https://farside.co.uk/bitcoin-etf-flow-all-data/"
EXCLUDE_TICKERS = {"GBTC", "TOTAL", ""}
MIN_SANE_PRICE = 100
MAX_SANE_PRICE = 1_000_000

MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def fetch_btc_price_history() -> dict:
    """fecha ISO -> precio de cierre usd. CoinGecko en su tier gratuito solo da 365 dias de
    historico (devuelve 401 "exceeds the allowed time range" con days=max) - se usa en su lugar
    blockchain.info, la misma fuente que ya usa fetchHalvingHistory() del lado del cliente para
    el historico completo de precio. OJO: con timespan=all, blockchain.info devuelve una
    muestra dispersa (confirmado en una corrida real: solo 174 de 704 dias de ETFs tenian
    precio, ~1 de cada 4) en vez de un punto por dia - los ETFs solo llevan desde ene-2024, asi
    que alcanza de sobra con una ventana mas corta, que si viene en resolucion diaria."""
    resp = requests.get(
        "https://api.blockchain.info/charts/market-price",
        params={"timespan": "4years", "format": "json", "cors": "true"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"blockchain.info respondio {resp.status_code}: {resp.text[:300]}")
    out = {}
    for row in resp.json().get("values", []):
        price = row.get("y")
        if not price or price <= 0:
            continue
        d = datetime.fromtimestamp(row["x"], tz=timezone.utc).date().isoformat()
        out[d] = price
    return out


def parse_farside_date(text: str) -> str | None:
    m = re.match(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", text.strip())
    if not m:
        return None
    day, mon, year = m.groups()
    month = MONTHS.get(mon[:3].title())
    if not month:
        return None
    try:
        return date(int(year), month, int(day)).isoformat()
    except ValueError:
        return None


def parse_flow_value(text: str) -> float | None:
    text = text.strip().replace(",", "").replace("US$", "").replace("$", "")
    if text in ("", "-", "—"):
        return None
    neg = text.startswith("(") and text.endswith(")")
    if neg:
        text = text[1:-1]
    try:
        v = float(text)
    except ValueError:
        return None
    return -v if neg else v


FARSIDE_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")


def fetch_farside_table() -> tuple[list[str], list[dict]]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(user_agent=FARSIDE_USER_AGENT)
        page.goto(FARSIDE_URL, wait_until="domcontentloaded", timeout=45000)
        # Cloudflare muestra "Just a moment..." un par de segundos y redirige solo a la pagina
        # real - un Chromium de verdad lo resuelve el solo, basta con esperar a que aparezca la
        # tabla (si nunca aparece, el timeout de abajo lo deja claro en vez de colgarse)
        page.wait_for_selector("table", timeout=30000)
        html = page.content()
        browser.close()
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError("no se encontro ninguna tabla en la pagina de Farside")
    trs = table.find_all("tr")
    if not trs:
        raise RuntimeError("tabla de Farside sin filas")
    header_cells = [c.get_text(strip=True) for c in trs[0].find_all(["th", "td"])]
    tickers = header_cells[1:]
    rows = []
    for tr in trs[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if not cells:
            continue
        d = parse_farside_date(cells[0])
        if d is None:
            continue  # fila "Total" / cabecera repetida / cualquier fila que no es una fecha
        values = {}
        for ticker, raw in zip(tickers, cells[1:]):
            values[ticker] = parse_flow_value(raw)
        rows.append({"date": d, **values})
    return tickers, rows


def compute_etf_daily_rows(tickers: list[str], flow_rows: list[dict], btc_price: dict) -> list[dict]:
    active = [t for t in tickers if t.strip().upper() not in EXCLUDE_TICKERS]
    state = {t: {"btc": 0.0, "cost": 0.0} for t in active}
    out = []
    for row in sorted(flow_rows, key=lambda r: r["date"]):
        d = row["date"]
        price = btc_price.get(d)
        if price is None or not (MIN_SANE_PRICE <= price <= MAX_SANE_PRICE):
            continue
        for t in active:
            flow_m = row.get(t)
            if flow_m is None:
                continue
            flow_usd = flow_m * 1_000_000  # Farside reporta en millones de USD
            st = state[t]
            if flow_usd > 0:
                st["btc"] += flow_usd / price
                st["cost"] += flow_usd
            elif flow_usd < 0 and st["btc"] > 0:
                btc_out = min(-flow_usd / price, st["btc"])
                avg = st["cost"] / st["btc"]
                st["cost"] -= btc_out * avg
                st["btc"] -= btc_out
        total_btc = sum(s["btc"] for s in state.values())
        total_cost = sum(s["cost"] for s in state.values())
        if total_btc > 0:
            avg_cost = total_cost / total_btc
            if MIN_SANE_PRICE <= avg_cost <= MAX_SANE_PRICE:
                out.append({
                    "date": d,
                    "total_btc_held": round(total_btc, 4),
                    "avg_cost_basis_usd": round(avg_cost, 2),
                })
    return forward_fill_daily(out), state, active


def forward_fill_daily(rows: list[dict]) -> list[dict]:
    # Farside solo publica dias habiles (el mercado de ETFs en EEUU cierra fines de semana) -
    # sin esto, la tabla queda con huecos en sabado/domingo y el merge del lado del cliente los
    # interpreta como "todavia no hay ETFs ese dia" en vez de "arrastrar el ultimo valor
    # conocido", alternando entre el costo combinado (dia habil) y solo-Treasuries (fin de
    # semana) - un zigzag en el grafico que no es un dato real, es un hueco (le paso de verdad)
    if not rows:
        return rows
    by_date = {r["date"]: r for r in rows}
    filled = []
    d = date.fromisoformat(rows[0]["date"])
    today = datetime.now(timezone.utc).date()
    last = None
    while d <= today:
        iso = d.isoformat()
        if iso in by_date:
            last = by_date[iso]
        if last is not None:
            filled.append({"date": iso, "total_btc_held": last["total_btc_held"],
                           "avg_cost_basis_usd": last["avg_cost_basis_usd"]})
        d += timedelta(days=1)
    return filled


def delete_all_rows():
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

    btc_price = fetch_btc_price_history()
    if btc_price:
        dates_sorted = sorted(btc_price)
        log.info(f"{len(btc_price)} dias de precio BTC, de {dates_sorted[0]} a {dates_sorted[-1]}")
    else:
        log.info("0 dias de precio BTC")

    tickers, flow_rows = fetch_farside_table()
    log.info(f"Farside: columnas {tickers}, {len(flow_rows)} filas de fecha")

    rows, state, active = compute_etf_daily_rows(tickers, flow_rows, btc_price)
    if not rows:
        log.error("No se pudo construir la serie de ETFs - no se actualiza Supabase")
        sys.exit(1)

    for t in sorted(active, key=lambda tk: state[tk]["btc"], reverse=True):
        btc = state[t]["btc"]
        avg = state[t]["cost"] / btc if btc > 0 else 0
        log.info(f"  {t}: {btc:,.0f} BTC @ ${avg:,.0f} costo base")
    costs = [r["avg_cost_basis_usd"] for r in rows]
    log.info(f"avg_cost_basis_usd en el historico: min=${min(costs):,.0f} max=${max(costs):,.0f} hoy=${costs[-1]:,.0f}")

    delete_all_rows()
    upsert_rows(rows)
    log.info(f"{len(rows)} dias actualizados a partir de {len(active)} ETFs")


if __name__ == "__main__":
    main()
