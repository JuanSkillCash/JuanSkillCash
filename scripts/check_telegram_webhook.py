"""
Vigila que el webhook de Telegram (supabase/functions/telegram-webhook/index.ts) siga
registrado y sano. No hace nada mas que avisar por log si algo esta mal - nunca debe tumbar
el robot horario del que es un paso mas (continue-on-error en el workflow), porque ese robot
ya subio datos reales del radar antes de llegar a esto.

Revisa (via getWebhookInfo de la API de Telegram):
  - que la URL registrada sea realmente la de este proyecto de Supabase
  - que no haya un error reciente reportado por Telegram al intentar entregar un update
  - que no se esten acumulando updates sin entregar (pending_update_count)

Variables de entorno requeridas:
    TELEGRAM_BOT_TOKEN
    SUPABASE_URL   (se usa solo para construir la URL esperada del webhook, no se llama)
"""

import os
import sys
import logging

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("check_telegram_webhook")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")


def main() -> None:
    if not BOT_TOKEN or not SUPABASE_URL:
        log.warning("Faltan TELEGRAM_BOT_TOKEN o SUPABASE_URL en el entorno, no se puede revisar.")
        sys.exit(0)  # no es un fallo del robot, solo no hay con que validar

    expected_url = f"{SUPABASE_URL}/functions/v1/telegram-webhook"

    resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo", timeout=20)
    if resp.status_code != 200:
        log.warning(f"getWebhookInfo respondio {resp.status_code}: {resp.text[:300]}")
        sys.exit(0)

    info = resp.json().get("result", {})
    url = info.get("url", "")
    pending = info.get("pending_update_count", 0)
    last_error_message = info.get("last_error_message")
    last_error_date = info.get("last_error_date")

    if not url:
        log.error(
            "NO hay webhook registrado en Telegram - la vinculacion de Telegram NO esta "
            "funcionando en tiempo real ahora mismo. Correr ./scripts/set_telegram_webhook.sh set"
        )
        return

    if url != expected_url:
        log.error(f"El webhook registrado NO es el esperado. Esperado={expected_url} Actual={url}")

    if last_error_message:
        log.warning(f"Telegram reporto un error reciente entregando al webhook: {last_error_message} (fecha unix {last_error_date})")

    if pending and pending > 20:
        log.warning(f"Hay {pending} updates sin entregar acumulados - revisar si el webhook esta respondiendo a tiempo.")

    if url == expected_url and not last_error_message and (not pending or pending <= 20):
        log.info(f"Webhook de Telegram OK (url correcta, sin errores recientes, pending_update_count={pending}).")


if __name__ == "__main__":
    main()
