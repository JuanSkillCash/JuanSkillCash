"""
LEGACY - ARCHIVADO, NO SE USA EN NINGUN WORKFLOW ACTUALMENTE.

Reemplazado por supabase/functions/telegram-webhook/index.ts (vinculacion al instante via
webhook, en vez de ir a preguntarle a Telegram cada rato). Este script usa getUpdates, que
Telegram responde con 409 Conflict mientras ese webhook este registrado (son mutuamente
excluyentes) - asi que NO sirve como "respaldo" corriendolo junto al webhook, fallaria
siempre. Solo se podria volver a usar despues de correr
`./scripts/set_telegram_webhook.sh delete` (ver ese script) para quitar el webhook y volver
a habilitar getUpdates.

Se deja aca por si algun dia hace falta volver al polling. Historial de donde vivia antes:
scripts/poll_telegram_links.py, llamado desde .github/workflows/poll-telegram-links.yml
(cron cada 5 min, que en la practica nunca se disparaba solo segun el historial real de
Actions) y como paso final de los robots horarios de deslistados/nuevos listados.

--- docstring original ---
Vincula cuentas del sitio con chats de Telegram. No hay un servidor propio escuchando en
vivo los mensajes del bot (todo este proyecto corre por robots en GitHub Actions, sin
servidor permanente), asi que esto se corria periodicamente y revisaba que mensajes nuevos le
llegaron al bot desde la ultima vez (Telegram "getUpdates" con un offset guardado en
Supabase, tabla telegram_poll_state - sin eso, cada corrida volveria a leer los mismos
mensajes viejos).

Flujo: el usuario pide un codigo en "Mi perfil" (fila en user_telegram_links con link_code,
chat_id aun null), abre t.me/<bot>?start=<codigo> y le da Start. Esto llega aca como un
mensaje "/start <codigo>" - si el codigo coincide con una fila pendiente, se guarda el
chat_id de quien escribio y se marca linked_at. Un codigo que no matchea nada (typo, ya
usado, inventado) se ignora con un aviso de vuelta al usuario, nunca se crea nada solo.

Variables de entorno requeridas:
    TELEGRAM_BOT_TOKEN
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("poll_telegram_links")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
LINKS_TABLE = "user_telegram_links"
STATE_TABLE = "telegram_poll_state"


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _send(chat_id, text: str) -> None:
    try:
        requests.post(
            TELEGRAM_API.format(token=BOT_TOKEN, method="sendMessage"),
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
    except requests.RequestException as e:
        log.warning(f"no se pudo responder al chat {chat_id}: {e}")


def _get_last_update_id() -> int:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{STATE_TABLE}",
        params={"id": "eq.1", "select": "last_update_id"},
        headers=_sb_headers(), timeout=20,
    )
    if resp.status_code == 200 and resp.json():
        return int(resp.json()[0]["last_update_id"])
    return 0


def _save_last_update_id(update_id: int) -> None:
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{STATE_TABLE}?on_conflict=id",
        json={"id": 1, "last_update_id": update_id},
        headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
        timeout=20,
    )
    if resp.status_code >= 300:
        log.warning(f"no se pudo guardar el cursor de Telegram ({resp.status_code}): {resp.text[:300]}")


def _find_pending_link(code: str) -> str | None:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{LINKS_TABLE}",
        params={"link_code": f"eq.{code}", "select": "user_id"},
        headers=_sb_headers(), timeout=20,
    )
    if resp.status_code == 200 and resp.json():
        return resp.json()[0]["user_id"]
    return None


def _complete_link(user_id: str, chat_id) -> bool:
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{LINKS_TABLE}",
        params={"user_id": f"eq.{user_id}"},
        json={"chat_id": chat_id, "linked_at": datetime.now(timezone.utc).isoformat()},
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        timeout=20,
    )
    return resp.status_code < 300


def main() -> None:
    if not BOT_TOKEN or not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan TELEGRAM_BOT_TOKEN, SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    # este script ahora tambien se llama como un paso mas al final de los robots horarios
    # (ver update_exchange_delistings.py / update_new_listings.py) porque el cron propio de
    # cada 5 min de este workflow nunca disparo solo ni una vez (confirmado revisando el
    # historial real) - una falla de red aca NUNCA debe tumbar esa corrida, que ya subio
    # datos reales del radar antes de llegar a esto
    try:
        _poll_once()
    except requests.RequestException as e:
        log.warning(f"fallo revisando mensajes de Telegram, se sigue de largo: {e}")


def _poll_once() -> None:
    last_update_id = _get_last_update_id()
    resp = requests.get(
        TELEGRAM_API.format(token=BOT_TOKEN, method="getUpdates"),
        params={"offset": last_update_id + 1, "timeout": 0},
        timeout=20,
    )
    if resp.status_code != 200:
        log.warning(f"getUpdates respondio {resp.status_code}: {resp.text[:300]}")
        return
    updates = resp.json().get("result", [])
    if not updates:
        log.info("sin mensajes nuevos")
        return

    max_update_id = last_update_id
    linked = 0
    for u in updates:
        max_update_id = max(max_update_id, u.get("update_id", max_update_id))
        msg = u.get("message") or {}
        text = (msg.get("text") or "").strip()
        chat_id = (msg.get("chat") or {}).get("id")
        if not chat_id or not text.startswith("/start"):
            continue
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            _send(
                chat_id,
                "👋 ¡Hola! Soy el bot de avisos de SkillCash Tools.\n\n"
                "Para conectarte, entra a juanskillcash.com → inicia sesión → Mi perfil → "
                "\"Conectar Telegram\". Desde ahí te traigo de vuelta aquí con el link correcto.",
            )
            continue
        code = parts[1].strip()
        user_id = _find_pending_link(code)
        if not user_id:
            _send(chat_id, "⚠️ Ese código no es válido o ya se usó. Genera uno nuevo en Mi perfil del sitio (juanskillcash.com).")
            continue
        if _complete_link(user_id, chat_id):
            linked += 1
            _send(
                chat_id,
                "✅ ¡Cuenta conectada! A partir de ahora te aviso aquí cuando una moneda de tu "
                "Mi Lista aparezca en el Radar de Deslistados o de Nuevos Listados.\n\n"
                "Para dejar de seguir alguna, hazlo desde el mismo radar en juanskillcash.com.",
            )
        else:
            _send(chat_id, "No se pudo completar la conexión. Intenta de nuevo en unos minutos.")

    _save_last_update_id(max_update_id)
    log.info(f"{len(updates)} mensaje(s) revisado(s), {linked} vinculo(s) nuevo(s)")


if __name__ == "__main__":
    main()
