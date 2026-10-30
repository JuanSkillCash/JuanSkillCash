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


def simulate_trades(candles: list[dict], signals: list[dict], stop_pct: float,
                     take_profit_pct: float, breakeven_trigger_pct: float | None,
                     max_bars: int) -> dict:
    """Simula cada señal como una operación real, vela a vela, usando máximo/mínimo (no solo
    el cierre) para decidir si tocó el stop o la meta:
    - stop_pct: qué tan lejos (en %) va el stop-loss inicial
    - take_profit_pct: qué tan lejos (en %) va la toma de ganancia
    - breakeven_trigger_pct: si el precio avanza esto a favor (en %), el stop se mueve a la
      entrada (empate protegido) - None para no usar protección a break-even
    - max_bars: si no toca ni el stop ni la meta en este número de velas, se cierra al precio
      de ese momento ("se acabó el tiempo")
    Si el stop y la meta caen en la misma vela, se asume que tocó el stop primero (conservador).
    No incluye comisiones ni slippage."""
    n = len(candles)
    outcomes = {"win": 0, "loss": 0, "breakeven": 0, "timeout": 0}
    returns = []

    for sig in signals:
        entry = sig["price"]
        is_long = sig["direction"] == "long"
        stop = entry * (1 - stop_pct / 100) if is_long else entry * (1 + stop_pct / 100)
        target = entry * (1 + take_profit_pct / 100) if is_long else entry * (1 - take_profit_pct / 100)
        breakeven_level = None
        if breakeven_trigger_pct is not None:
            breakeven_level = entry * (1 + breakeven_trigger_pct / 100) if is_long else entry * (1 - breakeven_trigger_pct / 100)
        armed = False
        outcome, exit_price = None, None

        for k in range(1, max_bars + 1):
            j = sig["idx"] + k
            if j >= n:
                break
            hi, lo = candles[j]["high"], candles[j]["low"]
            if is_long:
                if breakeven_level is not None and not armed and hi >= breakeven_level:
                    armed, stop = True, entry
                if lo <= stop:
                    outcome, exit_price = ("breakeven" if armed else "loss"), stop
                    break
                if hi >= target:
                    outcome, exit_price = "win", target
                    break
            else:
                if breakeven_level is not None and not armed and lo <= breakeven_level:
                    armed, stop = True, entry
                if hi >= stop:
                    outcome, exit_price = ("breakeven" if armed else "loss"), stop
                    break
                if lo <= target:
                    outcome, exit_price = "win", target
                    break

        if outcome is None:
            outcome = "timeout"
            j = min(sig["idx"] + max_bars, n - 1)
            exit_price = candles[j]["close"]

        ret_pct = (exit_price - entry) / entry * 100 if is_long else (entry - exit_price) / entry * 100
        outcomes[outcome] += 1
        returns.append(ret_pct)

    total = len(signals)
    return {
        "total": total, "outcomes": outcomes, "returns": returns,
        "win_rate": outcomes["win"] / total * 100 if total else 0,
        "avg_return": sum(returns) / len(returns) if returns else 0,
    }


def print_simulation_report(label: str, stop_pct: float, take_profit_pct: float,
                              breakeven_trigger_pct: float | None, max_bars: int, sim: dict):
    be_txt = f"protección a break-even tras +{breakeven_trigger_pct}%" if breakeven_trigger_pct is not None else "sin protección a break-even"
    print(f"\n--- {label}: stop {stop_pct}% | meta {take_profit_pct}% | {be_txt} | máx {max_bars} velas ---")
    o = sim["outcomes"]
    print(f"  {sim['total']} operaciones simuladas | acierto (toca la meta) {sim['win_rate']:.1f}% | "
          f"resultado medio {sim['avg_return']:+.2f}% por operación")
    print(f"  Meta: {o['win']} | Stop (pérdida completa): {o['loss']} | "
          f"Break-even (protegido, ni gana ni pierde): {o['breakeven']} | "
          f"Se acabó el tiempo sin tocar nada: {o['timeout']}")


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
