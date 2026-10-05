"""
Grafico de burbujas cripto: top 1000 monedas por capitalizacion de mercado, con su % de
cambio en 1h/24h/7d/30d/1y, para pintar un mapa de burbujas donde el tamano es la
capitalizacion y el color/intensidad es el % de cambio en la temporalidad elegida.

Por que corre asi: si cada visitante pidiera esto a una API directamente desde su navegador,
con 1000 monedas y trafico real se agotaria rapido el limite de cualquier API gratuita
compartida. En vez de eso, este robot corre una vez cada 10 minutos (sin importar cuanta
gente este viendo la pagina) y guarda la foto mas reciente en Supabase - cada visitante
solo lee esa tabla.

Fuente: CoinPaprika (publica, sin llave, cupo propio de 20,000 llamadas/mes - nunca antes
tocado por este robot ni por el resto del sitio, que usa la key de CoinGecko). Una sola
llamada a /v1/tickers trae market cap y el % de cambio en las 5 temporalidades en un solo
request. Cada 10 minutos = ~4,320 llamadas/mes, muy por debajo del cupo. CoinPaprika tambien
solo actualiza sus propios numeros cada ~10 minutos en su plan gratis, asi que pedir mas
seguido no traeria nada mas fresco.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys
import logging

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_crypto_bubbles")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "crypto_bubbles_latest"

COINPAPRIKA_TICKERS_URL = "https://api.coinpaprika.com/v1/tickers"
TOP_N = 1000

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def fetch_tickers():
    resp = requests.get(
        COINPAPRIKA_TICKERS_URL,
        params={"limit": TOP_N},
        headers=REQUEST_HEADERS,
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"CoinPaprika respondio {resp.status_code}: {resp.text}")
    coins = resp.json()
    if not isinstance(coins, list) or not coins:
        raise RuntimeError(f"CoinPaprika no devolvio monedas. Respuesta cruda: {coins}")
    return coins


def build_rows(coins):
    rows = []
    for c in coins:
        rank = c.get("rank")
        symbol = c.get("symbol")
        name = c.get("name")
        quotes = (c.get("quotes") or {}).get("USD") or {}
        if not c.get("id") or not rank or not symbol or not name:
            continue
        # sin precio o sin market cap la burbuja no se puede dibujar (ni tamano ni color) -
        # se descarta en vez de guardar un 0 enganoso
        if quotes.get("price") is None or quotes.get("market_cap") is None:
            continue
        rows.append({
            "id": c["id"],
            "rank": rank,
            "symbol": symbol.upper(),
            "name": name,
            "price_usd": quotes.get("price"),
            "market_cap_usd": quotes.get("market_cap"),
            "pct_1h": quotes.get("percent_change_1h"),
            "pct_24h": quotes.get("percent_change_24h"),
            "pct_7d": quotes.get("percent_change_7d"),
            "pct_30d": quotes.get("percent_change_30d"),
            "pct_1y": quotes.get("percent_change_1y"),
        })
    rows.sort(key=lambda r: r["rank"])
    return rows


def replace_table_rows(rows):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    # se borra todo y se reinserta - es una tabla de "ultima foto", no historico, asi que
    # reemplazar completo es lo mas simple y evita dejar filas viejas de monedas que salieron
    # del top 1000
    del_resp = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{TABLE}?id=neq.__none__",
        headers=headers, timeout=30,
    )
    if del_resp.status_code >= 300:
        raise RuntimeError(f"Supabase (delete) respondio {del_resp.status_code}: {del_resp.text}")

    insert_headers = dict(headers, **{"Prefer": "return=minimal"})
    # se inserta en tandas - Supabase/PostgREST puede rechazar un POST con 1000 filas de un
    # solo golpe segun el tamano del payload, tandas de 200 son seguras
    CHUNK = 200
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]
        resp = requests.post(f"{SUPABASE_URL}/rest/v1/{TABLE}", json=chunk, headers=insert_headers, timeout=30)
        if resp.status_code >= 300:
            raise RuntimeError(f"Supabase (insert) respondio {resp.status_code}: {resp.text}")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    log.info("Pidiendo top %d por capitalizacion a CoinPaprika...", TOP_N)
    coins = fetch_tickers()
    rows = build_rows(coins)

    log.info("Calculadas %d filas (de %d monedas devueltas).", len(rows), len(coins))
    if not rows:
        # si algo salio mal y no se armo ninguna fila, es mas seguro dejar la tabla como
        # estaba (datos viejos) que borrarla entera y dejar las burbujas vacias en el sitio
        log.error("No se armo ninguna fila - no se toca la tabla en Supabase, se aborta.")
        sys.exit(1)
    replace_table_rows(rows)
    log.info("Listo: burbujas cripto actualizadas en Supabase.")


if __name__ == "__main__":
    main()
