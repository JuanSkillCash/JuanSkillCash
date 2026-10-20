"""Bitunix: la seccion que se habia usado antes (13762039477017) resulto ser "Events and
Activities" (puro marketing) - la seccion REAL de nuevos listados es 13762037166105
(806 articulos), confirmada navegando el Zendesk real."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from delistings import zendesk

from .common import Row, classify_asset_class_or_ticker, is_noise, split_run

log = logging.getLogger("newlistings.bitunix")

EXCHANGE = "bitunix"
BASE_URL = "https://support.bitunix.com"
SECTION_ID = "13762037166105"
LOCALE = "en-us"

_SPOT_RE = re.compile(r"Will List\s+[^()]+?\(([A-Z0-9]{1,15})\)", re.IGNORECASE)
_GETS_LISTED_RE = re.compile(r"\(([A-Za-z0-9]{1,15})\)\s*Gets Listed on Bitunix", re.IGNORECASE)
_FUTURES_COMMA_RE = re.compile(
    r"to Launch\s+([A-Z0-9]+(?:USDT)?(?:\s*,\s*[A-Z0-9]+(?:USDT)?)*)\s+(?:in\s+)?Perpetual Futures",
    re.IGNORECASE,
)
_FUTURES_SINGLE_RE = re.compile(r"to Launch\s+([A-Z0-9]{2,15})\s+Pre-IPO Perpetual Futures", re.IGNORECASE)
_FUTURES_SLASH_RE = re.compile(r"to Launch\s+([A-Z0-9]{1,15})/(?:USDT|USDC)\s+in\s+Perpetual Futures", re.IGNORECASE)


def _strip_quote(tok: str) -> str:
    tok = tok.upper()
    for q in ("USDT", "USDC", "USD"):
        if tok.endswith(q) and len(tok) > len(q) + 1:
            return tok[: -len(q)]
    return tok


def _parse_created_at(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_tickers(title: str) -> tuple[list[str], str]:
    m = _SPOT_RE.search(title)
    if m:
        return [m.group(1).upper()], "spot"
    m = _GETS_LISTED_RE.search(title)
    if m:
        return [m.group(1).upper()], "spot"
    m = _FUTURES_SINGLE_RE.search(title)
    if m:
        return [_strip_quote(m.group(1))], "futures"
    m = _FUTURES_SLASH_RE.search(title)
    if m:
        return [_strip_quote(m.group(1))], "futures"
    m = _FUTURES_COMMA_RE.search(title)
    if m:
        return split_run(m.group(1)), "futures"
    return [], "spot"


def fetch(max_pages: int = 3) -> list[Row]:
    articles = zendesk.fetch_section_articles(BASE_URL, SECTION_ID, LOCALE, max_pages=max_pages)
    rows: list[Row] = []
    for art in articles:
        title = art.get("title", "")
        if not title or is_noise(title):
            continue
        source_url = art.get("html_url", "")
        created_at = _parse_created_at(art.get("created_at", ""))

        tickers, market = _extract_tickers(title)
        if not tickers:
            log.warning(f"[bitunix] no se pudieron sacar tickers de: {title!r} ({source_url})")
            continue

        for base in tickers:
            asset_class = classify_asset_class_or_ticker(title, base)
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=source_url, title=title, asset_class=asset_class,
                announced_at=created_at, market=market,
            ))

    log.info(f"[bitunix] {len(rows)} filas (de {len(articles)} articulos)")
    return rows
