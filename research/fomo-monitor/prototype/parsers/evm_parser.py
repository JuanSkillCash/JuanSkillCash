#!/usr/bin/env python3
"""
parsers/evm_parser.py — interpreta transacciones EVM (Robinhood Chain, y
cualquier otra chain EVM-compatible reusando el mismo codigo) como
operaciones BUY/SELL/SWAP/UNKNOWN, produciendo un NormalizedTrade.

SOLO LECTURA. No firma, no envia, ni construye transacciones. No requiere
ni acepta claves privadas, seed phrases ni API keys propias (si el
usuario decide usar un proveedor de RPC de pago para escalar, la API key
es SUYA y se pasa como parametro de conexion, nunca se hardcodea aqui).

------------------------------------------------------------------------
POR QUE ESTE DISEÑO (mismo principio que prototype/transaction_parser.py)
------------------------------------------------------------------------
Igual que en Solana, NO se decodifica la instruccion/calldata de cada DEX
(Uniswap V2/V3/V4, UniswapX, o cualquier agregador). En vez de eso se
comparan los eventos ERC-20 `Transfer` que aparecen en
`receipt.logs` DENTRO de la misma transaccion: el/los token(s) cuyo
`Transfer` tiene `from == wallet` salieron de la wallet; los que tienen
`to == wallet` entraron. Esto es protocol-agnostic: funciona igual si el
swap paso por Uniswap V2, V3, V4, UniswapX, un agregador, o un router que
nadie documento todavia — exactamente el mismo principio que en Solana
("comparar balances, no decodificar instrucciones").

El "topic0" (hash de la firma del evento) de los logs SI se usa, pero
solo para identificar el PROTOCOLO/DEX (si el log de una Swap conocida de
Uniswap V2/V3 aparece en la transaccion), nunca para inferir montos.

ERC-20 Transfer y las firmas de evento de Uniswap V2/V3 usadas aqui son
CONSTANTES UNIVERSALES DE EVM (identicas en cualquier chain EVM, no son
especificas de Robinhood Chain) y estan confirmadas via busqueda web con
fuente citada junto a cada constante. Las DIRECCIONES DE CONTRATO
especificas de Robinhood Chain (WETH, USDG, routers) son harina de otro
costal: no se pudieron verificar con la misma confianza en este sandbox
(ver INFORME_MULTICHAIN.md, seccion de limitaciones) — por eso este
modulo identifica "quote assets" (ETH/WETH/USDG/USDC/USDT) por SIMBOLO
(via `symbol()`, resuelto con una llamada eth_call estandar de ERC-20),
no por direccion de contrato hardcodeada. Es una decision de diseño
deliberada para no "inventar" direcciones que no pude confirmar.

------------------------------------------------------------------------
LIMITACION CONOCIDA: ETH nativo recibido (no via Transfer)
------------------------------------------------------------------------
Un swap "token -> ETH nativo" tipicamente envuelve/desenvuelve WETH
internamente dentro del router y entrega ETH nativo al final via una
llamada interna (no un evento Transfer de un ERC-20). Ese ETH nativo
recibido NO aparece en `receipt.logs` ni en `tx.value` (que solo refleja
lo que el FIRMANTE envio, no lo que recibio). Este modulo detecta
correctamente "gasto ETH nativo para comprar" (via `tx.value`) pero NO
detecta de forma fiable "recibi ETH nativo al vender" en su version
actual — queda documentado como limitacion conocida y como trabajo futuro
(vigilar el evento `Withdrawal(address,uint256)` del contrato WETH9,
tambien un estandar universal de EVM) en vez de forzar una deteccion a
medias que podria dar falsos negativos silenciosos.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, List, Set, Tuple, Any, Callable

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models.normalized_trade import NormalizedTrade  # noqa: E402

CHAIN_NAME = "robinhood"

# --------------------------------------------------------------------------
# Robinhood Chain — datos de red confirmados via busqueda web (ver
# INFORME_MULTICHAIN.md para las citas completas de cada uno).
# --------------------------------------------------------------------------
ROBINHOOD_CHAIN_ID = 4663
# RPC publico oficial: gratis, sin API key, con rate limit y sin SLA.
# https://docs.robinhood.com/chain/connecting/ (via busqueda web)
ROBINHOOD_RPC_HTTP = "https://rpc.mainnet.chain.robinhood.com"
# Explorador oficial (Blockscout, open source, API estilo Etherscan v2).
# https://robinhoodchain.blockscout.com/
ROBINHOOD_EXPLORER = "https://robinhoodchain.blockscout.com"

NATIVE_ETH_PSEUDO = "NATIVE"  # no es una direccion de contrato real

# --------------------------------------------------------------------------
# Firmas de evento — CONSTANTES UNIVERSALES DE EVM (no especificas de
# Robinhood Chain), confirmadas via busqueda web.
# --------------------------------------------------------------------------
# Transfer(address indexed from, address indexed to, uint256 value)
TRANSFER_EVENT_TOPIC0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Uniswap V3 Swap(address indexed sender, address indexed recipient,
# int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity,
# int24 tick) — confirmado via busqueda web.
UNISWAP_V3_SWAP_TOPIC0 = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"

# Uniswap V2 Swap(address indexed sender, uint amount0In, uint amount1In,
# uint amount0Out, uint amount1Out, address indexed to) — el propio evento
# esta confirmado via busqueda web; el hash topic0 concreto que se usa
# aqui viene de conocimiento de entrenamiento (constante muy citada en
# tooling de indexado DeFi) y NO se confirmo con una fuente que mostrara
# el hash explicito en esta sesion. Revalidar contra
# https://github.com/otterscan/topic0 (base de firmas de eventos) antes
# de depender de el en produccion.
UNISWAP_V2_SWAP_TOPIC0 = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"

KNOWN_EVENT_SIGNATURES: Dict[str, str] = {
    UNISWAP_V3_SWAP_TOPIC0: "Uniswap V3 (o fork compatible)",
    UNISWAP_V2_SWAP_TOPIC0: "Uniswap V2 (o fork compatible)",
}

# --------------------------------------------------------------------------
# ERC-4337 — direcciones CANONICAS (desplegadas de forma deterministica,
# identicas en cualquier chain EVM que las tenga desplegadas). Confirmado
# via busqueda web. Robinhood Chain anuncia soporte "de primera clase" para
# ERC-4337 (docs.robinhood.com/chain/account-abstraction/), pero no se
# confirmo por consulta RPC directa en este sandbox que estas direcciones
# especificas ya esten desplegadas en Robinhood Chain — se usan solo para
# anotar en `notes` cuando aparecen, nunca para bloquear la clasificacion.
# --------------------------------------------------------------------------
ENTRYPOINT_ADDRESSES: Dict[str, str] = {
    "0x5ff137d4b0fdcd49dca30c7cf57e578a026d2789": "ERC-4337 EntryPoint v0.6",
    "0x0000000071727de22e5e9d8baf0edac6f37da032": "ERC-4337 EntryPoint v0.7",
}

# --------------------------------------------------------------------------
# Quote assets — identificados por SIMBOLO (ver docstring del modulo:
# decision deliberada de no hardcodear direcciones de contrato que no
# pude confirmar con la misma solidez que en Solana).
# --------------------------------------------------------------------------
QUOTE_SYMBOLS: Set[str] = {"ETH", "WETH", "USDG", "USDC", "USDT"}
STABLE_SYMBOLS: Set[str] = {"USDG", "USDC", "USDT"}  # ~1:1 con USD (aproximacion)

RENT_NOISE_WEI_THRESHOLD = 0  # EVM no tiene "rent" como Solana; ver docstring.


@dataclass
class ResolvedToken:
    symbol: Optional[str]
    decimals: Optional[int]


def _default_resolver(_address: str) -> ResolvedToken:
    """Resolver "nulo": no intenta ninguna llamada de red. Se usa en modo
    offline/fixtures, donde el propio fixture ya trae symbol/decimals
    resueltos de antemano (ver tests/fixtures/evm/README.md)."""
    return ResolvedToken(symbol=None, decimals=None)


TokenResolver = Callable[[str], ResolvedToken]


# --------------------------------------------------------------------------
# Resolucion de symbol()/decimals() via eth_call (solo lectura, RPC
# estandar de cualquier nodo EVM; no requiere API key para el RPC publico).
# --------------------------------------------------------------------------
def make_rpc_token_resolver(rpc_url: str = ROBINHOOD_RPC_HTTP, timeout: float = 10.0) -> TokenResolver:
    """Devuelve un TokenResolver que consulta symbol()/decimals() en vivo
    contra un RPC EVM real via eth_call. Selectors ERC-20 estandar:
      symbol()   -> 0x95d89b41
      decimals() -> 0x313ce567
    (Ambos son parte de la interfaz ERC-20 estandar, no especificos de
    Robinhood Chain.)
    """

    def _eth_call(to: str, data: str) -> Optional[str]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_call",
            "params": [{"to": to, "data": data}, "latest"],
        }
        req = urllib.request.Request(
            rpc_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None
        if "error" in body:
            return None
        return body.get("result")

    def _decode_abi_string(hex_result: str) -> Optional[str]:
        """Decodifica el retorno ABI de un string dinamico (formato
        estandar: offset[32B] + length[32B] + bytes, padded)."""
        try:
            raw = bytes.fromhex(hex_result[2:])
            if len(raw) < 64:
                return None
            length = int.from_bytes(raw[32:64], "big")
            data = raw[64:64 + length]
            return data.decode("utf-8", errors="strict")
        except Exception:
            return None

    def resolver(address: str) -> ResolvedToken:
        symbol = None
        decimals = None

        sym_result = _eth_call(address, "0x95d89b41")
        if sym_result and sym_result not in ("0x", "0x0"):
            symbol = _decode_abi_string(sym_result)

        dec_result = _eth_call(address, "0x313ce567")
        if dec_result and dec_result not in ("0x", "0x0"):
            try:
                decimals = int(dec_result, 16)
            except ValueError:
                decimals = None

        return ResolvedToken(symbol=symbol, decimals=decimals)

    return resolver


# --------------------------------------------------------------------------
# Obtencion de transaccion/receipt via RPC publico (best-effort; no
# ejercitado en vivo en este sandbox — misma limitacion que Solana).
# --------------------------------------------------------------------------
def _rpc_call(method: str, params: list, rpc_url: str, timeout: float = 15.0) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    req = urllib.request.Request(
        rpc_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if "error" in body:
        raise RuntimeError(f"RPC error ({method}): {body['error']}")
    return body.get("result")


def fetch_transaction_and_receipt(
    tx_hash: str, rpc_url: str = ROBINHOOD_RPC_HTTP
) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[str]]:
    """getTransaction + getTransactionReceipt + timestamp del bloque.
    Documentado en https://ethereum.org/en/developers/docs/apis/json-rpc/
    (metodos estandar, no especificos de Robinhood Chain)."""
    tx = _rpc_call("eth_getTransactionByHash", [tx_hash], rpc_url)
    if tx is None:
        raise RuntimeError(f"eth_getTransactionByHash devolvio null para {tx_hash}")
    receipt = _rpc_call("eth_getTransactionReceipt", [tx_hash], rpc_url)
    if receipt is None:
        raise RuntimeError(f"eth_getTransactionReceipt devolvio null para {tx_hash}")

    timestamp = None
    block_number = tx.get("blockNumber")
    if block_number:
        block = _rpc_call("eth_getBlockByNumber", [block_number, False], rpc_url)
        if block and block.get("timestamp"):
            ts_int = int(block["timestamp"], 16)
            timestamp = datetime.fromtimestamp(ts_int, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return tx, receipt, timestamp


# --------------------------------------------------------------------------
# Decodificacion de logs Transfer
# --------------------------------------------------------------------------
def _topic_to_address(topic: str) -> str:
    """Un topic indexado de tipo address viene left-padded a 32 bytes."""
    return "0x" + topic[-40:]


def _decode_transfer_log(log: Dict[str, Any]) -> Optional[Tuple[str, str, str, int]]:
    """Devuelve (token_address, from_addr, to_addr, raw_value) si el log es
    un evento Transfer(address,address,uint256) estandar; None si no."""
    topics = log.get("topics") or []
    if not topics or topics[0].lower() != TRANSFER_EVENT_TOPIC0:
        return None
    if len(topics) < 3:
        return None  # Transfer no estandar (ej. ERC-721 con distinto indexado) -- no se interpreta
    from_addr = _topic_to_address(topics[1])
    to_addr = _topic_to_address(topics[2])
    data = log.get("data", "0x")
    try:
        raw_value = int(data, 16) if data not in ("0x", "") else 0
    except ValueError:
        return None
    return (log["address"].lower(), from_addr.lower(), to_addr.lower(), raw_value)


def _ui_amount(raw_value: int, decimals: Optional[int]) -> Decimal:
    """Convierte un monto entero (wei-like) a unidades UI. Si no se pudo
    resolver `decimals`, se asume 18 (el default de facto en EVM) pero se
    marca explicitamente como asuncion de baja confianza en el resultado
    (ver `_token_deltas_for_owner`)."""
    d = decimals if decimals is not None else 18
    try:
        return Decimal(raw_value) / (Decimal(10) ** d)
    except InvalidOperation:
        return Decimal(0)


def _token_deltas_for_owner(
    receipt: Dict[str, Any], owner: str, resolver: TokenResolver
) -> Tuple[Dict[str, Decimal], Dict[str, ResolvedToken], List[str]]:
    """Recorre receipt.logs, decodifica los Transfer relevantes para
    `owner`, y devuelve:
      - deltas: {token_address: delta_ui}  (positivo=entro, negativo=salio)
      - resolved: {token_address: ResolvedToken(symbol, decimals)}
      - unresolved_decimals: lista de tokens donde se asumio 18 decimales
        a falta de poder resolverlos (transparencia, no se oculta la
        asuncion).
    """
    owner = owner.lower()
    deltas: Dict[str, Decimal] = {}
    resolved: Dict[str, ResolvedToken] = {}
    unresolved_decimals: List[str] = []

    for log in receipt.get("logs", []):
        decoded = _decode_transfer_log(log)
        if decoded is None:
            continue
        token, from_addr, to_addr, raw_value = decoded
        if owner not in (from_addr, to_addr):
            continue

        if token not in resolved:
            resolved[token] = resolver(token)
            if resolved[token].decimals is None:
                unresolved_decimals.append(token)

        ui_value = _ui_amount(raw_value, resolved[token].decimals)

        delta = Decimal(0)
        if to_addr == owner:
            delta += ui_value
        if from_addr == owner:
            delta -= ui_value
        # (from==to==owner es un auto-transfer neto cero; delta ya lo refleja)

        deltas[token] = deltas.get(token, Decimal(0)) + delta

    return {k: v for k, v in deltas.items() if v != 0}, resolved, unresolved_decimals


def _collect_protocol_and_notes(
    receipt: Dict[str, Any],
) -> Tuple[Optional[str], List[str], List[str]]:
    """Detecta protocolo (por topic0 de Swap conocido) y menciones de
    ERC-4337 EntryPoint, sin depender de direcciones de router."""
    contracts_seen: List[str] = []
    protocol: Optional[str] = None
    extra_notes: List[str] = []

    addresses_touched = {log["address"].lower() for log in receipt.get("logs", [])}
    for addr in addresses_touched:
        if addr in ENTRYPOINT_ADDRESSES:
            extra_notes.append(
                f"la transaccion involucra el contrato {ENTRYPOINT_ADDRESSES[addr]} "
                "(probablemente enviada como ERC-4337 UserOperation, no como tx EOA directa)."
            )
            contracts_seen.append(addr)

    for log in receipt.get("logs", []):
        topics = log.get("topics") or []
        if not topics:
            continue
        topic0 = topics[0].lower()
        if topic0 in KNOWN_EVENT_SIGNATURES:
            contracts_seen.append(log["address"].lower())
            if protocol is None:
                protocol = KNOWN_EVENT_SIGNATURES[topic0]

    return protocol, contracts_seen, extra_notes


# --------------------------------------------------------------------------
# Precio / USD
# --------------------------------------------------------------------------
def _usd_value_of_leg(
    symbol: Optional[str], amount: Decimal, native_usd_price: Optional[float]
) -> Optional[Decimal]:
    if symbol in STABLE_SYMBOLS:
        return amount
    if symbol in ("ETH", "WETH") and native_usd_price is not None:
        return amount * Decimal(str(native_usd_price))
    return None


def _estimate_price(
    action: str,
    in_symbol: Optional[str],
    in_addr: str,
    in_amount: Decimal,
    out_symbol: Optional[str],
    out_addr: str,
    out_amount: Decimal,
    native_usd_price: Optional[float],
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    usd_in = _usd_value_of_leg(in_symbol, in_amount, native_usd_price)
    usd_out = _usd_value_of_leg(out_symbol, out_amount, native_usd_price)
    usd_value = usd_in if usd_in is not None else usd_out

    price: Optional[Decimal] = None
    unit: Optional[str] = None

    def label(symbol: Optional[str], addr: str) -> str:
        return symbol or (addr[:8] + "…")

    if action == "BUY" and out_amount != 0:
        price = in_amount / out_amount
        unit = label(in_symbol, in_addr)
    elif action == "SELL" and in_amount != 0:
        price = out_amount / in_amount
        unit = label(out_symbol, out_addr)
    elif action == "SWAP" and in_amount != 0:
        price = out_amount / in_amount
        unit = f"{label(out_symbol, out_addr)}/{label(in_symbol, in_addr)}"

    return (
        float(price) if price is not None else None,
        float(usd_value) if usd_value is not None else None,
        unit,
    )


# --------------------------------------------------------------------------
# Orquestador principal
# --------------------------------------------------------------------------
def interpret_transaction(
    tx: Dict[str, Any],
    receipt: Dict[str, Any],
    wallet: str,
    block_timestamp: Optional[str] = None,
    native_usd_price: Optional[float] = None,
    resolver: Optional[TokenResolver] = None,
) -> NormalizedTrade:
    """Interpreta una transaccion EVM ya descargada (tx + receipt) desde el
    punto de vista de `wallet`. `resolver` resuelve symbol()/decimals() de
    tokens desconocidos; por defecto no hace ninguna llamada de red (modo
    offline) — pasar `make_rpc_token_resolver(rpc_url)` para resolucion en
    vivo."""
    resolver = resolver or _default_resolver
    wallet = wallet.lower()
    tx_hash = receipt.get("transactionHash") or tx.get("hash")

    def unknown(confidence: float, notes: str, protocol: Optional[str] = None,
                programs_seen: Optional[List[str]] = None) -> NormalizedTrade:
        return NormalizedTrade(
            chain=CHAIN_NAME, wallet=wallet, signature=tx_hash, timestamp=block_timestamp,
            action="UNKNOWN", token_in=None, token_in_symbol=None, token_in_amount=None,
            token_out=None, token_out_symbol=None, token_out_amount=None,
            price=None, usd_value=None, protocol=protocol, confidence=confidence,
            notes=notes, programs_seen=programs_seen or [],
        )

    status = receipt.get("status")
    if status is not None and int(status, 16) == 0:
        return unknown(0.0, "La transaccion revirtio on-chain (receipt.status=0x0); no representa una operacion ejecutada con exito.")

    protocol, contracts_seen, extra_notes = _collect_protocol_and_notes(receipt)

    token_deltas, resolved, unresolved_decimals = _token_deltas_for_owner(receipt, wallet, resolver)

    legs: Dict[str, Decimal] = dict(token_deltas)
    leg_symbols: Dict[str, Optional[str]] = {addr: resolved[addr].symbol for addr in token_deltas}

    # Pata nativa: solo se detecta "ETH enviado por la wallet como parte de
    # la llamada" (tx.value cuando wallet es la firmante) -- ver limitacion
    # documentada en el docstring del modulo sobre ETH nativo RECIBIDO.
    if tx.get("from", "").lower() == wallet:
        try:
            native_value = int(tx.get("value", "0x0"), 16)
        except ValueError:
            native_value = 0
        if native_value > 0:
            legs[NATIVE_ETH_PSEUDO] = legs.get(NATIVE_ETH_PSEUDO, Decimal(0)) - (
                Decimal(native_value) / Decimal(10**18)
            )
            leg_symbols[NATIVE_ETH_PSEUDO] = "ETH"

    outflows = {a: -d for a, d in legs.items() if d < 0}
    inflows = {a: d for a, d in legs.items() if d > 0}
    n_out, n_in = len(outflows), len(inflows)

    if n_out == 0 and n_in == 0:
        return unknown(0.0, "Sin cambios de balance relevantes para esta wallet.", protocol, contracts_seen)

    if n_out + n_in == 1:
        return unknown(
            0.15,
            "Solo un activo cambio de balance para esta wallet: parece una transferencia "
            "simple (o ETH nativo recibido al vender, que este modulo NO detecta todavia -- "
            "ver limitacion documentada), no un swap de dos patas.",
            protocol, contracts_seen,
        )

    if not (n_out == 1 and n_in == 1):
        return unknown(
            0.25,
            f"Se detectaron {n_out} salida(s) y {n_in} entrada(s) de activos distintos "
            "(posible ruta multi-hop). No se adivina cual par es la operacion principal.",
            protocol, contracts_seen,
        )

    in_addr = next(iter(outflows))
    out_addr = next(iter(inflows))
    in_amount = outflows[in_addr]
    out_amount = inflows[out_addr]
    in_symbol = leg_symbols.get(in_addr)
    out_symbol = leg_symbols.get(out_addr)

    in_is_quote = in_symbol in QUOTE_SYMBOLS
    out_is_quote = out_symbol in QUOTE_SYMBOLS

    if in_is_quote and not out_is_quote:
        action = "BUY"
        base_confidence = 0.90  # 0.05 menos que Solana: aqui la deteccion de "quote" depende
        # de haber podido resolver el symbol() del token, un paso adicional que en Solana no existe.
    elif out_is_quote and not in_is_quote:
        action = "SELL"
        base_confidence = 0.90
    else:
        action = "SWAP"
        base_confidence = 0.75

    confidence = base_confidence
    notes_parts = list(extra_notes)
    if protocol is None:
        confidence -= 0.30
        notes_parts.append(
            "no se encontro ningun evento Swap conocido (Uniswap V2/V3) en los logs; "
            "la clasificacion se basa solo en transferencias ERC-20, no se confirmo el venue."
        )
    if in_symbol is None and in_addr != NATIVE_ETH_PSEUDO:
        confidence -= 0.10
        notes_parts.append(f"no se pudo resolver symbol() del token de entrada ({in_addr}).")
    if out_symbol is None and out_addr != NATIVE_ETH_PSEUDO:
        confidence -= 0.10
        notes_parts.append(f"no se pudo resolver symbol() del token de salida ({out_addr}).")
    if in_addr in unresolved_decimals or out_addr in unresolved_decimals:
        confidence -= 0.05
        notes_parts.append(
            "no se pudo resolver decimals() de al menos un token; se asumio 18 (default de "
            "facto en EVM, no confirmado para ese contrato especifico)."
        )
    confidence = max(0.0, min(1.0, confidence))

    price, usd_value, price_unit = _estimate_price(
        action, in_symbol, in_addr, in_amount, out_symbol, out_addr, out_amount, native_usd_price
    )
    if usd_value is None:
        notes_parts.append(
            "no se pudo estimar el valor en USD: ninguna de las dos patas es un stablecoin "
            "reconocido y no se proveyo un precio ETH/USD externo (native_usd_price)."
        )

    return NormalizedTrade(
        chain=CHAIN_NAME,
        wallet=wallet,
        signature=tx_hash,
        timestamp=block_timestamp,
        action=action,
        token_in=in_addr,
        token_in_symbol=in_symbol,
        token_in_amount=float(in_amount),
        token_out=out_addr,
        token_out_symbol=out_symbol,
        token_out_amount=float(out_amount),
        price=price,
        usd_value=usd_value,
        protocol=protocol,
        confidence=confidence,
        price_unit=price_unit,
        notes="; ".join(notes_parts),
        programs_seen=contracts_seen,
    )


def interpret_tx_hash(
    tx_hash: str,
    wallet: str,
    rpc_url: str = ROBINHOOD_RPC_HTTP,
    native_usd_price: Optional[float] = None,
    resolve_symbols_live: bool = True,
) -> NormalizedTrade:
    """Punto de entrada pensado para conectarse desde un chain adapter:
    dado un hash de transaccion nuevo detectado, descarga tx+receipt y lo
    interpreta. Solo lectura; mismo RPC publico, sin credenciales propias."""
    tx, receipt, timestamp = fetch_transaction_and_receipt(tx_hash, rpc_url=rpc_url)
    resolver = make_rpc_token_resolver(rpc_url) if resolve_symbols_live else _default_resolver
    return interpret_transaction(
        tx, receipt, wallet, block_timestamp=timestamp,
        native_usd_price=native_usd_price, resolver=resolver,
    )
