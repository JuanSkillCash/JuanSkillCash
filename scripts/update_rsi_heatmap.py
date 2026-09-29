"""
Mapa de calor de RSI + sesgo de MACD para el top 20 de criptomonedas por capitalizacion
(sin stablecoins), en 6 temporalidades (5m, 15m, 1h, 4h, 1d, 1w).

Por que corre asi: este dato se refresca cada 5 minutos (para que 5m/15m sirvan de verdad
para trading intradia). Si cada visitante pidiera esto directamente desde su navegador,
con trafico real se agotaria el limite compartido de la API y se romperian los precios en
todo el sitio. En vez de eso, este script corre UNA vez cada 5 minutos (sin importar cuanta
gente este viendo la pagina) y guarda el resultado ya calculado en Supabase - cada visitante
solo lee esa tabla, sin pedirle nada a ninguna API externa.

Fuentes:
  - CoinPaprika (publica, sin llave, cupo propio - nunca antes usado por el sitio): solo para
    elegir el top 20 por capitalizacion sin stablecoins, una llamada cada corrida. Se probaron
    dos alternativas antes de esta y ambas fallaron en vivo:
      * CoinGecko: Actions bloquea la peticion con un 403 de CloudFront ("Request blocked")
        en TODAS las corridas, sea cual sea el User-Agent - filtra por rango de IP a los
        runners de GitHub Actions, no por header.
      * CryptoCompare (con la key que el sitio YA usa client-side): respondio "over your rate
        limit" en la primera corrida real - esa key la comparten todos los visitantes del
        sitio, no tiene margen para 288 corridas/dia adicionales de este robot.
  - Kraken (publica, sin llave, acepta nativamente las 6 temporalidades que usa este mapa):
    velas de precio para calcular RSI y MACD. NO se usa Binance aqui: probado en vivo, responde
    451 "Service unavailable from a restricted location" en TODAS las corridas - Binance.com
    bloquea por geografia a los runners de GitHub Actions (alojados en EE.UU.), el mismo motivo
    por el que existe Binance.US como sitio aparte.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys
import logging
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_rsi_heatmap")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "rsi_heatmap_latest"

COINPAPRIKA_TICKERS_URL = "https://api.coinpaprika.com/v1/tickers"
KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"

TOP_N = 20
FETCH_BUFFER = 40  # se piden mas de 20 por si hay que descartar stablecoins/no-listados en Kraken

# Kraken usa "XBT" en vez de "BTC" para bitcoin (unica excepcion) - todo lo demas usa el simbolo
# estandar que ya trae CoinPaprika
KRAKEN_SYMBOL_OVERRIDES = {"BTC": "XBT"}

# temporalidad -> minutos (los unicos valores que acepta el endpoint OHLC de Kraken)
TIMEFRAME_MINUTES = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}
TIMEFRAMES = list(TIMEFRAME_MINUTES.keys())
KLINES_LIMIT = 200  # suficiente warm-up para RSI(14) y MACD(12,26,9) - Kraken ignora el limite exacto pero acepta 'since'

RSI_LENGTH = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9

# simbolos de stablecoins conocidos - se descartan del heat map (su RSI no aporta nada,
# siempre rondan el mismo precio)
STABLECOIN_SYMBOLS = {
    "usdt", "usdc", "dai", "busd", "tusd", "usdd", "fdusd", "pyusd", "usde",
    "usds", "usdp", "gusd", "frax", "lusd", "susd", "eurc", "eurt",
}

# User-Agent de navegador normal por si alguna de las dos APIs filtra el User-Agent por
# defecto de requests (python-requests/x.x) - no hace daño dejarlo puesto en ambas
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def fetch_top_candidates():
    params = {"limit": FETCH_BUFFER}
    resp = requests.get(COINPAPRIKA_TICKERS_URL, params=params, headers=REQUEST_HEADERS, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"CoinPaprika respondio {resp.status_code}: {resp.text}")
    coins = resp.json()
    if not isinstance(coins, list) or not coins:
        raise RuntimeError(f"CoinPaprika no devolvio monedas. Respuesta cruda: {coins}")
    # CoinPaprika ya los devuelve ordenados por rank ascendente, pero se ordena explicito
    # por si acaso - el "rank" que guardamos es el propio de ellos (posicion real de mercado)
    coins.sort(key=lambda c: c.get("rank") or 999999)
    out = []
    for c in coins:
        symbol = (c.get("symbol") or "").lower()
        if not symbol or symbol in STABLECOIN_SYMBOLS:
            continue
        out.append({
            "symbol": symbol.upper(),
            "name": c.get("name") or symbol.upper(),
            "rank": c.get("rank") or 999,
        })
    return out


def fetch_closes(kraken_pair, timeframe):
    params = {"pair": kraken_pair, "interval": TIMEFRAME_MINUTES[timeframe]}
    resp = requests.get(KRAKEN_OHLC_URL, params=params, headers=REQUEST_HEADERS, timeout=30)
    if resp.status_code >= 300:
        log.info("Kraken %s %s -> %s: %s", kraken_pair, timeframe, resp.status_code, resp.text[:200])
        return None
    payload = resp.json()
    # Kraken devuelve 200 OK con un array "error" no vacio para un par invalido, en vez de un
    # status HTTP de error - sin este chequeo ese caso se veria igual que "datos insuficientes"
    if payload.get("error"):
        log.info("Kraken %s %s -> error: %s", kraken_pair, timeframe, payload["error"])
        return None
    result = payload.get("result") or {}
    # la clave que Kraken usa en la respuesta a veces difiere del "pair" que se mando (ej. usa su
    # nombre interno "XXBTZUSD" en vez de "XBTUSD") - se toma la primera clave que no sea "last"
    candles = None
    for key, value in result.items():
        if key != "last":
            candles = value
            break
    if not isinstance(candles, list) or len(candles) < MACD_SLOW + MACD_SIGNAL:
        log.info("Kraken %s %s -> respuesta insuficiente (%s velas)", kraken_pair, timeframe, len(candles) if isinstance(candles, list) else type(candles))
        return None
    # formato de cada vela: [time, open, high, low, close, vwap, volume, count]
    closes = [float(k[4]) for k in candles]
    return closes


def rma(values, length):
    out = [None] * len(values)
    if len(values) < length:
        return out
    seed = sum(values[:length]) / length
    out[length - 1] = seed
    prev = seed
    for i in range(length, len(values)):
        prev = (prev * (length - 1) + values[i]) / length
        out[i] = prev
    return out


def compute_rsi(closes, length=RSI_LENGTH):
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = rma(gains, length)
    avg_loss = rma(losses, length)
    rsi_last = None
    for i in range(len(closes) - 1, -1, -1):
        if avg_gain[i] is not None and avg_loss[i] is not None:
            if avg_loss[i] == 0:
                rsi_last = 100.0 if avg_gain[i] > 0 else 50.0
            else:
                rsi_last = 100 - 100 / (1 + avg_gain[i] / avg_loss[i])
            break
    return rsi_last


def ema_series(values, length):
    k = 2 / (length + 1)
    out = [None] * len(values)
    seed = sum(values[:length]) / length
    out[length - 1] = seed
    prev = seed
    for i in range(length, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def compute_macd_bias(closes):
    ema_fast = ema_series(closes, MACD_FAST)
    ema_slow = ema_series(closes, MACD_SLOW)
    macd_line = []
    start = MACD_SLOW - 1
    for i in range(len(closes)):
        if i < start or ema_fast[i] is None or ema_slow[i] is None:
            continue
        macd_line.append(ema_fast[i] - ema_slow[i])
    if len(macd_line) < MACD_SIGNAL:
        return None
    signal_line = ema_series(macd_line, MACD_SIGNAL)
    hist_last = macd_line[-1] - signal_line[-1]
    return "bull" if hist_last >= 0 else "bear"


def replace_table_rows(rows):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    # se borra todo y se reinserta - es una tabla de "ultima foto", no historico, y son
    # pocas filas (top 20 x 6 temporalidades), asi que reemplazar completo es lo mas simple
    # y evita dejar filas viejas de monedas que salieron del top 20
    del_resp = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{TABLE}?symbol=neq.__none__",
        headers=headers, timeout=30,
    )
    if del_resp.status_code >= 300:
        raise RuntimeError(f"Supabase (delete) respondio {del_resp.status_code}: {del_resp.text}")

    if not rows:
        return
    insert_headers = dict(headers, **{"Prefer": "return=minimal"})
    resp = requests.post(f"{SUPABASE_URL}/rest/v1/{TABLE}", json=rows, headers=insert_headers, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase (insert) respondio {resp.status_code}: {resp.text}")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    log.info("Buscando top %d por capitalizacion (sin stablecoins)...", TOP_N)
    candidates = fetch_top_candidates()

    rows = []
    picked = 0
    for coin in candidates:
        if picked >= TOP_N:
            break
        kraken_symbol = KRAKEN_SYMBOL_OVERRIDES.get(coin["symbol"], coin["symbol"])
        kraken_pair = kraken_symbol + "USD"
        coin_rows = []
        ok = True
        for tf in TIMEFRAMES:
            closes = fetch_closes(kraken_pair, tf)
            if not closes:
                ok = False
                break
            rsi = compute_rsi(closes)
            macd_bias = compute_macd_bias(closes)
            if rsi is None or macd_bias is None:
                ok = False
                break
            coin_rows.append({
                "symbol": coin["symbol"],
                "name": coin["name"],
                "timeframe": tf,
                "rsi": round(rsi, 1),
                "macd_bias": macd_bias,
                "price": closes[-1],
                "rank": coin["rank"],
            })
            time.sleep(0.1)  # cortesia con la API publica de Kraken, no hace falta mas
        if not ok:
            log.info("Descartado %s (no listado en Kraken como %s, o datos insuficientes)", coin["symbol"], kraken_pair)
            continue
        rows.extend(coin_rows)
        picked += 1

    log.info("Calculado RSI+MACD para %d monedas x %d temporalidades (%d filas).", picked, len(TIMEFRAMES), len(rows))
    if not rows:
        # si algo salio mal y no se calculo nada, es mas seguro dejar la tabla como estaba
        # (datos viejos) que borrarla entera y dejar el heat map vacio en el sitio
        log.error("No se calculo ninguna fila - no se toca la tabla en Supabase, se aborta.")
        sys.exit(1)
    replace_table_rows(rows)
    log.info("Listo: mapa de calor RSI+MACD actualizado en Supabase.")


if __name__ == "__main__":
    main()
