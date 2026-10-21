"""
Radar de Nuevos Listados: junta avisos de nuevos listados (cripto, acciones, indices y
commodities que los exchanges listan en futuros perpetuos, estilo xStock/bStocks) de varios
exchanges y los guarda en Supabase (tabla exchange_new_listings). Hermano de
update_exchange_delistings.py - mismos exchanges, misma disciplina, categoria distinta.

Investigacion inicial (confirmada en GitHub Actions): BingX, OKX, Bitget, KuCoin, Binance,
MEXC. Investigacion de 9 exchanges mas (confirmada via navegador real, 2026-10-20): Bybit,
Gate, LBank, Pionex, CoinW, Weex, Blofin, y se corrigio la seccion real de Bitunix (la
original era "Events and Activities", no listados) y se encontro una fuente para Kraken
(su blog oficial, no el centro de ayuda).

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))  # para que "newlistings" se importe como paquete

from newlistings import (
    bingx, okx, bitget, kucoin, binance, mexc,
    bybit, gate, lbank, pionex, coinw, weex, blofin, bitunix, kraken,
)
from newlistings.common import upsert_rows, upsert_scraper_status, ExchangeBlocked, Row

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_new_listings")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

FETCHERS = {
    "bingx": bingx.fetch,
    "okx": okx.fetch,
    "bitget": bitget.fetch,
    "kucoin": kucoin.fetch,
    "binance": binance.fetch,
    "mexc": mexc.fetch,
    "bybit": bybit.fetch,
    "gate": gate.fetch,
    "lbank": lbank.fetch,
    "pionex": pionex.fetch,
    "coinw": coinw.fetch,
    "weex": weex.fetch,
    "blofin": blofin.fetch,
    "bitunix": bitunix.fetch,
    "kraken": kraken.fetch,
}


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    all_rows: list[Row] = []
    failures = []
    statuses: dict[str, tuple[str, str | None]] = {}

    for name, fetcher in FETCHERS.items():
        log.info(f"=== {name} ===")
        try:
            rows = fetcher()
            log.info(f"{name}: {len(rows)} filas")
            all_rows.extend(rows)
            statuses[name] = ("ok", None)
        except ExchangeBlocked as e:
            log.warning(f"{name} bloqueado esta corrida: {e}")
            failures.append(name)
            statuses[name] = ("blocked", str(e))
        except Exception as e:
            log.exception(f"{name} fallo, se sigue con los demas: {e}")
            failures.append(name)
            statuses[name] = ("blocked", f"error inesperado: {e}")

    log.info(f"Subiendo {len(all_rows)} filas en total a Supabase...")
    upsert_rows(SUPABASE_URL, SUPABASE_KEY, all_rows)
    upsert_scraper_status(SUPABASE_URL, SUPABASE_KEY, "new_listings", statuses)
    log.info(f"{len(all_rows)} filas subidas ({len(FETCHERS) - len(failures)}/{len(FETCHERS)} exchanges OK)")

    if failures:
        log.warning(f"Exchanges que fallaron esta corrida: {', '.join(failures)}")


if __name__ == "__main__":
    main()
