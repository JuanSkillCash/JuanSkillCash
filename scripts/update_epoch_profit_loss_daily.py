"""
Porcentaje del supply de BTC "en perdida" (comprado a mas del precio de hoy y que no se ha
movido desde entonces), separado por epoca de halving - version con datos reales y verificables
del equivalente a "Cycle Percent Supply in Profit" de checkonchain, pero usando las epocas reales
de halving en vez de los cortes de año propios (no publicados) de checkonchain:
    Epoca 0: genesis (03-ene-2009) -> bloque 210,000 (28-nov-2012)
    Epoca 1: 28-nov-2012 -> bloque 420,000 (09-jul-2016)
    Epoca 2: 09-jul-2016 -> bloque 630,000 (11-may-2020)
    Epoca 3: 11-may-2020 -> bloque 840,000 (20-abr-2024)
    Epoca 4: 20-abr-2024 -> hoy (epoca en curso)

Fuente: Bitview / Bitcoin Research Kit (bitview.space, bitcoinresearchkit/brk en GitHub) - mismo
API REST gratuito que ya usa update_sth_mvrv_daily.py. Confirmado en su codigo fuente publico
(bitview_client/__init__.py) que expone, por cada epoca N (0 a 4), tres series reales en BTC:
"epoch_N_supply" (supply total que sigue sin moverse desde esa epoca), "epoch_N_supply_in_profit"
y "epoch_N_supply_in_loss" - el porcentaje en perdida se calcula como in_loss/supply*100 aqui
mismo, no viene precalculado. Validado con una corrida real (ver historial de Actions): a precio
de hoy, las epocas 0-3 estan en ~0% de perdida (monedas viejas, comprabas muy baratas) y la epoca
4 (la mas reciente, comprada a precios de $60K-120K+) es la unica con perdida significativa.

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
log = logging.getLogger("update_epoch_profit_loss_daily")

# mismo indice "day1" y misma fecha ancla que ya uso/confirmo update_sth_mvrv_daily.py para
# Bitview (el indice 0 de la serie corresponde al 2009-01-02)
DAY1_EPOCH = date(2009, 1, 2)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "epoch_profit_loss_daily"

EPOCHS = [0, 1, 2, 3, 4]


def fetch_bitview_series(series_id: str) -> dict:
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

    supply = {}
    in_loss = {}
    for n in EPOCHS:
        log.info(f"Trayendo epoch_{n}_supply / epoch_{n}_supply_in_loss de Bitview...")
        supply[n] = fetch_bitview_series(f"epoch_{n}_supply")
        in_loss[n] = fetch_bitview_series(f"epoch_{n}_supply_in_loss")
        log.info(f"  epoca {n}: {len(supply[n])} dias de supply, {len(in_loss[n])} dias de in_loss")

    all_dates = set()
    for n in EPOCHS:
        all_dates |= set(supply[n])

    rows = []
    for d in sorted(all_dates):
        row = {"date": d}
        for n in EPOCHS:
            s = supply[n].get(d)
            l = in_loss[n].get(d)
            row[f"epoch{n}_supply_btc"] = s
            row[f"epoch{n}_pct_in_loss"] = round(l / s * 100, 4) if (s and s > 0 and l is not None) else None
        rows.append(row)

    log.info(f"Subiendo {len(rows)} filas a Supabase...")
    upsert_rows(rows)
    log.info(f"{len(rows)} dias actualizados a partir de 5 epocas de halving")


if __name__ == "__main__":
    main()
