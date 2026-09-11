#!/usr/bin/env python3
"""
Fase 4, Paso 5: mide la latencia EN VIVO entre que una operacion queda
confirmada on-chain y el momento en que este sistema termina de
detectarla + interpretarla, para Solana o Robinhood Chain.

REQUIERE ACCESO REAL A INTERNET Y una wallet que efectivamente opere
mientras el script esta corriendo (no funciona con datos historicos: la
latencia solo tiene sentido para una operacion nueva). Ver
validate/README.md y FASE_4_VALIDACION_REAL.md, Paso 5, para el
razonamiento sobre que numero esperar en cada chain.

Metodologia (documentada tambien en validate/README.md):
    latencia_total = ahora() - trade.timestamp
donde trade.timestamp es el blockTime/timestamp de bloque real de la
transaccion (dato on-chain), y ahora() es el reloj de esta maquina en el
momento en que la interpretacion (parsers/*.py) ya termino. Esto mide
"confirmacion on-chain -> deteccion + interpretacion completa" como un
solo numero combinado -- separar "deteccion" de "interpretacion" requiere
leer los timestamps que wallet_monitor.py ya imprime en cada linea de log
(Solana) o instrumentar chains/robinhood_adapter.py con un log adicional
antes de interpretar (Robinhood Chain, no incluido aqui, ver limitacion
en FASE_4_VALIDACION_REAL.md).

SOLO LECTURA. No firma nada, no requiere claves privadas ni API keys.

Uso:
    python validate/measure_latency.py solana <WALLET_1> [WALLET_2 ...] [--sol-usd-price 150]
    python validate/measure_latency.py robinhood <WALLET_1> [...] [--poll-interval 5] [--native-usd-price 3000]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "prototype"))

from models.normalized_trade import NormalizedTrade  # noqa: E402


def _parse_iso(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def make_on_trade(chain_label: str):
    async def on_trade(trade: NormalizedTrade) -> None:
        now = datetime.now(timezone.utc)
        if trade.timestamp:
            onchain_ts = _parse_iso(trade.timestamp)
            latency_s = (now - onchain_ts).total_seconds()
            print(
                f"[{chain_label}] {trade.signature}\n"
                f"  on-chain (blockTime)            : {trade.timestamp}\n"
                f"  deteccion+interpretacion (aqui)  : {now.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
                f"  LATENCIA TOTAL                   : {latency_s:.2f} s"
            )
        else:
            print(f"[{chain_label}] {trade.signature}: sin timestamp on-chain disponible, no se puede medir latencia.")
        print(trade.human_readable())
        print()

    return on_trade


async def run_solana(addresses: list[str], sol_usd_price: float | None) -> None:
    from chains import solana_adapter

    await solana_adapter.watch(addresses, make_on_trade("solana"), sol_usd_price=sol_usd_price)


async def run_robinhood(addresses: list[str], poll_interval: float, native_usd_price: float | None) -> None:
    from chains import robinhood_adapter

    await robinhood_adapter.watch(
        addresses, make_on_trade("robinhood"),
        poll_interval=poll_interval, native_usd_price=native_usd_price,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("chain", choices=["solana", "robinhood"])
    parser.add_argument("addresses", nargs="+")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--sol-usd-price", type=float, default=None)
    parser.add_argument("--native-usd-price", type=float, default=None)
    args = parser.parse_args()

    print("=== Medicion de latencia en vivo (Fase 4, Paso 5) ===")
    print("Dejar corriendo y esperar a que la wallet observada haga una operacion real.")
    print("Ctrl+C para detener.\n")

    try:
        if args.chain == "solana":
            asyncio.run(run_solana(args.addresses, args.sol_usd_price))
        else:
            asyncio.run(run_robinhood(args.addresses, args.poll_interval, args.native_usd_price))
    except KeyboardInterrupt:
        print("\nDetenido por el usuario.")


if __name__ == "__main__":
    main()
