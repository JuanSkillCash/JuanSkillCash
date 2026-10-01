"""
Actualizacion diaria de los insumos de "Costo de Produccion" en Supabase - ver
backfill_cost_of_production.py para el detalle de las fuentes y por que nunca se le pide
DiffMean a Coin Metrics.

Igual que el backfill, vuelve a pedir la serie COMPLETA cada vez (no solo "los ultimos dias"):
ambas fuentes son llamadas baratas (sin paginar miles de paginas) y asi se corrige cualquier
ajuste retroactivo que alguna de las dos le haga a dias pasados, sin mantener un estado de
"ultima fecha sincronizada" aparte.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys
import logging
from datetime import datetime

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_cost_of_production_daily")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "cost_of_production_history"


def fetch_blockchain_info_chart(chart_name: str) -> dict:
    resp = requests.get(
        f"https://api.blockchain.info/charts/{chart_name}",
        params={"timespan": "all", "format": "json", "sampled": "false"},
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"blockchain.info respondio {resp.status_code} para {chart_name}: {resp.text[:300]}")
    out = {}
    for row in resp.json().get("values", []):
        d = datetime.utcfromtimestamp(row["x"]).date().isoformat()
        v = row["y"]
        if chart_name == "difficulty" and v == 0.0:
            continue
        out[d] = v
    return out


def fetch_coinmetrics_blocks() -> dict:
    out = {}
    url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    params = {"assets": "btc", "metrics": "BlkCnt", "frequency": "1d", "start_time": "2009-01-01", "page_size": 10000}
    while url:
        resp = requests.get(url, params=params, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"Coin Metrics respondio {resp.status_code}: {resp.text[:300]}")
        payload = resp.json()
        for row in payload.get("data", []):
            if row.get("BlkCnt") is not None:
                out[row["time"][:10]] = float(row["BlkCnt"])
        url = payload.get("next_page_url")
        params = None
    return out


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

    difficulty = fetch_blockchain_info_chart("difficulty")
    fees_btc = fetch_blockchain_info_chart("transaction-fees")
    price_usd = fetch_blockchain_info_chart("market-price")
    blocks_mined = fetch_coinmetrics_blocks()

    all_dates = set(difficulty) | set(fees_btc) | set(price_usd) | set(blocks_mined)
    rows = []
    for d in sorted(all_dates):
        rows.append({
            "date": d,
            "difficulty": difficulty.get(d),
            "fees_btc": fees_btc.get(d),
            "blocks_mined": blocks_mined.get(d),
            "price_usd": price_usd.get(d),
        })

    upsert_rows(rows)
    log.info(f"{len(rows)} dias actualizados")


if __name__ == "__main__":
    main()
