"""
Mantenimiento puntual (workflow_dispatch, no corre en ningun cron): borra TODO lo que haya
en exchange_delistings. Se uso una sola vez para limpiar la primera corrida de prueba
(tenia simbolos mal parseados por bugs ya corregidos en common.py: el unique key es
(exchange,symbol,source_url), asi que un symbol corregido no pisa al viejo, queda como fila
duplicada/basura - hay que borrar y dejar que el pipeline la regenere limpia).

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

    url = f"{SUPABASE_URL}/rest/v1/exchange_delistings?id=gte.0"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "return=minimal",
    }
    resp = requests.delete(url, headers=headers, timeout=60)
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text[:500]}")
    print("Tabla exchange_delistings vaciada.")


if __name__ == "__main__":
    main()
