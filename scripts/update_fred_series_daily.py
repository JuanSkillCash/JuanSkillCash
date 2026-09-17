"""
Actualizacion diaria de las series macroeconomicas de FRED en Supabase.

A diferencia del respaldo inicial (que trae TODO el historico), este script
solo pide un margen de los ultimos ~2 anos por serie - de sobra para agarrar
el dato nuevo del mes (o del dia, para las series diarias) y cualquier
revision que FRED le haga a un dato ya publicado, sin tener que re-descargar
decadas de historia cada dia.

De paso, revisa si en ese margen aparecio algun cambio nuevo en DFF (Fed
Funds Rate diaria) y, si lo hay, lo guarda como una decision nueva del FOMC.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    FRED_API_KEY
"""

import os
import sys
import logging
from datetime import date, timedelta

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_fred_daily")

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

FRED_SERIES = [
    "CPIAUCSL", "CPILFESL", "PAYEMS", "UNRATE", "DFF",
    "DGS10", "PCEPI", "PPIACO", "M2SL", "VIXCLS",
]
DAYS_MARGIN = 730  # ~2 anos de margen, para agarrar revisiones de datos ya publicados

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "fred_series_history"
FOMC_TABLE = "fomc_decisions"


def fetch_series(series_id: str, start: str) -> list[dict]:
    resp = requests.get(
        FRED_URL,
        params={"series_id": series_id, "api_key": FRED_API_KEY, "file_type": "json", "observation_start": start},
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"FRED respondio {resp.status_code}: {resp.text}")
    return resp.json().get("observations", [])


def rows_from_observations(series_id: str, observations: list[dict]) -> list[dict]:
    rows = []
    for obs in observations:
        if obs.get("value") in (None, "."):
            continue
        rows.append({"series_id": series_id, "date": obs["date"], "value": float(obs["value"])})
    return rows


def upsert_rows(table: str, conflict_cols: str, rows: list[dict]):
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={conflict_cols}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    resp = requests.post(url, json=rows, headers=headers, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text}")


def derive_fomc_decisions(dff_rows: list[dict]) -> list[dict]:
    ordered = sorted(dff_rows, key=lambda r: r["date"])
    decisions = []
    prev_value = None
    for row in ordered:
        if prev_value is not None and row["value"] != prev_value:
            decisions.append({"date": row["date"], "old_rate": prev_value, "new_rate": row["value"]})
        prev_value = row["value"]
    return decisions


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)
    if not FRED_API_KEY:
        log.error("Falta FRED_API_KEY en el entorno.")
        sys.exit(1)

    start = (date.today() - timedelta(days=DAYS_MARGIN)).isoformat()
    dff_rows = []
    ok, failed = [], []
    for series_id in FRED_SERIES:
        try:
            observations = fetch_series(series_id, start)
            rows = rows_from_observations(series_id, observations)
            if rows:
                upsert_rows(TABLE, "series_id,date", rows)
            ok.append((series_id, len(rows)))
            log.info(f"{series_id}: {len(rows)} datos subidos/actualizados")
            if series_id == "DFF":
                dff_rows = rows
        except Exception as e:
            failed.append((series_id, str(e)))
            log.error(f"{series_id}: FALLO -> {e}")

    if dff_rows:
        decisions = derive_fomc_decisions(dff_rows)
        if decisions:
            upsert_rows(FOMC_TABLE, "date", decisions)
            log.info(f"FOMC: {len(decisions)} decision(es) en el margen revisado")

    print("\n=== Resumen ===")
    for s, n in ok:
        print(f"OK   {s}: {n} datos")
    for s, err in failed:
        print(f"FAIL {s}: {err}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
