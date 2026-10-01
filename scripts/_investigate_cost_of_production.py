"""
Script DESCARTABLE de investigacion (ronda 2) - NO escribe nada en Supabase, no usa secretos.
Corrige la ronda 1: Coin Metrics rechazo TODA la peticion (403) porque DiffMean ya no esta en
el plan gratis - se pidio junto con las demas metricas y tumbo el batch completo. Esta ronda:
  - pide a Coin Metrics SOLO lo que el catalogo confirmo como "community": true (BlkCnt,
    FeeTotNtv, PriceUSD, IssTotNtv) - sin DiffMean
  - usa la dificultad de blockchain.info (confirmada completa: 2009-01-03..hoy, sin huecos)
    como fuente principal de dificultad
  - usa blockchain.info transaction-fees (BTC) como fuente principal de fees
  - cruza blockchain.info vs Bitview para dificultad (ambas dieron historia completa en la
    ronda 1), y blockchain.info vs Coin Metrics para fees
  - cruza la issuance calculada (subsidy*bloques+fees) contra IssTotNtv de Coin Metrics Y
    contra btc-issued de bitcoin-data.com (ventana gratis limitada)

Formula pedida (Pine v6 de TradingView):
    subsidy(date)      -> 50 / 25 / 12.5 / 6.25 / 3.125 segun halving
    issuance_daily      = subsidy * bloques_minados_ese_dia + fees_en_BTC_ese_dia
    difficulty_90       = SMA(dificultad, 90)
    issuance_90         = SMA(issuance_daily, 90)
    cost_floor          = (1/1800) * difficulty_90**0.45 / issuance_90
    cost_zone           = cost_floor * 1.2
"""

import json
import statistics
from datetime import date, datetime, timedelta

import requests

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
    try:
        r = requests.get(url, params=params, timeout=60)
        print(f"  [{label}] GET {r.url}  status={r.status_code}")
        if r.status_code != 200:
            print(f"  [{label}] body[:400]={r.text[:400]}")
            return None
        return r.json()
    except Exception as e:
        print(f"  [{label}] ERROR: {e}")
        return None


def print_section(title):
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)


def pct_diff_report(name, series_a, series_b, label_a, label_b, skip_zero=True):
    common = sorted(set(series_a) & set(series_b))
    diffs = []
    for d in common:
        a, b = series_a[d], series_b[d]
        if a is None or b is None:
            continue
        if skip_zero and (a == 0 or b == 0):
            continue
        base = b if b != 0 else a
        pct = abs(a - b) / abs(base) * 100
        diffs.append((d, a, b, pct))
    print(f"\n  -- {name}: {label_a} vs {label_b} --")
    print(f"  fechas en comun: {len(common)}  comparables (no-cero): {len(diffs)}")
    if diffs:
        diffs.sort(key=lambda x: -x[3])
        pcts = [x[3] for x in diffs]
        print(f"  diff% maxima: {max(pcts):.4f}% en {diffs[0][0]} ({label_a}={diffs[0][1]!r}, {label_b}={diffs[0][2]!r})")
        print(f"  diff% promedio: {statistics.mean(pcts):.6f}%  mediana: {statistics.median(pcts):.6f}%")
        print(f"  peores 5: {diffs[:5]}")
    return diffs


# ---------------------------------------------------------------------------
print_section("1. BLOCKCHAIN.INFO - fuente principal (difficulty, fees, price)")
bc_series = {}
for chart_name in ["difficulty", "transaction-fees", "market-price"]:
    data = get_json(
        f"https://api.blockchain.info/charts/{chart_name}",
        params={"timespan": "all", "format": "json", "sampled": "false"},
        label=f"bc/{chart_name}",
    )
    if data and "values" in data:
        vals = data["values"]
        print(f"  [{chart_name}] unit={data.get('unit')!r} n={len(vals)} rango={datetime.utcfromtimestamp(vals[0]['x']).date()}..{datetime.utcfromtimestamp(vals[-1]['x']).date()}")
        series = {}
        for v in vals:
            d = datetime.utcfromtimestamp(v["x"]).date().isoformat()
            val = v["y"]
            # 0.0 en dificultad es un placeholder de "sin dato" (la dificultad real nunca es 0,
            # el minimo historico es 1.0) - se descarta, no se trata como valor real
            if chart_name == "difficulty" and val == 0.0:
                continue
            series[d] = val
        bc_series[chart_name] = series

# ---------------------------------------------------------------------------
print_section("2. COIN METRICS COMMUNITY API - solo metricas confirmadas gratis (sin DiffMean)")
cm_data = get_json(
    "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",
    params={
        "assets": "btc",
        "metrics": "BlkCnt,FeeTotNtv,PriceUSD,IssTotNtv",
        "frequency": "1d",
        "start_time": "2009-01-01",
        "page_size": 10000,
    },
    label="cm/timeseries",
)
cm_rows = {}
if cm_data and "data" in cm_data:
    rows = cm_data["data"]
    print(f"  n_rows={len(rows)}")
    if rows:
        print(f"  primeras 2: {rows[:2]}")
        print(f"  ultimas 2: {rows[-2:]}")
    for row in rows:
        cm_rows[row["time"][:10]] = row
    if cm_data.get("next_page_token") or cm_data.get("next_page_url"):
        print(f"  OJO: hay paginacion pendiente sin traer - next_page_url={cm_data.get('next_page_url')}")
else:
    print("  Coin Metrics NO devolvio datos utilizables")

# ---------------------------------------------------------------------------
print_section("3. BITVIEW - dificultad (respaldo/cruce), confirmado day1 en ronda 1")
bv_difficulty = {}
vals = get_json("https://bitview.space/api/series/difficulty/day1", label="bv/difficulty")
if vals and "data" in vals:
    epoch = date(2009, 1, 2)  # confirmado empiricamente en la investigacion de STH-MVRV
    for i, v in enumerate(vals["data"]):
        if v is None or v == 0.0:
            continue
        bv_difficulty[(epoch + timedelta(days=i)).isoformat()] = v
    print(f"  n_valores_no_nulos={len(bv_difficulty)}")

# ---------------------------------------------------------------------------
print_section("4. BITCOIN-DATA.COM - respaldo (ventana gratis ~4 anos)")
bg_difficulty, bg_issued = {}, {}
data = get_json("https://bitcoin-data.com/v1/difficulty-btc", label="bg/difficulty-btc")
if data:
    for row in data:
        if row.get("difficultyBtc") is not None:
            bg_difficulty[row["d"]] = float(row["difficultyBtc"])
    if bg_difficulty:
        print(f"  n={len(bg_difficulty)} rango={min(bg_difficulty)}..{max(bg_difficulty)}")
data = get_json("https://bitcoin-data.com/v1/btc-issued", label="bg/btc-issued")
if data:
    for row in data:
        if row.get("btcIssued") is not None:
            bg_issued[row["d"]] = float(row["btcIssued"])
    if bg_issued:
        print(f"  n={len(bg_issued)} rango={min(bg_issued)}..{max(bg_issued)}")

# ---------------------------------------------------------------------------
print_section("5. VALIDACION CRUZADA DE DIFICULTAD (3 fuentes independientes)")
pct_diff_report("Dificultad", bc_series.get("difficulty", {}), bv_difficulty, "blockchain.info", "Bitview")
pct_diff_report("Dificultad", bc_series.get("difficulty", {}), bg_difficulty, "blockchain.info", "bitcoin-data.com")

print_section("6. VALIDACION CRUZADA DE FEES (BTC/dia)")
cm_fees = {d: float(row["FeeTotNtv"]) for d, row in cm_rows.items() if row.get("FeeTotNtv") is not None}
pct_diff_report("Fees", bc_series.get("transaction-fees", {}), cm_fees, "blockchain.info", "Coin Metrics")

# ---------------------------------------------------------------------------
print_section("7. CALCULO DE issuance_daily Y cost_floor")
cm_blocks = {d: float(row["BlkCnt"]) for d, row in cm_rows.items() if row.get("BlkCnt") is not None}
cm_iss_reported = {d: float(row["IssTotNtv"]) for d, row in cm_rows.items() if row.get("IssTotNtv") is not None}
fees_src = bc_series.get("transaction-fees", {})
difficulty_src = bc_series.get("difficulty", {})

issuance_calc = {}
for d, blocks in cm_blocks.items():
    fees = fees_src.get(d)
    if fees is None:
        continue
    issuance_calc[d] = subsidy_for(date.fromisoformat(d)) * blocks + fees
print(f"  issuance_daily calculada (subsidy*BlkCnt_CoinMetrics + fees_blockchain.info) para {len(issuance_calc)} dias")

pct_diff_report("Issuance calculada vs IssTotNtv (Coin Metrics)", issuance_calc, cm_iss_reported, "calculada", "CM IssTotNtv")
pct_diff_report("Issuance calculada vs btc-issued (bitcoin-data.com)", issuance_calc, bg_issued, "calculada", "bitcoin-data.com")


def sma(values_by_date, dates_sorted, window):
    out = {}
    buf = []
    for d in dates_sorted:
        buf.append(values_by_date.get(d))
        if len(buf) > window:
            buf.pop(0)
        out[d] = (sum(buf) / window) if len(buf) == window and all(x is not None for x in buf) else None
    return out


all_dates = sorted(set(difficulty_src) | set(issuance_calc))
difficulty_90 = sma(difficulty_src, all_dates, 90)
issuance_90 = sma(issuance_calc, all_dates, 90)

cost_floor_by_date = {}
for d in all_dates:
    diff90, iss90 = difficulty_90.get(d), issuance_90.get(d)
    if diff90 is None or iss90 is None or iss90 <= 0:
        cost_floor_by_date[d] = None
        continue
    cost_floor_by_date[d] = (1 / 1800) * (diff90 ** 0.45) / iss90

n_valid = sum(1 for v in cost_floor_by_date.values() if v is not None)
print(f"\n  cost_floor calculado para {n_valid} / {len(all_dates)} dias totales en el rango")

print_section("8. VALORES EN FECHAS DE VALIDACION (comparar manualmente contra TradingView)")
check_dates = ["2018-12-15", "2020-03-13", "2022-11-21", "2024-04-20", all_dates[-1] if all_dates else None]
for d in check_dates:
    if d is None:
        continue
    cf = cost_floor_by_date.get(d)
    cz = cf * 1.2 if cf is not None else None
    price = bc_series.get("market-price", {}).get(d)
    print(f"  {d}: cost_floor={cf!r}  cost_zone={cz!r}  precio_real_BTC={price!r}  difficulty_90={difficulty_90.get(d)!r}  issuance_90={issuance_90.get(d)!r}")

print_section("9. CASOS BORDE")
if all_dates:
    print(f"  primera fecha en el rango combinado: {all_dates[0]}")
    first_valid = next((d for d in all_dates if cost_floor_by_date.get(d) is not None), None)
    print(f"  primera fecha con cost_floor valido (deberia ser ~90 dias despues de tener difficulty+issuance): {first_valid}")
for halving_date, new_subsidy in HALVINGS:
    print(f"\n  halving {halving_date.isoformat()} (subsidy pasa a {new_subsidy}):")
    for offset in [-1, 0, 1]:
        d = (halving_date + timedelta(days=offset)).isoformat()
        print(f"    {d}: subsidy_usado={subsidy_for(date.fromisoformat(d))}  blocks={cm_blocks.get(d)!r}  fees={fees_src.get(d)!r}  issuance_calc={issuance_calc.get(d)!r}  cost_floor={cost_floor_by_date.get(d)!r}")
missing_diff = [d for d in all_dates if difficulty_src.get(d) is None]
missing_blocks = [d for d in all_dates if d not in cm_blocks]
missing_fees = [d for d in all_dates if d not in fees_src]
print(f"\n  dias sin difficulty (blockchain.info): {len(missing_diff)} (muestra: {missing_diff[:5]})")
print(f"  dias sin blocks (Coin Metrics): {len(missing_blocks)} (muestra: {missing_blocks[:5]})")
print(f"  dias sin fees (blockchain.info): {len(missing_fees)} (muestra: {missing_fees[:5]})")

print_section("FIN DEL REPORTE")
