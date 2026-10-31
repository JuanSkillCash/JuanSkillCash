"""Correccion puntual (una sola vez, no permanente): las 3 corridas de Bitget con titulo
generico "Notice of Delisting N Spot Trading Pairs on <fecha>" (23 oct, 30 oct, 6 nov 2026)
ya habian quedado guardadas en exchange_delistings ANTES del fix del regex de fecha
(AM/PM entre la hora y "(UTC)" no matcheaba, asi que el parser termino agarrando por error
otra fecha suelta del cuerpo - confirmado con BRETT/USDT, que quedo con delist_at=2026-10-30
en vez del 6 de noviembre real).

El scraper normal NO se autocorrige solo en la proxima corrida: una vez que source_url ya
tiene un delist_at resuelto (aunque este mal), el cache de fechas conocidas (known_dates)
le dice que no hace falta volver a pedir el cuerpo del articulo - asi que el valor viejo e
incorrecto se queda pisado para siempre. Este script vuelve a bajar el cuerpo real de esas
3 URLs puntuales, saca la fecha correcta con el parser YA arreglado, y pisa el delist_at de
TODAS las filas de esas 3 URLs (los 6+3+8 = 17 tickers de los 3 lotes) via PATCH directo.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from delistings.common import DEFAULT_HEADERS, extract_delist_date_from_body, html_to_text  # noqa: E402

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# las 3 URLs confirmadas afectadas (vistas en los logs del scraper como "no se pudieron
# sacar tickers de" antes del fix de extract_tickers_from_body)
URLS = [
    "https://www.bitget.com/en/support/articles/12560603897809",  # 8 pares, 23 oct
    "https://www.bitget.com/en/support/articles/12560603898559",  # 3 pares, 30 oct
    "https://www.bitget.com/en/support/articles/12560603899149",  # 6 pares (BRETT...), 6 nov
]


def fetch_body(url: str) -> str:
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
    resp.raise_for_status()
    return html_to_text(resp.text)


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    headers = {
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", "Prefer": "return=representation",
    }

    for url in URLS:
        print(f"\n=== {url} ===")
        body = fetch_body(url)
        delist_at = extract_delist_date_from_body(body)
        print(f"fecha correcta parseada: {delist_at}")
        if delist_at is None:
            print("!! no se pudo parsear una fecha - NO se toca nada para esta URL, revisar a mano")
            continue

        patch_url = f"{SUPABASE_URL}/rest/v1/exchange_delistings"
        params = {"exchange": "eq.bitget", "source_url": f"eq.{url}"}
        resp = requests.patch(
            patch_url, params=params, headers=headers,
            json={"delist_at": delist_at.isoformat()}, timeout=30,
        )
        if resp.status_code >= 300:
            print(f"!! PATCH fallo ({resp.status_code}): {resp.text[:500]}")
            continue
        updated = resp.json()
        print(f"filas corregidas: {len(updated)}")
        for r in updated:
            print(f"  - {r['symbol']} -> delist_at={r['delist_at']}")


if __name__ == "__main__":
    main()
