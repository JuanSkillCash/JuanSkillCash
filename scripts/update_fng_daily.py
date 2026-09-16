"""
Respaldo diario del Indice de Miedo y Codicia (alternative.me) en Supabase.

Por que existe: hoy alternative.me da gratis el historico COMPLETO en una sola peticion
(limit=0), asi que la pagina lo pide en vivo cada vez y no necesita este respaldo para
funcionar. Pero si alternative.me algun dia deja de dar el servicio, cambia sus terminos,
o empieza a cobrar, este respaldo evita perder el historico que ya se tenia hasta ese punto.

A diferencia de update_cryptocap_daily.py (que solo pide los ultimos N dias de margen),
aqui SIEMPRE se pide el historico COMPLETO en cada corrida - es gratis, es una sola
peticion, y así el respaldo queda igual de completo que la fuente original sin tener que
razonar sobre gaps o dias perdidos.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys
import logging
from datetime import datetime, timezone

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("fng_daily")

FNG_URL = "https://api.alternative.me/fng/?limit=0"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "fng_history"
BATCH_SIZE = 500  # se sube en tandas para evitar un solo POST gigante (~3000 filas)


def fetch_fng():
    resp = requests.get(FNG_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        raise RuntimeError("alternative.me devolvio vacio")
    return data


def rows_from_fng(data):
    rows = []
    for entry in data:
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
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        resp = requests.post(url, json=batch, headers=headers, timeout=30)
        if resp.status_code >= 300:
            raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text}")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    log.info("Descargando historico completo de Miedo y Codicia...")
    data = fetch_fng()
    rows = rows_from_fng(data)
    log.info(f"{len(rows)} dias descargados ({rows[-1]['day']} a {rows[0]['day']}), subiendo a Supabase...")
    upsert_rows(rows)
    log.info(f"Listo: {len(rows)} dias respaldados en '{TABLE}' (upsert - nada existente se pierde).")


if __name__ == "__main__":
    main()
