"""
Guarda en Supabase (news_archive) los titulares que ya trae el Worker de noticias
(workers/rss-news/worker.js, categorías "crypto" y "macro") - para poder ver noticias de las
últimas 24h y BUSCAR noticias viejas, algo que antes no se podía: el Worker solo cachea 30 min y
el RSS de cada medio solo trae sus últimos 20-50 titulares, así que lo viejo desaparecía para
siempre sin dejar rastro.

Por qué le pide al Worker (no al RSS directo): el Worker ya hace todo el trabajo pesado (traduce
con Workers AI, arma el resumen corto + el resumen largo + detecta sentimiento) - pedirle lo
mismo otra vez al RSS crudo desde este script duplicaría esas llamadas a Workers AI sin necesidad
(y Juan preguntó explícitamente por el gasto de eso).

Por qué on_conflict=link con "ignore-duplicates" (NO "merge-duplicates"): una noticia que ya se
guardó una vez nunca se vuelve a sobreescribir en una corrida futura - sin esto, cada corrida le
pediría al Worker el resumen de las MISMAS noticias de siempre (siguen apareciendo en el RSS
hasta que el medio las empuja fuera) y, como el modelo de IA no da el mismo texto exacto dos
veces, el resumen guardado iría cambiando solo con el tiempo sin razón - además de gastar cupo de
Workers AI de más cada vez que el caché de 30 min del Worker expira entre corridas.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import logging
import os
import sys

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("update_news_archive")

NEWS_WORKER_URL = "https://skillcash-noticias.juanchodigital86.workers.dev"
CATEGORIES = ["crypto", "macro"]

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "news_archive"


def fetch_category(category):
    resp = requests.get(NEWS_WORKER_URL, params={"category": category}, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"Worker de noticias respondió {resp.status_code} para '{category}': {resp.text[:200]}")
    data = resp.json()
    items = data.get("items") or []
    filas = []
    for it in items:
        link = it.get("link")
        title = it.get("title")
        if not link or not title:
            continue
        published_at = None
        if it.get("publishedAt"):
            # publishedAt del Worker viene en milisegundos desde epoch (Date.now()/parse de JS)
            published_at = _ms_a_iso(it["publishedAt"])
        filas.append({
            "link": link,
            "title": title,
            "source": it.get("source"),
            "category": category,
            "published_at": published_at,
            "resumen": it.get("resumen"),
            "resumen_largo": it.get("resumenLargo"),
            "imagen": it.get("imagen"),
            "sentimiento": it.get("sentimiento"),
        })
    return filas


def _ms_a_iso(ms):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def guarda_en_supabase(filas):
    if not filas:
        return
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=link"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        # ignore-duplicates (no merge-duplicates): una fila con el mismo "link" que ya existe se
        # deja TAL CUAL estaba, nunca se pisa - ver explicación larga arriba
        "Prefer": "resolution=ignore-duplicates,return=minimal",
    }
    resp = requests.post(url, json=filas, headers=headers, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase respondió {resp.status_code}: {resp.text[:300]}")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)

    total = 0
    for category in CATEGORIES:
        log.info(f"Pidiendo titulares de '{category}' al Worker de noticias...")
        filas = fetch_category(category)
        log.info(f"{len(filas)} titulares de '{category}', guardando en Supabase ({TABLE})...")
        guarda_en_supabase(filas)
        total += len(filas)
    log.info(f"Listo. {total} titulares procesados (los que ya existían por 'link' no se tocaron).")


if __name__ == "__main__":
    main()
