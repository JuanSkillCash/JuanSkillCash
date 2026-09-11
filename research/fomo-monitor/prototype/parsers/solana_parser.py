#!/usr/bin/env python3
"""
parsers/solana_parser.py — adapta la salida de la Fase 2
(prototype/transaction_parser.py) al esquema NormalizedTrade multichain.

IMPORTANTE: este modulo NO reimplementa ni modifica la logica de
interpretacion de Solana. Solo importa transaction_parser.py (intacto,
tal como quedo en la Fase 2) y traduce su TradeEvent a NormalizedTrade.
"El parser que ya construimos... debe seguir funcionando exactamente
como hasta ahora" — se cumple literalmente: transaction_parser.py no se
toco en esta fase, ver `git diff` de este commit.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import transaction_parser as solana_tp  # noqa: E402  (Fase 2, sin modificar)
from models.normalized_trade import NormalizedTrade  # noqa: E402

CHAIN_NAME = "solana"


def to_normalized(event: "solana_tp.TradeEvent") -> NormalizedTrade:
    """Traduce un TradeEvent (Fase 2, especifico de Solana) a NormalizedTrade."""
    return NormalizedTrade(
        chain=CHAIN_NAME,
        wallet=event.wallet,
        signature=event.signature,
        timestamp=event.timestamp,
        action=event.action,
        token_in=event.token_in,
        token_in_symbol=event.token_in_symbol,
        token_in_amount=event.token_in_amount,
        token_out=event.token_out,
        token_out_symbol=event.token_out_symbol,
        token_out_amount=event.token_out_amount,
        price=event.estimated_price,
        usd_value=event.estimated_usd_value,
        protocol=event.protocol,
        confidence=event.confidence,
        price_unit=event.price_unit,
        notes=event.notes,
        programs_seen=list(event.programs_seen),
    )


def interpret_transaction(
    tx: Dict[str, Any], wallet: str, sol_usd_price: Optional[float] = None
) -> NormalizedTrade:
    """Punto de entrada multichain: misma firma conceptual que el parser EVM
    (interpret_transaction(tx, wallet, ...) -> NormalizedTrade), para que el
    Chain Adapter / Transaction Monitor puedan tratar a ambas chains de forma
    uniforme."""
    event = solana_tp.interpret_transaction(tx, wallet, sol_usd_price=sol_usd_price)
    return to_normalized(event)


def interpret_signature(
    signature: str,
    wallet: str,
    rpc_url: str = solana_tp.SOLANA_RPC_HTTP,
    sol_usd_price: Optional[float] = None,
) -> NormalizedTrade:
    event = solana_tp.interpret_signature(signature, wallet, rpc_url=rpc_url, sol_usd_price=sol_usd_price)
    return to_normalized(event)
