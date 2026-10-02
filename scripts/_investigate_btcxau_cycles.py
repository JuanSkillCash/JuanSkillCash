"""
Script DESCARTABLE de investigacion - reproduce EN PYTHON la misma logica de
detectCyclePeaksTroughs() que usa BTC/XAU en el sitio, con datos reales de
precio de BTC (blockchain.info) y oro (Twelve Data, misma llave publica ya
embebida en el frontend), para entender por que aparece un ciclo bajista de
solo "7 dias" (reportado por el usuario como imposible).
"""

import requests

TWELVE_DATA_API_KEY = "9a29593d7a534876afbf043270133831"


def fetch_btc_daily():
    r = requests.get(
        "https://api.blockchain.info/charts/market-price",
        params={"timespan": "all", "format": "json", "sampled": "false"},
        timeout=60,
    )
    print(f"  [btc] status={r.status_code}")
    rows = r.json()["values"]
    return sorted([{"t": v["x"] * 1000, "c": v["y"]} for v in rows if v["y"] > 0], key=lambda p: p["t"])


def fetch_gold_daily():
    out = []
    end_date = None
    for page in range(3):
        params = {
            "symbol": "XAU/USD",
            "interval": "1day",
            "outputsize": 5000,
            "apikey": TWELVE_DATA_API_KEY,
        }
        if end_date:
            params["end_date"] = end_date
        r = requests.get("https://api.twelvedata.com/time_series", params=params, timeout=60)
        print(f"  [gold p{page}] status={r.status_code}")
        data = r.json()
        values = data.get("values")
        if not values:
            print(f"  [gold p{page}] body[:300]={str(data)[:300]}")
            break
        out.extend(values)
        oldest = values[-1]["datetime"]
        if end_date == oldest:
            break
        end_date = oldest
        if len(values) < 5000:
            break
    rows = [{"t": __import__("datetime").datetime.strptime(v["datetime"], "%Y-%m-%d").timestamp() * 1000, "c": float(v["close"])} for v in out]
    rows.sort(key=lambda p: p["t"])
    # dedup por dia
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
        day_key = p["t"]
        while gi < len(gold_days) and gold_days[gi] <= day_key:
            last_gold = gold[gi]["c"]
            gi += 1
        if last_gold:
            rows.append({"t": p["t"], "ratio": p["c"] / last_gold})
    return rows


def detect_cycle_peaks_troughs(points, threshold_pct, min_days):
    if not points or len(points) < 2:
        return []
    min_ms = min_days * 86400000
    events = []
    mode = None
    candidate = points[0]
    leg_start_t = points[0]["t"]
    for i in range(1, len(points)):
        p = points[i]
        if mode is None:
            if p["ratio"] > candidate["ratio"]:
                mode = "seekingPeak"
                candidate = p
            elif p["ratio"] < candidate["ratio"]:
                mode = "seekingTrough"
                candidate = p
            continue
        if mode == "seekingPeak":
            if p["ratio"] >= candidate["ratio"]:
                candidate = p
            elif (candidate["ratio"] - p["ratio"]) / candidate["ratio"] >= threshold_pct and (p["t"] - leg_start_t) >= min_ms:
                events.append({"t": candidate["t"], "ratio": candidate["ratio"], "type": "peak", "confirmed_at": p["t"]})
                mode = "seekingTrough"
                leg_start_t = candidate["t"]
                candidate = p
        else:
            if p["ratio"] <= candidate["ratio"]:
                candidate = p
            elif (p["ratio"] - candidate["ratio"]) / candidate["ratio"] >= threshold_pct and (p["t"] - leg_start_t) >= min_ms:
                events.append({"t": candidate["t"], "ratio": candidate["ratio"], "type": "trough", "confirmed_at": p["t"]})
                mode = "seekingPeak"
                leg_start_t = candidate["t"]
                candidate = p
    if mode:
        events.append({"t": candidate["t"], "ratio": candidate["ratio"], "type": mode[len("seeking"):].lower(), "unconfirmed": True})
    return events


def fmt_date(ms):
    import datetime
    return datetime.datetime.utcfromtimestamp(ms / 1000).date().isoformat()


print("=== 1. Precio de BTC (blockchain.info) ===")
btc = fetch_btc_daily()
print(f"  {len(btc)} dias, {fmt_date(btc[0]['t'])} .. {fmt_date(btc[-1]['t'])}")

print("\n=== 2. Precio del oro (Twelve Data XAU/USD) ===")
gold = fetch_gold_daily()
print(f"  {len(gold)} dias, {fmt_date(gold[0]['t'])} .. {fmt_date(gold[-1]['t'])}" if gold else "  SIN DATOS")

if gold:
    print("\n=== 3. Construyendo BTC/XAU ===")
    rows = build_btc_xau_rows(btc, gold)
    print(f"  {len(rows)} filas, {fmt_date(rows[0]['t'])} .. {fmt_date(rows[-1]['t'])}")

    print("\n=== 4. Detectando ciclos (threshold=0.5, minDays=730) ===")
    events = detect_cycle_peaks_troughs(rows, 0.5, 730)
    print(f"  {len(events)} eventos")
    for i, e in enumerate(events):
        gap = ""
        if i > 0:
            days = round((e["t"] - events[i - 1]["t"]) / 86400000)
            gap = f"  <- {days} dias desde el evento anterior"
        conf = f" (confirmado en {fmt_date(e['confirmed_at'])})" if "confirmed_at" in e else " (SIN CONFIRMAR, en curso)"
        print(f"  [{i}] {e['type']:6s} {fmt_date(e['t'])}  ratio={e['ratio']:.6f}{conf}{gap}")

    print("\n=== 5. Detalle dia por dia alrededor de cada gap corto (<60 dias) ===")
    for i in range(1, len(events)):
        days = (events[i]["t"] - events[i - 1]["t"]) / 86400000
        if days < 60:
            a, b = events[i - 1], events[i]
            print(f"\n  --- gap de {days:.0f} dias entre {a['type']} {fmt_date(a['t'])} y {b['type']} {fmt_date(b['t'])} ---")
            window = [r for r in rows if a["t"] - 5 * 86400000 <= r["t"] <= b["t"] + 5 * 86400000]
            for r in window:
                print(f"    {fmt_date(r['t'])}: ratio={r['ratio']:.6f}")

print("\n=== FIN DEL REPORTE ===")
