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
import threading

sys.path.insert(0, os.path.dirname(__file__))  # para que "delistings" se importe como paquete

from delistings import (
    bitunix, bingx, okx, bitget, kucoin, bybit, binance, gate, mexc, kraken,
    lbank, pionex, coinw, weex, blofin,
)
from delistings.common import upsert_rows, upsert_scraper_status, ExchangeBlocked, Row
from watchlist_notify import notify_watchlist_matches

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_exchange_delistings")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

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
# propio hilo con threading.Thread(daemon=True) - NO con ThreadPoolExecutor: sus hilos se
# unen (join sin timeout) en un hook de atexit del propio modulo concurrent.futures al
# cerrar el interprete, pase lo que pase con shutdown(wait=False) en la instancia - eso tumbo
# una corrida real mas de 15 minutos aun con el limite de 120s ya puesto, porque el proceso
# quedaba esperando a un hilo colgado en una llamada de red sin que nada lo pudiera cortar.
# Un hilo daemon en cambio se abandona solo al terminar el hilo principal, sin bloquear nada.
FETCH_TIMEOUT_SECONDS = 120


def _run_with_timeout(fn, timeout: int):
    """Corre fn() en un hilo daemon y espera hasta timeout segundos. Devuelve (resultado,
    excepcion) - si se paso el tiempo, excepcion es TimeoutError y el hilo se abandona
    (sigue corriendo en el fondo, pero nunca bloquea el cierre del proceso)."""
    result: list = [None]
    error: list = [None]

    def _runner():
        try:
            result[0] = fn()
        except BaseException as e:  # noqa: BLE001 - se reempaqueta para el hilo principal
            error[0] = e

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return None, TimeoutError(f"excedio el limite de {timeout}s")
    if error[0] is not None:
        return None, error[0]
    return result[0], None


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    all_rows: list[Row] = []
    failures = []
    statuses: dict[str, tuple[str, str | None]] = {}

    for name, fetcher in FETCHERS.items():
        log.info(f"=== {name} ===")
        rows, error = _run_with_timeout(fetcher, FETCH_TIMEOUT_SECONDS)
        if error is None:
            log.info(f"{name}: {len(rows)} filas")
            all_rows.extend(rows)
            statuses[name] = ("ok", None)
        elif isinstance(error, TimeoutError):
            log.warning(f"{name} {error} , se sigue con los demas (el hilo se abandona solo)")
            failures.append(name)
            statuses[name] = ("blocked", str(error))
        elif isinstance(error, ExchangeBlocked):
            log.warning(f"{name} bloqueado esta corrida: {error}")
            failures.append(name)
            statuses[name] = ("blocked", str(error))
        else:
            log.exception(f"{name} fallo, se sigue con los demas: {error}", exc_info=error)
            failures.append(name)
            statuses[name] = ("blocked", f"error inesperado: {error}")

    log.info(f"Subiendo {len(all_rows)} filas en total a Supabase...")
    upsert_rows(SUPABASE_URL, SUPABASE_KEY, all_rows)
    try:
        notify_watchlist_matches(SUPABASE_URL, SUPABASE_KEY, "delistings", all_rows, telegram_bot_token=TELEGRAM_BOT_TOKEN)
    except Exception as e:
        log.warning(f"no se pudo revisar Mi Lista / notificaciones: {e}")
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
    # os._exit en vez de dejar que Python termine solo: una corrida real quedo colgada mas
    # de 15 minutos con hilos daemon abandonados que SI deberian dejar salir al proceso, pero
    # alguna libreria (Playwright) puede registrar su propio hilo/recurso no-daemon por
    # debajo - esto garantiza el cierre inmediato una vez que main() ya subio todo lo que
    # tenia que subir, sin esperar a nada que haya quedado atras.
    os._exit(0)
