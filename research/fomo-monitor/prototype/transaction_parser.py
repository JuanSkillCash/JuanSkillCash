#!/usr/bin/env python3
"""
transaction_parser.py — FASE 2: interpretar transacciones de Solana como
operaciones de trading (BUY / SELL / SWAP / UNKNOWN).

SOLO LECTURA. No firma, no envia, no construye transacciones. No requiere
ni acepta claves privadas, seed phrases ni API keys. No se conecta a
fomo.family ni a ningun servicio de terceros no verificado: unicamente al
RPC publico oficial de Solana (mismo endpoint que wallet_monitor.py,
Fase 1) para descargar (getTransaction) la transaccion ya confirmada que
el monitor detecto.

------------------------------------------------------------------------
POR QUE ESTE DISEÑO (leer antes de tocar la logica)
------------------------------------------------------------------------
Una transaccion de Solana NO dice "esto fue una compra". Un programa como
Jupiter/Raydium/Orca es codigo arbitrario: su instruccion de nivel superior
casi nunca esta "parseada" por el nodo RPC (jsonParsed solo decodifica
instrucciones de programas nativos/conocidos: System, SPL Token,
Associated Token Account, ComputeBudget, etc. Para programas custom como
los DEX, la instruccion vuelve como "partially decoded":
{accounts, data (base58 sin decodificar), programId} — confirmado en
https://solana.com/docs/rpc/json-structures y en el issue publico
https://github.com/solana-labs/solana/issues/31701).

Por eso la unica forma robusta y agnostica-al-protocolo de saber que
entro y que salio de una wallet es comparar los BALANCES antes/despues:
  - meta.preTokenBalances / meta.postTokenBalances (tokens SPL)
  - meta.preBalances / meta.postBalances (SOL, en lamports)
(Ambos documentados en https://solana.com/docs/rpc/http/gettransaction y
https://solana.com/docs/rpc/json-structures). El "programId" de las
instrucciones (top-level y las de meta.innerInstructions, cuando el CPI
invoca un programa conocido de DEX) solo se usa para identificar el
PROTOCOLO/DEX usado — nunca para inferir montos, exactamente como pide el
enunciado ("compara los balances antes y despues... determine que activo
salio y cual entro").

------------------------------------------------------------------------
LIMITACION DE ESTE ENTORNO (ver tambien INFORME_TECNICO_FOMO.md, seccion 0)
------------------------------------------------------------------------
Este modulo se escribio en un sandbox sin salida de red a dominios
externos (incluido api.mainnet-beta.solana.com). No se pudo:
  - Descargar una transaccion real en vivo con getTransaction.
  - Verificar byte-a-byte las direcciones de programa citadas abajo contra
    el RPC (se verificaron via busqueda web, con fuente citada en cada
    entrada del registro KNOWN_PROGRAMS).
Los tests (tests/) usan fixtures JSON construidos a mano que replican
FIELMENTE el esquema oficial de getTransaction (jsonParsed), pero NO son
una descarga real verificada en este sandbox — ver tests/fixtures/README.md
para el detalle exacto y como reemplazarlos por transacciones reales en un
entorno con acceso a Internet normal.
"""

from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple, Any

# --------------------------------------------------------------------------
# RPC público (mismo endpoint que wallet_monitor.py — sin API key)
# --------------------------------------------------------------------------
SOLANA_RPC_HTTP = "https://api.mainnet-beta.solana.com"

# --------------------------------------------------------------------------
# Mints "quote" reconocidos (activos que actuan como base/contrapartida de
# una operacion: stablecoins y SOL). Direcciones verificadas via busqueda
# web con fuente oficial/canonica citada en cada linea. No confirmadas por
# consulta RPC directa en este sandbox (ver limitacion arriba).
# --------------------------------------------------------------------------

# Native/Wrapped SOL mint — direccion canonica documentada en el propio
# SPL Token program ("native mint"); usada de forma universal en el
# ecosistema Solana (Jupiter, Raydium, Orca, exploradores, etc.).
WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"

# USDC en Solana — publicada por Circle. Confirmado via
# https://solana.com/docs (referencias multiples) y Circle.
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# USDT en Solana — confirmado via cuenta oficial @solana en X y
# Solana Explorer (https://explorer.solana.com/address/Es9v...enwNYB).
USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

QUOTE_ASSETS: Dict[str, str] = {
    WRAPPED_SOL_MINT: "SOL",
    USDC_MINT: "USDC",
    USDT_MINT: "USDT",
}

# Subconjunto de quote assets que se tratan como ~1:1 con USD para poder
# estimar estimated_usd_value sin depender de un oraculo externo de precio.
STABLECOIN_MINTS: Set[str] = {USDC_MINT, USDT_MINT}

# --------------------------------------------------------------------------
# Programas "de infraestructura": aparecen en casi cualquier transaccion
# (transferencias de SOL, apertura de cuentas de token, presupuesto de
# computo) pero NUNCA son "el protocolo de trading" en si mismos. Se
# excluyen al detectar el DEX/protocolo usado. IDs confirmados via
# busqueda web (Solana Explorer / Solscan / docs oficiales), citados
# individualmente.
# --------------------------------------------------------------------------
INFRA_PROGRAMS: Dict[str, str] = {
    # https://solana.com/docs/core/programs/builtin-programs
    "11111111111111111111111111111111": "System Program",
    # https://explorer.solana.com/address/ComputeBudget111111111111111111111111111111
    "ComputeBudget111111111111111111111111111111": "Compute Budget Program",
    # https://explorer.solana.com/address/TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "SPL Token Program",
    # https://solscan.io/account/ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL": "Associated Token Account Program",
}

# --------------------------------------------------------------------------
# Registro de protocolos/DEX conocidos en Solana. Cada entrada cita la
# fuente donde se confirmo el program id (no verificado por RPC directo en
# este sandbox — revalidar contra un explorador antes de produccion).
# Orden de PROTOCOL_PRIORITY: si aparece mas de un programa reconocido en
# la misma transaccion (p. ej. Jupiter enrutando a traves de Raydium), se
# reporta el mas "externo"/agregador primero, y el resto queda listado en
# `route` para no perder informacion.
# --------------------------------------------------------------------------
KNOWN_PROGRAMS: Dict[str, str] = {
    # Jupiter Aggregator v6 — confirmado en Solscan/SolanaFM.
    # https://solscan.io/account/JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter Aggregator v6",
    # Segundo deployment de Jupiter v6 citado junto al anterior.
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "Jupiter Aggregator v6",
    # Raydium AMM v4 (Liquidity Pool V4) — docs.raydium.io/reference/program-addresses
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM v4",
    # Raydium CLMM — docs.raydium.io/reference/program-addresses
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium CLMM",
    # Raydium CPMM — docs.raydium.io/reference/program-addresses
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "Raydium CPMM",
    # Orca Whirlpool — github.com/orca-so/whirlpools, docs.orca.so
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpool",
    # Pump.fun bonding curve — github.com/pump-fun/pump-public-docs
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "Pump.fun (bonding curve)",
    # PumpSwap (AMM post-graduacion de Pump.fun) — mismo repo oficial.
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "PumpSwap",
    # Meteora DLMM — solscan.io / docs.meteora.ag
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "Meteora DLMM",
}

# Prioridad: agregadores primero (envuelven a los demas), luego AMMs.
PROTOCOL_PRIORITY: List[str] = [
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
]

# Umbral heuristico (en lamports) para distinguir un cambio de SOL que es
# "ruido" de apertura/cierre de una Associated Token Account (el costo
# tipico de rent-exempt para una cuenta de token es pequeño, del orden de
# ~0.002 SOL) de un cambio de SOL que representa una pata real del swap.
# Es una heuristica documentada como tal, no una constante de protocolo:
# revisar/ajustar con datos reales antes de confiar en ella en produccion.
RENT_NOISE_LAMPORTS_THRESHOLD = 3_000_000  # 0.003 SOL


# --------------------------------------------------------------------------
# Estructura de datos normalizada
# --------------------------------------------------------------------------
@dataclass
class TradeEvent:
    wallet: str
    signature: str
    timestamp: Optional[str]  # ISO 8601 UTC, derivado de blockTime
    action: str  # "BUY" | "SELL" | "SWAP" | "UNKNOWN"
    token_in: Optional[str]  # mint del activo que la wallet ENTREGO
    token_in_amount: Optional[float]
    token_out: Optional[str]  # mint del activo que la wallet RECIBIO
    token_out_amount: Optional[float]
    estimated_price: Optional[float]
    estimated_usd_value: Optional[float]
    protocol: Optional[str]
    confidence: float

    # --- Campos adicionales (extension propia, no rompen el esquema pedido) ---
    token_in_symbol: Optional[str] = None
    token_out_symbol: Optional[str] = None
    price_unit: Optional[str] = None  # en que unidad esta expresado estimated_price
    notes: str = ""  # explicacion legible de la clasificacion/limitaciones
    programs_seen: List[str] = field(default_factory=list)  # programIds no-infra vistos

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def human_readable(self) -> str:
        lines = [
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
            if self.estimated_price is not None:
                lines.append(
                    f"Precio est.: {self.estimated_price} {self.price_unit or ''}"
                )
            if self.estimated_usd_value is not None:
                lines.append(f"Valor USD est.: ${self.estimated_usd_value:,.2f}")
        lines.append(f"Protocolo  : {self.protocol or 'no identificado'}")
        if self.programs_seen:
            lines.append(f"Programas vistos: {', '.join(self.programs_seen)}")
        if self.notes:
            lines.append(f"Notas      : {self.notes}")
        return "\n".join(lines)


def _unknown_event(
    wallet: str,
    signature: str,
    timestamp: Optional[str],
    confidence: float,
    notes: str,
    protocol: Optional[str] = None,
    programs_seen: Optional[List[str]] = None,
) -> TradeEvent:
    return TradeEvent(
        wallet=wallet,
        signature=signature,
        timestamp=timestamp,
        action="UNKNOWN",
        token_in=None,
        token_in_amount=None,
        token_out=None,
        token_out_amount=None,
        estimated_price=None,
        estimated_usd_value=None,
        protocol=protocol,
        confidence=confidence,
        notes=notes,
        programs_seen=programs_seen or [],
    )


# --------------------------------------------------------------------------
# Obtencion de la transaccion via RPC publico (best-effort; no ejercitado
# en vivo en este sandbox — ver limitacion en el docstring del modulo)
# --------------------------------------------------------------------------
def fetch_transaction_json(
    signature: str, rpc_url: str = SOLANA_RPC_HTTP, timeout: float = 15.0
) -> Dict[str, Any]:
    """Llama a getTransaction (encoding=jsonParsed) en un RPC publico de Solana.

    Solo lectura: es una consulta HTTP JSON-RPC estandar, sin autenticacion,
    documentada en https://solana.com/docs/rpc/http/gettransaction
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            signature,
            {
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 0,
                "commitment": "confirmed",
            },
        ],
    }
    req = urllib.request.Request(
        rpc_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if "error" in body:
        raise RuntimeError(f"RPC error al obtener {signature}: {body['error']}")
    result = body.get("result")
    if result is None:
        raise RuntimeError(
            f"getTransaction devolvio result=null para {signature} "
            "(firma no encontrada, no confirmada, o fuera de la ventana de retencion del nodo)."
        )
    return result


# --------------------------------------------------------------------------
# Resolucion de accountKeys (incluye Address Lookup Tables de tx versionadas)
# --------------------------------------------------------------------------
def _resolve_account_keys(tx: Dict[str, Any]) -> List[str]:
    """Devuelve la lista de pubkeys en el MISMO orden que preBalances/
    postBalances/preTokenBalances[].accountIndex/postTokenBalances[].accountIndex.

    Segun https://solana.com/docs/rpc/json-structures : los indices de
    balance pueden referirse a cuentas fuera de "accountKeys" que deben
    resolverse con "loadedAddresses" (transacciones versionadas con Address
    Lookup Tables). El orden usado aqui (estaticas -> loadedAddresses.writable
    -> loadedAddresses.readonly) sigue la convencion de compilacion de
    mensajes v0 de Solana (solana-web3.js / MessageV0). ADVERTENCIA: no se
    pudo verificar esta ordenacion contra una transaccion real con ALT en
    este sandbox (sin red) — es el punto mas fragil del parser y deberia
    confirmarse con una transaccion real de Jupiter (usa ALT con frecuencia)
    antes de confiar en el en produccion. Ver INFORME_TECNICO_FOMO.md.
    """
    message = tx["transaction"]["message"]
    keys: List[str] = []
    for entry in message.get("accountKeys", []):
        if isinstance(entry, dict):
            keys.append(entry["pubkey"])
        else:
            keys.append(entry)  # legacy: ya es un string

    loaded = (tx.get("meta") or {}).get("loadedAddresses") or {}
    keys.extend(loaded.get("writable", []))
    keys.extend(loaded.get("readonly", []))
    return keys


def _program_id_of_instruction(
    instr: Dict[str, Any], account_keys: List[str]
) -> Optional[str]:
    """Devuelve el programId de una instruccion (top-level o inner).

    Las instrucciones top-level en jsonParsed ya traen "programId" resuelto
    (parseadas o "partially decoded"). Las inner instructions pueden traer
    "programIdIndex" (indice en account_keys) en vez de "programId" resuelto
    — ambos casos estan documentados y se manejan aqui.
    """
    if "programId" in instr:
        return instr["programId"]
    idx = instr.get("programIdIndex")
    if idx is not None and 0 <= idx < len(account_keys):
        return account_keys[idx]
    return None


def _collect_program_ids(tx: Dict[str, Any], account_keys: List[str]) -> List[str]:
    """Junta todos los programIds (top-level + inner instructions), sin
    duplicados, excluyendo los programas de infraestructura (INFRA_PROGRAMS),
    preservando orden de aparicion."""
    seen: List[str] = []
    message = tx["transaction"]["message"]

    for instr in message.get("instructions", []):
        pid = _program_id_of_instruction(instr, account_keys)
        if pid and pid not in INFRA_PROGRAMS and pid not in seen:
            seen.append(pid)

    meta = tx.get("meta") or {}
    for inner in meta.get("innerInstructions") or []:
        for instr in inner.get("instructions", []):
            pid = _program_id_of_instruction(instr, account_keys)
            if pid and pid not in INFRA_PROGRAMS and pid not in seen:
                seen.append(pid)

    return seen


def detect_protocol(program_ids: List[str]) -> Optional[str]:
    """Elige el protocolo "principal" a reportar, priorizando agregadores
    sobre AMMs individuales (ver PROTOCOL_PRIORITY)."""
    program_id_set = set(program_ids)
    for pid in PROTOCOL_PRIORITY:
        if pid in program_id_set:
            return KNOWN_PROGRAMS[pid]
    return None


# --------------------------------------------------------------------------
# Balances: SOL y SPL tokens
# --------------------------------------------------------------------------
def _ui_amount_decimal(token_balance_entry: Dict[str, Any]) -> Decimal:
    ui = token_balance_entry.get("uiTokenAmount", {})
    raw = ui.get("amount")
    decimals = ui.get("decimals")
    if raw is not None and decimals is not None:
        try:
            return Decimal(raw) / (Decimal(10) ** int(decimals))
        except InvalidOperation:
            pass
    s = ui.get("uiAmountString")
    if s not in (None, ""):
        try:
            return Decimal(s)
        except InvalidOperation:
            pass
    return Decimal(0)


def _token_deltas_for_owner(meta: Dict[str, Any], owner: str) -> Dict[str, Decimal]:
    """Compara preTokenBalances vs postTokenBalances para las cuentas de
    token cuyo owner == wallet observada, y devuelve {mint: delta_ui}.
    delta > 0 => la wallet RECIBIO ese token; delta < 0 => lo ENTREGO.
    Si la wallet tiene mas de una cuenta del mismo mint, se suman.
    """
    pre: Dict[int, Tuple[str, Decimal]] = {}
    post: Dict[int, Tuple[str, Decimal]] = {}

    for tb in meta.get("preTokenBalances") or []:
        if tb.get("owner") == owner:
            pre[tb["accountIndex"]] = (tb["mint"], _ui_amount_decimal(tb))
    for tb in meta.get("postTokenBalances") or []:
        if tb.get("owner") == owner:
            post[tb["accountIndex"]] = (tb["mint"], _ui_amount_decimal(tb))

    deltas: Dict[str, Decimal] = {}
    for idx in set(pre) | set(post):
        mint_pre, amt_pre = pre.get(idx, (None, Decimal(0)))
        mint_post, amt_post = post.get(idx, (None, Decimal(0)))
        mint = mint_post or mint_pre
        if mint is None:
            continue
        delta = amt_post - amt_pre
        if delta != 0:
            deltas[mint] = deltas.get(mint, Decimal(0)) + delta
    return deltas


def _sol_delta_lamports(meta: Dict[str, Any], wallet_idx: int) -> int:
    """Delta de SOL de la wallet, EXCLUYENDO el efecto de la fee de red
    cuando la wallet es quien paga la transaccion.

    Invariante documentada de Solana: la cuenta que paga la fee es SIEMPRE
    accountKeys[0] (primer firmante) — ver
    https://solana.com/docs/core/transactions/transaction-structure
    Si la wallet observada es esa cuenta, su preBalance/postBalance ya
    refleja la fee descontada; para no confundir "fee de red" con "pata de
    un swap en SOL" se le vuelve a sumar la fee al delta.
    """
    pre = meta["preBalances"][wallet_idx]
    post = meta["postBalances"][wallet_idx]
    raw_delta = post - pre
    fee = meta.get("fee", 0)
    if wallet_idx == 0:
        return raw_delta + fee
    return raw_delta


def _iso_from_unix(block_time: Optional[int]) -> Optional[str]:
    if block_time is None:
        return None
    return datetime.fromtimestamp(block_time, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# --------------------------------------------------------------------------
# Estimacion de precio / valor en USD
# --------------------------------------------------------------------------
def _usd_value_of_leg(
    mint: str, amount: Decimal, sol_usd_price: Optional[float]
) -> Optional[Decimal]:
    """USD aproximado de una "pata" de la operacion.

    - Stablecoin (USDC/USDT): se asume ~1:1 con USD (aproximacion; ignora
      des-anclajes/depeg reales del stablecoin).
    - SOL: requiere que el llamador provea sol_usd_price (un precio externo,
      p. ej. de un oraculo tipo Pyth o de un agregador de precios). Este
      modulo NO consulta ningun proveedor de precio por si mismo — ver
      seccion "que falta para el precio" en el informe.
    - Cualquier otro token: no hay forma de valuarlo en USD sin una fuente
      de precio externa (no hay stablecoin/SOL involucrado directamente).
    """
    if mint in STABLECOIN_MINTS:
        return amount
    if mint == WRAPPED_SOL_MINT and sol_usd_price is not None:
        return amount * Decimal(str(sol_usd_price))
    return None


def _estimate_price(
    action: str,
    token_in: str,
    token_in_amount: Decimal,
    token_out: str,
    token_out_amount: Decimal,
    sol_usd_price: Optional[float],
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """Devuelve (estimated_price, estimated_usd_value, price_unit).

    estimated_price siempre se expresa "por unidad del token no-quote"
    cuando aplica (BUY/SELL), en la unidad indicada por price_unit — NO es
    automaticamente USD salvo que price_unit sea USDC/USDT, o que se haya
    provisto sol_usd_price para el caso SOL.
    """
    usd_in = _usd_value_of_leg(token_in, token_in_amount, sol_usd_price)
    usd_out = _usd_value_of_leg(token_out, token_out_amount, sol_usd_price)
    usd_value = usd_in if usd_in is not None else usd_out

    price: Optional[Decimal] = None
    unit: Optional[str] = None

    if action == "BUY" and token_out_amount != 0:
        price = token_in_amount / token_out_amount
        unit = QUOTE_ASSETS.get(token_in, token_in[:6] + "…")
    elif action == "SELL" and token_in_amount != 0:
        price = token_out_amount / token_in_amount
        unit = QUOTE_ASSETS.get(token_out, token_out[:6] + "…")
    elif action == "SWAP" and token_in_amount != 0:
        price = token_out_amount / token_in_amount
        in_sym = QUOTE_ASSETS.get(token_in, token_in[:6] + "…")
        out_sym = QUOTE_ASSETS.get(token_out, token_out[:6] + "…")
        unit = f"{out_sym}/{in_sym}"

    return (
        float(price) if price is not None else None,
        float(usd_value) if usd_value is not None else None,
        unit,
    )


# --------------------------------------------------------------------------
# Orquestador principal
# --------------------------------------------------------------------------
def interpret_transaction(
    tx: Dict[str, Any], wallet: str, sol_usd_price: Optional[float] = None
) -> TradeEvent:
    """Interpreta una transaccion ya descargada (resultado de getTransaction,
    encoding jsonParsed) desde el punto de vista de `wallet`.

    `sol_usd_price` es opcional y puramente informativo: si se provee (por
    ejemplo desde un oraculo de precio externo que el usuario decida
    integrar en una fase posterior), se usa solo para poder expresar en USD
    las operaciones cuya contrapartida es SOL nativo/wrapped. Si no se
    provee, esas operaciones quedan con estimated_usd_value=None en vez de
    inventar un numero.
    """
    signature = tx["transaction"]["signatures"][0]
    timestamp = _iso_from_unix(tx.get("blockTime"))
    meta = tx.get("meta")

    if meta is None:
        return _unknown_event(
            wallet, signature, timestamp, 0.0,
            "La transaccion no trae 'meta' (sin datos de balances); no se puede interpretar.",
        )

    if meta.get("err") is not None:
        return _unknown_event(
            wallet, signature, timestamp, 0.0,
            f"La transaccion fallo on-chain (meta.err = {meta['err']}); "
            "no representa una operacion ejecutada con exito.",
        )

    account_keys = _resolve_account_keys(tx)
    try:
        wallet_idx = account_keys.index(wallet)
    except ValueError:
        return _unknown_event(
            wallet, signature, timestamp, 0.0,
            "La wallet indicada no aparece en las cuentas de esta transaccion.",
        )

    program_ids = _collect_program_ids(tx, account_keys)
    protocol = detect_protocol(program_ids)

    # --- deltas por activo ---
    legs: Dict[str, Decimal] = {}

    sol_lamports_delta = _sol_delta_lamports(meta, wallet_idx)
    if sol_lamports_delta != 0:
        legs[WRAPPED_SOL_MINT] = Decimal(sol_lamports_delta) / Decimal(10**9)

    for mint, delta in _token_deltas_for_owner(meta, wallet).items():
        legs[mint] = legs.get(mint, Decimal(0)) + delta

    # Filtrar ruido de rent: un cambio de SOL pequeño (apertura/cierre de
    # una Associated Token Account) cuando YA hay otras patas de token que
    # explican la operacion no debe contarse como una pata adicional real.
    rent_noise = False
    sol_leg = legs.get(WRAPPED_SOL_MINT)
    if (
        sol_leg is not None
        and len(legs) >= 2
        and abs(sol_leg) * Decimal(10**9) < RENT_NOISE_LAMPORTS_THRESHOLD
    ):
        del legs[WRAPPED_SOL_MINT]
        rent_noise = True

    outflows = {m: -d for m, d in legs.items() if d < 0}
    inflows = {m: d for m, d in legs.items() if d > 0}
    n_out, n_in = len(outflows), len(inflows)

    if n_out == 0 and n_in == 0:
        return _unknown_event(
            wallet, signature, timestamp, 0.0,
            "Sin cambios de balance relevantes para esta wallet (mas alla de la fee de red).",
            protocol=protocol, programs_seen=program_ids,
        )

    if n_out + n_in == 1:
        return _unknown_event(
            wallet, signature, timestamp, 0.15,
            "Solo un activo cambio de balance para esta wallet: parece una "
            "transferencia simple (o solo pago de rent/fee), no un swap de dos patas.",
            protocol=protocol, programs_seen=program_ids,
        )

    if not (n_out == 1 and n_in == 1):
        return _unknown_event(
            wallet, signature, timestamp, 0.25,
            f"Se detectaron {n_out} salida(s) y {n_in} entrada(s) de activos distintos "
            "(posible ruta multi-hop u operacion compuesta). No se adivina cual par es "
            "'la operacion principal'; revisar manualmente.",
            protocol=protocol, programs_seen=program_ids,
        )

    token_in_mint = next(iter(outflows))
    token_out_mint = next(iter(inflows))
    token_in_amount = outflows[token_in_mint]
    token_out_amount = inflows[token_out_mint]

    in_is_quote = token_in_mint in QUOTE_ASSETS
    out_is_quote = token_out_mint in QUOTE_ASSETS

    if in_is_quote and not out_is_quote:
        action = "BUY"
        base_confidence = 0.95
    elif out_is_quote and not in_is_quote:
        action = "SELL"
        base_confidence = 0.95
    else:
        # Ambos son quote assets (ej. SOL<->USDC) o ninguno lo es (ej.
        # token<->token): no hay forma no-arbitraria de decidir cual lado
        # es "lo comprado", asi que se reporta como SWAP en vez de inventar
        # un BUY/SELL.
        action = "SWAP"
        base_confidence = 0.80

    confidence = base_confidence
    notes_parts = []
    if protocol is None:
        confidence -= 0.30
        notes_parts.append(
            "no se reconocio ningun programa de DEX conocido en la transaccion "
            "(KNOWN_PROGRAMS); la clasificacion se basa solo en balances."
        )
    if rent_noise:
        confidence -= 0.05
        notes_parts.append(
            "se descarto una pata de SOL pequeña, tratada como rent de "
            "apertura/cierre de cuenta de token (heuristica, no protocolo)."
        )
    confidence = max(0.0, min(1.0, confidence))

    price, usd_value, price_unit = _estimate_price(
        action, token_in_mint, token_in_amount, token_out_mint, token_out_amount, sol_usd_price
    )
    if usd_value is None:
        notes_parts.append(
            "no se pudo estimar el valor en USD: ninguna de las dos patas es un "
            "stablecoin y no se proveyo un precio SOL/USD externo (sol_usd_price)."
        )

    return TradeEvent(
        wallet=wallet,
        signature=signature,
        timestamp=timestamp,
        action=action,
        token_in=token_in_mint,
        token_in_amount=float(token_in_amount),
        token_out=token_out_mint,
        token_out_amount=float(token_out_amount),
        estimated_price=price,
        estimated_usd_value=usd_value,
        protocol=protocol,
        confidence=confidence,
        token_in_symbol=QUOTE_ASSETS.get(token_in_mint),
        token_out_symbol=QUOTE_ASSETS.get(token_out_mint),
        price_unit=price_unit,
        notes="; ".join(notes_parts),
        programs_seen=program_ids,
    )


def interpret_signature(
    signature: str,
    wallet: str,
    rpc_url: str = SOLANA_RPC_HTTP,
    sol_usd_price: Optional[float] = None,
) -> TradeEvent:
    """Punto de entrada pensado para conectarse desde wallet_monitor.py:
    dada una firma nueva detectada por el monitor, descarga la transaccion
    completa y la interpreta. Solo lectura; misma politica de red que
    wallet_monitor.py (RPC publico, sin credenciales)."""
    tx = fetch_transaction_json(signature, rpc_url=rpc_url)
    return interpret_transaction(tx, wallet, sol_usd_price=sol_usd_price)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _run_fixture_demo() -> None:
    """Modo por defecto (sin argumentos): interpreta los fixtures locales
    en tests/fixtures/*.json, sin necesitar red. Sirve para poder ejecutar
    `python transaction_parser.py` y ver una interpretacion legible incluso
    en un entorno sin salida a Internet (como este sandbox)."""
    fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
    manifest_path = fixtures_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"No se encontro {manifest_path}. Nada que demostrar.")
        return

    manifest = json.loads(manifest_path.read_text())
    print("=== Modo demo (offline): interpretando fixtures locales ===")
    print(f"({len(manifest)} transacciones de ejemplo en {fixtures_dir})\n")

    for entry in manifest:
        tx_path = fixtures_dir / entry["file"]
        tx = json.loads(tx_path.read_text())
        event = interpret_transaction(
            tx, entry["wallet"], sol_usd_price=entry.get("sol_usd_price_hint")
        )
        print(f"--- {entry['file']} ({entry.get('description', '')}) ---")
        print(event.human_readable())
        print()


def main() -> None:
    if len(sys.argv) == 1:
        _run_fixture_demo()
        print(
            "Uso con una transaccion real (requiere red saliente hacia el RPC "
            "publico de Solana, no disponible en este sandbox):\n"
            "  python transaction_parser.py <SIGNATURE> <WALLET_ADDRESS> [sol_usd_price]"
        )
        return

    if len(sys.argv) < 3:
        print("Uso: python transaction_parser.py <SIGNATURE> <WALLET_ADDRESS> [sol_usd_price]")
        sys.exit(1)

    signature = sys.argv[1]
    wallet = sys.argv[2]
    sol_usd_price = float(sys.argv[3]) if len(sys.argv) > 3 else None

    event = interpret_signature(signature, wallet, sol_usd_price=sol_usd_price)
    print(event.human_readable())


if __name__ == "__main__":
    main()
