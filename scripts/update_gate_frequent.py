"""
Gate es el unico exchange del proyecto con un hueco real de cobertura: su pagina completa
de anuncios esta bloqueada por Akamai para la IP de GitHub Actions (bloqueo por reputacion
de IP, confirmado con diagnostico real - no se arregla con headers ni librerias distintas),
asi que se usa como respaldo su WebSocket publico (wss://api.gateio.ws/ws/v4/ann), que SOLO
entrega el ultimo anuncio en cache en el momento de conectarse - no un historial. Si Gate
publica 2+ deslistados/listados en el lapso entre corridas, solo se ve el mas reciente y los
anteriores se pierden para siempre.

Este script corre SOLO Gate (deslistados + nuevos listados) con mas frecuencia que el resto
de exchanges (cada 15-20 min en vez de cada hora, ver workflow) para achicar al minimo esa
ventana, sin aumentar la carga sobre los otros 14 exchanges que ya tienen cobertura completa
via sus APIs oficiales.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from delistings import gate as delistings_gate
from delistings.common import (
    upsert_rows as upsert_delistings_rows,
    upsert_scraper_status as upsert_delistings_status,
    ExchangeBlocked,
)
from newlistings import gate as newlistings_gate
from newlistings.common import (
    upsert_rows as upsert_newlistings_rows,
    upsert_scraper_status as upsert_newlistings_status,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_gate_frequent")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _run_radar(label, fetch_fn, upsert_rows_fn, upsert_status_fn, radar_name):
    try:
        rows = fetch_fn()
        log.info(f"[{label}] {len(rows)} filas")
        status = ("ok", None)
    except ExchangeBlocked as e:
        log.warning(f"[{label}] bloqueado esta corrida: {e}")
        rows, status = [], ("blocked", str(e))
    except Exception as e:
        log.exception(f"[{label}] fallo: {e}")
        rows, status = [], ("blocked", f"error inesperado: {e}")

    if rows:
        upsert_rows_fn(SUPABASE_URL, SUPABASE_KEY, rows)
    try:
        upsert_status_fn(SUPABASE_URL, SUPABASE_KEY, radar_name, {"gate": status})
    except Exception as e:
        log.warning(f"[{label}] no se pudo subir exchange_scraper_status: {e}")
    return len(rows)


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    n1 = _run_radar("gate-delistings", delistings_gate.fetch, upsert_delistings_rows, upsert_delistings_status, "delistings")
    n2 = _run_radar("gate-newlistings", newlistings_gate.fetch, upsert_newlistings_rows, upsert_newlistings_status, "new_listings")
    log.info(f"Gate: {n1} filas de deslistados, {n2} filas de nuevos listados")


if __name__ == "__main__":
    main()
    os._exit(0)
