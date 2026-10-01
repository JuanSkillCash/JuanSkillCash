"""
Respaldo UNICO (correr una sola vez a mano) del historico COMPLETO de interes de busqueda en
Google Trends para varios terminos relacionados con Bitcoin/cripto, via pytrends (libreria NO
OFICIAL que simula lo que hace el navegador en trends.google.com - Google no tiene una API
publica oficial y gratuita para esto).

Cada termino se pide con timeframe='all' (una sola llamada por termino, resolucion semanal desde
2004) - esto da una serie 0-100 internamente consistente en toda su historia, sin tener que pedir
la historia en pedazos y "coser" los tramos (cada llamada separada a Google Trends devuelve su
propio 0-100 relativo SOLO a esa ventana de tiempo, asi que mezclar llamadas de ventanas distintas
sin re-escalar daria una serie sin sentido).

OJO: Google Trends bloquea/limita agresivamente el trafico automatizado repetido (HTTP 429),
sobre todo desde IPs compartidas como las de GitHub Actions - a diferencia de FRED/TradingView
(APIs pensadas para esto), aqui puede fallar de forma intermitente (visto en vivo: el primer
termino de una corrida fresca es el mas propenso). Por eso cada termino reintenta solo con
backoff creciente (ver fetch_term) antes de darse por vencido, ademas de la pausa entre terminos,
y el workflow diario que corre este mismo mecanismo (update_google_trends_daily.py) tiene
continue-on-error para no tumbar el resto del pipeline si aun asi Google Trends bloquea.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY

Uso (una sola vez, desde tu maquina o donde tengas acceso a internet):
    export SUPABASE_URL="https://xxxxx.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="eyJ..."
    pip install pytrends requests
    python scripts/backfill_google_trends.py
"""

import os
import sys
import time
import logging

import requests
from pytrends.request import TrendReq

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("backfill_google_trends")

# mismos 4 terminos que usa el frontend (ver BTC_TRENDS_OVERLAY_DEFS en index.html) - si agregas
# uno aqui, agregalo tambien alla (y viceversa), no hay nada que los sincronice automaticamente
GOOGLE_TRENDS_TERMS = ["bitcoin", "buy bitcoin", "bitcoin crash", "altcoin season"]
SLEEP_BETWEEN_TERMS_SECONDS = 20  # margen generoso para no disparar el limite de Google

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


RETRY_WAITS_SECONDS = [15, 30, 60]  # backoff creciente - el 429 de Google suele ser momentaneo


def fetch_term(pytrends, term):
    last_err = None
    for attempt, wait in enumerate([0] + RETRY_WAITS_SECONDS):
        if wait:
            log.info(f"{term}: reintentando en {wait}s (intento {attempt + 1})...")
            time.sleep(wait)
        try:
            pytrends.build_payload([term], timeframe="all")
            df = pytrends.interest_over_time()
            if df is None or df.empty:
                raise RuntimeError("interest_over_time() devolvio vacio")
            return df[term]
        except Exception as e:
            last_err = e
    raise last_err


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    pytrends = TrendReq(hl="en-US", tz=0)
    ok, failed = [], []
    for i, term in enumerate(GOOGLE_TRENDS_TERMS):
        try:
            series = fetch_term(pytrends, term)
            rows = rows_from_series(term, series)
            upsert_rows(rows)
            ok.append((term, len(rows)))
            log.info(f"{term}: {len(rows)} datos respaldados")
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
