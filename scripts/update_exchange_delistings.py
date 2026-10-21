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

import concurrent.futures
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))  # para que "delistings" se importe como paquete

from delistings import (
    bitunix, bingx, okx, bitget, kucoin, bybit, binance, gate, mexc, kraken,
    lbank, pionex, coinw, weex, blofin,
)
from delistings.common import upsert_rows, upsert_scraper_status, ExchangeBlocked, Row

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
    "kraken": kraken.fetch,
    "lbank": lbank.fetch,
    "pionex": pionex.fetch,
    "coinw": coinw.fetch,
    "weex": weex.fetch,
    "blofin": blofin.fetch,
}

# Presupuesto duro de reloj por exchange: el try/except ya evita que UNO se caiga y tumbe a
# los demas, pero no evitaba que uno se quedara COLGADO (ej. una corrida real se fue a mas
# de 25 minutos por acumular timeouts de red reales en varios articulos de los scrapers
# nuevos) - eso bloquea igual toda la corrida (y, por la concurrency del workflow sin
# cancel-in-progress, hasta las corridas horarias siguientes). Se corre cada fetch() en su
# propio hilo daemon con un limite de tiempo: si se pasa, se cuenta como "blocked" y se
# sigue con el resto sin esperar a que ese hilo termine solo.
FETCH_TIMEOUT_SECONDS = 120


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    all_rows: list[Row] = []
    failures = []
    statuses: dict[str, tuple[str, str | None]] = {}

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="fetcher")
    for name, fetcher in FETCHERS.items():
        log.info(f"=== {name} ===")
        future = executor.submit(fetcher)
        try:
            rows = future.result(timeout=FETCH_TIMEOUT_SECONDS)
            log.info(f"{name}: {len(rows)} filas")
            all_rows.extend(rows)
            statuses[name] = ("ok", None)
        except concurrent.futures.TimeoutError:
            log.warning(f"{name} se paso de {FETCH_TIMEOUT_SECONDS}s, se sigue con los demas (el hilo se abandona solo)")
            failures.append(name)
            statuses[name] = ("blocked", f"excedio el limite de {FETCH_TIMEOUT_SECONDS}s")
        except ExchangeBlocked as e:
            log.warning(f"{name} bloqueado esta corrida: {e}")
            failures.append(name)
            statuses[name] = ("blocked", str(e))
        except Exception as e:
            log.exception(f"{name} fallo, se sigue con los demas: {e}")
            failures.append(name)
            statuses[name] = ("blocked", f"error inesperado: {e}")
    executor.shutdown(wait=False, cancel_futures=False)

    log.info(f"Subiendo {len(all_rows)} filas en total a Supabase...")
    upsert_rows(SUPABASE_URL, SUPABASE_KEY, all_rows)
    try:
        upsert_scraper_status(SUPABASE_URL, SUPABASE_KEY, "delistings", statuses)
    except Exception as e:
        # el aviso de "problema de red" es un extra (ej. la tabla exchange_scraper_status
        # todavia no existe) - nunca debe tumbar una corrida que ya subio datos reales
        log.warning(f"no se pudo subir exchange_scraper_status: {e}")
    log.info(f"{len(all_rows)} filas subidas ({len(FETCHERS) - len(failures)}/{len(FETCHERS)} exchanges OK)")

    if failures:
        log.warning(f"Exchanges que fallaron esta corrida: {', '.join(failures)}")
        # no sys.exit(1): un exchange caido no debe marcar roja toda la corrida si los demas
        # subieron bien - igual que el resto de robots de este proyecto (continue-on-error)


if __name__ == "__main__":
    main()
