"""Diagnostico de una sola corrida: confirmar si el WebSocket oficial de anuncios de Gate
(wss://api.gateio.ws/ws/v4/ann) es alcanzable desde el runner de GitHub Actions, como
alternativa a www.gate.com (bloqueado por Akamai - 403 "Access Denied" / errors.edgesuite.net,
confirmado que es reputacion de IP del runner, no un cambio del sitio: desde una IP
residencial real www.gate.com responde 200 normal). api.gateio.ws es la API de trading,
infraestructura separada de la del sitio web, con su propio WAF (o ninguno) - este
diagnostico es la unica forma de confirmarlo antes de construir el scraper real sobre esto.

No escribe nada a Supabase. Imprime cada mensaje recibido para poder ver la forma real del
JSON (campos exactos de `result`, si trae o no `tags`, etc.) antes de escribir el parser."""

from __future__ import annotations

import json
import time

import websocket  # paquete "websocket-client"

WS_URL = "wss://api.gateio.ws/ws/v4/ann"
CHANNELS = ["announcement.summary_listing", "announcement.summary_delisting"]
LISTEN_SECONDS = 25


def main():
    print(f"=== conectando a {WS_URL} ===")
    try:
        ws = websocket.create_connection(WS_URL, timeout=15)
    except Exception as e:
        print(f"FALLO conectando: {e!r}")
        return
    print("conectado OK")

    for ch in CHANNELS:
        payload = {"time": int(time.time()), "channel": ch, "event": "subscribe", "payload": ["en"]}
        ws.send(json.dumps(payload))
        print(f"-> suscrito a {ch}")

    deadline = time.time() + LISTEN_SECONDS
    msg_count = 0
    while time.time() < deadline:
        remaining = deadline - time.time()
        ws.settimeout(max(1, remaining))
        try:
            raw = ws.recv()
        except Exception as e:
            print(f"(fin de escucha: {e!r})")
            break
        msg_count += 1
        print(f"MSG {msg_count}: {raw}")

    ws.close()
    print(f"=== {msg_count} mensajes recibidos en {LISTEN_SECONDS}s ===")


if __name__ == "__main__":
    main()
