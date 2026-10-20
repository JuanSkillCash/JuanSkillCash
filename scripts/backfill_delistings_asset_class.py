"""
Backfill puntual (workflow_dispatch, se corre UNA vez): recalcula asset_class para las
filas de exchange_delistings que ya existian antes de que la columna existiera (todas
quedaron con el default 'crypto' al agregarse la columna). Lee cada fila, recalcula
asset_class a partir de su title con classify_asset_class, y sube solo las que cambian.

Requiere haber corrido antes scripts/sql/alter_exchange_delistings_asset_class.sql.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))  # para que "delistings" se importe como paquete
from delistings.common import classify_asset_class

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "exchange_delistings"


def fetch_all_rows():
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?select=id,title,asset_class&order=id.asc"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    rows = []
    offset = 0
    PAGE = 1000
    while True:
        h = dict(headers, Range=f"{offset}-{offset + PAGE - 1}")
        resp = requests.get(url, headers=h, timeout=60)
        if resp.status_code not in (200, 206):
            raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text[:300]}")
        batch = resp.json()
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE
    return rows


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    rows = fetch_all_rows()
    print(f"TOTAL filas leidas: {len(rows)}")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    updated = 0
    from collections import Counter
    new_counts = Counter()
    for r in rows:
        new_class = classify_asset_class(r.get("title") or "")
        new_counts[new_class] += 1
        if new_class == r.get("asset_class"):
            continue
        url = f"{SUPABASE_URL}/rest/v1/{TABLE}?id=eq.{r['id']}"
        resp = requests.patch(url, json={"asset_class": new_class}, headers=headers, timeout=30)
        if resp.status_code >= 300:
            print(f"  fallo id={r['id']}: {resp.status_code} {resp.text[:200]}")
            continue
        updated += 1

    print(f"Filas actualizadas (cambiaron de clase): {updated}/{len(rows)}")
    print(f"Distribucion final esperada: {dict(new_counts)}")


if __name__ == "__main__":
    main()
