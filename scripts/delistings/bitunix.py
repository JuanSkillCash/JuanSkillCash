"""Bitunix: centro de soporte en Zendesk Help Center, seccion "Delisting" (sin auth).
Fuente: investigacion confirmada - section_id 47601070306585, 133 articulos (oct-2026)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from . import zendesk
from .common import (
    Row, extract_delist_date_from_body, extract_tickers, extract_tickers_from_body,
    detect_market, is_noise, is_completion_notice, is_delay_notice,
    classify_asset_class,
)

log = logging.getLogger("delistings.bitunix")

EXCHANGE = "bitunix"
BASE_URL = "https://support.bitunix.com"
SECTION_ID = "47601070306585"
LOCALE = "en-us"


def _parse_created_at(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch(max_pages: int = 5) -> list[Row]:
    articles = zendesk.fetch_section_articles(BASE_URL, SECTION_ID, LOCALE, max_pages=max_pages)
    rows: list[Row] = []
    for art in articles:
        title = art.get("title", "")
        if not title or is_noise(title):
            continue
        source_url = art.get("html_url", "")
        created_at = _parse_created_at(art.get("created_at", ""))
        body = art.get("body", "") or ""

        delist_at = extract_delist_date_from_body(body, created_at)
        if not delist_at:
            delist_at = None  # el fallback al titulo lo hace extract_tickers/rows_from_title mas abajo

        market = detect_market(title)
        tickers = extract_tickers(title)
        if not tickers and body:
            # titulos genericos tipo "Notice of Delisting N Spot Trading Pairs on ..." no
            # traen tickers, solo la cantidad - la lista real vive en el cuerpo del aviso
            tickers = extract_tickers_from_body(body)
        if not tickers:
            log.warning(f"[bitunix] no se pudieron sacar tickers de: {title!r} ({source_url})")
            continue

        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=source_url, title=title, asset_class=classify_asset_class(title),
                announced_at=created_at, delist_at=delist_at, market=market,
            ))

    log.info(f"[bitunix] {len(rows)} filas (de {len(articles)} articulos)")
    return rows
