"""
Respaldo UNICO (correr una sola vez, vía el workflow) del historico completo de STH-MVRV
(Short-Term Holder MVRV) y STH Realized Price de Bitcoin.

Fuente principal: Bitview / Bitcoin Research Kit (bitview.space), un API REST gratuito,
autoalojado por la comunidad, calculado desde un nodo Bitcoin Core propio (ver
https://github.com/bitcoinresearchkit/brk). Da la historia COMPLETA desde el genesis de
Bitcoin en una sola llamada por serie (sin paginar, sin API key, sin limite de tasa
documentado).

Las series se piden con el indice "day1" (un dia por punto), que viene como un arreglo
posicional (sin fechas explicitas) - el indice 0 corresponde al 2009-01-02. Esta fecha
ancla se confirmo cruzando el valor de un dia real contra bitcoin-data.com (ver mas abajo),
no es una suposicion: el indice 6474 dio sth_mvrv=1.160928, que coincide con el 1.16 que
bitcoin-data.com reporta para el 2026-09-24 (2009-01-02 + 6474 dias = 2026-09-24).

Fuente secundaria (solo para verificacion cruzada, columnas *_crosscheck): bitcoin-data.com
(BGeometrics), que expone el mismo indicador ya calculado (sth-mvrv, sth-realized-price) via
API REST gratuita sin token, pero el plan gratis solo da los ultimos ~4 anos de historia.
Sirve para confirmar que los numeros de Bitview tienen sentido, no reemplaza la fuente
principal.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys
import logging
from datetime import date, timedelta

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("backfill_sth_mvrv")

# indice 0 de la serie "day1" de Bitview - confirmado empiricamente (ver docstring), no es
# el genesis real de Bitcoin (2009-01-03), esta un dia antes
DAY1_EPOCH = date(2009, 1, 2)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "sth_mvrv_history"


def fetch_bitview_series(series_id: str) -> dict:
    """Trae la historia completa de una serie 'day1' de Bitview: {fecha: valor}, sin nulls."""
    url = f"https://bitview.space/api/series/{series_id}/day1"
    resp = requests.get(url, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Bitview respondio {resp.status_code} para {series_id}: {resp.text[:300]}")
    payload = resp.json()
    out = {}
    for i, value in enumerate(payload.get("data", [])):
        if value is None:
            continue
        d = DAY1_EPOCH + timedelta(days=i)
        out[d.isoformat()] = float(value)
    return out


def fetch_bgeometrics_series(path: str, value_key: str) -> dict:
    """Trae la ventana gratuita (~4 anos) de bitcoin-data.com para cruce de verificacion."""
    resp = requests.get(f"https://bitcoin-data.com/v1/{path}", timeout=30)
    if resp.status_code != 200:
        log.warning(f"bitcoin-data.com respondio {resp.status_code} para {path} (no bloquea el backfill)")
        return {}
    out = {}
    for row in resp.json():
        d = row.get("d")
        v = row.get(value_key)
        if d is None or v is None:
            continue
        out[d] = float(v)
    return out


def upsert_rows(rows: list[dict]):
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=date"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    # Supabase/PostgREST no acepta payloads enormes de una - se manda en lotes
    BATCH = 2000
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        resp = requests.post(url, json=batch, headers=headers, timeout=60)
        if resp.status_code >= 300:
            raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text[:500]}")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    log.info("Trayendo sth_realized_price de Bitview...")
    realized_price = fetch_bitview_series("sth_realized_price")
    log.info(f"{len(realized_price)} dias con sth_realized_price")

    log.info("Trayendo sth_mvrv de Bitview...")
    mvrv = fetch_bitview_series("sth_mvrv")
    log.info(f"{len(mvrv)} dias con sth_mvrv")

    log.info("Trayendo cruce de verificacion de bitcoin-data.com...")
    mvrv_cross = fetch_bgeometrics_series("sth-mvrv", "sthMvrv")
    realized_price_cross = fetch_bgeometrics_series("sth-realized-price", "sthRealizedPrice")
    log.info(f"{len(mvrv_cross)} dias de cruce para sth_mvrv, {len(realized_price_cross)} para sth_realized_price")

    all_dates = set(realized_price) | set(mvrv)
    rows = []
    for d in sorted(all_dates):
        rows.append({
            "date": d,
            "sth_realized_price": realized_price.get(d),
            "sth_mvrv": mvrv.get(d),
            "sth_realized_price_crosscheck": realized_price_cross.get(d),
            "sth_mvrv_crosscheck": mvrv_cross.get(d),
        })

    log.info(f"Subiendo {len(rows)} filas a Supabase...")
    upsert_rows(rows)
    log.info("Listo.")


if __name__ == "__main__":
    main()
