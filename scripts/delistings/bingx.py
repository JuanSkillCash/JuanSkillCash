"""BingX: centro de soporte tambien en Zendesk, pero en el dominio real del backend
(bingxservice.zendesk.com, no bingx.zendesk.com - confirmado en la investigacion), locale
en-001. Seccion "Delisting" con 716 articulos."""

from __future__ import annotations

import logging
from datetime import datetime

from . import zendesk
from .common import (
    Row, extract_delist_date_from_body, extract_tickers, extract_tickers_from_body,
    detect_market, is_noise, classify_asset_class,
)

log = logging.getLogger("delistings.bingx")

EXCHANGE = "bingx"
BASE_URL = "https://bingxservice.zendesk.com"
SECTION_ID = "11257015847311"
LOCALE = "en-001"
PUBLIC_URL_TMPL = "https://bingx.com/en/support/articles/{id}/"


def _parse_created_at(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch(max_pages: int = 8) -> list[Row]:
    articles = zendesk.fetch_section_articles(BASE_URL, SECTION_ID, LOCALE, max_pages=max_pages)
    rows: list[Row] = []
    for art in articles:
        title = art.get("title", "")
        if not title or is_noise(title):
            continue

        article_id = art.get("id")
        source_url = PUBLIC_URL_TMPL.format(id=article_id) if article_id else art.get("html_url", "")
        created_at = _parse_created_at(art.get("created_at", ""))

        body = art.get("body", "") or ""
        if not body and article_id:
            # la investigacion marco el endpoint de detalle como INFERIDO para este exchange
            # (no confirmado que la lista ya traiga 'body' como en Bitunix) - si viene vacio,
            # se pide aparte
            body = zendesk.fetch_article_body(BASE_URL, LOCALE, article_id)

        delist_at = extract_delist_date_from_body(body, created_at)

        market = detect_market(title)
        tickers = extract_tickers(title)
        if not tickers and body:
            tickers = extract_tickers_from_body(body)
        if not tickers:
            log.warning(f"[bingx] no se pudieron sacar tickers de: {title!r} ({source_url})")
            continue

        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=source_url, title=title, asset_class=classify_asset_class(title),
                announced_at=created_at, delist_at=delist_at, market=market,
            ))

    log.info(f"[bingx] {len(rows)} filas (de {len(articles)} articulos)")
    return rows
