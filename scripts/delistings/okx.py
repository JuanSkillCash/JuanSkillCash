"""OKX: API v5 oficial y publica (sin auth), annType=announcements-delistings. El JSON de
listado no trae la fecha exacta de deslistado -> hay que entrar al articulo (campo 'url')
y sacarla del cuerpo."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from .common import (
    Row, DEFAULT_HEADERS, extract_delist_date_from_body, extract_tickers, detect_market,
    is_noise, html_to_text,
)

log = logging.getLogger("delistings.okx")

EXCHANGE = "okx"
LIST_URL = "https://www.okx.com/api/v5/support/announcements"


def _epoch_ms_to_dt(s) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _fetch_article_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[okx] articulo {url} respondio {resp.status_code}")
            return ""
        return html_to_text(resp.text)
    except requests.RequestException as e:
        log.warning(f"[okx] fallo trayendo articulo {url}: {e}")
        return ""


def fetch(max_pages: int = 5) -> list[Row]:
    rows: list[Row] = []
    page = 1
    total_page = 1
    items = []
    while page <= total_page and page <= max_pages:
        resp = requests.get(
            LIST_URL, params={"annType": "announcements-delistings", "page": page},
            headers=DEFAULT_HEADERS, timeout=30,
        )
        if resp.status_code != 200:
            log.warning(f"[okx] listado pagina {page} respondio {resp.status_code}: {resp.text[:300]}")
            break
        payload = resp.json()
        if payload.get("code") != "0":
            log.warning(f"[okx] respuesta con code!=0: {payload.get('msg')}")
            break
        data = (payload.get("data") or [{}])[0]
        try:
            total_page = int(data.get("totalPage", 1))
        except (TypeError, ValueError):
            total_page = 1
        items.extend(data.get("details", []))
        page += 1
        if page <= total_page:
            time.sleep(1)

    log.info(f"[okx] {len(items)} anuncios en {page - 1} pagina(s) (totalPage={total_page})")

    for item in items:
        title = item.get("title", "")
        url = item.get("url", "")
        if not title or is_noise(title):
            continue
        announced_at = _epoch_ms_to_dt(item.get("businessPTime") or item.get("pTime"))

        body_text = _fetch_article_text(url) if url else ""
        delist_at = extract_delist_date_from_body(body_text, announced_at) if body_text else None
        if delist_at is None and body_text:
            # sin contexto spot/delist claro en el cuerpo, probar con el titulo como ultimo recurso
            from .common import parse_delist_datetime
            delist_at = parse_delist_datetime(title)

        market = detect_market(title)
        tickers = extract_tickers(title)
        if not tickers:
            log.warning(f"[okx] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title,
                announced_at=announced_at, delist_at=delist_at, market=market,
            ))
        time.sleep(0.5)  # una peticion extra por articulo (detalle) - no saturar

    log.info(f"[okx] {len(rows)} filas")
    return rows
