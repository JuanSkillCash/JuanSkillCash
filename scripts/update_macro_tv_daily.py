"""
Actualizacion diaria de DXY + PMI (Manufacturero y de Servicios) via
TradingView en Supabase - ver backfill_macro_tv.py para el detalle de que es
cada simbolo y por que se guardan asi.

Solo pide un margen de los ultimos dias (no todo el historico) para agarrar
el dato nuevo sin re-descargar todo cada vez.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys
import logging

import requests
from tvDatafeed import TvDatafeed, Interval

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_macro_tv_daily")

MACRO_TV_SYMBOLS = [
    {"exchange": "TVC", "symbol": "DXY"},
    {"exchange": "ECONOMICS", "symbol": "USBCOI"},
    {"exchange": "ECONOMICS", "symbol": "USSPMI"},
]
N_BARS_DAILY_UPDATE = 45  # margen de sobra: el PMI solo publica una vez al mes

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "macro_tv_history"


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
    resp = requests.post(url, json=rows, headers=headers, timeout=30)
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
                n_bars=N_BARS_DAILY_UPDATE,
            )
            if df is None or df.empty:
                raise RuntimeError("get_hist devolvio vacio")
            rows = rows_from_df(symbol_full, df)
            upsert_rows(rows)
            ok.append((symbol_full, len(rows)))
            log.info(f"{symbol_full}: {len(rows)} datos subidos/actualizados")
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
