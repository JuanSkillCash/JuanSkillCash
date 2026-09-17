"""
Respaldo UNICO (correr una sola vez a mano) del historico COMPLETO de las series
macroeconomicas de FRED (Federal Reserve Economic Data, del Banco de la Reserva
Federal de St. Louis) en Supabase.

Series que trae (todas oficiales y gratis via la API de FRED):
    CPIAUCSL  -> CPI (inflacion general)
    CPILFESL  -> Core CPI (inflacion nucleo)
    PAYEMS    -> Non-Farm Payrolls (nomina no agricola)
    UNRATE    -> Unemployment Rate (tasa de desempleo)
    DFF       -> Fed Funds Rate, version DIARIA (no la mensual FEDFUNDS) - se usa
                 la diaria porque de ahi se derivan despues las fechas exactas de
                 las decisiones del FOMC (cada cambio de valor = una decision)
    DGS10     -> 10-Year Treasury Yield
    PCEPI     -> PCE (gasto de consumo personal, la medida de inflacion que
                 mas mira la Fed)
    PPIACO    -> PPI (indice de precios al productor)
    M2SL      -> M2 Money Supply
    VIXCLS    -> VIX (indice de volatilidad)

De paso, a partir del historico de DFF ya subido, arma tambien el historico
completo de decisiones del FOMC (tabla fomc_decisions) - cada dia en que la
tasa cambio de un dia a otro es, por definicion, el dia de una decision.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    FRED_API_KEY   (gratis, se saca en https://fred.stlouisfed.org/docs/api/api_key.html)

Uso (una sola vez, desde tu maquina o donde tengas acceso a internet):
    export SUPABASE_URL="https://xxxxx.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="eyJ..."
    export FRED_API_KEY="tu-llave-de-fred"
    pip install requests
    python scripts/backfill_fred_series.py
"""

import os
import sys
import logging

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("backfill_fred")

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

FRED_SERIES = [
    "CPIAUCSL", "CPILFESL", "PAYEMS", "UNRATE", "DFF",
    "DGS10", "PCEPI", "PPIACO", "M2SL", "VIXCLS",
]

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "fred_series_history"
FOMC_TABLE = "fomc_decisions"
BATCH_SIZE = 1000


def fetch_series(series_id: str) -> list[dict]:
    resp = requests.get(
        FRED_URL,
        params={"series_id": series_id, "api_key": FRED_API_KEY, "file_type": "json"},
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"FRED respondio {resp.status_code}: {resp.text}")
    return resp.json().get("observations", [])


def rows_from_observations(series_id: str, observations: list[dict]) -> list[dict]:
    rows = []
    for obs in observations:
        # FRED usa "." para marcar un valor todavia no publicado/faltante
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
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        resp = requests.post(url, json=batch, headers=headers, timeout=30)
        if resp.status_code >= 300:
            raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text}")


def derive_fomc_decisions(dff_rows: list[dict]) -> list[dict]:
    """De la serie diaria de Fed Funds Rate (DFF), cada dia en que el valor
    cambia respecto al dia anterior es una decision del FOMC."""
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

    dff_rows = []
    ok, failed = [], []
    for series_id in FRED_SERIES:
        try:
            log.info(f"Descargando historico completo de {series_id}...")
            observations = fetch_series(series_id)
            rows = rows_from_observations(series_id, observations)
            if not rows:
                raise RuntimeError("FRED devolvio vacio")
            upsert_rows(TABLE, "series_id,date", rows)
            ok.append((series_id, len(rows)))
            log.info(f"{series_id}: {len(rows)} datos respaldados")
            if series_id == "DFF":
                dff_rows = rows
        except Exception as e:
            failed.append((series_id, str(e)))
            log.error(f"{series_id}: FALLO -> {e}")

    if dff_rows:
        decisions = derive_fomc_decisions(dff_rows)
        upsert_rows(FOMC_TABLE, "date", decisions)
        log.info(f"FOMC: {len(decisions)} decisiones historicas derivadas de DFF y respaldadas")

    print("\n=== Resumen ===")
    for s, n in ok:
        print(f"OK   {s}: {n} datos")
    for s, err in failed:
        print(f"FAIL {s}: {err}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
