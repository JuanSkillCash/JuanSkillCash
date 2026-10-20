"""
Radar de Deslistados: junta avisos de deslistado de varios exchanges y los guarda en
Supabase (tabla exchange_delistings). Cada exchange vive en su propio modulo dentro de
scripts/delistings/, con una interfaz comun fetch() -> list[Row] (ver scripts/delistings/common.py).

Un exchange que falle (cambio de API, bloqueo, etc.) NO debe tumbar a los demas - por eso
cada fetch() va en su propio try/except, no como pasos separados de GitHub Actions
(continue-on-error por step hubiera servido igual, pero asi un solo log cuenta toda la
corrida junta).

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))  # para que "delistings" se importe como paquete

from delistings import bitunix, bingx, okx, bitget, kucoin, bybit, binance, gate, mexc
from delistings.common import upsert_rows, Row

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_exchange_delistings")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Fase 1: los 4 exchanges de menor riesgo segun la investigacion (API oficial o Zendesk
# publico, sin bloqueo de IP conocido). El resto se va agregando aqui mismo a medida que
# se valida cada uno por separado.
FETCHERS = {
    "bitunix": bitunix.fetch,
    "bingx": bingx.fetch,
    "okx": okx.fetch,
    "bitget": bitget.fetch,
    "kucoin": kucoin.fetch,
    "bybit": bybit.fetch,
    "binance": binance.fetch,
    "gate": gate.fetch,
    "mexc": mexc.fetch,
}


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    all_rows: list[Row] = []
    failures = []

    for name, fetcher in FETCHERS.items():
        log.info(f"=== {name} ===")
        try:
            rows = fetcher()
            log.info(f"{name}: {len(rows)} filas")
            all_rows.extend(rows)
        except Exception as e:
            log.exception(f"{name} fallo, se sigue con los demas: {e}")
            failures.append(name)

    log.info(f"Subiendo {len(all_rows)} filas en total a Supabase...")
    upsert_rows(SUPABASE_URL, SUPABASE_KEY, all_rows)
    log.info(f"{len(all_rows)} filas subidas ({len(FETCHERS) - len(failures)}/{len(FETCHERS)} exchanges OK)")

    if failures:
        log.warning(f"Exchanges que fallaron esta corrida: {', '.join(failures)}")
        # no sys.exit(1): un exchange caido no debe marcar roja toda la corrida si los demas
        # subieron bien - igual que el resto de robots de este proyecto (continue-on-error)


if __name__ == "__main__":
    main()
