"""
Actualizacion diaria de STH-MVRV y STH Realized Price en Supabase - ver backfill_sth_mvrv.py
para el detalle de las fuentes y de por que el indice "day1" de Bitview se convierte a fecha
con DAY1_EPOCH.

Igual que el backfill, vuelve a pedir la serie COMPLETA cada vez que corre (no solo "los
ultimos dias"): Bitview no documenta un limite de tasa y la llamada es barata (una sola
peticion por serie), asi que repetir todo el historico cada dia es mas simple y corrige
cualquier ajuste retroactivo que el indexador le haga a dias pasados.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys
import logging
from datetime import date, timedelta

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_sth_mvrv_daily")

DAY1_EPOCH = date(2009, 1, 2)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "sth_mvrv_history"


def fetch_bitview_series(series_id: str) -> dict:
    url = f"https://bitview.space/api/series/{series_id}/day1"
    resp = requests.get(url, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Bitview respondio {resp.status_code} para {series_id}: {resp.text[:300]}")
    payload = resp.json()
    out = {}
    for i, value in enumerate(payload.get("data", [])):
        if value is None:
            continue
        d = DAY1_EPOCH + timedelta(days=i)
        out[d.isoformat()] = float(value)
    return out


def fetch_bgeometrics_series(path: str, value_key: str) -> dict:
    resp = requests.get(f"https://bitcoin-data.com/v1/{path}", timeout=30)
    if resp.status_code != 200:
        log.warning(f"bitcoin-data.com respondio {resp.status_code} para {path} (no bloquea la actualizacion)")
        return {}
    out = {}
    for row in resp.json():
        d = row.get("d")
        v = row.get(value_key)
        if d is None or v is None:
            continue
        out[d] = float(v)
    return out


def upsert_rows(rows: list[dict]):
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=date"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    BATCH = 2000
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        resp = requests.post(url, json=batch, headers=headers, timeout=60)
        if resp.status_code >= 300:
            raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text[:500]}")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    realized_price = fetch_bitview_series("sth_realized_price")
    mvrv = fetch_bitview_series("sth_mvrv")
    mvrv_cross = fetch_bgeometrics_series("sth-mvrv", "sthMvrv")
    realized_price_cross = fetch_bgeometrics_series("sth-realized-price", "sthRealizedPrice")

    all_dates = set(realized_price) | set(mvrv)
    rows = []
    for d in sorted(all_dates):
        rows.append({
            "date": d,
            "sth_realized_price": realized_price.get(d),
            "sth_mvrv": mvrv.get(d),
            "sth_realized_price_crosscheck": realized_price_cross.get(d),
            "sth_mvrv_crosscheck": mvrv_cross.get(d),
        })

    upsert_rows(rows)
    log.info(f"{len(rows)} dias actualizados")


if __name__ == "__main__":
    main()
