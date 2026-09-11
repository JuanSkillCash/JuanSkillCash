#!/usr/bin/env python3
"""
Monitor local de solo lectura para wallets en Solana (RPC público oficial).

Que SI hace:
  - Se conecta al endpoint JSON-RPC/WebSocket publico de Solana
    (por defecto: wss://api.mainnet-beta.solana.com), documentado en
    https://solana.com/docs/rpc/websocket/logssubscribe
  - Se suscribe con "logsSubscribe" a una o mas direcciones de wallet
    que el usuario indique por configuracion.
  - Imprime en consola cada firma de transaccion nueva detectada para
    esas direcciones (slot, firma, exito/fallo, logs del programa).

Que NO hace (por diseño, no por omision):
  - No se conecta a fomo.family ni a ningun servicio de terceros
    (fomoapi.io, fomoscan.sh, etc.) - esos endpoints no fueron
    verificados en el informe adjunto.
  - No firma, no envia, ni construye ninguna transaccion.
  - No requiere ni acepta claves privadas, seed phrases ni API keys.
  - No intenta identificar automaticamente "traders de FOMO": la lista
    de wallets a observar la decide el usuario explicitamente.

Este script es deliberadamente generico (observador de wallet on-chain),
porque es la unica pieza de la cadena de valor descrita en el informe
que se pudo fundamentar contra una fuente publica, oficial y documentada.

Uso (modo Fase 1, solo detectar firmas):
    pip install websockets
    python wallet_monitor.py <WALLET_ADDRESS_1> [WALLET_ADDRESS_2 ...]

Uso (modo Fase 2, con interpretacion BUY/SELL/SWAP/UNKNOWN):
    python wallet_monitor.py --interpret [--sol-usd-price 150.0] <WALLET_1> [...]

    Al detectar una firma nueva y exitosa, descarga la transaccion completa
    (getTransaction via RPC HTTP publico, solo lectura) y la pasa por
    transaction_parser.py (ver ese modulo) antes de imprimir la alerta.
    El pipeline es exactamente:
        NUEVA TRANSACCION -> OBTENER DETALLES -> INTERPRETAR -> BUY/SELL/UNKNOWN -> ALERTA
    Sigue sin ejecutar ninguna operacion ni requerir credenciales.

Ejemplo (con una wallet publica cualquiera, aqui la del programa
System Program de Solana solo a modo de humo/smoke test):
    python wallet_monitor.py 11111111111111111111111111111111
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import websockets
except ImportError:
    print("Falta la dependencia 'websockets'. Instala con: pip install websockets")
    sys.exit(1)

SOLANA_PUBLIC_WSS = "wss://api.mainnet-beta.solana.com"
SOLANA_PUBLIC_HTTP = "https://api.mainnet-beta.solana.com"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}")


async def watch_wallet(ws, address: str, sub_id_map: dict) -> None:
    """Envia una suscripcion logsSubscribe filtrada por 'mentions' de la wallet."""
    request = {
        "jsonrpc": "2.0",
        "id": address,
        "method": "logsSubscribe",
        "params": [
            {"mentions": [address]},
            {"commitment": "confirmed"},
        ],
    }
    await ws.send(json.dumps(request))
    log(f"Suscripcion enviada para wallet {address}")


async def _interpret_and_alert(
    addr: str, signature: str, http_rpc_url: str, sol_usd_price: float | None
) -> None:
    """OBTENER DETALLES -> INTERPRETAR -> MOSTRAR ALERTA para una firma nueva.

    transaction_parser.fetch_transaction_json usa urllib (bloqueante), asi
    que se corre en un executor para no congelar el loop de asyncio que
    sigue recibiendo eventos del WebSocket mientras tanto.
    """
    loop = asyncio.get_running_loop()
    try:
        event = await loop.run_in_executor(
            None, tp.interpret_signature, signature, addr, http_rpc_url, sol_usd_price
        )
    except Exception as exc:  # RPC caido, firma no encontrada, timeout, etc.
        log(f"  [interpretacion fallida] {addr} / {signature}: {exc}")
        return

    log("  === ALERTA (interpretacion) ===")
    for line in event.human_readable().splitlines():
        log(f"  {line}")
    log("")


async def run(
    addresses: list[str],
    rpc_url: str = SOLANA_PUBLIC_WSS,
    interpret: bool = False,
    http_rpc_url: str = SOLANA_PUBLIC_HTTP,
    sol_usd_price: float | None = None,
) -> None:
    log(f"Conectando a RPC publico de Solana: {rpc_url}")
    async with websockets.connect(rpc_url, ping_interval=20, ping_timeout=20) as ws:
        log("Conexion establecida (solo lectura, sin autenticacion).")

        sub_id_map: dict[str, str] = {}
        for addr in addresses:
            await watch_wallet(ws, addr, sub_id_map)

        async for raw in ws:
            msg = json.loads(raw)

            # Confirmacion de suscripcion: {"result": <sub_id>, "id": "<address>"}
            if "result" in msg and "id" in msg and isinstance(msg["id"], str):
                addr = msg["id"]
                sub_id = msg["result"]
                sub_id_map[str(sub_id)] = addr
                log(f"Suscripcion confirmada: wallet={addr} subscription_id={sub_id}")
                continue

            # Evento de log entrante
            if msg.get("method") == "logsNotification":
                params = msg.get("params", {})
                sub_id = str(params.get("subscription"))
                addr = sub_id_map.get(sub_id, "desconocida")
                result = params.get("result", {})
                value = result.get("value", {})
                signature = value.get("signature")
                err = value.get("err")
                logs = value.get("logs", [])

                status = "OK" if err is None else f"ERROR: {err}"
                log(f"--- Nueva transaccion detectada ---")
                log(f"  wallet observada : {addr}")
                log(f"  firma (signature) : {signature}")
                log(f"  estado            : {status}")
                log(f"  logs del programa :")
                for line in logs[:10]:
                    log(f"    {line}")
                if len(logs) > 10:
                    log(f"    ... ({len(logs) - 10} lineas adicionales omitidas)")
                log("")

                if interpret:
                    if err is None:
                        await _interpret_and_alert(addr, signature, http_rpc_url, sol_usd_price)
                    else:
                        log(f"  [sin interpretar: la transaccion {signature} fallo on-chain]\n")


def _parse_args(argv: list[str]):
    interpret = False
    sol_usd_price = None
    addresses: list[str] = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--interpret":
            interpret = True
            i += 1
        elif arg == "--sol-usd-price":
            if i + 1 >= len(argv):
                print("--sol-usd-price requiere un valor, ej: --sol-usd-price 150.0")
                sys.exit(1)
            sol_usd_price = float(argv[i + 1])
            i += 2
        else:
            addresses.append(arg)
            i += 1

    return interpret, sol_usd_price, addresses


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    interpret, sol_usd_price, addresses = _parse_args(sys.argv[1:])

    if not addresses:
        print("No se indico ninguna wallet a observar.")
        print(__doc__)
        sys.exit(1)

    if interpret:
        # Import diferido: transaction_parser.py (Fase 2) es opcional para
        # quien solo quiera el monitor original de Fase 1 sin tocar nada.
        global tp
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import transaction_parser as tp  # noqa: E402

    log("=== Monitor de solo lectura (RPC publico de Solana) ===")
    log("Este proceso NO ejecuta operaciones ni requiere credenciales.")
    log(f"Wallets a observar: {', '.join(addresses)}")
    if interpret:
        log("Interpretacion de transacciones (Fase 2) ACTIVADA.")
        if sol_usd_price is not None:
            log(f"Precio SOL/USD provisto manualmente: {sol_usd_price}")
        else:
            log(
                "Sin --sol-usd-price: las operaciones cuya contrapartida es SOL "
                "quedaran sin estimated_usd_value (no se inventa el precio)."
            )

    try:
        asyncio.run(
            run(
                addresses,
                interpret=interpret,
                sol_usd_price=sol_usd_price,
            )
        )
    except KeyboardInterrupt:
        log("Detenido por el usuario.")


if __name__ == "__main__":
    main()
