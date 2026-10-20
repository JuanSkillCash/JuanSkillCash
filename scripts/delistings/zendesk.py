"""Helper compartido por Bitunix y BingX (su centro de soporte corre sobre Zendesk Help
Center, misma API publica sin auth en ambos - confirmado en la investigacion)."""

from __future__ import annotations

import logging
import time

import requests

from .common import DEFAULT_HEADERS

log = logging.getLogger("delistings.zendesk")


def fetch_section_articles(base_url: str, section_id: str, locale: str, max_pages: int = 10) -> list[dict]:
    """Trae los articulos de una seccion de Zendesk Help Center, mas recientes primero.
    base_url ej "https://support.bitunix.com" o "https://bingxservice.zendesk.com"."""
    articles: list[dict] = []
    url = (
        f"{base_url}/api/v2/help_center/{locale}/sections/{section_id}/articles.json"
        f"?sort_by=created_at&sort_order=desc&per_page=100&page=1"
    )
    page = 0
    while url and page < max_pages:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"Zendesk {base_url} respondio {resp.status_code} en pagina {page + 1}: {resp.text[:300]}")
            break
        data = resp.json()
        batch = data.get("articles", [])
        articles.extend(batch)
        url = data.get("next_page")
        page += 1
        if url:
            time.sleep(1)  # 1 req/s, regla comun #7
    log.info(f"Zendesk {base_url}: {len(articles)} articulos traidos de la seccion {section_id}")
    return articles


def fetch_article_body(base_url: str, locale: str, article_id) -> str:
    """Solo se usa si la lista no trajo 'body' (BingX, segun la investigacion, puede
    requerir esta llamada aparte)."""
    url = f"{base_url}/api/v2/help_center/{locale}/articles/{article_id}.json"
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
    if resp.status_code != 200:
        log.warning(f"Zendesk {base_url} detalle {article_id} respondio {resp.status_code}")
        return ""
    return (resp.json().get("article") or {}).get("body", "") or ""
