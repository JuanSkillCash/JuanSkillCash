#!/usr/bin/env python3
"""
chains/robinhood_adapter.py — Chain Adapter de Robinhood Chain (EVM) para
la arquitectura multichain (Fase 3).

SOLO LECTURA. No firma, no envia, ni construye transacciones. No requiere
ni acepta claves privadas. No usa ninguna credencial propia: el RPC por
defecto es el endpoint publico oficial de Robinhood Chain
(rpc.mainnet.chain.robinhood.com), sin API key.

------------------------------------------------------------------------
POR QUE POLLING (eth_getLogs) Y NO eth_subscribe POR DEFECTO
------------------------------------------------------------------------
Investigado y documentado en INFORME_MULTICHAIN.md: el RPC publico
gratuito de Robinhood Chain (HTTP) no tiene garantizado un equivalente
WebSocket sin API key -- los proveedores que SI ofrecen `eth_subscribe`
en Robinhood Chain (Dwellir, QuickNode, Chainstack, etc., segun lo
encontrado via busqueda web) requieren una API key PROPIA del usuario.
Como esta fase no debe usar credenciales, el modo por defecto de este
adapter es **polling con eth_getLogs** contra el RPC publico HTTP, que no
requiere ninguna key. Si el usuario decide mas adelante usar un proveedor
con WSS (con SU PROPIA API key, nunca hardcodeada aqui), puede pasar
`wss_url` a `watch()` para usar `eth_subscribe` en vez de polling -- ver
`watch_via_websocket()`.

------------------------------------------------------------------------
COMO SE DETECTA "ACTIVIDAD NUEVA" DE UNA WALLET
------------------------------------------------------------------------
A diferencia de Solana (`logsSubscribe` con `mentions`), en EVM estandar
no existe un filtro de "todas las transacciones que tocan esta wallet".
Lo mas cercano y ESTANDAR es filtrar logs del evento ERC-20
`Transfer(address,address,uint256)` por posicion de topic:
  - topics=[TRANSFER_TOPIC0, [wallet_topic], null]  -> wallet como emisor
  - topics=[TRANSFER_TOPIC0, null, [wallet_topic]]  -> wallet como receptor
(dos filtros, ejecutados en cada ciclo de polling; JSON-RPC no permite
"OR entre posiciones de topic distintas" en un solo filtro). Esto detecta
cualquier swap que mueva tokens ERC-20 de/hacia la wallet, sin importar el
DEX. NO detecta una operacion que sea 100% en ETH nativo en ambas patas
(no existe tal cosa en un swap real) ni actividad que no emita Transfer
(fuera de alcance para "detectar operaciones de trading").
"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parsers import evm_parser  # noqa: E402
from models.normalized_trade import NormalizedTrade  # noqa: E402

CHAIN_NAME = "robinhood"
DEFAULT_POLL_INTERVAL_SECONDS = 5.0

OnTradeCallback = Callable[[NormalizedTrade], Awaitable[None]]


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}")


def _topic_from_address(address: str) -> str:
    return "0x" + address[2:].lower().rjust(64, "0")


def _rpc_call(method: str, params: list, rpc_url: str, timeout: float = 15.0):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    req = urllib.request.Request(
        rpc_url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if "error" in body:
        raise RuntimeError(f"RPC error ({method}): {body['error']}")
    return body.get("result")


def _get_block_number(rpc_url: str) -> int:
    return int(_rpc_call("eth_blockNumber", [], rpc_url), 16)


def _get_logs_for_wallets(
    rpc_url: str, addresses: List[str], from_block: int, to_block: int
) -> Dict[str, Set[str]]:
    """Devuelve {tx_hash: {wallets que aparecen como from o to en ese tx}}."""
    address_topics = [_topic_from_address(a) for a in addresses]
    tx_to_wallets: Dict[str, Set[str]] = {}

    filters = [
        {"topics": [evm_parser.TRANSFER_EVENT_TOPIC0, address_topics, None]},   # como emisor
        {"topics": [evm_parser.TRANSFER_EVENT_TOPIC0, None, address_topics]},   # como receptor
    ]
    for f in filters:
        params = {
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "topics": f["topics"],
        }
        logs = _rpc_call("eth_getLogs", [params], rpc_url) or []
        for entry in logs:
            tx_hash = entry["transactionHash"]
            topics = entry.get("topics", [])
            touched = set()
            if len(topics) > 1 and topics[1] in address_topics:
                touched.add(evm_parser._topic_to_address(topics[1]))
            if len(topics) > 2 and topics[2] in address_topics:
                touched.add(evm_parser._topic_to_address(topics[2]))
            tx_to_wallets.setdefault(tx_hash, set()).update(touched)

    return tx_to_wallets


async def watch(
    addresses: List[str],
    on_trade: OnTradeCallback,
    rpc_http: str = evm_parser.ROBINHOOD_RPC_HTTP,
    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    native_usd_price: Optional[float] = None,
    resolve_symbols_live: bool = True,
    start_from_current_block: bool = True,
) -> None:
    """Bucle de polling: SOLO LECTURA, sin credenciales. Cada `poll_interval`
    segundos consulta eth_getLogs por rango de bloques nuevo, filtrando
    transferencias ERC-20 que toquen alguna de `addresses`, interpreta cada
    transaccion nueva (parsers.evm_parser) y llama a `on_trade`."""
    addresses = [a.lower() for a in addresses]

    last_block = _get_block_number(rpc_http) if start_from_current_block else 0
    log(f"Conectando (polling HTTP) a RPC publico de Robinhood Chain: {rpc_http}")
    log(f"Bloque inicial: {last_block}. Intervalo de polling: {poll_interval}s.")
    seen_tx_hashes: Set[str] = set()

    while True:
        # Solo los pasos de RED (consultar el RPC) se protegen de forma
        # amplia -- un fallo transitorio del RPC publico no debe tumbar el
        # monitor, se reintenta en el siguiente ciclo. `on_trade` (el
        # callback del que llama) se invoca FUERA de este try/except: si el
        # llamador quiere detener el monitor lanzando una excepcion desde su
        # callback, o tiene un bug en su propio codigo de alerta, eso no
        # debe quedar silenciosamente tragado como si fuera "un RPC caido".
        new_events = []
        try:
            current_block = _get_block_number(rpc_http)
            if current_block > last_block:
                tx_to_wallets = _get_logs_for_wallets(rpc_http, addresses, last_block + 1, current_block)
                for tx_hash, wallets in tx_to_wallets.items():
                    if tx_hash in seen_tx_hashes:
                        continue
                    seen_tx_hashes.add(tx_hash)
                    for wallet in wallets:
                        try:
                            trade = evm_parser.interpret_tx_hash(
                                tx_hash, wallet, rpc_url=rpc_http,
                                native_usd_price=native_usd_price,
                                resolve_symbols_live=resolve_symbols_live,
                            )
                        except Exception as exc:
                            log(f"  [interpretacion fallida] {wallet} / {tx_hash}: {exc}")
                            continue
                        new_events.append(trade)
                last_block = current_block
        except Exception as exc:
            log(f"  [polling] error consultando RPC, se reintenta en el proximo ciclo: {exc}")

        for trade in new_events:
            await on_trade(trade)

        await asyncio.sleep(poll_interval)


async def watch_via_websocket(
    addresses: List[str],
    on_trade: OnTradeCallback,
    wss_url: str,
    rpc_http: str = evm_parser.ROBINHOOD_RPC_HTTP,
    native_usd_price: Optional[float] = None,
    resolve_symbols_live: bool = True,
) -> None:
    """Modo alternativo con `eth_subscribe` (logs) via WebSocket, para
    cuando el usuario tiene su PROPIO proveedor de RPC con soporte WSS
    (Dwellir/QuickNode/Chainstack/etc. con su propia API key en `wss_url`
    -- esta funcion nunca genera ni almacena esa key, solo la recibe como
    parametro de conexion). Requiere `pip install websockets` (misma
    dependencia que wallet_monitor.py)."""
    try:
        import websockets
    except ImportError:
        raise RuntimeError("Falta la dependencia 'websockets'. Instala con: pip install websockets")

    addresses = [a.lower() for a in addresses]
    address_topics = [_topic_from_address(a) for a in addresses]
    resolver = evm_parser.make_rpc_token_resolver(rpc_http) if resolve_symbols_live else None

    log(f"Conectando (WebSocket) a {wss_url}")
    async with websockets.connect(wss_url, ping_interval=20, ping_timeout=20) as ws:
        for topics in (
            [evm_parser.TRANSFER_EVENT_TOPIC0, address_topics, None],
            [evm_parser.TRANSFER_EVENT_TOPIC0, None, address_topics],
        ):
            req = {
                "jsonrpc": "2.0", "id": 1, "method": "eth_subscribe",
                "params": ["logs", {"topics": topics}],
            }
            await ws.send(json.dumps(req))
        log("Suscripciones enviadas (Transfer como emisor / como receptor).")

        seen_tx_hashes: Set[str] = set()
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("method") != "eth_subscription":
                continue
            entry = msg["params"]["result"]
            tx_hash = entry["transactionHash"]
            topics = entry.get("topics", [])
            touched = set()
            if len(topics) > 1 and topics[1] in address_topics:
                touched.add(evm_parser._topic_to_address(topics[1]))
            if len(topics) > 2 and topics[2] in address_topics:
                touched.add(evm_parser._topic_to_address(topics[2]))
            if tx_hash in seen_tx_hashes or not touched:
                continue
            seen_tx_hashes.add(tx_hash)
            for wallet in touched:
                try:
                    tx, receipt, ts = evm_parser.fetch_transaction_and_receipt(tx_hash, rpc_http)
                    trade = evm_parser.interpret_transaction(
                        tx, receipt, wallet, block_timestamp=ts,
                        native_usd_price=native_usd_price, resolver=resolver,
                    )
                except Exception as exc:
                    log(f"  [interpretacion fallida] {wallet} / {tx_hash}: {exc}")
                    continue
                await on_trade(trade)


async def _print_alert(trade: NormalizedTrade) -> None:
    log("  === ALERTA (interpretacion) ===")
    for line in trade.human_readable().splitlines():
        log(f"  {line}")
    log("")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Monitor de solo lectura para wallets en Robinhood Chain (polling eth_getLogs, sin credenciales)."
    )
    parser.add_argument("addresses", nargs="+", help="Direcciones 0x... a observar")
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL_SECONDS)
    parser.add_argument("--native-usd-price", type=float, default=None)
    parser.add_argument("--rpc-http", default=evm_parser.ROBINHOOD_RPC_HTTP)
    parser.add_argument("--no-resolve-symbols", action="store_true")
    args = parser.parse_args()

    log("=== Monitor de solo lectura (RPC publico de Robinhood Chain) ===")
    log("Este proceso NO ejecuta operaciones ni requiere credenciales.")
    log(f"Wallets a observar: {', '.join(args.addresses)}")

    try:
        asyncio.run(
            watch(
                args.addresses, _print_alert, rpc_http=args.rpc_http,
                poll_interval=args.poll_interval, native_usd_price=args.native_usd_price,
                resolve_symbols_live=not args.no_resolve_symbols,
            )
        )
    except KeyboardInterrupt:
        log("Detenido por el usuario.")


if __name__ == "__main__":
    main()
