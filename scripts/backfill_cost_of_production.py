"""
Respaldo UNICO (correr una sola vez, via el workflow) del historico completo de los insumos de
"Costo de Produccion" de Bitcoin (dificultad, comisiones, bloques minados, precio) para el
indicador "Pulso de Fondo".

Fuente principal: blockchain.info Charts API (gratis, sin key, historia completa 2009-hoy, sin
huecos). Confirmado con validacion cruzada contra Bitview y bitcoin-data.com: diferencia mediana
0% en dificultad (ver investigacion del 2026-10-01).

Complemento: Coin Metrics Community API (gratis, sin key) para bloques minados por dia (BlkCnt) -
blockchain.info no tiene esa serie propia. OJO: Coin Metrics retiro DiffMean (dificultad) de su
plan gratis - pedirla junto con las demas metricas tumba TODA la respuesta con un 403, asi que
aqui NUNCA se pide esa metrica.

El frontend (loadMarketFloorData en index.html) sigue calculando el Canal de Keltner semanal y el
Costo de Produccion (formula publica: (1/1800) * dificultad^0.45 / emision_diaria, suavizado con
SMA de 13 semanas) a partir de estas filas crudas - este script solo guarda los insumos, no el
resultado final.

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
log = logging.getLogger("backfill_cost_of_production")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "cost_of_production_history"


def fetch_blockchain_info_chart(chart_name: str) -> dict:
    """Trae una serie completa de blockchain.info: {fecha: valor}, descartando 0.0 en dificultad
    (placeholder de "sin dato" - la dificultad real nunca es 0, el minimo historico es 1.0)."""
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
    """Bloques minados por dia (BlkCnt) de Coin Metrics Community - NUNCA pedir DiffMean junto
    con esto, Coin Metrics rechaza el batch COMPLETO si una sola metrica no esta en el plan gratis."""
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
        params = None  # next_page_url ya trae todos los query params incluidos
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

    log.info("Trayendo dificultad de blockchain.info...")
    difficulty = fetch_blockchain_info_chart("difficulty")
    log.info(f"{len(difficulty)} dias con dificultad")

    log.info("Trayendo comisiones (BTC) de blockchain.info...")
    fees_btc = fetch_blockchain_info_chart("transaction-fees")
    log.info(f"{len(fees_btc)} dias con comisiones")

    log.info("Trayendo precio de blockchain.info...")
    price_usd = fetch_blockchain_info_chart("market-price")
    log.info(f"{len(price_usd)} dias con precio")

    log.info("Trayendo bloques minados por dia de Coin Metrics...")
    blocks_mined = fetch_coinmetrics_blocks()
    log.info(f"{len(blocks_mined)} dias con bloques minados")

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

    log.info(f"Subiendo {len(rows)} filas a Supabase...")
    upsert_rows(rows)
    log.info("Listo.")


if __name__ == "__main__":
    main()
