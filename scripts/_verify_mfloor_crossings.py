"""
Script DESCARTABLE de verificacion - NO escribe nada en Supabase, no usa secretos. Reproduce EN
PYTHON, paso a paso, la misma logica de Pulso de Fondo (Keltner semanal + Costo de Produccion)
que corre en el navegador, para encontrar los cruces REALES (sin adivinar) y compararlos contra
lo que el usuario ve en su grafico de TradingView.
"""

import json
import bisect
from datetime import date, datetime, timedelta

import requests

EPOCH = datetime(1970, 1, 1)

HALVINGS = [
    (date(2012, 11, 28), 25.0),
    (date(2016, 7, 9), 12.5),
    (date(2020, 5, 11), 6.25),
    (date(2024, 4, 20), 3.125),
]


def subsidy_for(d: date) -> float:
    subsidy = 50.0
    for halving_date, new_subsidy in HALVINGS:
        if d >= halving_date:
            subsidy = new_subsidy
    return subsidy


def get_json(url, params=None, label=""):
    r = requests.get(url, params=params, timeout=60)
    print(f"  [{label}] status={r.status_code}")
    if r.status_code != 200:
        print(f"  [{label}] body[:300]={r.text[:300]}")
        return None
    return r.json()


print("=== 1. Binance BTCUSDT semanal ===")
klines = get_json(
    "https://api.binance.com/api/v3/klines",
    params={"symbol": "BTCUSDT", "interval": "1w", "limit": 1000},
    label="binance",
)
weekly = None
if klines and isinstance(klines, list):
    weekly = [{"t": k[6], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4])} for k in klines]
    weekly.sort(key=lambda w: w["t"])
    print(f"  {len(weekly)} velas semanales (Binance, t=CIERRE de la semana), rango {datetime.utcfromtimestamp(weekly[0]['t']/1000).date()} .. {datetime.utcfromtimestamp(weekly[-1]['t']/1000).date()}")
else:
    # Binance bloquea IPs de datacenter (GitHub Actions incluido) - mismo respaldo que ya usa el
    # sitio en vivo: precio diario de blockchain.info, agrupado por semana ISO (lunes-domingo),
    # con el timestamp = LUNES (inicio de semana) - OJO: distinto de Binance, que da el cierre
    # (domingo). Para comparar fechas contra TradingView hay que tener esto en cuenta.
    print("  Binance no disponible - usando respaldo (blockchain.info, agrupado por semana ISO)")
    price_raw = get_json(
        "https://api.blockchain.info/charts/market-price",
        params={"timespan": "all", "format": "json", "sampled": "false"},
        label="bc-price",
    )
    daily_price = sorted([{"t": v["x"] * 1000, "c": v["y"]} for v in price_raw["values"] if v["y"] > 0], key=lambda p: p["t"])

    def iso_week_key_ms(t_ms):
        # aritmetica pura relativa al epoch (sin pasar por .timestamp(), que interpreta un
        # datetime naive como hora LOCAL del sistema y desfasaria todo por la zona horaria)
        d = datetime.utcfromtimestamp(t_ms / 1000)
        day_start = datetime(d.year, d.month, d.day)
        monday = day_start - timedelta(days=d.weekday())  # weekday(): 0=lunes
        return int((monday - EPOCH).total_seconds() * 1000)

    buckets = {}
    for p in daily_price:
        key = iso_week_key_ms(p["t"])
        if key not in buckets:
            buckets[key] = {"t": key, "o": p["c"], "h": p["c"], "l": p["c"], "c": p["c"]}
        b = buckets[key]
        b["h"] = max(b["h"], p["c"])
        b["l"] = min(b["l"], p["c"])
        b["c"] = p["c"]
    weekly = sorted(buckets.values(), key=lambda w: w["t"])
    print(f"  {len(weekly)} semanas (respaldo, t=INICIO/lunes de la semana), rango {datetime.utcfromtimestamp(weekly[0]['t']/1000).date()} .. {datetime.utcfromtimestamp(weekly[-1]['t']/1000).date()}")

print("\n=== 2. blockchain.info dificultad ===")
diff_raw = get_json(
    "https://api.blockchain.info/charts/difficulty",
    params={"timespan": "all", "format": "json", "sampled": "false"},
    label="bc-difficulty",
)
difficulty = sorted(
    [{"t": v["x"] * 1000, "v": v["y"]} for v in diff_raw["values"] if v["y"] != 0.0],
    key=lambda p: p["t"],
)
print(f"  {len(difficulty)} dias")

print("\n=== 3. blockchain.info fees (BTC) ===")
fees_raw = get_json(
    "https://api.blockchain.info/charts/transaction-fees",
    params={"timespan": "all", "format": "json", "sampled": "false"},
    label="bc-fees",
)
fees = sorted([{"t": v["x"] * 1000, "v": v["y"]} for v in fees_raw["values"]], key=lambda p: p["t"])
print(f"  {len(fees)} dias")

print("\n=== 4. Coin Metrics bloques minados (BlkCnt) ===")
cm = get_json(
    "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",
    params={"assets": "btc", "metrics": "BlkCnt", "frequency": "1d", "start_time": "2009-01-01", "page_size": 10000},
    label="cm-blocks",
)
blocks = sorted(
    [{"t": int(datetime.fromisoformat(r["time"].replace("Z", "+00:00")).timestamp() * 1000), "v": float(r["BlkCnt"])}
     for r in cm["data"] if r.get("BlkCnt") is not None],
    key=lambda p: p["t"],
)
print(f"  {len(blocks)} dias")


def last_value_before(series, target_ms):
    ts = [p["t"] for p in series]
    idx = bisect.bisect_right(ts, target_ms) - 1
    if idx < 0:
        return series[0]["v"]
    return series[idx]["v"]


print("\n=== 5. Calculando issuance diaria, Keltner semanal y Costo de Produccion ===")
daily_issuance = []
for f in fees:
    blocks_that_day = last_value_before(blocks, f["t"]) or 144
    d = datetime.utcfromtimestamp(f["t"] / 1000).date()
    daily_issuance.append({"t": f["t"], "v": subsidy_for(d) * blocks_that_day + f["v"]})

weekly_difficulty = [last_value_before(difficulty, w["t"]) for w in weekly]
weekly_issuance = [last_value_before(daily_issuance, w["t"]) for w in weekly]


def sma_trailing(values, n):
    out = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


MFLOOR_K = 0.45
MFLOOR_ALPHA = 11.48
MFLOOR_SMOOTH_WEEKS = 13

diff_sma = sma_trailing(weekly_difficulty, MFLOOR_SMOOTH_WEEKS)
iss_sma = sma_trailing(weekly_issuance, MFLOOR_SMOOTH_WEEKS)
cost_smooth = [None if (d is None or i is None or i <= 0) else MFLOOR_ALPHA * (d ** MFLOOR_K) / i for d, i in zip(diff_sma, iss_sma)]

closes = [w["c"] for w in weekly]
true_ranges = []
for i, w in enumerate(weekly):
    if i == 0:
        true_ranges.append(w["h"] - w["l"])
    else:
        true_ranges.append(max(w["h"] - w["l"], abs(w["h"] - weekly[i - 1]["c"]), abs(w["l"] - weekly[i - 1]["c"])))


def ema_series(values, length):
    alpha = 2 / (length + 1)
    out = [None] * len(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def rma_series(values, length):
    alpha = 1 / length
    out = [None] * len(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


ema20 = ema_series(closes, 20)
atr10 = rma_series(true_ranges, 10)
keltner_lower = [e - 2 * a for e, a in zip(ema20, atr10)]

points = []
for i, w in enumerate(weekly):
    points.append({"t": w["t"], "price": w["c"], "keltnerLower": keltner_lower[i], "costSmooth": cost_smooth[i]})

valid_start = next(i for i, p in enumerate(points) if p["costSmooth"] is not None)
points = points[valid_start:]
print(f"  primer punto con Costo valido: {datetime.utcfromtimestamp(points[0]['t']/1000).date()}")
print(f"  ultimo punto: {datetime.utcfromtimestamp(points[-1]['t']/1000).date()}")

print("\n=== 6. TODOS los cruces reales (Keltner cruza por debajo del Costo) ===")
prev_below = None
for p in points:
    below = p["keltnerLower"] < p["costSmooth"]
    if prev_below is False and below is True:
        d = datetime.utcfromtimestamp(p["t"] / 1000).date()
        print(f"  CRUCE ABAJO (entra en capitulacion): {d}  precio=${p['price']:.0f}  keltner=${p['keltnerLower']:.0f}  costo=${p['costSmooth']:.0f}")
    if prev_below is True and below is False:
        d = datetime.utcfromtimestamp(p["t"] / 1000).date()
        print(f"  cruce arriba (sale de capitulacion): {d}  precio=${p['price']:.0f}  keltner=${p['keltnerLower']:.0f}  costo=${p['costSmooth']:.0f}")
    prev_below = below

print("\n=== 7. Detalle semana por semana, jun-sep 2024 (para comparar contra TradingView) ===")
for p in points:
    d = datetime.utcfromtimestamp(p["t"] / 1000).date()
    if date(2024, 6, 1) <= d <= date(2024, 9, 30):
        print(f"  {d}: precio=${p['price']:.0f}  keltner=${p['keltnerLower']:.0f}  costo=${p['costSmooth']:.0f}  {'<-- keltner DEBAJO' if p['keltnerLower'] < p['costSmooth'] else ''}")

print("\n=== 8. Detalle semana por semana, oct 2024 - ene 2025 (para comparar el 'cruce de nov 2024') ===")
for p in points:
    d = datetime.utcfromtimestamp(p["t"] / 1000).date()
    if date(2024, 10, 1) <= d <= date(2025, 1, 31):
        print(f"  {d}: precio=${p['price']:.0f}  keltner=${p['keltnerLower']:.0f}  costo=${p['costSmooth']:.0f}  {'<-- keltner DEBAJO' if p['keltnerLower'] < p['costSmooth'] else ''}")

print("\n=== 9. Detalle semana por semana, abr-jul 2026 (para comparar el cruce de jun 2026) ===")
for p in points:
    d = datetime.utcfromtimestamp(p["t"] / 1000).date()
    if date(2026, 4, 1) <= d <= date(2026, 7, 31):
        print(f"  {d}: precio=${p['price']:.0f}  keltner=${p['keltnerLower']:.0f}  costo=${p['costSmooth']:.0f}  {'<-- keltner DEBAJO' if p['keltnerLower'] < p['costSmooth'] else ''}")

print("\n=== FIN DEL REPORTE ===")
