"""Diagnostico puntual (manual, no permanente): busca en exchange_delistings un symbol/par
por nombre parcial y muestra la fila completa, igual a como quedo guardada - para confirmar
si una moneda puntual (ej. BRETT) esta de verdad en la tabla y por que no aparece en el
frontend (filtro de status/fecha, no datos faltantes).

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY

Uso: python scripts/debug_delisting_symbol.py BRETT
"""
import os
import sys
from datetime import datetime, timezone

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
    term = sys.argv[1] if len(sys.argv) > 1 else "BRETT"

    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/exchange_delistings"
    params = {
        "select": "exchange,symbol,pair_base,market,asset_class,announced_at,delist_at,title,source_url,status",
        "pair_base": f"ilike.*{term}*",
        "order": "exchange.asc",
    }
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    print(f"status: {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text[:500])
        sys.exit(1)
    rows = resp.json()
    now = datetime.now(timezone.utc)
    print(f"'{term}' -> {len(rows)} fila(s) encontradas\n")
    for r in rows:
        delist_at_raw = r.get("delist_at")
        is_future = None
        if delist_at_raw:
            dt = datetime.fromisoformat(delist_at_raw.replace("Z", "+00:00"))
            is_future = dt >= now
        print(f"- exchange={r['exchange']} symbol={r['symbol']} pair_base={r['pair_base']}")
        print(f"  market={r.get('market')} asset_class={r.get('asset_class')} status(guardado)={r.get('status')}")
        print(f"  announced_at={r.get('announced_at')}")
        print(f"  delist_at={delist_at_raw}  (es futuro ahora mismo? {is_future})")
        print(f"  title={r.get('title')!r}")
        print(f"  source_url={r.get('source_url')}")
        print()


if __name__ == "__main__":
    main()
