"""
Calcula el volumen de trading real (en USD) del MES EN CURSO de cada usuario ya conectado a
Bitunix (user_exchange_connections, status='connected'), y con eso su rango dentro de la
cajita "Rango de Manada" (ver docs/roadmap-plataforma-afiliados-tiers.md para los montos).

El rango se reinicia cada mes (decision de Juan: si no, con el tiempo todo el mundo termina en
Alfa sin seguir operando) - por eso esto NO acumula de por vida: cada corrida vuelve a sumar
desde el dia 1 del mes en curso (UTC) hasta ahora y pisa la fila completa con el total fresco.
Un mes nunca pasa de 31 dias, asi que siempre cabe en el limite de 180 dias por llamada que
tiene la API de Bitunix.

Usa un solo llamado a queryPnlAndTradeCnt (ver scripts/bitunix_api.py) que trae el volumen y
numero de operaciones de TODOS los referidos directos de Juan de una vez, en vez de un llamado
por usuario conectado - mucho mas eficiente y dentro del limite de 30 llamadas/10s de Bitunix
aunque haya muchos usuarios conectados.

Aviso por Telegram de subida de rango: se compara el current_rank que ya estaba guardado (de
ANTES de esta corrida) contra el recien calculado - si subio de verdad (y es el mismo mes, para
no confundir el reinicio mensual con una "bajada" de rango) se le manda un mensaje al chat_id
vinculado (user_telegram_links). Si no tiene Telegram conectado, simplemente no se le avisa por
ahi (sigue viendo el rango nuevo en la cajita del sitio igual). Un fallo mandando los avisos
nunca debe tumbar la corrida - el volumen/rango ya quedo guardado en Supabase antes de llegar
a esa parte.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    BITUNIX_API_KEY
    BITUNIX_API_SECRET
    TELEGRAM_BOT_TOKEN   (opcional - sin esto simplemente no se mandan los avisos de subida)
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

import requests

import bitunix_api

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_bitunix_volume")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BITUNIX_API_KEY = os.environ.get("BITUNIX_API_KEY", "")
BITUNIX_API_SECRET = os.environ.get("BITUNIX_API_SECRET", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

CONNECTIONS_TABLE = "user_exchange_connections"
VOLUME_TABLE = "user_exchange_volume"
VOLUME_HISTORY_TABLE = "user_exchange_volume_history"
TELEGRAM_LINKS_TABLE = "user_telegram_links"

# limites del mes en curso (decidido con Juan: el rango se reinicia cada mes)
RANK_THRESHOLDS_USD = [
    ("alfa", 500_000),
    ("depredador", 150_000),
    ("cazador", 50_000),
    ("explorador", 10_000),
]

# de menor a mayor - el indice en esta lista es lo que se compara para saber si de verdad
# "subio" de rango (nunca baja dentro del mismo mes, el volumen solo se acumula)
RANK_ORDER = ["sin_rango", "cria", "explorador", "cazador", "depredador", "alfa"]

RANK_PROMO_TEXT = {
    "cria": ("🐣", "Cría"),
    "explorador": ("🧭", "Explorador"),
    "cazador": ("🎯", "Cazador"),
    "depredador": ("🦈", "Depredador"),
    "alfa": ("👑", "Alfa"),
}


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


def _rank_for_volume(trade_count: int, volume_usd: float) -> str:
    if trade_count < 1:
        return "sin_rango"
    for rank, threshold in RANK_THRESHOLDS_USD:
        if volume_usd >= threshold:
            return rank
    return "cria"


def _upsert_volume_rows(rows: list[dict]) -> bool:
    if not rows:
        return True
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{VOLUME_TABLE}?on_conflict=user_id",
        json=rows,
        headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
        timeout=30,
    )
    if resp.status_code >= 300:
        log.warning(f"no se pudo guardar el volumen ({resp.status_code}): {resp.text[:300]}")
        return False
    return True


def _upsert_history_rows(rows: list[dict]) -> None:
    """Copia month/trade_count/month_volume_usd/current_rank en user_exchange_volume_history
    (ver scripts/sql/create_admin_dashboard.sql) para que el panel de admin pueda filtrar por
    mes - a diferencia de VOLUME_TABLE, esta tabla nunca se pisa entre meses distintos, solo
    se refresca la fila del mes en curso hasta que termina. Un fallo aca nunca debe tumbar la
    corrida: el volumen real ya quedo guardado en VOLUME_TABLE antes de llegar a esto."""
    if not rows:
        return
    history_rows = [{
        "user_id": r["user_id"],
        "month": r["month"],
        "trade_count": r["trade_count"],
        "month_volume_usd": r["month_volume_usd"],
        "current_rank": r["current_rank"],
        "updated_at": r["updated_at"],
    } for r in rows]
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{VOLUME_HISTORY_TABLE}?on_conflict=user_id,month",
        json=history_rows,
        headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
        timeout=30,
    )
    if resp.status_code >= 300:
        log.warning(f"no se pudo guardar el historial de volumen ({resp.status_code}): {resp.text[:300]}")


def _fetch_previous_ranks(user_ids: list[str]) -> dict[str, dict]:
    """Trae el month/current_rank que YA estaba guardado antes de esta corrida, para poder
    comparar despues contra el recien calculado y detectar una subida de rango real."""
    if not user_ids:
        return {}
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{VOLUME_TABLE}",
        params={"select": "user_id,month,current_rank", "user_id": f"in.({','.join(user_ids)})"},
        headers=_sb_headers(), timeout=20,
    )
    if resp.status_code != 200:
        log.warning(f"no se pudo leer el rango anterior ({resp.status_code}): {resp.text[:300]}")
        return {}
    return {row["user_id"]: row for row in resp.json()}


def _fetch_chat_ids(user_ids: list[str]) -> dict[str, int]:
    if not user_ids:
        return {}
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{TELEGRAM_LINKS_TABLE}",
        params={"select": "user_id,chat_id", "user_id": f"in.({','.join(user_ids)})", "chat_id": "not.is.null"},
        headers=_sb_headers(), timeout=20,
    )
    if resp.status_code != 200:
        log.warning(f"no se pudo leer los chat_id de telegram ({resp.status_code}): {resp.text[:300]}")
        return {}
    return {row["user_id"]: row["chat_id"] for row in resp.json()}


def _send_telegram(chat_id: int, text: str) -> None:
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        if resp.status_code >= 300:
            log.warning(f"telegram respondio {resp.status_code} mandando aviso de rango a {chat_id}: {resp.text[:200]}")
    except requests.RequestException as e:
        log.warning(f"fallo mandando aviso de rango por telegram a {chat_id}: {e}")


def _notify_promotions(promotions: list[dict]) -> None:
    """promotions: [{user_id, new_rank, volume_usd}] - ya filtrado para solo incluir subidas
    de rango reales dentro del mismo mes (ver main())."""
    if not promotions:
        return
    if not TELEGRAM_BOT_TOKEN:
        log.info(f"{len(promotions)} subida(s) de rango detectada(s), pero falta TELEGRAM_BOT_TOKEN - no se avisa por ahi")
        return

    chat_ids = _fetch_chat_ids([p["user_id"] for p in promotions])
    sent = 0
    for p in promotions:
        chat_id = chat_ids.get(p["user_id"])
        if not chat_id:
            continue
        emoji, label = RANK_PROMO_TEXT.get(p["new_rank"], ("🦈", p["new_rank"]))
        text = (
            f"{emoji} ¡Subiste de rango en la Manada! Ahora eres {label} en Bitunix.\n\n"
            f"Volumen de este mes: ${p['volume_usd']:,.0f} USD.\n\n"
            "Sigue operando para subir todavía más este mes — revisa tu progreso en "
            "juanskillcash.com → Mi perfil → Rango de Manada."
        )
        _send_telegram(chat_id, text)
        sent += 1
    log.info(f"{len(promotions)} subida(s) de rango detectada(s), {sent} aviso(s) de telegram mandado(s)")


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

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_label = now.strftime("%Y-%m")
    start_str = month_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    by_uid = bitunix_api.query_pnl_and_trade_cnt_all(start_str, end_str, BITUNIX_API_KEY, BITUNIX_API_SECRET)
    if by_uid is None:
        log.error("no se pudo leer el volumen del mes desde Bitunix - no se toca ninguna fila")
        sys.exit(1)

    user_ids = [c["user_id"] for c in connected if c.get("user_id")]
    previous = _fetch_previous_ranks(user_ids)

    rows = []
    promotions = []
    for conn in connected:
        uid = str(conn.get("uid") or "").strip()
        user_id = conn.get("user_id")
        if not uid or not user_id:
            continue
        item = by_uid.get(uid)
        trade_count = int(item.get("tradeCnt") or 0) if item else 0
        volume_usd = float(item.get("tradeAmount") or 0) if item else 0.0
        new_rank = _rank_for_volume(trade_count, volume_usd)
        rows.append({
            "user_id": user_id,
            "exchange": "bitunix",
            "uid": uid,
            "month": month_label,
            "trade_count": trade_count,
            "month_volume_usd": volume_usd,
            "current_rank": new_rank,
            "updated_at": now.isoformat(),
        })

        # subida de rango real: tenia fila de ESTE MISMO mes y el rango nuevo quedo mas
        # arriba en RANK_ORDER que el que tenia - si es el primer mes que se le calcula o
        # si lo que cambio fue el mes (reinicio mensual), nunca se avisa como "subida"
        prev = previous.get(user_id)
        if prev and prev.get("month") == month_label:
            prev_rank = prev.get("current_rank") or "sin_rango"
            if prev_rank in RANK_ORDER and new_rank in RANK_ORDER and RANK_ORDER.index(new_rank) > RANK_ORDER.index(prev_rank):
                promotions.append({"user_id": user_id, "new_rank": new_rank, "volume_usd": volume_usd})

    if _upsert_volume_rows(rows):
        log.info(f"volumen de {len(rows)} usuario(s) actualizado para {month_label}")
    else:
        sys.exit(1)

    try:
        _upsert_history_rows(rows)
    except Exception as e:
        log.warning(f"fallo guardando el historial de volumen: {e}")

    try:
        _notify_promotions(promotions)
    except Exception as e:
        # el volumen/rango ya quedo guardado arriba - un fallo mandando avisos nunca debe
        # hacer fallar la corrida completa
        log.warning(f"fallo procesando los avisos de subida de rango: {e}")


if __name__ == "__main__":
    main()
