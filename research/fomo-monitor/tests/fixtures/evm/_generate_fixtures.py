#!/usr/bin/env python3
"""
Script de generacion (no es parte del runtime): construye los fixtures
JSON de tests/fixtures/evm/ con direcciones/topics EVM garantizadamente
bien formados (20 bytes / 40 hex chars para direcciones, 32 bytes / 64 hex
chars para topics), en vez de escribirlos a mano con riesgo de errores de
conteo de caracteres. Se deja en el repo para que quien reemplace estos
fixtures por datos reales tenga la misma utilidad de construccion
disponible. No se ejecuta como parte de los tests ni del runtime.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

TRANSFER_TOPIC0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
UNIV3_SWAP_TOPIC0 = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
UNIV2_SWAP_TOPIC0 = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
ENTRYPOINT_V07 = "0x0000000071727de22e5e9d8baf0edac6f37da032"


def addr(seed: str) -> str:
    """Direccion EVM valida (20 bytes) a partir de una semilla legible."""
    seed_hex = seed.encode("utf-8").hex()
    body = (seed_hex * 5)[:40]
    return "0x" + body


def topic_from_address(address: str) -> str:
    hex_part = address[2:].lower()
    return "0x" + hex_part.rjust(64, "0")


def amount_topic_data(raw_value: int) -> str:
    return "0x" + format(raw_value, "x").rjust(64, "0")


WALLET_V3_BUYER = addr("wallet-v3-buyer")
WALLET_V2_SELLER = addr("wallet-v2-seller")
WALLET_ETH_BUYER = addr("wallet-eth-buyer")
WALLET_FAILED = WALLET_V3_BUYER
WALLET_TRANSFER = addr("wallet-transfer")
WALLET_TRANSFER_DEST = addr("wallet-transfer-dest")
WALLET_MULTIHOP = addr("wallet-multihop")
WALLET_USEROP = addr("wallet-userop")

USDG = addr("token-usdg")
WETH = addr("token-weth")
MEME = addr("token-meme")
RESID = addr("token-resid")

POOL_V3 = addr("pool-uniswap-v3")
PAIR_V2 = addr("pair-uniswap-v2")
ROUTER = addr("router-universal")

RAW = {
    "usdg_100": 100 * 10**18,
    "meme_250000": 250000 * 10**18,
    "token_sold_50": 50 * 10**18,
    "weth_received_2": 2 * 10**18,
    "eth_spent_0_5": 5 * 10**17,
    "token_received_750000": 750000 * 10**18,
    "simple_transfer_10": 10 * 10**18,
    "multihop_usdg_200": 200 * 10**18,
    "multihop_tokenA_400000": 400000 * 10**18,
    "multihop_residual": 7 * 10**14,
    "userop_usdg_60": 60 * 10**18,
    "userop_out_1200": 1200 * 10**18,
}


def transfer_log(token: str, from_addr: str, to_addr: str, raw_value: int) -> dict:
    return {
        "address": token,
        "topics": [TRANSFER_TOPIC0, topic_from_address(from_addr), topic_from_address(to_addr)],
        "data": amount_topic_data(raw_value),
    }


def swap_log(pool: str, topic0: str, sender: str, recipient: str, placeholder_data: str) -> dict:
    return {
        "address": pool,
        "topics": [topic0, topic_from_address(sender), topic_from_address(recipient)],
        "data": placeholder_data,
    }


def write_fixture(filename: str, tx: dict, receipt: dict, block_timestamp: str, notes: str) -> None:
    out = {
        "tx": tx,
        "receipt": receipt,
        "block_timestamp": block_timestamp,
        "_fixture_notes": notes,
    }
    (HERE / filename).write_text(json.dumps(out, indent=2) + "\n")
    print("wrote", filename)


def make_tx(tx_hash: str, sender: str, to: str, value_wei: int, block_number_hex: str) -> dict:
    return {
        "hash": tx_hash,
        "from": sender,
        "to": to,
        "value": hex(value_wei),
        "blockNumber": block_number_hex,
        "nonce": "0x1",
        "input": "0xDemoCalldataNotDecodedByThisModule",
    }


def make_receipt(tx_hash: str, status_hex: str, block_number_hex: str, logs: list) -> dict:
    return {
        "transactionHash": tx_hash,
        "status": status_hex,
        "blockNumber": block_number_hex,
        "logs": logs,
    }


# 1) Uniswap V3 BUY: USDG -> MEME
tx_hash = "0x" + "a1" * 32
tx = make_tx(tx_hash, WALLET_V3_BUYER, ROUTER, 0, "0x64")
receipt = make_receipt(tx_hash, "0x1", "0x64", [
    transfer_log(USDG, WALLET_V3_BUYER, POOL_V3, RAW["usdg_100"]),
    transfer_log(MEME, POOL_V3, WALLET_V3_BUYER, RAW["meme_250000"]),
    swap_log(POOL_V3, UNIV3_SWAP_TOPIC0, ROUTER, WALLET_V3_BUYER, "0xDemoUndecodedUniswapV3SwapEventData"),
])
write_fixture(
    "uniswap_v3_buy_usdg_to_token.json", tx, receipt, "2026-08-10T10:00:00Z",
    "SINTETICO (ver README.md). Wallet gasta 100 USDG (18 decimales) para comprar 250000 "
    "unidades de un memecoin via un pool de Uniswap V3 (identificado por el topic0 del "
    "evento Swap emitido por el propio pool, direccion-agnostico). tx.value=0 porque el "
    "pago fue en USDG (ERC-20), no en ETH nativo. Resultado esperado: action=BUY, "
    "protocol='Uniswap V3 (o fork compatible)', confidence alta (~0.90).",
)

# 2) Uniswap V2 SELL: MEME -> WETH
tx_hash = "0x" + "b2" * 32
tx = make_tx(tx_hash, WALLET_V2_SELLER, ROUTER, 0, "0x65")
receipt = make_receipt(tx_hash, "0x1", "0x65", [
    transfer_log(MEME, WALLET_V2_SELLER, PAIR_V2, RAW["token_sold_50"]),
    transfer_log(WETH, PAIR_V2, WALLET_V2_SELLER, RAW["weth_received_2"]),
    swap_log(PAIR_V2, UNIV2_SWAP_TOPIC0, ROUTER, WALLET_V2_SELLER, "0xDemoUndecodedUniswapV2SwapEventData"),
])
write_fixture(
    "uniswap_v2_sell_token_to_weth.json", tx, receipt, "2026-08-10T11:00:00Z",
    "SINTETICO (ver README.md). Wallet vende 50 unidades de un memecoin (18 decimales) "
    "directamente en un pool de Uniswap V2 y recibe 2 WETH. tx.value=0 (swap ERC20-a-ERC20; "
    "el WETH recibido sigue siendo WETH, no se desenvuelve a ETH nativo). Resultado esperado: "
    "action=SELL, token_in=memecoin(50), token_out=WETH(2), "
    "protocol='Uniswap V2 (o fork compatible)', confidence ~0.90.",
)

# 3) BUY con ETH nativo via tx.value
tx_hash = "0x" + "c3" * 32
tx = make_tx(tx_hash, WALLET_ETH_BUYER, ROUTER, RAW["eth_spent_0_5"], "0x66")
receipt = make_receipt(tx_hash, "0x1", "0x66", [
    transfer_log(MEME, POOL_V3, WALLET_ETH_BUYER, RAW["token_received_750000"]),
    swap_log(POOL_V3, UNIV3_SWAP_TOPIC0, ROUTER, WALLET_ETH_BUYER, "0xDemoUndecodedUniswapV3SwapEventDataETH"),
])
write_fixture(
    "buy_with_native_eth.json", tx, receipt, "2026-08-10T12:00:00Z",
    "SINTETICO (ver README.md). Wallet envia 0.5 ETH nativo directamente en tx.value al "
    "router (funcion tipo 'exactInputSingle' pagable), el router lo envuelve a WETH "
    "internamente (sin emitir Transfer visible de WETH desde la wallet) y el pool entrega "
    "750000 unidades de un memecoin. Unica pata de salida detectable: ETH nativo via "
    "tx.value (NATIVE_ETH_PSEUDO). Resultado esperado: action=BUY, "
    "token_in=NATIVE(0.5 ETH), token_out=memecoin(750000), "
    "protocol='Uniswap V3 (o fork compatible)'. Ejercita la deteccion de ETH nativo "
    "GASTADO via tx.value -- ver limitacion sobre ETH nativo RECIBIDO (no cubierta).",
)

# 4) Transaccion fallida
tx_hash = "0x" + "d4" * 32
tx = make_tx(tx_hash, WALLET_FAILED, ROUTER, 0, "0x67")
receipt = make_receipt(tx_hash, "0x0", "0x67", [])
write_fixture(
    "failed_tx.json", tx, receipt, "2026-08-10T13:00:00Z",
    "SINTETICO (ver README.md). La transaccion revirtio on-chain (receipt.status=0x0, "
    "tipico de un swap que fallo por slippage/deadline). Sin logs de Transfer. "
    "Resultado esperado: action=UNKNOWN, confidence=0.0.",
)

# 5) Transferencia ERC-20 simple (no swap)
tx_hash = "0x" + "e5" * 32
tx = make_tx(tx_hash, WALLET_TRANSFER, USDG, 0, "0x68")
receipt = make_receipt(tx_hash, "0x1", "0x68", [
    transfer_log(USDG, WALLET_TRANSFER, WALLET_TRANSFER_DEST, RAW["simple_transfer_10"]),
])
write_fixture(
    "simple_erc20_transfer.json", tx, receipt, "2026-08-10T14:00:00Z",
    "SINTETICO (ver README.md). Transferencia ERC-20 simple de 10 USDG a otra direccion "
    "(no un router/pool conocido), sin ningun evento Swap en los logs. Unica pata: USDG "
    "saliente. Resultado esperado: action=UNKNOWN (una sola pata, parece transferencia, "
    "no swap), confidence=0.15, protocol=None.",
)

# 6) Multi-hop ambiguo (1 salida + 2 entradas)
tx_hash = "0x" + "f6" * 32
tx = make_tx(tx_hash, WALLET_MULTIHOP, ROUTER, 0, "0x69")
receipt = make_receipt(tx_hash, "0x1", "0x69", [
    transfer_log(USDG, WALLET_MULTIHOP, POOL_V3, RAW["multihop_usdg_200"]),
    transfer_log(MEME, POOL_V3, WALLET_MULTIHOP, RAW["multihop_tokenA_400000"]),
    transfer_log(RESID, POOL_V3, WALLET_MULTIHOP, RAW["multihop_residual"]),
    swap_log(POOL_V3, UNIV3_SWAP_TOPIC0, ROUTER, WALLET_MULTIHOP, "0xDemoUndecodedMultiHopSwapEventData"),
])
write_fixture(
    "multihop_ambiguous.json", tx, receipt, "2026-08-10T15:00:00Z",
    "SINTETICO (ver README.md). La wallet gasta 200 USDG y recibe DOS tokens distintos "
    "(400000 del token 'objetivo' y un residual minusculo de 0.0007 de otro token "
    "intermedio, tipico de rounding en rutas multi-hop). 1 salida + 2 entradas = 3 patas "
    "netas. Resultado esperado: action=UNKNOWN, confidence=0.25, "
    "protocol='Uniswap V3 (o fork compatible)'.",
)

# 7) ERC-4337 UserOperation BUY (con symbol de salida sin resolver)
tx_hash = "0x" + "17" * 32
tx = make_tx(tx_hash, ENTRYPOINT_V07, ENTRYPOINT_V07, 0, "0x6a")
receipt = make_receipt(tx_hash, "0x1", "0x6a", [
    {
        "address": ENTRYPOINT_V07,
        "topics": ["0x" + "ff" * 32, topic_from_address(WALLET_USEROP)],
        "data": "0xDemoUserOperationEventData",
    },
    transfer_log(USDG, WALLET_USEROP, POOL_V3, RAW["userop_usdg_60"]),
    transfer_log(MEME, POOL_V3, WALLET_USEROP, RAW["userop_out_1200"]),
    swap_log(POOL_V3, UNIV3_SWAP_TOPIC0, ROUTER, WALLET_USEROP, "0xDemoUndecodedUniswapV3SwapEventDataUserOp"),
])
write_fixture(
    "erc4337_userop_buy.json", tx, receipt, "2026-08-10T16:00:00Z",
    "SINTETICO (ver README.md). La wallet (smart account ERC-4337) compro un token via "
    "una UserOperation enviada al EntryPoint v0.7 canonico. tx.from/tx.to de nivel superior "
    "son del bundler/EntryPoint, no de la wallet -- la deteccion depende solo de los logs "
    "Transfer donde la wallet aparece como from/to. El topic0 del log del EntryPoint es "
    "un placeholder (0xff...), el codigo NO depende de ese hash para detectarlo (solo mira "
    "log.address). Resultado esperado: action=BUY (60 USDG -> 1200 MEME), "
    "protocol='Uniswap V3 (o fork compatible)', notes menciona 'EntryPoint v0.7'.",
)

manifest = [
    {
        "file": "uniswap_v3_buy_usdg_to_token.json",
        "wallet": WALLET_V3_BUYER,
        "description": "BUY limpio: USDG -> memecoin, Uniswap V3 (pool identificado por topic0 del evento Swap)",
        "expected_action": "BUY",
        "expected_protocol": "Uniswap V3 (o fork compatible)",
        "token_registry": {USDG: {"symbol": "USDG", "decimals": 18}, MEME: {"symbol": "MEME", "decimals": 18}},
    },
    {
        "file": "uniswap_v2_sell_token_to_weth.json",
        "wallet": WALLET_V2_SELLER,
        "description": "SELL limpio: memecoin -> WETH, directo en un pool de Uniswap V2",
        "expected_action": "SELL",
        "expected_protocol": "Uniswap V2 (o fork compatible)",
        "token_registry": {MEME: {"symbol": "MEME", "decimals": 18}, WETH: {"symbol": "WETH", "decimals": 18}},
    },
    {
        "file": "buy_with_native_eth.json",
        "wallet": WALLET_ETH_BUYER,
        "description": "BUY limpio: ETH nativo (via tx.value) -> memecoin, Uniswap V3",
        "expected_action": "BUY",
        "expected_protocol": "Uniswap V3 (o fork compatible)",
        "token_registry": {MEME: {"symbol": "MEME", "decimals": 18}},
    },
    {
        "file": "failed_tx.json",
        "wallet": WALLET_FAILED,
        "description": "Transaccion revertida on-chain (receipt.status=0x0)",
        "expected_action": "UNKNOWN",
        "expected_protocol": None,
        "token_registry": {},
    },
    {
        "file": "simple_erc20_transfer.json",
        "wallet": WALLET_TRANSFER,
        "description": "Transferencia ERC-20 simple, sin evento Swap - no es un swap",
        "expected_action": "UNKNOWN",
        "expected_protocol": None,
        "token_registry": {USDG: {"symbol": "USDG", "decimals": 18}},
    },
    {
        "file": "multihop_ambiguous.json",
        "wallet": WALLET_MULTIHOP,
        "description": "Ruta con residual: 1 salida + 2 entradas, ambiguo",
        "expected_action": "UNKNOWN",
        "expected_protocol": "Uniswap V3 (o fork compatible)",
        "token_registry": {
            USDG: {"symbol": "USDG", "decimals": 18},
            MEME: {"symbol": "MEME", "decimals": 18},
            RESID: {"symbol": "RESID", "decimals": 18},
        },
    },
    {
        "file": "erc4337_userop_buy.json",
        "wallet": WALLET_USEROP,
        "description": "BUY via ERC-4337 UserOperation (EntryPoint v0.7); symbol del token de salida deliberadamente NO resoluble (prueba la penalizacion de confidence)",
        "expected_action": "BUY",
        "expected_protocol": "Uniswap V3 (o fork compatible)",
        "token_registry": {USDG: {"symbol": "USDG", "decimals": 18}},
    },
]
(HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("wrote manifest.json")

print()
print("Direcciones generadas (para referencia / depuracion):")
for name, value in [
    ("WALLET_V3_BUYER", WALLET_V3_BUYER), ("WALLET_V2_SELLER", WALLET_V2_SELLER),
    ("WALLET_ETH_BUYER", WALLET_ETH_BUYER), ("WALLET_TRANSFER", WALLET_TRANSFER),
    ("WALLET_MULTIHOP", WALLET_MULTIHOP), ("WALLET_USEROP", WALLET_USEROP),
    ("USDG", USDG), ("WETH", WETH), ("MEME", MEME), ("RESID", RESID),
    ("POOL_V3", POOL_V3), ("PAIR_V2", PAIR_V2), ("ROUTER", ROUTER),
]:
    print(f"  {name} = {value}  (len={len(value)-2} hex chars)")
