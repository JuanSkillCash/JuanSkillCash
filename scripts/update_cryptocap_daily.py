"""
Actualizacion diaria de la tabla cryptocap_history en Supabase.

A diferencia de la carga inicial (que trajo TODO el historico), este script
trae solo los ultimos dias de cada simbolo (suficiente para cubrir el dia
nuevo, mas un margen por si el robot no corrio uno o dos dias) y los sube a
Supabase con upsert: si la fecha ya existia, la reemplaza con el valor mas
reciente (la vela de "hoy" en TradingView se sigue moviendo hasta el cierre);
si no existia, la inserta.

Variables de entorno requeridas:
    SUPABASE_URL               ej. https://xxxxx.supabase.co
    SUPABASE_SERVICE_ROLE_KEY  la "service_role" key (Project Settings -> API)
                                 NUNCA la publishable/anon key: esta necesita
                                 poder escribir, y la anon key en este proyecto
                                 solo tiene permiso de lectura.

Uso local (opcional, para probarlo a mano):
    export SUPABASE_URL="https://xxxxx.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="eyJ..."
    python scripts/update_cryptocap_daily.py
"""

import os
import sys
import time
import logging

import requests
from tvDatafeed import TvDatafeed, Interval

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("cryptocap_daily")

EXCHANGE = "CRYPTOCAP"
SYMBOLS = [
    "TOTAL",
    "TOTAL2",
    "TOTAL3",
    "OTHERS",
    "BTC",
    "ETH",
    "NEAR",
    "BTC.D",
    "ETH.D",
    "USDC.D",
    "USDT.D",
]
N_BARS_DAILY_UPDATE = 15  # margen de sobra: cubre fines de semana largos o si el robot fallo un dia

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "cryptocap_history"


def connect_tv():
    username = os.environ.get("TV_USERNAME")
    password = os.environ.get("TV_PASSWORD")
    if username and password:
        return TvDatafeed(username=username, password=password)
    return TvDatafeed()


def rows_from_df(symbol_full: str, df) -> list[dict]:
    rows = []
    for ts, r in df.iterrows():
        rows.append({
            "datetime": ts.isoformat(),
            "symbol": symbol_full,
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r["volume"]),
        })
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
    for sym in SYMBOLS:
        symbol_full = f"{EXCHANGE}:{sym}"
        try:
            df = tv.get_hist(
                symbol=sym,
                exchange=EXCHANGE,
                interval=Interval.in_daily,
                n_bars=N_BARS_DAILY_UPDATE,
            )
            if df is None or df.empty:
                raise RuntimeError("get_hist devolvio vacio")

            rows = rows_from_df(symbol_full, df)
            upsert_rows(rows)
            ok.append((symbol_full, len(rows)))
            log.info(f"{symbol_full}: {len(rows)} velas subidas/actualizadas")
        except Exception as e:
            failed.append((symbol_full, str(e)))
            log.error(f"{symbol_full}: FALLO -> {e}")
        time.sleep(1)

    print("\n=== Resumen ===")
    for s, n in ok:
        print(f"OK   {s}: {n} velas")
    for s, err in failed:
        print(f"FAIL {s}: {err}")

    if failed:
        sys.exit(1)  # marca el run de GitHub Actions como fallido si algo no se pudo subir


if __name__ == "__main__":
    main()
