"""
Script DESCARTABLE - implementa las reglas de deteccion de ciclos que pidio el
usuario (techo = ATH que cae 65%+, min 700 dias entre techos quedandose con el
mas alto, piso = minimo real entre techos consecutivos, min 200 dias entre
cualquier techo/piso, tramo final provisional) sobre datos reales de BTC/XAU,
para producir la tabla de validacion ANTES de tocar index.html.
"""

import requests
import datetime

TWELVE_DATA_API_KEY = "9a29593d7a534876afbf043270133831"

# ---- parametros editables (mismos que pide el usuario para el codigo final) ----
PEAK_DRAWDOWN_PCT = 0.65
MIN_DAYS_BETWEEN_PEAKS = 650
MIN_DAYS_ANY_GAP = 200


def fetch_btc_daily():
    r = requests.get(
        "https://api.blockchain.info/charts/market-price",
        params={"timespan": "all", "format": "json", "sampled": "false"},
        timeout=60,
    )
    rows = r.json()["values"]
    return sorted([{"t": v["x"] * 1000, "c": v["y"]} for v in rows if v["y"] > 0], key=lambda p: p["t"])


def fetch_gold_daily():
    out = []
    end_date = None
    for page in range(3):
        params = {"symbol": "XAU/USD", "interval": "1day", "outputsize": 5000, "apikey": TWELVE_DATA_API_KEY}
        if end_date:
            params["end_date"] = end_date
        r = requests.get("https://api.twelvedata.com/time_series", params=params, timeout=60)
        data = r.json()
        values = data.get("values")
        if not values:
            break
        out.extend(values)
        oldest = values[-1]["datetime"]
        if end_date == oldest:
            break
        end_date = oldest
        if len(values) < 5000:
            break
    rows = [{"t": datetime.datetime.strptime(v["datetime"], "%Y-%m-%d").timestamp() * 1000, "c": float(v["close"])} for v in out]
    seen = {}
    for p in rows:
        seen[p["t"]] = p
    return sorted(seen.values(), key=lambda p: p["t"])


def build_btc_xau_rows(btc, gold):
    gold_days = [p["t"] for p in gold]
    gi = 0
    last_gold = None
    rows = []
    for p in btc:
        while gi < len(gold_days) and gold_days[gi] <= p["t"]:
            last_gold = gold[gi]["c"]
            gi += 1
        if last_gold:
            rows.append({"t": p["t"], "ratio": p["c"] / last_gold})
    return rows


def raw_zigzag(points, threshold_pct):
    """Zigzag puro (sin filtro de tiempo): confirma un maximo/minimo en cuanto el
    precio se revierte threshold_pct desde el candidato. Regla 1 literal."""
    events = []
    mode = None
    candidate = points[0]
    for i in range(1, len(points)):
        p = points[i]
        if mode is None:
            if p["ratio"] > candidate["ratio"]:
                mode = "peak"
                candidate = p
            elif p["ratio"] < candidate["ratio"]:
                mode = "trough"
                candidate = p
            continue
        if mode == "peak":
            if p["ratio"] >= candidate["ratio"]:
                candidate = p
            elif (candidate["ratio"] - p["ratio"]) / candidate["ratio"] >= threshold_pct:
                events.append(dict(candidate, type="peak"))
                mode = "trough"
                candidate = p
        else:
            if p["ratio"] <= candidate["ratio"]:
                candidate = p
            elif (p["ratio"] - candidate["ratio"]) / candidate["ratio"] >= threshold_pct:
                events.append(dict(candidate, type="trough"))
                mode = "peak"
                candidate = p
    if mode:
        events.append(dict(candidate, type=mode, unconfirmed=True))
    return events


def merge_close_peaks(raw_peaks, min_days):
    """Regla 2: entre dos techos debe haber minimo min_days. Si dos candidatos
    estan mas cerca, se conserva solo el mas alto. Secuencial: se compara cada
    nuevo candidato contra el ULTIMO techo ya confirmado."""
    survivors = []
    for p in raw_peaks:
        if not survivors:
            survivors.append(p)
            continue
        last = survivors[-1]
        gap_days = (p["t"] - last["t"]) / 86400000
        if gap_days >= min_days:
            survivors.append(p)
        else:
            if p["ratio"] > last["ratio"]:
                survivors[-1] = p  # el nuevo es mas alto: reemplaza al anterior
            # si no, se descarta el nuevo (el anterior ya es mas alto)
    return survivors


def find_cycles(points):
    raw = raw_zigzag(points, PEAK_DRAWDOWN_PCT)
    raw_peaks_confirmed = [e for e in raw if e["type"] == "peak" and not e.get("unconfirmed")]
    peaks = merge_close_peaks(raw_peaks_confirmed, MIN_DAYS_BETWEEN_PEAKS)

    cycle_events = []
    for i, peak in enumerate(peaks):
        cycle_events.append({"t": peak["t"], "ratio": peak["ratio"], "type": "peak"})
        # piso = minimo real entre este techo y el siguiente (o hasta el final si es el ultimo)
        window_end = peaks[i + 1]["t"] if i + 1 < len(peaks) else None
        window = [p for p in points if p["t"] > peak["t"] and (window_end is None or p["t"] < window_end)]
        if not window:
            continue
        trough_point = min(window, key=lambda p: p["ratio"])
        is_last = (i == len(peaks) - 1)
        cycle_events.append({
            "t": trough_point["t"], "ratio": trough_point["ratio"], "type": "trough",
            "unconfirmed": is_last,
        })
    return cycle_events, raw, peaks


def fmt_date(ms):
    return datetime.datetime.utcfromtimestamp(ms / 1000).date().isoformat()


print("=== 1. Precio de BTC ===")
btc = fetch_btc_daily()
print(f"  {len(btc)} dias")

print("\n=== 2. Precio del oro ===")
gold = fetch_gold_daily()
print(f"  {len(gold)} dias" if gold else "  SIN DATOS")

if gold:
    rows = build_btc_xau_rows(btc, gold)
    print(f"\n=== 3. BTC/XAU: {len(rows)} filas, {fmt_date(rows[0]['t'])} .. {fmt_date(rows[-1]['t'])} ===")

    cycle_events, raw, peaks = find_cycles(rows)

    print(f"\n=== 4. TODOS los eventos RAW (zigzag puro, threshold={PEAK_DRAWDOWN_PCT}, SIN filtro de tiempo) ===")
    prev_t = None
    for e in raw:
        gap = "" if prev_t is None else f"  <- {round((e['t']-prev_t)/86400000)} dias"
        print(f"  {e['type']:6s} {fmt_date(e['t'])}  ratio={e['ratio']:.6f}{gap}" + ("  (unconfirmed)" if e.get("unconfirmed") else ""))
        prev_t = e['t']

    print(f"\n=== 5. Techos tras aplicar regla 2 (min {MIN_DAYS_BETWEEN_PEAKS} dias, se queda el mas alto) ===")
    for p in peaks:
        print(f"  peak {fmt_date(p['t'])}  ratio={p['ratio']:.6f}")

    print("\n=== 6. TABLA FINAL DE VALIDACION ===")
    print(f"  {'tipo':8s} {'fecha':12s} {'ratio':>12s} {'dias desde anterior':>20s}")
    prev_t = None
    for e in cycle_events:
        days = "" if prev_t is None else str(round((e['t'] - prev_t) / 86400000)) + ("+" if e.get("unconfirmed") else "")
        marker = " (PROVISIONAL)" if e.get("unconfirmed") else ""
        print(f"  {e['type']:8s} {fmt_date(e['t']):12s} {e['ratio']:12.6f} {days:>20s}{marker}")
        prev_t = e['t']

    print("\n=== 7. Validacion de regla 4 (min 200 dias entre cualquier techo/piso adyacente) ===")
    prev_t = None
    violations = 0
    for e in cycle_events:
        if prev_t is not None:
            days = (e['t'] - prev_t) / 86400000
            if days < MIN_DAYS_ANY_GAP:
                print(f"  VIOLACION: {fmt_date(prev_t)} -> {fmt_date(e['t'])} = {days:.0f} dias (< {MIN_DAYS_ANY_GAP})")
                violations += 1
        prev_t = e['t']
    print(f"  {violations} violaciones encontradas" if violations else "  sin violaciones")

print("\n=== FIN DEL REPORTE ===")
