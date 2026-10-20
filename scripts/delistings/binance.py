"""Binance: el feed de anuncios no esta en el HTML de la pagina ni documentado
publicamente - la investigacion solo pudo inferir el endpoint interno (bapi) desde
repos de terceros, sin ver una respuesta real (robots.txt bloqueo la herramienta usada
alli). Se prueba aca mismo contra el runner de GitHub Actions; si el endpoint principal
(catalogId=161, categoria "Delisting") falla, se cae a un feed general sin filtro de
categoria y se filtra por palabras clave en el titulo."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from .common import (
    Row, DEFAULT_HEADERS, extract_delist_date_from_body, extract_tickers, detect_market,
    is_noise, html_to_text, parse_delist_datetime,
)

log = logging.getLogger("delistings.binance")

EXCHANGE = "binance"
CATALOG_ID = "161"  # categoria "Delisting", confirmada en la investigacion (la pagina web)
LIST_URL = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
GENERAL_FEED_URL = "https://www.binance.com/bapi/composite/v1/public/market/notice/get"
DETAIL_URL_TMPL = "https://www.binance.com/en/support/announcement/detail/{code}"

_DELIST_WORDS = ("delist",)


def _epoch_ms_to_dt(s) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _fetch_article_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[binance] articulo {url} respondio {resp.status_code}")
            return ""
        return html_to_text(resp.text)
    except requests.RequestException as e:
        log.warning(f"[binance] fallo trayendo articulo {url}: {e}")
        return ""


def _fetch_catalog_pages(max_pages: int) -> list[dict]:
    items = []
    page = 1
    total = None
    while page <= max_pages and (total is None or len(items) < total):
        params = {"type": 1, "catalogId": CATALOG_ID, "pageNo": page, "pageSize": 20}
        resp = requests.get(LIST_URL, params=params, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[binance] catalogo {CATALOG_ID} pagina {page} respondio {resp.status_code}: {resp.text[:300]}")
            return items
        payload = resp.json()
        data = payload.get("data") or {}
        catalogs = data.get("catalogs") or []
        if not catalogs:
            return items
        cat = catalogs[0]
        total = cat.get("total", 0)
        batch = cat.get("articles") or []
        if not batch:
            break
        items.extend(batch)
        page += 1
        if page <= max_pages:
            time.sleep(1)
    return items


def _fetch_general_feed(max_pages: int) -> list[dict]:
    items = []
    for page in range(1, max_pages + 1):
        params = {"page": page, "rows": 20}
        resp = requests.get(GENERAL_FEED_URL, params=params, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[binance] feed general pagina {page} respondio {resp.status_code}: {resp.text[:300]}")
            break
        payload = resp.json()
        batch = ((payload.get("data") or {}).get("catalogs") or [{}])[0].get("articles") \
            if isinstance(payload.get("data"), dict) else None
        if batch is None:
            # estructura distinta a la del catalogo - probar data directo como lista
            batch = payload.get("data") if isinstance(payload.get("data"), list) else []
        if not batch:
            break
        filtered = [a for a in batch if any(w in (a.get("title", "") or "").lower() for w in _DELIST_WORDS)]
        items.extend(filtered)
        time.sleep(1)
    return items


def fetch(max_pages: int = 5) -> list[Row]:
    items = _fetch_catalog_pages(max_pages)
    source = "catalogId=161"
    if not items:
        log.info("[binance] catalogId=161 no devolvio nada, probando feed general con filtro de titulo")
        items = _fetch_general_feed(max_pages)
        source = "feed general filtrado"

    log.info(f"[binance] {len(items)} anuncios ({source})")
    rows: list[Row] = []

    for item in items:
        title = (item.get("title") or "").strip()
        if not title or is_noise(title):
            continue
        code = item.get("code")
        url = DETAIL_URL_TMPL.format(code=code) if code else ""
        announced_at = _epoch_ms_to_dt(item.get("releaseDate"))

        body_text = _fetch_article_text(url) if url else ""
        delist_at = extract_delist_date_from_body(body_text, announced_at) if body_text else None
        if delist_at is None:
            delist_at = parse_delist_datetime(title)

        market = detect_market(title)
        tickers = extract_tickers(title)
        if not tickers:
            log.warning(f"[binance] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url or f"binance:{code}", title=title,
                announced_at=announced_at, delist_at=delist_at, market=market,
            ))
        time.sleep(0.4)

    log.info(f"[binance] {len(rows)} filas")
    return rows
