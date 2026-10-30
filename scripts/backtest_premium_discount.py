"""
Backtest del indicador "Premium and Discount Pivot Matrix [BigBeluga]" (Pine Script, CC
BY-NC-SA 4.0, (c) BigBeluga) sobre historia real de Binance - pedido de Juan: saber cuántas
veces hubiera acertado/fallado esa señal en 5-6 años, en 15m o 5m.

Replica la lógica del Pine tal cual:
  - pivot alto/bajo confirmado con N velas a cada lado (ta.pivothigh/pivotlow, default 5/5)
  - resistencia = máximo de los últimos `array_size` pivots altos confirmados (default 10)
  - soporte     = mínimo de los últimos `array_size` pivots bajos confirmados
  - señal alcista ("Bullish Reversal" en el propio script) = hl2 cruza ABAJO del soporte
  - señal bajista ("Bearish Reversal" en el propio script)  = hl2 cruza ARRIBA de la resistencia
  - enfriamiento: no cuenta una señal nueva si pasaron 5 velas o menos desde la última

OJO con la interpretación: el propio script etiqueta la ruptura de resistencia como "Bearish
Reversal" (espera que BAJE) y la ruptura de soporte como "Bullish Reversal" (espera que SUBA) -
es un indicador de REVERSIÓN en los extremos (premium/discount), no de seguir la ruptura. Este
script calcula el resultado bajo ESA interpretación Y bajo la contraria (seguir la ruptura), para
poder comparar.

Nada de esto corre en el sitio público - es un análisis de investigación, uso no comercial
(respeta la licencia NC-SA del indicador original).
"""
import argparse
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

BINANCE_REST = "https://api.binance.com"
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
            break  # ya llegamos a lo más reciente disponible
        time.sleep(0.15)  # no abusar del rate limit publico
    return [c for c in out if c["t"] < end_ms]


def detect_signals(candles: list[dict], pivot_legs: int, array_size: int, cooldown: int):
    """Replica pivothigh/pivotlow + resistencia/soporte + cruces, sin look-ahead:
    un pivot en la vela i solo se conoce a partir de la vela i+pivot_legs (hace falta esa
    cantidad de velas futuras para confirmar que fue el máximo/mínimo del tramo)."""
    n = len(candles)
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    hl2 = [(c["high"] + c["low"]) / 2 for c in candles]

    # resistance_known[i] / support_known[i] = valor vigente usando solo pivots YA confirmados a esa vela
    high_pivots, low_pivots = [], []
    resistance_known = [None] * n
    support_known = [None] * n

    for i in range(n):
        # ¿se confirma un pivot alto/bajo en la vela i - pivot_legs en este momento?
        center = i - pivot_legs
        if center >= pivot_legs:
            lo = center - pivot_legs
            hi = center + pivot_legs
            window_h = highs[lo:hi + 1]
            window_l = lows[lo:hi + 1]
            if highs[center] == max(window_h):
                high_pivots.append(highs[center])
                if len(high_pivots) > array_size:
                    high_pivots.pop(0)
            if lows[center] == min(window_l):
                low_pivots.append(lows[center])
                if len(low_pivots) > array_size:
                    low_pivots.pop(0)
        resistance_known[i] = max(high_pivots) if high_pivots else None
        support_known[i] = min(low_pivots) if low_pivots else None

    signals = []  # {idx, kind: 'break_resistance'|'break_support', price, time}
    last_break = -10_000
    for i in range(2, n):
        r_prev1, r_prev2 = resistance_known[i - 1], resistance_known[i - 2]
        s_prev1, s_prev2 = support_known[i - 1], support_known[i - 2]
        bullish = r_prev2 is not None and r_prev1 is not None and hl2[i - 1] <= r_prev2 and hl2[i] > r_prev1
        bearish = s_prev2 is not None and s_prev1 is not None and hl2[i - 1] >= s_prev2 and hl2[i] < s_prev1
        # nombres "bullish"/"bearish" como en el Pine = cruce de resistencia / cruce de soporte
        if (bullish or bearish) and (i - last_break > cooldown):
            kind = "break_resistance" if bullish else "break_support"
            signals.append({"idx": i, "kind": kind, "price": candles[i]["close"], "t": candles[i]["t"]})
            last_break = i
    return signals


def evaluate(candles: list[dict], signals: list[dict], horizons: list[int]):
    closes = [c["close"] for c in candles]
    n = len(candles)
    results = {"reversion": {h: {"win": 0, "loss": 0, "flat": 0, "returns": []} for h in horizons},
               "continuacion": {h: {"win": 0, "loss": 0, "flat": 0, "returns": []} for h in horizons}}
    counted = {"break_resistance": 0, "break_support": 0}
    for sig in signals:
        counted[sig["kind"]] += 1
        for h in horizons:
            j = sig["idx"] + h
            if j >= n:
                continue
            ret_pct = (closes[j] - sig["price"]) / sig["price"] * 100
            # reversion (lo que el propio script etiqueta): romper resistencia -> espera BAJA; romper soporte -> espera SUBE
            predicted_up_reversion = sig["kind"] == "break_support"
            # continuacion (al revés): romper resistencia -> espera SIGUE SUBIENDO; romper soporte -> espera SIGUE BAJANDO
            predicted_up_continuacion = sig["kind"] == "break_resistance"
            for mode, predicted_up in (("reversion", predicted_up_reversion), ("continuacion", predicted_up_continuacion)):
                bucket = results[mode][h]
                signed_ret = ret_pct if predicted_up else -ret_pct
                bucket["returns"].append(signed_ret)
                if signed_ret > 0.01:
                    bucket["win"] += 1
                elif signed_ret < -0.01:
                    bucket["loss"] += 1
                else:
                    bucket["flat"] += 1
    return results, counted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="15m", choices=list(INTERVAL_MS.keys()))
    ap.add_argument("--years", type=int, default=6)
    ap.add_argument("--pivot-legs", type=int, default=5)
    ap.add_argument("--array-size", type=int, default=10)
    ap.add_argument("--cooldown", type=int, default=5)
    ap.add_argument("--horizons", default="10,20", help="velas hacia adelante para medir el resultado, separadas por coma")
    args = ap.parse_args()

    horizons = [int(h) for h in args.horizons.split(",")]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * args.years)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    print(f"Descargando {args.symbol} {args.interval} desde {start.date()} hasta {end.date()}...", flush=True)
    candles = fetch_all_klines(args.symbol, args.interval, start_ms, end_ms)
    print(f"{len(candles)} velas descargadas.", flush=True)
    if len(candles) < 500:
        print("Muy pocas velas, algo falló en la descarga.", flush=True)
        sys.exit(1)

    signals = detect_signals(candles, args.pivot_legs, args.array_size, args.cooldown)
    print(f"{len(signals)} señales detectadas (cooldown {args.cooldown} velas).", flush=True)

    results, counted = evaluate(candles, signals, horizons)

    print("\n=== Premium and Discount Pivot Matrix [BigBeluga] — Backtest ===")
    print(f"Símbolo: {args.symbol} | Temporalidad: {args.interval} | Periodo: {args.years} años ({start.date()} a {end.date()})")
    print(f"Pivot legs: {args.pivot_legs} | Pivots en memoria: {args.array_size} | Enfriamiento: {args.cooldown} velas")
    print(f"Rompimientos de resistencia detectados: {counted['break_resistance']}")
    print(f"Rompimientos de soporte detectados:     {counted['break_support']}")

    for mode, label in (("reversion", "REVERSIÓN (como lo etiqueta el propio script: romper resistencia = corto, romper soporte = largo)"),
                          ("continuacion", "CONTINUACIÓN (al revés: romper resistencia = largo, romper soporte = corto)")):
        print(f"\n--- Interpretación {label} ---")
        for h in horizons:
            b = results[mode][h]
            total = b["win"] + b["loss"] + b["flat"]
            if total == 0:
                print(f"  A {h} velas: sin datos suficientes todavía (señales muy cerca del final del histórico)")
                continue
            winrate = b["win"] / total * 100
            avg_ret = sum(b["returns"]) / len(b["returns"]) if b["returns"] else 0
            print(f"  A {h} velas: {total} señales evaluadas | acierto {winrate:.1f}% ({b['win']} a favor / {b['loss']} en contra / {b['flat']} planas) | resultado medio {avg_ret:+.2f}%")

    print("\nOJO: esto mide si el precio estaba más arriba/abajo N velas después del cierre de la señal,")
    print("sin stop ni toma de ganancia real, sin comisiones ni slippage - es una medida simple de acierto")
    print("direccional, no el resultado de una estrategia ejecutable tal cual.")


if __name__ == "__main__":
    main()
