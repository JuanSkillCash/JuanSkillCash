"""Diagnostico puntual: imprime el texto crudo del cuerpo de un articulo de Bitget, para ver
exactamente que formato de fecha usa de verdad (en vez de asumirlo) - el fix anterior de
fechas se baso en una suposicion sobre el formato que resulto no estar confirmada contra el
cuerpo real."""
import sys

import requests

sys.path.insert(0, "scripts")
from delistings.common import DEFAULT_HEADERS, html_to_text  # noqa: E402

URLS = [
    "https://www.bitget.com/en/support/articles/12560603897809",  # 8 pares, titulo dice 23 oct
    "https://www.bitget.com/en/support/articles/12560603898559",  # 3 pares, titulo dice 30 oct
    "https://www.bitget.com/en/support/articles/12560603899149",  # 6 pares (BRETT...), titulo dice 6 nov
]

for url in URLS:
    print(f"\n{'=' * 20} {url} {'=' * 20}")
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
    print(f"status: {resp.status_code}, len html: {len(resp.text)}")
    text = html_to_text(resp.text)
    print(f"len texto: {len(text)}")
    print("--- primeros 2000 caracteres del texto ---")
    print(text[:2000])
    print("--- fin del extracto ---")
