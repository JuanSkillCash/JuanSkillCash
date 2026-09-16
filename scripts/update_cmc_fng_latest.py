"""
Respaldo del valor EN VIVO del CMC Crypto Fear and Greed Index (CoinMarketCap) en Supabase.

Por que existe: cmc_fng_history (llenada por update_cmc_fng_daily.py, una vez al dia) solo
tiene el valor ya CERRADO de cada dia - ese valor no queda disponible en la API de CMC hasta
que el dia termina. Mientras el dia esta en curso, CoinMarketCap sigue mostrando un numero que
va cambiando en vivo (su endpoint /latest, que ellos actualizan cada 15 minutos). Sin esto, el
widget del dashboard se quedaria mostrando el numero de ayer (o cayendo a alternative.me) durante
todo el dia de hoy, aunque el usuario compare contra lo que ve ahora mismo en CoinMarketCap.

Este script guarda ese valor en vivo en una tabla de una sola fila (cmc_fng_latest, id=1) que se
sobreescribe en cada corrida - no es historico, es solo el ultimo valor conocido.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    CMC_API_KEY
"""

import os
import sys
import logging

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_cmc_fng_latest")

CMC_URL = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest"
CMC_API_KEY = os.environ.get("CMC_API_KEY", "")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "cmc_fng_latest"


def fetch_latest():
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
    resp = requests.get(CMC_URL, headers=headers, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"CoinMarketCap respondio {resp.status_code}: {resp.text}")
    data = resp.json().get("data")
    if not data:
        raise RuntimeError("CoinMarketCap devolvio vacio")
    return data


def upsert_row(entry):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=id"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    row = {
        "id": 1,
        "value": int(entry["value"]),
        "value_classification": entry.get("value_classification"),
        "update_time": entry.get("update_time"),
    }
    resp = requests.post(url, json=row, headers=headers, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text}")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)
    if not CMC_API_KEY:
        log.error("Falta CMC_API_KEY en el entorno.")
        sys.exit(1)

    log.info("Descargando valor en vivo del CMC Fear and Greed Index...")
    entry = fetch_latest()
    upsert_row(entry)
    log.info(f"Listo: valor en vivo respaldado ({entry['value']} - {entry.get('value_classification')}).")


if __name__ == "__main__":
    main()
