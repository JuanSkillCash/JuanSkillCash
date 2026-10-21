"""
Mi Lista + Notificaciones: despues de que un robot (update_exchange_delistings.py o
update_new_listings.py) sube sus filas de esta corrida a Supabase, esta funcion revisa si
alguna coincide con lo que algun usuario tiene marcado en su "Mi Lista" (tabla
user_watchlist) y, si es asi, crea una fila en user_notifications para que la vea en el
apartado de Notificaciones del sitio.

Corre con la SERVICE ROLE KEY (la misma que ya usan los robots para subir filas) porque
necesita leer la lista de TODOS los usuarios, algo que un usuario normal no puede hacer por
RLS - por diseno, el usuario solo puede leer/crear SU PROPIA fila de user_watchlist desde el
navegador, nunca la de los demas.

No debe tumbar nunca la corrida del robot que lo llama: cualquier falla aca (tabla no
existe todavia, Supabase caido, etc.) se registra como warning y se sigue de largo - las
filas del radar ya se subieron antes de llamar a esto, eso es lo que de verdad importa.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

log = logging.getLogger("watchlist_notify")

WATCHLIST_TABLE = "user_watchlist"
NOTIFICATIONS_TABLE = "user_notifications"


def notify_watchlist_matches(supabase_url: str, supabase_key: str, radar: str, rows: list) -> int:
    """rows: lista de Row (de delistings.common o newlistings.common - ambas tienen
    exchange/symbol/pair_base/source_url/title, y una de delist_at/listed_at/announced_at).
    Devuelve cuantas notificaciones nuevas se crearon (0 si no hubo match o algo fallo)."""
    if not rows:
        return 0

    supabase_url = supabase_url.rstrip("/")
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.get(
            f"{supabase_url}/rest/v1/{WATCHLIST_TABLE}",
            params={"select": "user_id,symbol,exchange"},
            headers=headers, timeout=20,
        )
        if resp.status_code != 200:
            log.warning(f"no se pudo leer {WATCHLIST_TABLE} ({resp.status_code}): {resp.text[:300]}")
            return 0
        watchlist = resp.json()
    except requests.RequestException as e:
        log.warning(f"fallo leyendo {WATCHLIST_TABLE}: {e}")
        return 0

    if not watchlist:
        return 0

    by_symbol: dict[str, list[dict]] = {}
    for w in watchlist:
        by_symbol.setdefault((w.get("symbol") or "").upper(), []).append(w)

    payload: list[dict[str, Any]] = []
    for row in rows:
        base = (getattr(row, "pair_base", "") or "").upper()
        watchers = by_symbol.get(base)
        if not watchers:
            continue
        event_at = getattr(row, "delist_at", None) or getattr(row, "listed_at", None) or getattr(row, "announced_at", None)
        for w in watchers:
            if w.get("exchange") not in ("any", row.exchange):
                continue
            payload.append({
                "user_id": w["user_id"],
                "radar": radar,
                "exchange": row.exchange,
                "symbol": base,
                "title": row.title,
                "source_url": row.source_url,
                "event_at": event_at.isoformat() if event_at else None,
            })

    if not payload:
        return 0

    try:
        resp = requests.post(
            f"{supabase_url}/rest/v1/{NOTIFICATIONS_TABLE}?on_conflict=user_id,source_url",
            json=payload,
            headers={**headers, "Prefer": "resolution=ignore-duplicates,return=minimal"},
            timeout=30,
        )
        if resp.status_code >= 300:
            log.warning(f"no se pudo escribir {NOTIFICATIONS_TABLE} ({resp.status_code}): {resp.text[:300]}")
            return 0
    except requests.RequestException as e:
        log.warning(f"fallo escribiendo {NOTIFICATIONS_TABLE}: {e}")
        return 0

    log.info(f"[watchlist] {len(payload)} notificacion(es) candidata(s) subida(s) ({radar}, duplicados ignorados)")
    return len(payload)
