#!/usr/bin/env python3
"""
models/normalized_trade.py — estructura común a TODAS las blockchains
soportadas (Fase 3: arquitectura multichain).

Cada chain-parser (Solana, EVM/Robinhood Chain, y los que se agreguen
despues) produce esta MISMA estructura, para que el resto del sistema
(alertas, base de datos, ranking de traders) no necesite saber en que
blockchain ocurrio la operacion.

SOLO LECTURA. Esta estructura no ejecuta nada, no firma nada, no contiene
claves privadas. Es puramente un contenedor de datos ya interpretados.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


@dataclass
class NormalizedTrade:
    # --- Campos pedidos explicitamente en el diseño multichain ---
    chain: str  # "solana" | "robinhood" | ... (nuevas chains se agregan aqui)
    wallet: str
    signature: str  # firma de Solana, o transactionHash de EVM (0x...)
    timestamp: Optional[str]  # ISO 8601 UTC
    action: str  # "BUY" | "SELL" | "SWAP" | "UNKNOWN"
    token_in: Optional[str]  # mint (Solana) o direccion de contrato (EVM), o "NATIVE"
    token_in_symbol: Optional[str]
    token_in_amount: Optional[float]
    token_out: Optional[str]
    token_out_symbol: Optional[str]
    token_out_amount: Optional[float]
    price: Optional[float]
    usd_value: Optional[float]
    protocol: Optional[str]
    confidence: float

    # --- Extensiones propias, no rompen el esquema pedido ---
    price_unit: Optional[str] = None  # unidad de "price" (USDC, ETH, ratio, etc.)
    notes: str = ""  # explicacion legible de la clasificacion/limitaciones
    programs_seen: List[str] = field(default_factory=list)  # program IDs / contract addresses relevantes vistos

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def human_readable(self) -> str:
        lines = [
            f"Chain      : {self.chain}",
            f"Wallet     : {self.wallet}",
            f"Signature  : {self.signature}",
            f"Timestamp  : {self.timestamp}",
            f"Accion     : {self.action}  (confidence={self.confidence:.2f})",
        ]
        if self.action in ("BUY", "SELL", "SWAP"):
            lines.append(
                f"Token IN   : {self.token_in_amount} {self.token_in_symbol or self.token_in}"
            )
            lines.append(
                f"Token OUT  : {self.token_out_amount} {self.token_out_symbol or self.token_out}"
            )
            if self.price is not None:
                lines.append(f"Precio est.: {self.price} {self.price_unit or ''}")
            if self.usd_value is not None:
                lines.append(f"Valor USD est.: ${self.usd_value:,.2f}")
        lines.append(f"Protocolo  : {self.protocol or 'no identificado'}")
        if self.programs_seen:
            lines.append(f"Programas/contratos vistos: {', '.join(self.programs_seen)}")
        if self.notes:
            lines.append(f"Notas      : {self.notes}")
        return "\n".join(lines)
