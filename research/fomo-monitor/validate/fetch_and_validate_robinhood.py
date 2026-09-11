#!/usr/bin/env python3
"""
Fase 4, Pasos 2+3 (Robinhood Chain): descarga transacciones REALES de una
wallet via el RPC publico de Robinhood Chain y las interpreta con el
parser de la Fase 3 (evm_parser.py, sin modificar), mostrando RAW vs
PARSER.

REQUIERE ACCESO REAL A INTERNET (no funciona en el sandbox donde se
construyo este proyecto). Ver validate/README.md y FASE_4_VALIDACION_REAL.md.

SOLO LECTURA. No firma nada, no requiere claves privadas ni API keys.

Uso:
    python validate/fetch_and_validate_robinhood.py <WALLET_0x...>
        [--limit 5] [--lookback-blocks 500000] [--native-usd-price 3000]
        [--rpc-http https://rpc.mainnet.chain.robinhood.com]
        [--json-out validate/out/robinhood_results.json]

Nota sobre --lookback-blocks: a diferencia de Solana (getSignaturesForAddress
indexa por direccion), eth_getLogs de EVM estandar requiere un rango de
bloques explicito -- no hay forma de pedir "todo el historial de esta
wallet" en una sola llamada. Con bloques de ~100ms (documentado para
Robinhood Chain), 500.000 bloques son ~14 horas; ajustar segun que tan
reciente fue la actividad de la wallet elegida.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "prototype"))
from parsers import evm_parser as ep  # noqa: E402  (Fase 3, sin modificar)
from chains import robinhood_adapter as ra  # noqa: E402  (Fase 3, sin modificar)


def _raw_summary(tx: dict, receipt: dict, wallet: str) -> dict:
    """Resumen 'RAW': logs Transfer donde la wallet es from/to, y tx.value
    -- los mismos datos de entrada que usa evm_parser, mostrados sin pasar
    por su logica de clasificacion."""
    wallet_l = wallet.lower()
    transfer_logs = []
    for log in receipt.get("logs", []):
        decoded = ep._decode_transfer_log(log)
        if decoded is None:
            continue
        token, from_addr, to_addr, raw_value = decoded
        if wallet_l in (from_addr, to_addr):
            transfer_logs.append({
                "token_contract": token, "from": from_addr, "to": to_addr,
                "raw_value": raw_value,
            })
    return {
        "tx_hash": receipt.get("transactionHash"),
        "status": receipt.get("status"),
        "tx_from": tx.get("from"),
        "tx_to": tx.get("to"),
        "tx_value_wei": tx.get("value"),
        "transfer_logs_touching_wallet": transfer_logs,
        "all_log_addresses": [log["address"] for log in receipt.get("logs", [])],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wallet")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--lookback-blocks", type=int, default=500_000)
    parser.add_argument("--native-usd-price", type=float, default=None)
    parser.add_argument("--rpc-http", default=ep.ROBINHOOD_RPC_HTTP)
    parser.add_argument("--no-resolve-symbols", action="store_true")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    wallet = args.wallet.lower()
    print(f"=== Fase 4 / Robinhood Chain: descargando actividad real de {wallet} ===")
    print(f"RPC: {args.rpc_http}\n")

    current_block = ra._get_block_number(args.rpc_http)
    from_block = max(0, current_block - args.lookback_blocks)
    print(f"Buscando eventos Transfer entre los bloques {from_block} y {current_block}...")

    tx_to_wallets = ra._get_logs_for_wallets(args.rpc_http, [wallet], from_block, current_block)
    tx_hashes = list(tx_to_wallets.keys())[: args.limit]

    if not tx_hashes:
        print(
            "No se encontraron transferencias ERC-20 para esta wallet en el rango de "
            "bloques indicado. Probar con --lookback-blocks mas grande, o confirmar que "
            "la wallet tuvo actividad reciente en robinhoodchain.blockscout.com."
        )
        sys.exit(1)

    resolver = None if args.no_resolve_symbols else ep.make_rpc_token_resolver(args.rpc_http)
    results = []

    for tx_hash in tx_hashes:
        fetch_start = time.time()
        try:
            tx, receipt, block_timestamp = ep.fetch_transaction_and_receipt(tx_hash, args.rpc_http)
        except Exception as exc:
            print(f"--- {tx_hash} ---\n  [error obteniendo transaccion]: {exc}\n")
            continue
        fetch_ms = (time.time() - fetch_start) * 1000

        raw = _raw_summary(tx, receipt, wallet)
        event = ep.interpret_transaction(
            tx, receipt, wallet, block_timestamp=block_timestamp,
            native_usd_price=args.native_usd_price, resolver=resolver,
        )

        print(f"--- {tx_hash} ---")
        print("RAW:")
        print(json.dumps(raw, indent=2, ensure_ascii=False))
        print("PARSER:")
        print(json.dumps(event.to_dict(), indent=2, ensure_ascii=False))
        print(f"tiempo de RPC (tx+receipt+block+symbols): {fetch_ms:.1f} ms")
        print()

        results.append({"raw": raw, "parsed": event.to_dict(), "rpc_fetch_ms": fetch_ms})

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"Resultados guardados en {out_path}")


if __name__ == "__main__":
    main()
