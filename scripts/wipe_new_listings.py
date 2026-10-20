"""
Mantenimiento puntual (workflow_dispatch, no corre en ningun cron): borra TODO lo que haya
en exchange_new_listings. Util para limpiar una corrida de prueba con parsers aun no
afinados, igual que wipe_exchange_delistings.py.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    url = f"{SUPABASE_URL}/rest/v1/exchange_new_listings?id=gte.0"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "return=minimal",
    }
    resp = requests.delete(url, headers=headers, timeout=60)
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text[:500]}")
    print("Tabla exchange_new_listings vaciada.")


if __name__ == "__main__":
    main()
