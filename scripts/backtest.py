"""CLI genérico de backtesting - corre cualquier indicador registrado en
scripts/backtesting/indicators/ contra historia real de Binance (publica, sin llave).

Ejemplo: python scripts/backtest.py --indicator premium_discount --symbol BTCUSDT \
  --interval 15m --years 6 --horizons 10,20 --param mode=reversion

Ver scripts/backtesting/indicators/__init__.py para la lista de indicadores y cómo agregar uno.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, __file__.rsplit("/", 1)[0])  # permite correr este archivo directo
from backtesting.data import fetch_all_klines, fetch_all_klines_cached, INTERVAL_MS  # noqa: E402
from backtesting.engine import evaluate, print_report, simulate_trades, print_simulation_report  # noqa: E402
from backtesting.indicators import INDICATORS  # noqa: E402


def parse_params(pairs: list[str]) -> dict:
    out = {}
    for p in pairs or []:
        key, _, val = p.partition("=")
        if val.lower() in ("true", "false"):
            out[key] = val.lower() == "true"
        else:
            try:
                out[key] = int(val)
            except ValueError:
                try:
                    out[key] = float(val)
                except ValueError:
                    out[key] = val
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indicator", required=True, choices=list(INDICATORS.keys()))
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="15m", choices=list(INTERVAL_MS.keys()))
    ap.add_argument("--years", type=int, default=6)
    ap.add_argument("--horizons", default="10,20", help="velas hacia adelante para medir el resultado, separadas por coma")
    ap.add_argument("--param", action="append", help="parámetro propio del indicador, formato clave=valor (puede repetirse)")
    ap.add_argument("--modes", default=None, help="modos del indicador a probar en la misma corrida, separados por coma (ej. reversion,continuacion) - si no se da, usa el 'mode' de --param o el default del indicador")
    ap.add_argument("--simulate", action="store_true", help="además del acierto direccional simple, simula operaciones reales con stop/meta/break-even")
    ap.add_argument("--stop-pcts", default="1.0", help="distancias de stop-loss a probar, en %%, separadas por coma")
    ap.add_argument("--take-profits", default="0.5,1,1.5,2,3", help="metas de ganancia a probar, en %%, separadas por coma")
    ap.add_argument("--breakeven-pct", default="0.5", help="a cuánto % de ganancia se protege moviendo el stop a la entrada - 'none' para no usar protección a break-even")
    ap.add_argument("--max-bars", type=int, default=50, help="velas máximas a esperar por operación antes de cerrar por tiempo")
    ap.add_argument("--cache-dir", default=None, help="carpeta donde guardar/reusar las velas ya descargadas, para no volver a pedirlas en la próxima corrida")
    args = ap.parse_args()

    horizons = [int(h) for h in args.horizons.split(",")]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * args.years)
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)

    print(f"Descargando {args.symbol} {args.interval} desde {start.date()} hasta {end.date()}...", flush=True)
    if args.cache_dir:
        cache_path = os.path.join(args.cache_dir, f"{args.symbol}_{args.interval}.csv")
        candles = fetch_all_klines_cached(args.symbol, args.interval, start_ms, end_ms, cache_path)
    else:
        candles = fetch_all_klines(args.symbol, args.interval, start_ms, end_ms)
    print(f"{len(candles)} velas en total.", flush=True)
    if len(candles) < 500:
        print("Muy pocas velas, algo falló en la descarga.", flush=True)
        sys.exit(1)

    spec = INDICATORS[args.indicator]
    base_params = dict(spec["default_params"])
    base_params.update(parse_params(args.param))

    modes = args.modes.split(",") if args.modes else [base_params.get("mode", "reversion")]
    stop_pcts = [float(s) for s in args.stop_pcts.split(",")]
    take_profits = [float(tp) for tp in args.take_profits.split(",")]
    breakeven_pct = None if args.breakeven_pct.lower() == "none" else float(args.breakeven_pct)

    for mode in modes:
        params = dict(base_params)
        params["mode"] = mode
        signals = spec["detect_signals"](candles, **params)
        print(f"\n########## modo={mode} — {len(signals)} señales detectadas ##########", flush=True)

        results = evaluate(candles, signals, horizons)
        meta = {
            "Símbolo": args.symbol, "Temporalidad": args.interval,
            "Periodo": f"{args.years} años ({start.date()} a {end.date()})",
            "Parámetros": ", ".join(f"{k}={v}" for k, v in params.items()),
        }
        print_report(f"{spec['description']} [{mode}]", meta, signals, results, horizons)

        if args.simulate:
            print(f"\n=== Simulación con stop/meta/break-even — modo={mode} ===")
            for stop_pct in stop_pcts:
                for tp in take_profits:
                    sim = simulate_trades(candles, signals, stop_pct, tp, breakeven_pct, args.max_bars)
                    print_simulation_report(f"stop {stop_pct}% / meta {tp}%", stop_pct, tp, breakeven_pct, args.max_bars, sim)


if __name__ == "__main__":
    main()
