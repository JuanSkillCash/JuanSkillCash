"""
Solo para diagnostico manual (workflow_dispatch, no corre en el cron): resumen de lo que hay
en exchange_new_listings y filas sospechosas, antes de confiar en estos datos para el
frontend. Hermano de debug_delistings_report.py.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys
from collections import Counter

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def fetch_all_rows():
    url = (
        f"{SUPABASE_URL}/rest/v1/exchange_new_listings"
        f"?select=exchange,symbol,pair_base,market,asset_class,announced_at,listed_at,title,status,source_url"
        f"&order=id.asc"
    )
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
    print(f"TOTAL filas: {len(rows)}")
    if not rows:
        return

    print("\nPor exchange:")
    for ex, n in Counter(r["exchange"] for r in rows).most_common():
        print(f"  {ex}: {n}")

    print("\nPor asset_class:", dict(Counter(r["asset_class"] for r in rows)))
    print("Por status:", dict(Counter(r["status"] for r in rows)))
    print("Por market:", dict(Counter(r.get("market") for r in rows)))

    print("\n--- Muestra de activos NO cripto (stock/index/commodity) para revisar a ojo ---")
    non_crypto = [r for r in rows if r.get("asset_class") != "crypto"]
    for r in non_crypto[:30]:
        print(f"  [{r['exchange']}] {r['asset_class']:10} {r['symbol']:15}  <-  {r['title']!r}")
    print(f"  ({len(non_crypto)} en total)")

    print("\n--- Posibles tickers mal parseados (symbol muy largo, > 15 chars) ---")
    long_symbols = [r for r in rows if len(r.get("symbol") or "") > 15]
    for r in long_symbols[:30]:
        print(f"  [{r['exchange']}] {r['symbol']!r}  <-  {r['title']!r}")
    print(f"  ({len(long_symbols)} en total)")

    print("\n--- Symbol == solo el quote (USDTUSDT, USDUSD, etc.) ---")
    bad = [r for r in rows if (r.get("pair_base") or "").upper() in ("USDT", "USDC", "USD", "")]
    for r in bad[:20]:
        print(f"  [{r['exchange']}] base={r['pair_base']!r} symbol={r['symbol']!r}  <-  {r['title']!r}")
    print(f"  ({len(bad)} en total)")

    print("\n--- Muestra de 15 filas mas recientes ---")
    recent = sorted((r for r in rows if r.get("announced_at")), key=lambda r: r["announced_at"], reverse=True)
    for r in recent[:15]:
        print(f"  [{r['exchange']}] {r['symbol']}  asset_class={r['asset_class']}  announced_at={r['announced_at']}")


if __name__ == "__main__":
    main()
