#!/usr/bin/env bash
# Registra (o quita) el webhook de Telegram que reemplaza al polling de
# scripts/poll_telegram_links.py. Se corre a MANO, una sola vez (y de nuevo si alguna vez
# cambia la URL del proyecto de Supabase o el secreto).
#
# getUpdates (lo que usa poll_telegram_links.py) y un webhook activo son mutuamente
# excluyentes: mientras el webhook este registrado, getUpdates del MISMO bot responde
# 409 Conflict - por eso hay que borrar poll-telegram-links.yml y el paso que llama a
# poll_telegram_links.py en los robots horarios ANTES o justo despues de registrar esto.
#
# Variables de entorno requeridas (no se piden por flag para no dejarlas en el historial
# de la shell con `history`; exportalas en la terminal antes de correr el script):
#   TELEGRAM_BOT_TOKEN       - el mismo token que ya usan los robots de GitHub Actions
#   TELEGRAM_WEBHOOK_SECRET  - el mismo valor que se puso en Edge Functions > Secrets de
#                              la funcion telegram-webhook (32+ caracteres, solo A-Za-z0-9_-)
#   SUPABASE_PROJECT_REF     - el ID del proyecto de Supabase (el subdominio antes de
#                              ".supabase.co", Project Settings > General > Reference ID)
#
# Uso:
#   ./scripts/set_telegram_webhook.sh set       (registra el webhook - uso normal)
#   ./scripts/set_telegram_webhook.sh info       (consulta el estado actual sin cambiar nada)
#   ./scripts/set_telegram_webhook.sh delete     (rollback: vuelve a habilitar getUpdates/polling)

set -euo pipefail

ACTION="${1:-}"
if [[ "$ACTION" != "set" && "$ACTION" != "info" && "$ACTION" != "delete" ]]; then
  echo "Uso: $0 {set|info|delete}" >&2
  exit 1
fi

: "${TELEGRAM_BOT_TOKEN:?Falta exportar TELEGRAM_BOT_TOKEN}"

API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"

if [[ "$ACTION" == "info" ]]; then
  echo "Consultando getWebhookInfo..."
  curl -sS "${API}/getWebhookInfo" | python3 -m json.tool
  exit 0
fi

if [[ "$ACTION" == "delete" ]]; then
  echo "Borrando el webhook (esto vuelve a habilitar getUpdates/poll_telegram_links.py)..."
  curl -sS -X POST "${API}/deleteWebhook" -d "drop_pending_updates=false" | python3 -m json.tool
  echo
  echo "Listo. Si vas a volver al polling de verdad, recuerda restaurar"
  echo "poll-telegram-links.yml y el paso en los robots horarios desde el historial de git."
  exit 0
fi

: "${TELEGRAM_WEBHOOK_SECRET:?Falta exportar TELEGRAM_WEBHOOK_SECRET}"
: "${SUPABASE_PROJECT_REF:?Falta exportar SUPABASE_PROJECT_REF}"

WEBHOOK_URL="https://${SUPABASE_PROJECT_REF}.supabase.co/functions/v1/telegram-webhook"

echo "Registrando webhook en: ${WEBHOOK_URL}"
# drop_pending_updates=false: cualquier /start que haya quedado pendiente mientras se
# desplegaba la funcion se entrega igual al webhook en vez de perderse
curl -sS -X POST "${API}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"${WEBHOOK_URL}\",\"secret_token\":\"${TELEGRAM_WEBHOOK_SECRET}\",\"allowed_updates\":[\"message\"],\"drop_pending_updates\":false}" \
  | python3 -m json.tool

echo
echo "Verificando con getWebhookInfo (la 'url' debe ser la de arriba, 'pending_update_count'"
echo "deberia bajar a 0 en un rato y no deberia haber 'last_error_message' reciente):"
curl -sS "${API}/getWebhookInfo" | python3 -m json.tool
