"""
Script DESCARTABLE de investigacion - NO escribe nada en Supabase, no usa secretos. Solo
imprime en el log un reporte completo para decidir si "BTC Cost of Production" se puede
recrear con fuentes 100% gratuitas, sin Glassnode.

Formula pedida (Pine v6 de TradingView):
    subsidy(date)      -> 50 / 25 / 12.5 / 6.25 / 3.125 segun halving
    issuance_daily      = subsidy * bloques_minados_ese_dia + fees_en_BTC_ese_dia
    difficulty_90       = SMA(dificultad, 90)
    issuance_90         = SMA(issuance_daily, 90)
    cost_floor          = (1/1800) * difficulty_90**0.45 / issuance_90
    cost_zone           = cost_floor * 1.2

Fuentes probadas:
    1. blockchain.info Charts API (sin key)
    2. Coin Metrics Community API (sin key) - incluye IssTotNtv (issuance total ya calculada
       por ellos), que sirve como VALIDACION INDEPENDIENTE de issuance_daily sin depender de
       calcularla a mano desde subsidy+fees+bloques
    3. Bitview / Bitcoin Research Kit (respaldo)
    4. bitcoin-data.com (respaldo, ventana gratis limitada)
"""

import sys
import json
import statistics
from datetime import date, datetime, timezone, timedelta

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


def get_json(url, params=None, headers=None, label=""):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=60)
        print(f"  [{label}] GET {r.url}")
        print(f"  [{label}] status={r.status_code} content-type={r.headers.get('content-type')}")
        if r.status_code != 200:
            print(f"  [{label}] body[:500]={r.text[:500]}")
            return None
        return r.json()
    except Exception as e:
        print(f"  [{label}] ERROR: {e}")
        return None


def print_section(title):
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)


# ---------------------------------------------------------------------------
print_section("1. BLOCKCHAIN.INFO - probando endpoints candidatos")
bc_series = {}
for chart_name in [
    "difficulty",
    "transaction-fees",
    "transaction-fees-usd",
    "market-price",
    "n-transactions-per-block",
    "blocks-size",
    "n-transactions",
]:
    data = get_json(
        f"https://api.blockchain.info/charts/{chart_name}",
        params={"timespan": "all", "format": "json", "sampled": "false"},
        label=f"blockchain.info/{chart_name}",
    )
    if data and "values" in data:
        vals = data["values"]
        print(f"  [{chart_name}] unit={data.get('unit')!r} period={data.get('period')!r} n_points={len(vals)}")
        if vals:
            first_d = datetime.utcfromtimestamp(vals[0]["x"]).date()
            last_d = datetime.utcfromtimestamp(vals[-1]["x"]).date()
            print(f"  [{chart_name}] rango: {first_d} .. {last_d}")
            print(f"  [{chart_name}] primeros 3: {vals[:3]}")
            print(f"  [{chart_name}] ultimos 3: {vals[-3:]}")
        bc_series[chart_name] = {datetime.utcfromtimestamp(v["x"]).date().isoformat(): v["y"] for v in vals}

# ---------------------------------------------------------------------------
print_section("2. COIN METRICS COMMUNITY API - catalogo (que sigue siendo gratis)")
cm_catalog = get_json(
    "https://community-api.coinmetrics.io/v4/catalog-v2/asset-metrics",
    params={"assets": "btc", "metrics": "DiffMean,BlkCnt,FeeTotNtv,PriceUSD,IssTotNtv"},
    label="coinmetrics/catalog-v2",
)
if cm_catalog is None:
    cm_catalog = get_json(
        "https://community-api.coinmetrics.io/v4/catalog/asset-metrics",
        params={"assets": "btc", "metrics": "DiffMean,BlkCnt,FeeTotNtv,PriceUSD,IssTotNtv"},
        label="coinmetrics/catalog-v1",
    )
if cm_catalog:
    print(json.dumps(cm_catalog, indent=2)[:4000])

print_section("2b. COIN METRICS COMMUNITY API - datos")
cm_data = get_json(
    "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",
    params={
        "assets": "btc",
        "metrics": "DiffMean,BlkCnt,FeeTotNtv,PriceUSD,IssTotNtv",
        "frequency": "1d",
        "start_time": "2011-01-01",
        "page_size": 10000,
    },
    label="coinmetrics/timeseries",
)
cm_rows = {}
if cm_data and "data" in cm_data:
    rows = cm_data["data"]
    print(f"  n_rows={len(rows)}")
    if rows:
        print(f"  primeras 3: {rows[:3]}")
        print(f"  ultimas 3: {rows[-3:]}")
    for row in rows:
        cm_rows[row["time"][:10]] = row
    if "next_page_token" in cm_data or "next_page_url" in cm_data:
        print(f"  OJO: hay paginacion pendiente - next_page_url={cm_data.get('next_page_url')}")

# ---------------------------------------------------------------------------
print_section("3. BITVIEW - buscando series candidatas")
bv_series_ids = {}
for query in ["difficulty", "subsidy", "fee", "issuance", "blocks_mined", "block_count"]:
    data = get_json("https://bitview.space/api/series/search", params={"q": query}, label=f"bitview/search:{query}")
    if data:
        print(f"  [{query}] -> {data[:30]}")

bv_data = {}
for series_id in ["difficulty", "fee", "subsidy", "issuance", "block_count"]:
    meta = get_json(f"https://bitview.space/api/series/{series_id}", label=f"bitview/meta:{series_id}")
    if meta:
        print(f"  [{series_id}] meta: {json.dumps(meta)[:500]}")
        vals = get_json(f"https://bitview.space/api/series/{series_id}/day1", label=f"bitview/day1:{series_id}")
        if vals and "data" in vals:
            print(f"  [{series_id}] start={vals.get('start')} end={vals.get('end')} n={len(vals['data'])}")
            print(f"  [{series_id}] ultimos 5: {vals['data'][-5:]}")
            bv_data[series_id] = vals

# ---------------------------------------------------------------------------
print_section("4. BITCOIN-DATA.COM - respaldo (ventana gratis limitada)")
for path in ["difficulty-btc", "btc-issued", "difficulty", "issued-btc"]:
    data = get_json(f"https://bitcoin-data.com/v1/{path}", label=f"bgeometrics/{path}")
    if data:
        print(f"  [{path}] tipo={type(data)} muestra={str(data)[:300]}")

# ---------------------------------------------------------------------------
print_section("5. VALIDACION CRUZADA: dificultad blockchain.info vs Coin Metrics")
if "difficulty" in bc_series and cm_rows:
    common_dates = sorted(set(bc_series["difficulty"]) & set(cm_rows))
    print(f"  fechas en comun: {len(common_dates)}")
    diffs = []
    for d in common_dates:
        bc_val = bc_series["difficulty"][d]
        cm_val = cm_rows[d].get("DiffMean")
        if bc_val and cm_val:
            cm_val = float(cm_val)
            pct = abs(bc_val - cm_val) / cm_val * 100
            diffs.append((d, bc_val, cm_val, pct))
    if diffs:
        diffs.sort(key=lambda x: -x[3])
        pcts = [x[3] for x in diffs]
        print(f"  diff % maxima: {max(pcts):.4f}% en {diffs[0][0]} (bc={diffs[0][1]}, cm={diffs[0][2]})")
        print(f"  diff % promedio: {statistics.mean(pcts):.6f}%")
        print(f"  peores 5: {diffs[:5]}")
    else:
        print("  no se pudo comparar (valores faltantes)")
else:
    print("  faltan datos de una de las dos fuentes para comparar dificultad")

print_section("5b. VALIDACION CRUZADA: fees en BTC blockchain.info vs Coin Metrics (FeeTotNtv)")
if "transaction-fees" in bc_series and cm_rows:
    common_dates = sorted(set(bc_series["transaction-fees"]) & set(cm_rows))
    diffs = []
    for d in common_dates:
        bc_val = bc_series["transaction-fees"][d]
        cm_val = cm_rows[d].get("FeeTotNtv")
        if bc_val is not None and cm_val is not None:
            cm_val = float(cm_val)
            if cm_val > 0:
                pct = abs(bc_val - cm_val) / cm_val * 100
                diffs.append((d, bc_val, cm_val, pct))
    if diffs:
        diffs.sort(key=lambda x: -x[3])
        pcts = [x[3] for x in diffs]
        print(f"  n comparados: {len(diffs)}")
        print(f"  diff % maxima: {max(pcts):.4f}% en {diffs[0][0]} (bc={diffs[0][1]}, cm={diffs[0][2]})")
        print(f"  diff % promedio: {statistics.mean(pcts):.6f}%")
        print(f"  peores 5: {diffs[:5]}")
    else:
        print("  no se pudo comparar (valores faltantes o cero)")
else:
    print("  faltan datos de transaction-fees o Coin Metrics")

# ---------------------------------------------------------------------------
print_section("6. CALCULO DE cost_floor - usando Coin Metrics (si hay suficientes datos)")


def sma(values_by_date, dates_sorted, window):
    out = {}
    buf = []
    for d in dates_sorted:
        v = values_by_date.get(d)
        buf.append(v)
        if len(buf) > window:
            buf.pop(0)
        valid = [x for x in buf if x is not None]
        out[d] = (sum(valid) / len(valid)) if len(valid) == window and all(x is not None for x in buf) else None
    return out


if cm_rows:
    all_dates = sorted(cm_rows.keys())
    difficulty_by_date = {d: float(cm_rows[d]["DiffMean"]) if cm_rows[d].get("DiffMean") is not None else None for d in all_dates}
    blocks_by_date = {d: float(cm_rows[d]["BlkCnt"]) if cm_rows[d].get("BlkCnt") is not None else None for d in all_dates}
    fees_by_date = {d: float(cm_rows[d]["FeeTotNtv"]) if cm_rows[d].get("FeeTotNtv") is not None else None for d in all_dates}
    iss_reported_by_date = {d: float(cm_rows[d]["IssTotNtv"]) if cm_rows[d].get("IssTotNtv") is not None else None for d in all_dates}

    issuance_calc_by_date = {}
    for d in all_dates:
        blocks = blocks_by_date.get(d)
        fees = fees_by_date.get(d)
        if blocks is None or fees is None:
            issuance_calc_by_date[d] = None
            continue
        dt = date.fromisoformat(d)
        issuance_calc_by_date[d] = subsidy_for(dt) * blocks + fees

    # comparar issuance calculada a mano vs IssTotNtv reportado por Coin Metrics (si existe)
    both = [(d, issuance_calc_by_date[d], iss_reported_by_date.get(d)) for d in all_dates
            if issuance_calc_by_date.get(d) is not None and iss_reported_by_date.get(d) is not None]
    if both:
        pcts = []
        for d, calc, reported in both:
            if reported > 0:
                pcts.append(abs(calc - reported) / reported * 100)
        if pcts:
            print(f"  issuance calculada (subsidy*bloques+fees) vs IssTotNtv de Coin Metrics:")
            print(f"  n comparados: {len(pcts)}  diff% max: {max(pcts):.4f}  diff% promedio: {statistics.mean(pcts):.6f}")
    else:
        print("  Coin Metrics no devolvio IssTotNtv en el plan gratis (o faltan BlkCnt/FeeTotNtv) - no se puede validar issuance de forma independiente")

    difficulty_90 = sma(difficulty_by_date, all_dates, 90)
    issuance_90 = sma(issuance_calc_by_date, all_dates, 90)

    cost_floor_by_date = {}
    for d in all_dates:
        diff90 = difficulty_90.get(d)
        iss90 = issuance_90.get(d)
        if diff90 is None or iss90 is None or iss90 <= 0:
            cost_floor_by_date[d] = None
            continue
        cost_floor_by_date[d] = (1 / 1800) * (diff90 ** 0.45) / iss90

    n_valid = sum(1 for v in cost_floor_by_date.values() if v is not None)
    print(f"  cost_floor calculado para {n_valid} / {len(all_dates)} dias")

    print_section("7. VALORES EN FECHAS DE VALIDACION (comparar manualmente contra TradingView)")
    check_dates = ["2018-12-15", "2020-03-13", "2022-11-21", "2024-04-20", all_dates[-1]]
    for d in check_dates:
        cf = cost_floor_by_date.get(d)
        cz = cf * 1.2 if cf is not None else None
        price = None
        if d in cm_rows and cm_rows[d].get("PriceUSD") is not None:
            price = float(cm_rows[d]["PriceUSD"])
        print(f"  {d}: cost_floor={cf!r}  cost_zone={cz!r}  precio_real={price!r}  difficulty_90={difficulty_90.get(d)!r}  issuance_90={issuance_90.get(d)!r}")

    print_section("8. CASOS BORDE")
    print(f"  primera fecha con datos: {all_dates[0]}")
    print(f"  primeros 90 dias (deberian dar cost_floor=None): {[cost_floor_by_date.get(d) for d in all_dates[:5]]} ... {[cost_floor_by_date.get(d) for d in all_dates[85:92]]}")
    for halving_date, _ in HALVINGS:
        iso = halving_date.isoformat()
        window = [all_dates[i] for i in range(len(all_dates)) if abs((date.fromisoformat(all_dates[i]) - halving_date).days) <= 2]
        print(f"  alrededor de halving {iso}: subsidy antes={subsidy_for(halving_date - timedelta(days=1))} subsidy despues={subsidy_for(halving_date)}")
        for d in window:
            print(f"    {d}: blocks={blocks_by_date.get(d)!r} fees={fees_by_date.get(d)!r} issuance_calc={issuance_calc_by_date.get(d)!r}")
    missing_diff = [d for d in all_dates if difficulty_by_date.get(d) is None]
    missing_blocks = [d for d in all_dates if blocks_by_date.get(d) is None]
    missing_fees = [d for d in all_dates if fees_by_date.get(d) is None]
    print(f"  dias sin difficulty: {len(missing_diff)} (ej: {missing_diff[:5]})")
    print(f"  dias sin blocks: {len(missing_blocks)} (ej: {missing_blocks[:5]})")
    print(f"  dias sin fees: {len(missing_fees)} (ej: {missing_fees[:5]})")
else:
    print("Coin Metrics no devolvio datos - no se puede calcular cost_floor con esta fuente")

print_section("FIN DEL REPORTE")
