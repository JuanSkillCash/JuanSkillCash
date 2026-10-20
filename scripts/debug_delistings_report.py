"""
Solo para diagnostico manual (workflow_dispatch, no corre en el cron): imprime un resumen
de lo que hay en exchange_delistings y marca filas sospechosas (symbol demasiado largo,
symbol vacio o igual al quote, titulos duplicados con distinto symbol, etc.) para poder
revisar a ojo si el parser de tickers esta generando basura antes de construir el frontend
sobre estos datos.

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
    url = f"{SUPABASE_URL}/rest/v1/exchange_delistings?select=exchange,symbol,pair_base,market,announced_at,delist_at,title,status,source_url&order=id.asc"
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

    by_exchange = Counter(r["exchange"] for r in rows)
    print("\nPor exchange:")
    for ex, n in by_exchange.most_common():
        print(f"  {ex}: {n}")

    by_status = Counter(r["status"] for r in rows)
    print("\nPor status:", dict(by_status))

    with_delist_at = sum(1 for r in rows if r.get("delist_at"))
    print(f"\nCon delist_at resuelto: {with_delist_at}/{len(rows)} ({100 * with_delist_at / len(rows):.1f}%)")

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

    print("\n--- Muestra de 15 filas 'upcoming' mas proximas a deslistar ---")
    upcoming = sorted(
        (r for r in rows if r["status"] == "upcoming" and r.get("delist_at")),
        key=lambda r: r["delist_at"],
    )
    for r in upcoming[:15]:
        print(f"  [{r['exchange']}] {r['symbol']}  delist_at={r['delist_at']}  market={r.get('market')}")

    print("\n--- Distribucion de longitud de symbol (para ver si hay un patron raro) ---")
    lens = Counter(len(r.get("symbol") or "") for r in rows)
    for length in sorted(lens):
        print(f"  len={length}: {lens[length]}")


if __name__ == "__main__":
    main()
