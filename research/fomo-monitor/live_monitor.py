#!/usr/bin/env python3
"""
live_monitor.py — PRUEBA LIVE FINAL: monitorea varias wallets reales
(Solana + Robinhood Chain) al mismo tiempo y muestra cada operacion NUEVA
detectada despues de arrancar, interpretada por los parsers ya existentes
(transaction_parser.py Fase 2, evm_parser.py Fase 3 — SIN modificar).

SOLO LECTURA:
  - No ejecuta ninguna operacion, no firma nada.
  - No conecta wallets privadas, no pide ni acepta claves privadas.
  - No interactua con fomo.family de ninguna forma (ni scraping, ni API).
  - Usa unicamente el RPC publico oficial de cada chain (el mismo que
    usan wallet_monitor.py y chains/robinhood_adapter.py desde las fases
    anteriores) — sin API key.
  - No inventa datos: si el precio o el valor en USD no se pueden
    determinar con una fuente solida, salen como null/None (ver
    parsers/evm_parser.py y transaction_parser.py, Fases 2-3).

REQUIERE ACCESO REAL A INTERNET (no funciona en el sandbox donde se
desarrollo este proyecto — ver FASE_4_VALIDACION_REAL.md).

Uso:
    python live_monitor.py wallets.txt

wallets.txt: una wallet por linea, formato "CHAIN,DIRECCION"
(mayusculas/minusculas no importan; lineas vacias y las que empiezan con
'#' se ignoran):

    SOLANA,7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
    SOLANA,otraWalletDeSolanaAqui...
    ROBINHOOD,0x1234567890abcdef1234567890abcdef12345678

Solo se detectan operaciones NUEVAS a partir del momento en que el
programa arranca — no descarga historial (logsSubscribe en Solana y
polling desde el bloque actual en Robinhood Chain ya funcionan asi por
diseño, ver chains/solana_adapter.py y chains/robinhood_adapter.py).

Cada operacion detectada se imprime en consola Y se guarda (una linea
JSON por operacion) en el archivo indicado por --output (por defecto
"detected_trades.jsonl", en el directorio donde se ejecuta el comando).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent / "prototype"))

from models.normalized_trade import NormalizedTrade  # noqa: E402

SOLANA_ADDRESS_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")  # base58, sin 0/O/I/l
ROBINHOOD_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def log(msg: str = "") -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}" if msg else "")


def parse_wallets_file(path: Path) -> Tuple[List[str], List[str]]:
    """Lee wallets.txt y devuelve (wallets_solana, wallets_robinhood).
    Valida el formato de cada direccion ANTES de abrir ninguna conexion,
    para no dejar el monitor corriendo toda la noche vigilando una wallet
    mal pegada por error."""
    if not path.exists():
        print(f"ERROR: no existe el archivo {path}")
        sys.exit(1)

    solana_wallets: List[str] = []
    robinhood_wallets: List[str] = []
    errors: List[str] = []

    for line_num, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 2:
            errors.append(f"  linea {line_num}: se esperaba 'CHAIN,DIRECCION', se recibio: {raw_line!r}")
            continue
        chain, address = parts[0].upper(), parts[1]

        if chain == "SOLANA":
            if not SOLANA_ADDRESS_RE.match(address):
                errors.append(f"  linea {line_num}: '{address}' no parece una direccion valida de Solana (base58, 32-44 caracteres)")
                continue
            solana_wallets.append(address)
        elif chain == "ROBINHOOD":
            if not ROBINHOOD_ADDRESS_RE.match(address):
                errors.append(f"  linea {line_num}: '{address}' no parece una direccion valida de Robinhood Chain (0x + 40 hex)")
                continue
            robinhood_wallets.append(address.lower())
        else:
            errors.append(f"  linea {line_num}: chain desconocida '{parts[0]}' (soportadas: SOLANA, ROBINHOOD)")

    if errors:
        print(f"ERROR: {path} tiene {len(errors)} linea(s) invalida(s):")
        for e in errors:
            print(e)
        print("\nCorregi el archivo y volve a correr el comando.")
        sys.exit(1)

    return solana_wallets, robinhood_wallets


class TradeRecorder:
    """Imprime en consola y guarda (JSONL, una linea por operacion) cada
    NormalizedTrade detectado. Un solo proceso asyncio, sin threads reales
    -- un append+flush simple es seguro, no hace falta lock de archivo."""

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.count = 0
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def _fmt(self, value, suffix: str = "") -> str:
        if value is None:
            return "null (no se pudo determinar con una fuente solida)"
        return f"{value}{suffix}"

    async def __call__(self, trade: NormalizedTrade) -> None:
        self.count += 1
        print()
        print("=" * 70)
        print(f"OPERACION DETECTADA #{self.count}")
        print("=" * 70)
        print(f"  Blockchain     : {trade.chain}")
        print(f"  Wallet         : {trade.wallet}")
        print(f"  Accion         : {trade.action}")
        print(f"  Token IN       : {self._fmt(trade.token_in_amount)} {trade.token_in_symbol or trade.token_in or ''}")
        print(f"  Token OUT      : {self._fmt(trade.token_out_amount)} {trade.token_out_symbol or trade.token_out or ''}")
        print(f"  Precio         : {self._fmt(trade.price, f' {trade.price_unit}' if trade.price is not None and trade.price_unit else '')}")
        print(f"  Valor USD      : {self._fmt(trade.usd_value, ' USD' if trade.usd_value is not None else '')}")
        print(f"  Protocolo      : {trade.protocol or 'no identificado'}")
        print(f"  Timestamp      : {trade.timestamp}")
        print(f"  Tx hash/sig.   : {trade.signature}")
        print(f"  Confidence     : {trade.confidence:.2f}")
        if trade.notes:
            print(f"  Notas          : {trade.notes}")
        print("=" * 70)

        with self.output_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(trade.to_dict(), ensure_ascii=False) + "\n")
            f.flush()


async def _run_with_reconnect(label: str, watch_coro_fn, *, max_backoff: float = 60.0) -> None:
    """Envoltorio de reconexion a nivel de orquestacion -- NO modifica
    chains/solana_adapter.py ni chains/robinhood_adapter.py. Si watch()
    corta (WebSocket caido, excepcion no manejada), se reintenta con
    backoff exponencial en vez de tumbar todo el monitor."""
    backoff = 2.0
    while True:
        try:
            await watch_coro_fn()
            return  # watch() solo termina si el usuario corta (no deberia pasar en uso normal)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log(f"[{label}] conexion interrumpida ({exc}); reintentando en {backoff:.0f}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


async def main_async(args: argparse.Namespace) -> None:
    solana_wallets, robinhood_wallets = parse_wallets_file(Path(args.wallets_file))

    if not solana_wallets and not robinhood_wallets:
        print(f"ERROR: {args.wallets_file} no tiene ninguna wallet valida (solo comentarios/lineas vacias).")
        sys.exit(1)

    recorder = TradeRecorder(Path(args.output))

    log("=== live_monitor.py — PRUEBA LIVE FINAL ===")
    log("SOLO LECTURA: no ejecuta operaciones, no conecta wallets privadas, no usa claves.")
    log(f"Wallets Solana    ({len(solana_wallets)}): {', '.join(solana_wallets) or '-'}")
    log(f"Wallets Robinhood ({len(robinhood_wallets)}): {', '.join(robinhood_wallets) or '-'}")
    log(f"Guardando cada operacion detectada en: {recorder.output_path.resolve()}")
    log("Esperando operaciones NUEVAS (no se descarga historial). Ctrl+C para detener.\n")

    tasks = []
    if solana_wallets:
        from chains import solana_adapter

        async def watch_solana():
            await solana_adapter.watch(solana_wallets, recorder, sol_usd_price=args.sol_usd_price)

        tasks.append(_run_with_reconnect("solana", watch_solana))

    if robinhood_wallets:
        from chains import robinhood_adapter

        async def watch_robinhood():
            await robinhood_adapter.watch(
                robinhood_wallets, recorder,
                poll_interval=args.poll_interval,
                native_usd_price=args.native_usd_price,
            )

        tasks.append(_run_with_reconnect("robinhood", watch_robinhood))

    await asyncio.gather(*tasks)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("wallets_file", help="Archivo de texto con las wallets a observar (ver formato arriba)")
    parser.add_argument("--output", default="detected_trades.jsonl", help="Archivo JSONL donde guardar cada operacion detectada")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Segundos entre consultas de polling a Robinhood Chain")
    parser.add_argument("--sol-usd-price", type=float, default=None, help="Precio SOL/USD a usar para estimar usd_value en Solana (opcional; sin esto, usd_value queda null cuando la contrapartida es SOL)")
    parser.add_argument("--native-usd-price", type=float, default=None, help="Precio ETH/USD a usar para estimar usd_value en Robinhood Chain (opcional; mismo criterio)")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        log("\nDetenido por el usuario.")


if __name__ == "__main__":
    main()
