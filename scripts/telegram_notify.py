"""Envia un mensaje de Telegram a un chat_id puntual via el Bot API. Lo usa
watchlist_notify.py para avisarle por Telegram, ademas de la notificacion dentro del sitio,
a los usuarios que ya vincularon su cuenta (ver scripts/poll_telegram_links.py).

Nunca debe tumbar la corrida del robot que lo llama: una falla de red o un chat_id invalido
(la persona bloqueo el bot, por ejemplo) se registra como warning y se sigue de largo."""

from __future__ import annotations

import logging

import requests

log = logging.getLogger("telegram_notify")

TELEGRAM_API_TMPL = "https://api.telegram.org/bot{token}/{method}"


def send_telegram_message(bot_token: str, chat_id, text: str) -> bool:
    if not bot_token or not chat_id:
        return False
    try:
        resp = requests.post(
            TELEGRAM_API_TMPL.format(token=bot_token, method="sendMessage"),
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning(f"sendMessage a chat {chat_id} respondio {resp.status_code}: {resp.text[:300]}")
            return False
        return True
    except requests.RequestException as e:
        log.warning(f"fallo enviando a chat {chat_id}: {e}")
        return False
