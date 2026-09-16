"""
Respaldo diario del CMC Crypto Fear and Greed Index (CoinMarketCap) en Supabase.

Por que existe: la pagina muestra el Indice de Miedo y Codicia mezclando el valor de
CoinMarketCap (el mas reconocido) con el historico gratis de alternative.me para los
dias mas viejos que CMC no cubre. Para poder mostrar el valor de CMC hace falta
guardarlo dia a dia aqui, porque su API exige una llave secreta (CMC_API_KEY) y por
eso no se puede pedir directo desde el navegador del usuario.

A diferencia de backfill_cmc_fng.py (que trae TODO el historico una sola vez), aqui
se piden los ultimos dias con margen (no solo el de hoy) para que, si alguna corrida
diaria falla o se salta, el siguiente dia se auto-corrija solo - mismo criterio que
ya usa update_cryptocap_daily.py con TradingView.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    CMC_API_KEY
"""

import os
import sys
import logging
from datetime import datetime, timezone

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_cmc_fng_daily")

CMC_URL = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical"
CMC_API_KEY = os.environ.get("CMC_API_KEY", "")
DAYS_MARGIN = 10  # margen de dias por si alguna corrida diaria falla o se salta

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "cmc_fng_history"


def fetch_recent_cmc():
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
    resp = requests.get(
        CMC_URL,
        headers=headers,
        params={"start": 1, "limit": DAYS_MARGIN},
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"CoinMarketCap respondio {resp.status_code}: {resp.text}")
    data = resp.json().get("data", [])
    if not data:
        raise RuntimeError("CoinMarketCap devolvio vacio")
    return data


def rows_from_entries(entries):
    rows = []
    for entry in entries:
        day = datetime.fromtimestamp(int(entry["timestamp"]), tz=timezone.utc).date().isoformat()
        rows.append({
            "day": day,
            "value": int(entry["value"]),
            "value_classification": entry.get("value_classification"),
        })
    return rows


def upsert_rows(rows):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=day"
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
    if not CMC_API_KEY:
        log.error("Falta CMC_API_KEY en el entorno.")
        sys.exit(1)

    log.info(f"Descargando los ultimos {DAYS_MARGIN} dias del CMC Fear and Greed Index...")
    entries = fetch_recent_cmc()
    rows = rows_from_entries(entries)
    days = sorted(r["day"] for r in rows)
    log.info(f"{len(rows)} dias descargados ({days[0]} a {days[-1]}), subiendo a Supabase...")
    upsert_rows(rows)
    log.info(f"Listo: {len(rows)} dias respaldados en '{TABLE}'.")


if __name__ == "__main__":
    main()
