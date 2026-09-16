"""
Respaldo UNICO (correr una sola vez a mano) del historico COMPLETO del
CMC Crypto Fear and Greed Index (CoinMarketCap) en Supabase.

Por que existe: a diferencia de alternative.me (que da el historico completo gratis en
una sola peticion), la API de CoinMarketCap pagina de a maximo 500 dias por llamada.
Este script recorre todas las paginas una sola vez para traer todo el historico
disponible; despues de eso, update_cmc_fng_daily.py (que corre solo todos los dias)
se encarga de mantenerlo al dia con margen de sobra.

Uso (una sola vez, desde tu maquina o donde tengas acceso a internet):
    export SUPABASE_URL="https://xxxxx.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="eyJ..."
    export CMC_API_KEY="tu-api-key-de-coinmarketcap"
    pip install requests
    python scripts/backfill_cmc_fng.py

Despues de correrlo una vez no hace falta volver a correrlo - el robot diario
(update_cmc_fng_daily.py) ya se encarga de mantenerlo al dia.
"""

import os
import sys
import logging
from datetime import datetime, timezone

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("backfill_cmc_fng")

CMC_URL = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical"
CMC_API_KEY = os.environ.get("CMC_API_KEY", "")
PAGE_LIMIT = 500  # maximo permitido por la API en una sola peticion

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "cmc_fng_history"
BATCH_SIZE = 500


def fetch_all_cmc_history() -> list[dict]:
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
    all_entries = []
    start = 1
    while True:
        resp = requests.get(
            CMC_URL,
            headers=headers,
            params={"start": start, "limit": PAGE_LIMIT},
            timeout=30,
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"CoinMarketCap respondio {resp.status_code}: {resp.text}")
        page = resp.json().get("data", [])
        if not page:
            break
        all_entries.extend(page)
        log.info(f"Pagina desde start={start}: {len(page)} dias (van {len(all_entries)} en total)")
        if len(page) < PAGE_LIMIT:
            break
        start += PAGE_LIMIT
    return all_entries


def rows_from_entries(entries: list[dict]) -> list[dict]:
    rows = []
    for entry in entries:
        day = datetime.fromtimestamp(int(entry["timestamp"]), tz=timezone.utc).date().isoformat()
        rows.append({
            "day": day,
            "value": int(entry["value"]),
            "value_classification": entry.get("value_classification"),
        })
    return rows


def upsert_rows(rows: list[dict]):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=day"
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
    if not CMC_API_KEY:
        log.error("Falta CMC_API_KEY en el entorno.")
        sys.exit(1)

    log.info("Descargando historico completo del CMC Fear and Greed Index...")
    entries = fetch_all_cmc_history()
    if not entries:
        log.error("CoinMarketCap devolvio vacio.")
        sys.exit(1)

    rows = rows_from_entries(entries)
    days = sorted(r["day"] for r in rows)
    log.info(f"{len(rows)} dias descargados ({days[0]} a {days[-1]}), subiendo a Supabase...")
    upsert_rows(rows)
    log.info(f"Listo: {len(rows)} dias respaldados en '{TABLE}' (upsert - nada existente se pierde).")


if __name__ == "__main__":
    main()
