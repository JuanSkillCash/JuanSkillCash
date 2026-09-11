#!/usr/bin/env python3
"""
chains/solana_adapter.py — Chain Adapter de Solana para la arquitectura
multichain (Fase 3).

Este modulo NO reimplementa nada: envuelve wallet_monitor.py (Fase 1,
intacto) para exponer la misma interfaz conceptual que
chains/robinhood_adapter.py (`watch(addresses, on_signature, ...)`), de
modo que un Transaction Monitor de mas alto nivel pueda tratar a ambas
chains de forma uniforme sin conocer los detalles de cada RPC.

SOLO LECTURA. Ver wallet_monitor.py para el detalle completo de que hace
y que no hace.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Awaitable, Callable, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wallet_monitor  # noqa: E402  (Fase 1, sin modificar)
from parsers import solana_parser  # noqa: E402

CHAIN_NAME = "solana"

OnTradeCallback = Callable[["solana_parser.NormalizedTrade"], Awaitable[None]]


async def watch(
    addresses: List[str],
    on_trade,
    rpc_wss: str = wallet_monitor.SOLANA_PUBLIC_WSS,
    rpc_http: str = wallet_monitor.SOLANA_PUBLIC_HTTP,
    sol_usd_price: Optional[float] = None,
) -> None:
    """Se suscribe (logsSubscribe) a `addresses` y, por cada firma nueva y
    exitosa, descarga+interpreta la transaccion y llama a
    `on_trade(NormalizedTrade)`. Reutiliza wallet_monitor.run() con
    interpret=True pero redirige la alerta a `on_trade` en vez de solo
    imprimirla -- para eso se parchea temporalmente
    wallet_monitor._interpret_and_alert via un wrapper minimo, sin tocar
    el archivo original.
    """
    original = wallet_monitor._interpret_and_alert

    async def _bridge(addr, signature, http_rpc_url, price):
        loop = asyncio.get_running_loop()
        try:
            trade = await loop.run_in_executor(
                None, solana_parser.interpret_signature, signature, addr, http_rpc_url, price
            )
        except Exception as exc:
            wallet_monitor.log(f"  [interpretacion fallida] {addr} / {signature}: {exc}")
            return
        await on_trade(trade)

    wallet_monitor._interpret_and_alert = _bridge
    try:
        await wallet_monitor.run(
            addresses, rpc_url=rpc_wss, interpret=True,
            http_rpc_url=rpc_http, sol_usd_price=sol_usd_price,
        )
    finally:
        wallet_monitor._interpret_and_alert = original
