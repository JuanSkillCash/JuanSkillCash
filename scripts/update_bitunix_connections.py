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

Cuando se promueve a "connected" se avisa de dos formas (ver scripts/sql/
bitunix_approval_notify.sql): SIEMPRE una fila en user_notifications (la campanita del sitio),
y ADEMAS por Telegram si la persona marco "avisame por Telegram" al pedir la conexion Y ya
tiene su Telegram vinculado (user_telegram_links.chat_id) - igual que
scripts/watchlist_notify.py. Ninguno de los dos avisos puede tumbar la corrida: si fallan, se
deja un warning y se sigue (la conexion ya quedo "connected" de todas formas, eso es lo que
importa).

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    BITUNIX_API_KEY
    BITUNIX_API_SECRET
Opcional:
    TELEGRAM_BOT_TOKEN (si falta, simplemente no se manda el aviso de Telegram)
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

import requests

import bitunix_api
from telegram_notify import send_telegram_message

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_bitunix_connections")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BITUNIX_API_KEY = os.environ.get("BITUNIX_API_KEY", "")
BITUNIX_API_SECRET = os.environ.get("BITUNIX_API_SECRET", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

CONNECTIONS_TABLE = "user_exchange_connections"
NOTIFICATIONS_TABLE = "user_notifications"
TELEGRAM_LINKS_TABLE = "user_telegram_links"

APPROVAL_TITLE = "Tu cuenta de Bitunix ya quedó verificada — ya puedes usar las herramientas de Rango de Manada."
APPROVAL_TELEGRAM_TEXT = (
    "🎉 ¡Felicidades!\n\n"
    "Tu cuenta de Bitunix ya quedó verificada — ya puedes usar las herramientas de Rango de Manada "
    "en juanskillcash.com."
)


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _fetch_pending() -> list[dict]:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{CONNECTIONS_TABLE}",
        params={"select": "user_id,uid,notify_telegram", "exchange": "eq.bitunix", "status": "eq.pending"},
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


def _notify_in_app(user_id: str) -> None:
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{NOTIFICATIONS_TABLE}?on_conflict=user_id,source_url",
        json={
            "user_id": user_id, "kind": "bitunix_approved", "radar": "bitunix",
            "exchange": "bitunix", "title": APPROVAL_TITLE, "source_url": "bitunix-approval",
        },
        # ignore-duplicates: si este robot vuelve a correr sobre el mismo usuario (no deberia,
        # ya quedo "connected", pero por si acaso) no duplica el aviso
        headers={**_sb_headers(), "Prefer": "resolution=ignore-duplicates,return=minimal"},
        timeout=20,
    )
    if resp.status_code >= 300:
        log.warning(f"no se pudo crear la notificacion en el sitio para {user_id} ({resp.status_code}): {resp.text[:300]}")


def _notify_telegram_if_opted_in(user_id: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        return
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{TELEGRAM_LINKS_TABLE}",
        params={"select": "chat_id", "user_id": f"eq.{user_id}", "chat_id": "not.is.null"},
        headers=_sb_headers(), timeout=20,
    )
    if resp.status_code != 200 or not resp.json():
        return
    chat_id = resp.json()[0].get("chat_id")
    send_telegram_message(TELEGRAM_BOT_TOKEN, chat_id, APPROVAL_TELEGRAM_TEXT)


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
                _notify_in_app(user_id)
                if row.get("notify_telegram"):
                    _notify_telegram_if_opted_in(user_id)
            else:
                failed += 1
        else:
            still_pending += 1

    log.info(f"{len(pending)} pendiente(s) revisado(s): {promoted} conectado(s), {still_pending} siguen pendientes, {failed} fallo(s)")


if __name__ == "__main__":
    main()
