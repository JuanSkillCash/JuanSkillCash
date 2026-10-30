"""Descarga de velas históricas de Binance (publico, sin llave) - compartido por todos los
indicadores del motor de backtesting."""
import csv
import os
import time

import requests

# api.binance.com bloquea por región las peticiones que salen de las maquinas de GitHub Actions
# (451 "no disponible por razones legales"). data-api.binance.vision es el espejo público de
# SOLO DATOS de Binance (mismo formato, pensado justo para este uso) y no tiene ese bloqueo.
BINANCE_REST = "https://data-api.binance.vision"
INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000,
}


def fetch_all_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> list[dict]:
    """Pagina hacia adelante con startTime, 1000 velas por pedido (el máximo de Binance)."""
    out = []
    cursor = start_ms
    step_ms = INTERVAL_MS[interval]
    while cursor < end_ms:
        resp = requests.get(
            f"{BINANCE_REST}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "startTime": cursor, "limit": 1000},
            timeout=20,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            break
        for r in rows:
            out.append({
                "t": r[0], "open": float(r[1]), "high": float(r[2]),
                "low": float(r[3]), "close": float(r[4]), "volume": float(r[5]),
            })
        last_open = rows[-1][0]
        if last_open <= cursor:
            break  # evita loop infinito si Binance devuelve algo raro
        cursor = last_open + step_ms
        if len(rows) < 1000:
            break  # ya llegamos a lo mas reciente disponible
        time.sleep(0.15)  # no abusar del rate limit publico
    return [c for c in out if c["t"] < end_ms]


def _load_cache(cache_path: str) -> list[dict]:
    if not os.path.exists(cache_path):
        return []
    with open(cache_path, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # encabezado
        return [
            {"t": int(r[0]), "open": float(r[1]), "high": float(r[2]), "low": float(r[3]), "close": float(r[4]), "volume": float(r[5])}
            for r in reader
        ]


def _save_cache(cache_path: str, candles: list[dict]):
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    with open(cache_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t", "open", "high", "low", "close", "volume"])
        for c in candles:
            writer.writerow([c["t"], c["open"], c["high"], c["low"], c["close"], c["volume"]])


def fetch_all_klines_cached(symbol: str, interval: str, start_ms: int, end_ms: int, cache_path: str) -> list[dict]:
    """Igual que fetch_all_klines, pero guarda lo descargado en cache_path (un CSV) y en
    llamadas futuras solo le pide a Binance las velas nuevas desde la última que ya tiene
    guardada - para no volver a descargar años de historia cada vez que se corre un backtest
    (el workflow de GitHub Actions persiste esta carpeta entre corridas con actions/cache)."""
    cached = _load_cache(cache_path)
    step_ms = INTERVAL_MS[interval]
    fetch_start = max(start_ms, cached[-1]["t"] + step_ms) if cached else start_ms
    if fetch_start < end_ms:
        print(f"  cache: {len(cached)} velas ya guardadas, pidiendo nuevas desde ahí...", flush=True)
        new_candles = fetch_all_klines(symbol, interval, fetch_start, end_ms)
    else:
        print(f"  cache: {len(cached)} velas ya guardadas, ya está al día, no se pide nada nuevo.", flush=True)
        new_candles = []
    all_candles = cached + new_candles
    if new_candles:
        _save_cache(cache_path, all_candles)
    return [c for c in all_candles if c["t"] >= start_ms]
