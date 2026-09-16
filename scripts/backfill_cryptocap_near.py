"""
Respaldo UNICO (correr una sola vez a mano) del historico COMPLETO de
CRYPTOCAP:NEAR en Supabase.

Por que existe: la tabla cryptocap_history ya tenia TOTAL/TOTAL2/TOTAL3/
OTHERS/BTC/ETH/BTC.D/ETH.D/USDC.D/USDT.D con su historico completo desde
antes, pero NEAR se agrego despues a update_cryptocap_daily.py - ese script
diario solo trae los ultimos 15 dias (para no repetir la carga completa cada
vez), asi que sin este respaldo "Valoracion Relativa NEAR vs Altcoins" se
quedaria sin datos historicos durante mucho tiempo, acumulando de a un dia
por corrida.

Uso (una sola vez, desde tu maquina o donde tengas acceso a internet):
    export SUPABASE_URL="https://xxxxx.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="eyJ..."
    pip install "git+https://github.com/rongardF/tvdatafeed.git" requests
    python scripts/backfill_cryptocap_near.py

Despues de correrlo una vez no hace falta volver a correrlo - el robot
diario (update_cryptocap_daily.py) ya se encarga de mantenerlo al dia.
"""

import os
import sys
import logging

import requests
from tvDatafeed import TvDatafeed, Interval

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("backfill_near")

SYMBOL = "NEAR"
EXCHANGE = "CRYPTOCAP"
SYMBOL_FULL = f"{EXCHANGE}:{SYMBOL}"
N_BARS_FULL_HISTORY = 5000  # de sobra: NEAR lleva bastante menos de 5000 dias listado

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "cryptocap_history"
BATCH_SIZE = 500


def connect_tv():
    username = os.environ.get("TV_USERNAME")
    password = os.environ.get("TV_PASSWORD")
    if username and password:
        return TvDatafeed(username=username, password=password)
    return TvDatafeed()


def rows_from_df(df) -> list[dict]:
    rows = []
    for ts, r in df.iterrows():
        rows.append({
            "datetime": ts.isoformat(),
            "symbol": SYMBOL_FULL,
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r["volume"]),
        })
    return rows


def upsert_rows(rows: list[dict]):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=symbol,datetime"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        resp = requests.post(url, json=batch, headers=headers, timeout=30)
        if resp.status_code >= 300:
            raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text}")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    log.info(f"Descargando historico completo de {SYMBOL_FULL} desde TradingView...")
    tv = connect_tv()
    df = tv.get_hist(symbol=SYMBOL, exchange=EXCHANGE, interval=Interval.in_daily, n_bars=N_BARS_FULL_HISTORY)
    if df is None or df.empty:
        log.error("TradingView devolvio vacio - revisa que el simbolo exista tal cual (CRYPTOCAP:NEAR).")
        sys.exit(1)

    rows = rows_from_df(df)
    log.info(f"{len(rows)} velas descargadas ({rows[0]['datetime']} a {rows[-1]['datetime']}), subiendo a Supabase...")
    upsert_rows(rows)
    log.info(f"Listo: {len(rows)} velas de {SYMBOL_FULL} respaldadas en '{TABLE}'.")


if __name__ == "__main__":
    main()
