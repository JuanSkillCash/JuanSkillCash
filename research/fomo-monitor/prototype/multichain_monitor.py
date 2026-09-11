#!/usr/bin/env python3
"""
multichain_monitor.py — punto de entrada unico para la arquitectura
multichain (Fase 3): Trader wallet -> Chain Adapter -> Parser ->
NormalizedTrade -> Alerta.

SOLO LECTURA. No ejecuta operaciones, no conecta wallets privadas, no usa
claves privadas. Deliberadamente simple (sin colas, sin workers, sin
Redis/Postgres) -- ver INFORME_MULTICHAIN.md, seccion de escalabilidad,
para que se necesitaria para ir mas alla de esto.

Uso:
    python multichain_monitor.py solana <WALLET_1> [WALLET_2 ...]
    python multichain_monitor.py robinhood <WALLET_1> [WALLET_2 ...] [--poll-interval 5] [--native-usd-price 3000]

    Se pueden observar ambas chains a la vez pasando --chain dos veces:
    python multichain_monitor.py --chain solana:WALLET_SOL --chain robinhood:WALLET_EVM
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from models.normalized_trade import NormalizedTrade  # noqa: E402


async def print_alert(trade: NormalizedTrade) -> None:
    print("\n=== ALERTA (NormalizedTrade) ===")
    print(trade.human_readable())
    print()


async def run_solana(addresses: list[str], sol_usd_price: float | None) -> None:
    from chains import solana_adapter

    await solana_adapter.watch(addresses, print_alert, sol_usd_price=sol_usd_price)


async def run_robinhood(
    addresses: list[str], poll_interval: float, native_usd_price: float | None
) -> None:
    from chains import robinhood_adapter

    await robinhood_adapter.watch(
        addresses, print_alert, poll_interval=poll_interval, native_usd_price=native_usd_price
    )


async def run_both(
    solana_addresses: list[str],
    robinhood_addresses: list[str],
    sol_usd_price: float | None,
    poll_interval: float,
    native_usd_price: float | None,
) -> None:
    tasks = []
    if solana_addresses:
        tasks.append(run_solana(solana_addresses, sol_usd_price))
    if robinhood_addresses:
        tasks.append(run_robinhood(robinhood_addresses, poll_interval, native_usd_price))
    if not tasks:
        print("No se indico ninguna wallet a observar en ninguna chain.")
        return
    await asyncio.gather(*tasks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("chain", nargs="?", choices=["solana", "robinhood"], help="Chain a observar (modo simple)")
    parser.add_argument("addresses", nargs="*", help="Wallets a observar (modo simple)")
    parser.add_argument(
        "--chain", dest="chain_pairs", action="append", default=[],
        help="chain:wallet (repetible) -- modo multichain, ej: --chain solana:ABC --chain robinhood:0xDEF",
    )
    parser.add_argument("--sol-usd-price", type=float, default=None)
    parser.add_argument("--native-usd-price", type=float, default=None)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    args = parser.parse_args()

    solana_addresses: list[str] = []
    robinhood_addresses: list[str] = []

    if args.chain and args.addresses:
        if args.chain == "solana":
            solana_addresses.extend(args.addresses)
        else:
            robinhood_addresses.extend(args.addresses)

    for pair in args.chain_pairs:
        if ":" not in pair:
            print(f"Formato invalido para --chain: {pair!r} (esperado chain:wallet)")
            sys.exit(1)
        chain, wallet = pair.split(":", 1)
        if chain == "solana":
            solana_addresses.append(wallet)
        elif chain == "robinhood":
            robinhood_addresses.append(wallet)
        else:
            print(f"Chain desconocida: {chain!r} (soportadas: solana, robinhood)")
            sys.exit(1)

    if not solana_addresses and not robinhood_addresses:
        parser.print_help()
        sys.exit(1)

    print("=== Monitor multichain de solo lectura ===")
    print("NO ejecuta operaciones, NO conecta wallets privadas, NO usa credenciales.")
    if solana_addresses:
        print(f"Solana    : {', '.join(solana_addresses)}")
    if robinhood_addresses:
        print(f"Robinhood : {', '.join(robinhood_addresses)}")

    try:
        asyncio.run(
            run_both(
                solana_addresses, robinhood_addresses,
                args.sol_usd_price, args.poll_interval, args.native_usd_price,
            )
        )
    except KeyboardInterrupt:
        print("\nDetenido por el usuario.")


if __name__ == "__main__":
    main()
