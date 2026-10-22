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
log = logging.getLogger("update_bitunix_volume")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BITUNIX_API_KEY = os.environ.get("BITUNIX_API_KEY", "")
BITUNIX_API_SECRET = os.environ.get("BITUNIX_API_SECRET", "")

CONNECTIONS_TABLE = "user_exchange_connections"
VOLUME_TABLE = "user_exchange_volume"

# limites del mes en curso (decidido con Juan: el rango se reinicia cada mes)
RANK_THRESHOLDS_USD = [
    ("alfa", 500_000),
    ("depredador", 150_000),
    ("cazador", 50_000),
    ("explorador", 10_000),
]


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

    rows = []
    for conn in connected:
        uid = str(conn.get("uid") or "").strip()
        user_id = conn.get("user_id")
        if not uid or not user_id:
            continue
        item = by_uid.get(uid)
        trade_count = int(item.get("tradeCnt") or 0) if item else 0
        volume_usd = float(item.get("tradeAmount") or 0) if item else 0.0
        rows.append({
            "user_id": user_id,
            "exchange": "bitunix",
            "uid": uid,
            "month": month_label,
            "trade_count": trade_count,
            "month_volume_usd": volume_usd,
            "current_rank": _rank_for_volume(trade_count, volume_usd),
            "updated_at": now.isoformat(),
        })

    if _upsert_volume_rows(rows):
        log.info(f"volumen de {len(rows)} usuario(s) actualizado para {month_label}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
