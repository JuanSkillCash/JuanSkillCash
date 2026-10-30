"""Premium and Discount Pivot Matrix [BigBeluga] (Pine Script, TradingView, CC BY-NC-SA 4.0,
(c) BigBeluga) - replicado para backtesting, uso no comercial/de investigación.

Lógica del Pine:
  - pivot alto/bajo confirmado con N velas a cada lado (ta.pivothigh/pivotlow, default 5/5)
  - resistencia = máximo de los últimos `array_size` pivots altos confirmados (default 10)
  - soporte     = mínimo de los últimos `array_size` pivots bajos confirmados
  - señal "Bearish Reversal" (el propio script la llama así) = hl2 cruza ARRIBA de la resistencia
  - señal "Bullish Reversal" (el propio script la llama así)  = hl2 cruza ABAJO del soporte
  - enfriamiento: no cuenta una señal nueva si pasaron `cooldown` velas o menos desde la última

El propio script etiqueta romper resistencia como "Bearish Reversal" (espera que BAJE) y romper
soporte como "Bullish Reversal" (espera que SUBA) - es un indicador de REVERSIÓN en los extremos
(premium/discount), no de seguir la ruptura. Por default usa esa interpretación (mode='reversion');
pasa mode='continuacion' para probar lo contrario (seguir la ruptura).
"""

DEFAULT_PARAMS = {"pivot_legs": 5, "array_size": 10, "cooldown": 5, "mode": "reversion"}


def detect_signals(candles: list[dict], pivot_legs: int = 5, array_size: int = 10,
                    cooldown: int = 5, mode: str = "reversion") -> list[dict]:
    """Sin look-ahead: un pivot en la vela i solo se conoce a partir de la vela i+pivot_legs
    (hace falta esa cantidad de velas futuras para confirmar que fue el máximo/mínimo del tramo)."""
    n = len(candles)
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    hl2 = [(c["high"] + c["low"]) / 2 for c in candles]

    high_pivots, low_pivots = [], []
    resistance_known = [None] * n
    support_known = [None] * n

    for i in range(n):
        center = i - pivot_legs
        if center >= pivot_legs:
            lo, hi = center - pivot_legs, center + pivot_legs
            if highs[center] == max(highs[lo:hi + 1]):
                high_pivots.append(highs[center])
                if len(high_pivots) > array_size:
                    high_pivots.pop(0)
            if lows[center] == min(lows[lo:hi + 1]):
                low_pivots.append(lows[center])
                if len(low_pivots) > array_size:
                    low_pivots.pop(0)
        resistance_known[i] = max(high_pivots) if high_pivots else None
        support_known[i] = min(low_pivots) if low_pivots else None

    signals = []
    last_break = -10_000
    for i in range(2, n):
        r_prev1, r_prev2 = resistance_known[i - 1], resistance_known[i - 2]
        s_prev1, s_prev2 = support_known[i - 1], support_known[i - 2]
        break_resistance = r_prev2 is not None and r_prev1 is not None and hl2[i - 1] <= r_prev2 and hl2[i] > r_prev1
        break_support = s_prev2 is not None and s_prev1 is not None and hl2[i - 1] >= s_prev2 and hl2[i] < s_prev1
        if (break_resistance or break_support) and (i - last_break > cooldown):
            if mode == "reversion":
                direction = "short" if break_resistance else "long"
            else:  # continuacion
                direction = "long" if break_resistance else "short"
            label = "break_resistance" if break_resistance else "break_support"
            signals.append({"idx": i, "direction": direction, "price": candles[i]["close"], "t": candles[i]["t"], "label": label})
            last_break = i
    return signals
