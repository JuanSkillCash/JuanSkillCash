"""
Actualizacion diaria de interes de busqueda en Google Trends en Supabase - ver
backfill_google_trends.py para el detalle de por que no hay una API oficial y como se trae.

A diferencia de los demas scripts "daily" de este repo (que solo piden un margen de los ultimos
dias), este vuelve a pedir la historia COMPLETA (timeframe='all') de cada termino cada vez que
corre. Es deliberado: Google Trends solo da un 0-100 internamente consistente DENTRO de una misma
llamada - pedir solo "los ultimos dias" devolveria un 0-100 relativo a esa ventana chiquita, que
no se podria pegar sin desentonar contra el resto de la serie ya guardada. Volver a traer todo y
sobreescribir evita ese problema (y de paso corrige cualquier ajuste retroactivo que Google le
haga a sus propios numeros), a costa de ser una llamada mas pesada por termino.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys
import time
import logging

import requests
from pytrends.request import TrendReq

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_google_trends_daily")

GOOGLE_TRENDS_TERMS = ["bitcoin", "buy bitcoin", "bitcoin crash", "altcoin season"]
SLEEP_BETWEEN_TERMS_SECONDS = 20

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "google_trends_history"


def rows_from_series(term: str, series) -> list[dict]:
    rows = []
    for ts, value in series.items():
        if ts is None:
            continue
        rows.append({"term": term, "date": ts.strftime("%Y-%m-%d"), "value": float(value)})
    return rows


def upsert_rows(rows: list[dict]):
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=term,date"
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

    pytrends = TrendReq(hl="en-US", tz=0)
    ok, failed = [], []
    for i, term in enumerate(GOOGLE_TRENDS_TERMS):
        try:
            pytrends.build_payload([term], timeframe="all")
            df = pytrends.interest_over_time()
            if df is None or df.empty:
                raise RuntimeError("interest_over_time() devolvio vacio")
            rows = rows_from_series(term, df[term])
            upsert_rows(rows)
            ok.append((term, len(rows)))
            log.info(f"{term}: {len(rows)} datos actualizados")
        except Exception as e:
            failed.append((term, str(e)))
            log.error(f"{term}: FALLO -> {e}")
        if i < len(GOOGLE_TRENDS_TERMS) - 1:
            time.sleep(SLEEP_BETWEEN_TERMS_SECONDS)

    print("\n=== Resumen ===")
    for s, n in ok:
        print(f"OK   {s}: {n} datos")
    for s, err in failed:
        print(f"FAIL {s}: {err}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
