"""
Respaldo UNICO (correr una sola vez a mano) del historico COMPLETO de los
indicadores macro que no estan en FRED, via TradingView (tvDatafeed) - mismo
mecanismo que ya usa este repo para CRYPTOCAP:BTC.D, ETH.D, etc.

Simbolos que trae:
    TVC:DXY              -> DXY (Indice del Dolar que usa el mercado)
    ECONOMICS:USBCOI     -> ISM Manufacturing PMI
    ECONOMICS:USSPMI     -> ISM Services PMI

Estos dos ultimos son simbolos de "calendario economico" de TradingView, no
un precio que se negocia - tvDatafeed los trae igual como una serie de velas
(con open=high=low=close=el valor publicado ese mes), asi que solo se guarda
el "close" como el valor real del indicador.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY

Uso (una sola vez, desde tu maquina o donde tengas acceso a internet):
    export SUPABASE_URL="https://xxxxx.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="eyJ..."
    pip install "git+https://github.com/rongardF/tvdatafeed.git"
    python scripts/backfill_macro_tv.py
"""

import os
import sys
import logging

import requests
from tvDatafeed import TvDatafeed, Interval

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("backfill_macro_tv")

MACRO_TV_SYMBOLS = [
    {"exchange": "TVC", "symbol": "DXY"},
    {"exchange": "ECONOMICS", "symbol": "USBCOI"},  # ISM Manufacturing PMI
    {"exchange": "ECONOMICS", "symbol": "USSPMI"},  # ISM Services PMI
]
N_BARS_FULL_HISTORY = 5000

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "macro_tv_history"
BATCH_SIZE = 1000


def connect_tv():
    username = os.environ.get("TV_USERNAME")
    password = os.environ.get("TV_PASSWORD")
    if username and password:
        return TvDatafeed(username=username, password=password)
    return TvDatafeed()


def rows_from_df(symbol_full: str, df) -> list[dict]:
    rows = []
    for ts, r in df.iterrows():
        rows.append({"symbol": symbol_full, "datetime": ts.isoformat(), "value": float(r["close"])})
    return rows


def upsert_rows(rows: list[dict]):
    if not rows:
        return
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

    tv = connect_tv()
    ok, failed = [], []
    for item in MACRO_TV_SYMBOLS:
        symbol_full = f"{item['exchange']}:{item['symbol']}"
        try:
            df = tv.get_hist(
                symbol=item["symbol"],
                exchange=item["exchange"],
                interval=Interval.in_daily,
                n_bars=N_BARS_FULL_HISTORY,
            )
            if df is None or df.empty:
                raise RuntimeError("get_hist devolvio vacio")
            rows = rows_from_df(symbol_full, df)
            upsert_rows(rows)
            ok.append((symbol_full, len(rows)))
            log.info(f"{symbol_full}: {len(rows)} datos respaldados")
        except Exception as e:
            failed.append((symbol_full, str(e)))
            log.error(f"{symbol_full}: FALLO -> {e}")

    print("\n=== Resumen ===")
    for s, n in ok:
        print(f"OK   {s}: {n} datos")
    for s, err in failed:
        print(f"FAIL {s}: {err}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
