"""
Diagnostico puntual (manual, no queda en el repo a largo plazo): replica exactamente el
filtro que usa el frontend (delist_at >= ahora) para ver, por exchange, cuantas filas son
REALMENTE proximas en este momento - a diferencia del reporte normal, que cuenta la columna
'status' ya guardada (se congela en el momento en que se escribio esa fila y no se
recalcula sola).

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys
from collections import Counter
from datetime import datetime, timezone

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    now_iso = datetime.now(timezone.utc).isoformat()
    url = (
        f"{SUPABASE_URL}/rest/v1/exchange_delistings"
        f"?select=exchange,symbol,market,delist_at,title,source_url"
        f"&delist_at=gte.{now_iso}&order=delist_at.asc"
    )
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    resp = requests.get(url, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text[:300]}")
    rows = resp.json()

    print(f"now_iso usado: {now_iso}")
    print(f"TOTAL filas con delist_at >= ahora (igual al filtro del frontend): {len(rows)}")
    print("\nPor exchange (esto es exactamente lo que deberian mostrar las tarjetas):")
    for ex, n in Counter(r["exchange"] for r in rows).most_common():
        print(f"  {ex}: {n}")

    # tambien: cuantas filas tiene CADA exchange en total, resueltas o no, para contrastar
    url2 = f"{SUPABASE_URL}/rest/v1/exchange_delistings?select=exchange,delist_at"
    rows2 = []
    offset = 0
    PAGE = 1000
    while True:
        h = dict(headers, Range=f"{offset}-{offset + PAGE - 1}")
        r = requests.get(url2, headers=h, timeout=60)
        batch = r.json()
        rows2.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE

    print("\nPor exchange, TOTAL filas vs con delist_at NULO (no resuelto) vs delist_at en el pasado:")
    by_ex = {}
    for r in rows2:
        ex = r["exchange"]
        d = by_ex.setdefault(ex, {"total": 0, "null": 0, "past": 0, "future": 0})
        d["total"] += 1
        if not r.get("delist_at"):
            d["null"] += 1
        else:
            dt = datetime.fromisoformat(r["delist_at"].replace("Z", "+00:00"))
            if dt >= datetime.now(timezone.utc):
                d["future"] += 1
            else:
                d["past"] += 1
    for ex, d in sorted(by_ex.items(), key=lambda kv: -kv[1]["total"]):
        print(f"  {ex}: total={d['total']} futuro={d['future']} pasado={d['past']} sin_fecha={d['null']}")


if __name__ == "__main__":
    main()
