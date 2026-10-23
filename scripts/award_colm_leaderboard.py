"""
Premia con Sharkoins al Top 10 del ranking del minijuego "Salto del Tiburón", semanal y
mensual (ver scripts/sql/create_colm_leaderboard.sql e index.html - pestañas de ranking dentro
del modal del juego).

Se ejecuta DESPUES de que el período ya terminó (nunca durante), por eso las fechas de corte se
calculan en Python con el período ANTERIOR al actual, no con "ahora mismo":
  - Semanal: corre el lunes a primera hora UTC, premia la semana ISO que recien termino
    (lunes 00:00 UTC -> el lunes siguiente 00:00 UTC, exclusivo).
  - Mensual: corre el dia 1 de cada mes a primera hora UTC, premia el mes calendario que
    recien termino.

La deduplicacion (para que un re-run, o que el workflow corra dos veces por error, nunca pague
doble) usa el mismo mecanismo del resto del sistema de Colmillos: el unique (user_id,
event_type, period_key) de user_colmillos_events, mas un upsert con "resolution=ignore-
duplicates" - si la fila ya existe, Postgres simplemente la ignora en vez de fallar o duplicar.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY

Uso:
    python scripts/award_colm_leaderboard.py weekly
    python scripts/award_colm_leaderboard.py monthly
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("award_colm_leaderboard")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

EVENTS_TABLE = "user_colmillos_events"

# premios por puesto - el 1ro se lleva mas, del 4to al 10mo todos ganan el mismo "premio de
# consolacion" por haber entrado al Top 10. Facil de ajustar: son solo estos dos diccionarios.
WEEKLY_REWARDS = {1: 50, 2: 35, 3: 25}
WEEKLY_REWARD_DEFAULT = 12  # puestos 4-10
MONTHLY_REWARDS = {1: 200, 2: 140, 3: 100}
MONTHLY_REWARD_DEFAULT = 50  # puestos 4-10


def reward_for_rank(period: str, rnk: int) -> int:
    table = WEEKLY_REWARDS if period == "weekly" else MONTHLY_REWARDS
    default = WEEKLY_REWARD_DEFAULT if period == "weekly" else MONTHLY_REWARD_DEFAULT
    return table.get(rnk, default)


def period_bounds(period: str, now: datetime) -> tuple[datetime, datetime, str]:
    """Devuelve (inicio, fin, etiqueta) del periodo YA TERMINADO, en UTC. `fin` es exclusivo."""
    if period == "weekly":
        # date.weekday(): lunes=0 ... domingo=6. "hoy" (el lunes en que corre el robot) menos
        # 7 dias nos deja parados en el lunes de la semana que recien termino.
        this_monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start = this_monday - timedelta(days=7)
        end = this_monday
        label = f"colm_weekly_rank_{start.date().isoformat()}"
        return start, end, label
    if period == "monthly":
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if this_month_start.month == 1:
            prev_month_start = this_month_start.replace(year=this_month_start.year - 1, month=12)
        else:
            prev_month_start = this_month_start.replace(month=this_month_start.month - 1)
        label = f"colm_monthly_rank_{prev_month_start.strftime('%Y-%m')}"
        return prev_month_start, this_month_start, label
    raise ValueError(f"periodo invalido: {period}")


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_top10(start: datetime, end: datetime) -> list[dict]:
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/get_colm_leaderboard_for_award",
        json={"p_start": start.isoformat(), "p_end": end.isoformat()},
        headers=_sb_headers(),
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"get_colm_leaderboard_for_award respondio {resp.status_code}: {resp.text[:400]}")
    return resp.json()


def award_rows(period: str, label: str, top10: list[dict]) -> list[dict]:
    event_type = "colm_weekly_rank" if period == "weekly" else "colm_monthly_rank"
    return [
        {
            "user_id": row["user_id"],
            "event_type": event_type,
            "period_key": label,
            "amount": reward_for_rank(period, row["rnk"]),
        }
        for row in top10
    ]


def upsert_ignore_duplicates(rows: list[dict]) -> None:
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/{EVENTS_TABLE}?on_conflict=user_id,event_type,period_key"
    headers = {**_sb_headers(), "Prefer": "resolution=ignore-duplicates,return=representation"}
    resp = requests.post(url, json=rows, headers=headers, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase respondio {resp.status_code} premiando el ranking: {resp.text[:500]}")
    inserted = len(resp.json()) if resp.text else 0
    log.info(f"{inserted} de {len(rows)} premios insertados (el resto ya estaba otorgado de una corrida anterior).")


def main() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)
    if len(sys.argv) < 2 or sys.argv[1] not in ("weekly", "monthly"):
        log.error("Uso: python scripts/award_colm_leaderboard.py weekly|monthly")
        sys.exit(1)
    period = sys.argv[1]

    now = datetime.now(timezone.utc)
    start, end, label = period_bounds(period, now)
    log.info(f"Premiando ranking {period} ({label}): {start.isoformat()} -> {end.isoformat()}")

    top10 = fetch_top10(start, end)
    if not top10:
        log.info("Nadie jugo en ese periodo - no hay nada que premiar.")
        return

    rows = award_rows(period, label, top10)
    for row, entry in zip(rows, top10):
        log.info(f"  #{entry['rnk']} {entry['username']} - puntaje {entry['score']} -> +{row['amount']} Sharkoins")
    upsert_ignore_duplicates(rows)


if __name__ == "__main__":
    main()
