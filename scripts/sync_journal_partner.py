"""
Llena la Bitacora de trading (trade_journal_trades/trade_journal_capital) para los usuarios
conectados a Bitunix (user_exchange_connections, status='connected') que todavia NO conectaron
su propia API key personal via la Edge Function trade-journal-sync - usando en su lugar el
Partner API de Juan (ver docs/bitunix-partner-api.md), que ya puede leer el historial de
cualquier referido sin pedirle nada a esa persona.

A quien SI tiene su clave personal conectada (trade_journal_sync.status='connected' con
exchange='bitunix') se lo salta por completo en el paso de operaciones, para no duplicar filas
entre las dos fuentes (source='bitunix' = clave personal, mas preciso: trae comisiones y
funding exactos; source='bitunix_partner' = este robot, sin esos dos datos porque el Partner
API no los da por posicion - ver docs/bitunix-partner-api.md).

El saldo mensual (trade_journal_capital) SI se intenta guardar para TODOS los conectados, tengan
o no clave personal - es information independiente (cuanto tenian al principio del mes) y el
upsert con "ignore-duplicates" nunca pisa un valor que ya exista (puesto por este mismo robot
en una corrida anterior, o corregido a mano por el usuario).

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    BITUNIX_API_KEY
    BITUNIX_API_SECRET
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

import requests

import bitunix_api

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("sync_journal_partner")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BITUNIX_API_KEY = os.environ.get("BITUNIX_API_KEY", "")
BITUNIX_API_SECRET = os.environ.get("BITUNIX_API_SECRET", "")

CONNECTIONS_TABLE = "user_exchange_connections"
JOURNAL_SYNC_TABLE = "trade_journal_sync"
JOURNAL_CAPITAL_TABLE = "trade_journal_capital"
JOURNAL_TRADES_TABLE = "trade_journal_trades"
PARTNER_EXCHANGE = "bitunix_partner"


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _fetch_connected() -> list[dict]:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{CONNECTIONS_TABLE}",
        params={"select": "user_id,uid", "exchange": "eq.bitunix", "status": "eq.connected"},
        headers=_sb_headers(), timeout=20,
    )
    if resp.status_code != 200:
        log.warning(f"no se pudo leer conexiones conectadas ({resp.status_code}): {resp.text[:300]}")
        return []
    return resp.json()


def _fetch_personal_key_user_ids() -> set[str]:
    """Quienes ya tienen su propia clave de Bitunix conectada via trade-journal-sync - a esos
    no se les toca su Bitacora con el Partner API, solo el saldo mensual."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{JOURNAL_SYNC_TABLE}",
        params={"select": "user_id", "exchange": "eq.bitunix", "status": "eq.connected"},
        headers=_sb_headers(), timeout=20,
    )
    if resp.status_code != 200:
        log.warning(f"no se pudo leer quien tiene clave personal ({resp.status_code}): {resp.text[:300]}")
        return set()
    return {row["user_id"] for row in resp.json()}


def _fetch_last_sync(user_id: str) -> str | None:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{JOURNAL_SYNC_TABLE}",
        params={"select": "last_sync_at", "user_id": f"eq.{user_id}", "exchange": f"eq.{PARTNER_EXCHANGE}"},
        headers=_sb_headers(), timeout=20,
    )
    if resp.status_code != 200 or not resp.json():
        return None
    return resp.json()[0].get("last_sync_at")


def _upsert_sync_state(user_id: str, status: str, trades_synced: int, last_error: str | None) -> None:
    payload = {
        "user_id": user_id, "exchange": PARTNER_EXCHANGE, "status": status,
        "last_sync_at": datetime.now(timezone.utc).isoformat(), "last_error": last_error,
        "trades_synced": trades_synced,
    }
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{JOURNAL_SYNC_TABLE}?on_conflict=user_id,exchange",
        json=payload, headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
        timeout=20,
    )
    if resp.status_code >= 300:
        log.warning(f"no se pudo guardar el estado de sync de {user_id} ({resp.status_code}): {resp.text[:300]}")


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _iso(v) -> str | None:
    if not v:
        return None
    try:
        # Bitunix manda "yyyy-MM-ddTHH:mm:ssZ" - ya es ISO valido tal cual
        return str(v)
    except Exception:
        return None


def _side(raw) -> str:
    return "short" if str(raw or "").upper() in ("SELL", "SHORT") else "long"


def _map_closed(item: dict, user_id: str) -> dict:
    return {
        "user_id": user_id, "source": PARTNER_EXCHANGE, "external_id": str(item.get("positionId")),
        "symbol": str(item.get("pair") or "").upper(), "side": _side(item.get("side")),
        "status": "open" if str(item.get("status") or "").lower() == "open" else "closed",
        "leverage": _num(item.get("leverage")), "margin": None,
        "qty": _num(item.get("maxHeld")), "entry_price": _num(item.get("entryPrice")),
        "exit_price": _num(item.get("closePrice")), "pnl": _num(item.get("positionPnl")) or 0,
        "fees": 0, "funding": 0,  # el Partner API no los da por posicion - ver docs/bitunix-partner-api.md
        "opened_at": _iso(item.get("timeOpened")) or datetime.now(timezone.utc).isoformat(),
        "closed_at": _iso(item.get("timeClosed")) or datetime.now(timezone.utc).isoformat(),
    }


def _map_open(item: dict, user_id: str) -> dict:
    return {
        "user_id": user_id, "source": PARTNER_EXCHANGE, "external_id": str(item.get("positionId")),
        "symbol": str(item.get("pair") or "").upper(), "side": _side(item.get("side")),
        "status": "open",
        "leverage": _num(item.get("leverage")), "margin": _num(item.get("margin")),
        "qty": _num(item.get("amount")), "entry_price": _num(item.get("entryPrice")),
        "exit_price": None, "pnl": 0, "fees": 0, "funding": 0,
        "opened_at": _iso(item.get("timeOpened")) or datetime.now(timezone.utc).isoformat(),
        "closed_at": None,
    }


def _upsert_trades(rows: list[dict]) -> bool:
    if not rows:
        return True
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{JOURNAL_TRADES_TABLE}?on_conflict=user_id,source,external_id",
        json=rows, headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
        timeout=30,
    )
    if resp.status_code >= 300:
        log.warning(f"no se pudieron guardar operaciones ({resp.status_code}): {resp.text[:300]}")
        return False
    return True


def _delete_stale_open(user_id: str) -> None:
    requests.delete(
        f"{SUPABASE_URL}/rest/v1/{JOURNAL_TRADES_TABLE}",
        params={"user_id": f"eq.{user_id}", "source": f"eq.{PARTNER_EXCHANGE}", "status": "eq.open"},
        headers=_sb_headers(), timeout=20,
    )


def sync_trades(user_id: str, uid: str) -> int:
    now = datetime.now(timezone.utc)
    DAY_SECONDS = 86400
    last_sync = _fetch_last_sync(user_id)
    if last_sync:
        from_dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00")).timestamp() - 3 * DAY_SECONDS
    else:
        from_dt = now.timestamp() - 365 * DAY_SECONDS  # primera vez: el ultimo año

    rows: list[dict] = []
    cursor = from_dt
    while cursor < now.timestamp():
        window_end = min(cursor + 30 * DAY_SECONDS, now.timestamp())
        start_str = datetime.fromtimestamp(cursor, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = datetime.fromtimestamp(window_end, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        page = 1
        while True:
            result = bitunix_api.futures_positions_history_page(uid, start_str, end_str, page, BITUNIX_API_KEY, BITUNIX_API_SECRET)
            if result is None:
                raise RuntimeError(f"futuresPositionsHistory fallo para uid={uid}")
            items = result.get("items") or []
            rows.extend(_map_closed(it, user_id) for it in items)
            if len(items) < 100 or page * 100 >= int(result.get("total") or 0):
                break
            page += 1
        cursor = window_end

    page = 1
    while True:
        result = bitunix_api.futures_open_positions_page(uid, page, BITUNIX_API_KEY, BITUNIX_API_SECRET)
        if result is None:
            break  # sin posiciones abiertas no es un error fatal, simplemente no hay nada que agregar
        items = result.get("items") or []
        rows.extend(_map_open(it, user_id) for it in items)
        if len(items) < 100 or page * 100 >= int(result.get("total") or 0):
            break
        page += 1

    _delete_stale_open(user_id)
    for i in range(0, len(rows), 500):
        if not _upsert_trades(rows[i:i + 500]):
            raise RuntimeError(f"no se pudieron guardar operaciones para uid={uid}")
    return len(rows)


def snapshot_capital(user_id: str, uid: str) -> None:
    result = bitunix_api.total_asset_value(uid, BITUNIX_API_KEY, BITUNIX_API_SECRET)
    if result is None:
        log.warning(f"no se pudo leer el saldo de uid={uid}")
        return
    balance = _num(result.get("totalAssetValue"))
    if balance is None or balance <= 0:
        return
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{JOURNAL_CAPITAL_TABLE}?on_conflict=user_id,month",
        json={"user_id": user_id, "month": month, "starting_capital": balance},
        headers={**_sb_headers(), "Prefer": "resolution=ignore-duplicates,return=minimal"},
        timeout=20,
    )
    if resp.status_code >= 300:
        log.warning(f"no se pudo guardar el capital inicial de {user_id} ({resp.status_code}): {resp.text[:300]}")


def main() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)
    if not BITUNIX_API_KEY or not BITUNIX_API_SECRET:
        log.error("Faltan BITUNIX_API_KEY o BITUNIX_API_SECRET en el entorno.")
        sys.exit(1)

    connected = _fetch_connected()
    if not connected:
        log.info("sin usuarios conectados a Bitunix todavia")
        return
    personal_key_users = _fetch_personal_key_user_ids()

    had_error = False
    for conn in connected:
        user_id = conn.get("user_id")
        uid = str(conn.get("uid") or "").strip()
        if not user_id or not uid:
            continue

        snapshot_capital(user_id, uid)

        if user_id in personal_key_users:
            continue  # ya tiene su propia clave conectada - su Bitacora la llena trade-journal-sync

        try:
            n = sync_trades(user_id, uid)
            _upsert_sync_state(user_id, "connected", n, None)
            log.info(f"uid={uid}: {n} operacion(es) via Partner API")
        except Exception as e:
            had_error = True
            log.warning(f"fallo sincronizando uid={uid} via Partner API: {e}")
            _upsert_sync_state(user_id, "error", 0, str(e)[:300])

    if had_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
