"""Motor genérico de backtesting: toma las señales que detectó un indicador (cada una ya con
su dirección, 'long' o 'short') y mide qué tan seguido acertaron, en varios horizontes de
velas hacia adelante. No sabe nada de ningún indicador en particular - por eso agregar uno
nuevo no toca este archivo."""


def evaluate(candles: list[dict], signals: list[dict], horizons: list[int]) -> dict:
    """signals: lista de {idx, direction: 'long'|'short', price, t, label (opcional)}.
    Devuelve {horizonte: {win, loss, flat, returns: [...]}}."""
    closes = [c["close"] for c in candles]
    n = len(candles)
    results = {h: {"win": 0, "loss": 0, "flat": 0, "returns": []} for h in horizons}

    for sig in signals:
        for h in horizons:
            j = sig["idx"] + h
            if j >= n:
                continue
            ret_pct = (closes[j] - sig["price"]) / sig["price"] * 100
            signed_ret = ret_pct if sig["direction"] == "long" else -ret_pct
            bucket = results[h]
            bucket["returns"].append(signed_ret)
            if signed_ret > 0.01:
                bucket["win"] += 1
            elif signed_ret < -0.01:
                bucket["loss"] += 1
            else:
                bucket["flat"] += 1
    return results


def print_report(indicator_name: str, meta: dict, signals: list[dict], results: dict, horizons: list[int]):
    print(f"\n=== Backtest: {indicator_name} ===")
    for k, v in meta.items():
        print(f"{k}: {v}")
    long_count = sum(1 for s in signals if s["direction"] == "long")
    short_count = sum(1 for s in signals if s["direction"] == "short")
    print(f"Señales totales: {len(signals)} ({long_count} largo / {short_count} corto)")

    for h in horizons:
        b = results[h]
        total = b["win"] + b["loss"] + b["flat"]
        if total == 0:
            print(f"  A {h} velas: sin datos suficientes todavía (señales muy cerca del final del histórico)")
            continue
        winrate = b["win"] / total * 100
        avg_ret = sum(b["returns"]) / len(b["returns"]) if b["returns"] else 0
        print(f"  A {h} velas: {total} señales evaluadas | acierto {winrate:.1f}% "
              f"({b['win']} a favor / {b['loss']} en contra / {b['flat']} planas) | "
              f"resultado medio {avg_ret:+.2f}%")

    print("\nOJO: esto mide si el precio estaba más arriba/abajo N velas después del cierre de la señal,")
    print("sin stop ni toma de ganancia real, sin comisiones ni slippage - es una medida simple de acierto")
    print("direccional, no el resultado de una estrategia ejecutable tal cual.")
