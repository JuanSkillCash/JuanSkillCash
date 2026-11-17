"""
Refresca la copia de Forex Factory (horario/importancia/previsión/anterior) del calendario
económico, guardándola en Supabase en vez de en el KV del Worker de Cloudflare.

Por qué existe: el Worker (workers/economic-calendar/worker.js) refrescaba esto él mismo cada
30 min con un Cron Trigger, pidiéndole el JSON a Forex Factory directo desde Cloudflare. Desde
el 17-nov-2026 ~4:30am UTC, Forex Factory empezó a devolver 429 (demasiadas peticiones) a esas
peticiones de forma sostenida - probablemente porque las IPs de salida de Cloudflare Workers son
compartidas entre miles de clientes, y Forex Factory le puso un límite a ese rango completo (no
es nuestro propio tráfico el que lo causa: una sola petición cada 30 min, desde SIEMPRE, nunca
había sido el problema). Las IPs de los runners de GitHub Actions son un rango totalmente
distinto, así que mover el refresco para acá esquiva ese límite específico.

Este script hace EXACTAMENTE la misma transformación que antes hacía `obtenerDeForexFactory()`
en el Worker (mismo hash de id, misma traducción de títulos) y deja el resultado en una tabla de
una sola fila (economic_calendar_ff_cache, id=1, lectura pública vía RLS) que el Worker ahora lee
en vez de su KV. El Worker conserva su lógica vieja (KV + fetch directo a Forex Factory) como
respaldo por si Supabase llegara a fallar - ver worker.js.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import logging
import os
import sys
from datetime import datetime, timezone

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_economic_calendar_ff")

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "economic_calendar_ff_cache"

# misma lista que TRADUCCIONES en worker.js - mantener las dos en sync si se agrega una
TRADUCCIONES = [
    ("core inflation rate mom", "IPC subyacente m/m"),
    ("core cpi", "IPC subyacente m/m"),
    ("inflation rate mom", "IPC m/m"),
    ("cpi", "IPC m/m"),
    ("ppi mom", "IPP m/m"),
    ("retail sales mom", "Ventas minoristas m/m"),
    ("initial jobless claims", "Peticiones de subsidio por desempleo"),
    ("unemployment claims", "Peticiones de subsidio por desempleo"),
    ("non farm payrolls", "Nóminas no agrícolas"),
    ("non-farm employment change", "Nóminas no agrícolas"),
    ("nonfarm payrolls", "Nóminas no agrícolas"),
    ("unemployment rate", "Tasa de desempleo"),
    ("fed interest rate decision", "Decisión de tipos de la Fed"),
    ("federal funds rate", "Tasa de fondos federales"),
    ("existing home sales", "Ventas de viviendas de segunda mano"),
    ("housing starts", "Inicios de viviendas"),
    ("building permits", "Permisos de construcción"),
    ("gdp growth rate", "PIB"),
    ("ecb interest rate decision", "Decisión de tipos del BCE"),
    ("crude oil inventories", "Inventarios de petróleo crudo"),
]

IMPACT_MAP = {"Low": 1, "Medium": 2, "High": 3}


def traduce_evento(titulo_ingles):
    clave = str(titulo_ingles or "").strip().lower()
    for ing, es in TRADUCCIONES:
        if ing in clave:
            return es
    return titulo_ingles


def to_num(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def format_valor_ff(texto):
    if texto is None or texto == "":
        return None
    return str(texto).replace(".", ",")


def hash_corto(s):
    # mismo algoritmo que hashCorto() en worker.js (h = h*31 + charCode, entero de 32 bits con
    # signo via overflow) - no hace falta que coincida bit a bit con lo que generaba el Worker
    # antes (esta tabla reemplaza esa fuente por completo), pero se porta igual para que el id
    # de un mismo evento no cambie de una corrida a otra de ESTE script
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return format(h & 0xFFFFFFFF, "x")


def fetch_forex_factory():
    resp = requests.get(FF_URL, headers={"User-Agent": UA}, timeout=20)
    if resp.status_code >= 300:
        raise RuntimeError(f"Forex Factory respondió {resp.status_code}: {resp.text[:200]}")
    items = resp.json()
    if not isinstance(items, list):
        raise RuntimeError("Forex Factory no devolvió una lista")

    eventos = []
    for it in items:
        es_feriado = it.get("impact") == "Holiday"
        prevision_num = to_num(_quita_sufijos(it.get("forecast")))
        anterior_num = to_num(_quita_sufijos(it.get("previous")))
        titulo = it.get("title")
        fecha_iso = it.get("date")
        # misma fecha que new Date(it.date).toISOString() en JS
        fecha_utc = datetime.fromisoformat(fecha_iso).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        eventos.append({
            "id": "ff-" + hash_corto(f"{titulo}|{fecha_iso}"),
            "fechaUTC": fecha_utc,
            "divisa": it.get("country") or "",
            "pais": it.get("country") or "",
            "importancia": 1 if es_feriado else IMPACT_MAP.get(it.get("impact"), 1),
            "evento": titulo,
            "eventoES": traduce_evento(titulo),
            "actual": None,
            "prevision": format_valor_ff(it.get("forecast")),
            "anterior": format_valor_ff(it.get("previous")),
            "actualNum": None,
            "previsionNum": prevision_num,
            "anteriorNum": anterior_num,
            "tendencia": "neutral",
            "direccion": None,
            "unidad": "",
            "escala": "",
            "fuente": "Forex Factory",
            "fuenteActual": None,
            "consenso": None,
            "esFeriado": es_feriado,
        })
    return eventos


def _quita_sufijos(texto):
    if texto is None:
        return None
    out = str(texto)
    for ch in "%KMB":
        out = out.replace(ch, "").replace(ch.lower(), "")
    return out


def upsert_cache(eventos):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=id"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    row = {
        "id": 1,
        "eventos": eventos,
        "actualizado": datetime.now(timezone.utc).isoformat(),
    }
    resp = requests.post(url, json=row, headers=headers, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase respondió {resp.status_code}: {resp.text[:300]}")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    log.info("Descargando calendario de Forex Factory...")
    eventos = fetch_forex_factory()
    log.info(f"{len(eventos)} eventos descargados, guardando en Supabase ({TABLE})...")
    upsert_cache(eventos)
    log.info("Listo.")


if __name__ == "__main__":
    main()
