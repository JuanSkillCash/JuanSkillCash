"""
Valida automaticamente las conexiones de Bitunix que quedaron "pending" en
user_exchange_connections (ver scripts/sql/create_user_exchange_connections.sql) - tanto las
de "me registro de cero con el link de Juan" como las de "ya tenia cuenta, pedi traslado
manual con captura" - usando el Partner API real de Bitunix (validateUser, ver
scripts/bitunix_api.py).

Si Bitunix confirma que el UID es un referido real de Juan (result.result == True), la
conexion pasa sola a "connected" - ya no hace falta que Juan la revise a mano. Si Bitunix dice
que NO lo es (result.result == False), se deja como estaba ("pending") en vez de rechazarla de
una: quizas la persona todavia esta esperando a que soporte de Bitunix complete el traslado de
su cuenta existente, o se demoro en darle Start al registro. Nunca se auto-rechaza una
conexion - eso lo sigue haciendo Juan a mano si hace falta.

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
log = logging.getLogger("update_bitunix_connections")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BITUNIX_API_KEY = os.environ.get("BITUNIX_API_KEY", "")
BITUNIX_API_SECRET = os.environ.get("BITUNIX_API_SECRET", "")

CONNECTIONS_TABLE = "user_exchange_connections"


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _fetch_pending() -> list[dict]:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{CONNECTIONS_TABLE}",
        params={"select": "user_id,uid", "exchange": "eq.bitunix", "status": "eq.pending"},
        headers=_sb_headers(), timeout=20,
    )
    if resp.status_code != 200:
        log.warning(f"no se pudo leer conexiones pendientes ({resp.status_code}): {resp.text[:300]}")
        return []
    return resp.json()


def _mark_connected(user_id: str) -> bool:
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{CONNECTIONS_TABLE}",
        params={"user_id": f"eq.{user_id}", "exchange": "eq.bitunix"},
        json={"status": "connected", "reviewed_at": datetime.now(timezone.utc).isoformat()},
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        timeout=20,
    )
    return resp.status_code < 300


def main() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)
    if not BITUNIX_API_KEY or not BITUNIX_API_SECRET:
        log.error("Faltan BITUNIX_API_KEY o BITUNIX_API_SECRET en el entorno.")
        sys.exit(1)

    pending = _fetch_pending()
    if not pending:
        log.info("sin conexiones pendientes de Bitunix")
        return

    promoted = 0
    still_pending = 0
    failed = 0
    for row in pending:
        uid = str(row.get("uid") or "").strip()
        user_id = row.get("user_id")
        if not uid or not user_id:
            continue
        result = bitunix_api.validate_user(uid, BITUNIX_API_KEY, BITUNIX_API_SECRET)
        if result is None:
            failed += 1
            continue
        if result.get("result") is True:
            if _mark_connected(user_id):
                promoted += 1
            else:
                failed += 1
        else:
            still_pending += 1

    log.info(f"{len(pending)} pendiente(s) revisado(s): {promoted} conectado(s), {still_pending} siguen pendientes, {failed} fallo(s)")


if __name__ == "__main__":
    main()
