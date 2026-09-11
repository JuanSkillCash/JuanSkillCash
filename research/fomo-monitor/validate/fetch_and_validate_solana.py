#!/usr/bin/env python3
"""
Fase 4, Pasos 2+3 (Solana): descarga transacciones REALES de una wallet
via el RPC publico de Solana y las interpreta con el parser de la Fase 2
(transaction_parser.py, sin modificar), mostrando RAW vs PARSER.

REQUIERE ACCESO REAL A INTERNET (no funciona en el sandbox donde se
construyo este proyecto). Ver validate/README.md y FASE_4_VALIDACION_REAL.md.

SOLO LECTURA. No firma nada, no requiere claves privadas ni API keys.

Uso:
    python validate/fetch_and_validate_solana.py <WALLET> [--limit 5]
        [--sol-usd-price 150] [--rpc-http https://api.mainnet-beta.solana.com]
        [--json-out validate/out/solana_results.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "prototype"))
import transaction_parser as tp  # noqa: E402  (Fase 2, sin modificar)


def _rpc_call(method: str, params: list, rpc_url: str, timeout: float = 20.0) -> Any:
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


def fetch_recent_signatures(wallet: str, limit: int, rpc_url: str) -> List[Dict[str, Any]]:
    """getSignaturesForAddress -- documentado en
    https://solana.com/docs/rpc/http/getsignaturesforaddress ; devuelve
    las firmas mas recientes primero, sin necesitar el 1000-tx limit para
    un `limit` chico como el que usamos aqui."""
    return _rpc_call("getSignaturesForAddress", [wallet, {"limit": limit}], rpc_url) or []


def _raw_summary(tx: Dict[str, Any], wallet: str) -> Dict[str, Any]:
    """Resumen 'RAW' (datos crudos de la respuesta RPC, sin la logica de
    clasificacion del parser) para comparar lado a lado con el resultado
    interpretado. Reutiliza los helpers de resolucion de cuentas de
    transaction_parser.py (misma fuente de verdad que usa el parser real),
    pero NO reutiliza su logica de clasificacion -- eso es justamente lo
    que se esta validando."""
    meta = tx.get("meta") or {}
    account_keys = tp._resolve_account_keys(tx)
    try:
        wallet_idx = account_keys.index(wallet)
    except ValueError:
        wallet_idx = None

    token_balance_changes = []
    for pre in meta.get("preTokenBalances") or []:
        if pre.get("owner") != wallet:
            continue
        post = next(
            (p for p in (meta.get("postTokenBalances") or [])
             if p.get("accountIndex") == pre.get("accountIndex")),
            None,
        )
        token_balance_changes.append({
            "mint": pre.get("mint"),
            "pre_amount": pre.get("uiTokenAmount", {}).get("uiAmountString"),
            "post_amount": (post or {}).get("uiTokenAmount", {}).get("uiAmountString"),
        })
    for post in meta.get("postTokenBalances") or []:
        if post.get("owner") != wallet:
            continue
        already = any(c["mint"] == post.get("mint") for c in token_balance_changes)
        if not already:
            token_balance_changes.append({
                "mint": post.get("mint"),
                "pre_amount": None,
                "post_amount": post.get("uiTokenAmount", {}).get("uiAmountString"),
            })

    sol_pre = sol_post = None
    if wallet_idx is not None:
        sol_pre = meta.get("preBalances", [None])[wallet_idx] if wallet_idx < len(meta.get("preBalances", [])) else None
        sol_post = meta.get("postBalances", [None])[wallet_idx] if wallet_idx < len(meta.get("postBalances", [])) else None

    return {
        "signature": tx["transaction"]["signatures"][0],
        "blockTime": tx.get("blockTime"),
        "err": meta.get("err"),
        "fee_lamports": meta.get("fee"),
        "sol_pre_lamports": sol_pre,
        "sol_post_lamports": sol_post,
        "token_balance_changes": token_balance_changes,
        "top_level_program_ids": [
            instr.get("programId") for instr in tx["transaction"]["message"].get("instructions", [])
            if instr.get("programId")
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wallet")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--sol-usd-price", type=float, default=None)
    parser.add_argument("--rpc-http", default=tp.SOLANA_RPC_HTTP)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    print(f"=== Fase 4 / Solana: descargando actividad real de {args.wallet} ===")
    print(f"RPC: {args.rpc_http}\n")

    sig_infos = fetch_recent_signatures(args.wallet, args.limit, args.rpc_http)
    if not sig_infos:
        print("No se encontraron firmas para esta wallet (o la wallet no existe / esta vacia).")
        sys.exit(1)

    results = []
    for sig_info in sig_infos:
        signature = sig_info["signature"]
        fetch_start = time.time()
        try:
            tx = tp.fetch_transaction_json(signature, rpc_url=args.rpc_http)
        except Exception as exc:
            print(f"--- {signature} ---\n  [error obteniendo transaccion]: {exc}\n")
            continue
        fetch_ms = (time.time() - fetch_start) * 1000

        raw = _raw_summary(tx, args.wallet)
        event = tp.interpret_transaction(tx, args.wallet, sol_usd_price=args.sol_usd_price)

        block_time = tx.get("blockTime")
        staleness_s = (time.time() - block_time) if block_time else None

        print(f"--- {signature} ---")
        print("RAW:")
        print(json.dumps(raw, indent=2, ensure_ascii=False))
        print("PARSER:")
        print(json.dumps(event.to_dict(), indent=2, ensure_ascii=False))
        print(f"tiempo de RPC (getTransaction): {fetch_ms:.1f} ms")
        if staleness_s is not None:
            print(f"antiguedad de la tx al momento de esta corrida: {staleness_s:.1f} s")
        print()

        results.append({
            "raw": raw,
            "parsed": event.to_dict(),
            "rpc_fetch_ms": fetch_ms,
            "staleness_seconds_at_fetch": staleness_s,
        })

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"Resultados guardados en {out_path}")


if __name__ == "__main__":
    main()
