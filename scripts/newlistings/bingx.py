"""BingX: mismo centro de soporte Zendesk que delistings/bingx.py (bingxservice.zendesk.com),
pero "Nuevos Listados" vive repartido en 3 secciones (confirmado en el sondeo):
  - Spot Listing (11257060005007): "Nombre (TICKER) Coin Gets/Will Be Listed on BingX Spot"
  - Futures Listing (11257015822991): "BingX Adds TICKER[, TICKER2 ...] [and More] for Perpetual Futures"
    (aca aparecen los casos de acciones/commodities: "BingX Adds XAUXPT, XAUZAR ... ", "BingX
    Adds KKR, DTE and More for Perpetual Futures")
  - Innovation Listing (13117025062927): mismo patron que Spot Listing, con "[Innovation Zone]"
    de prefijo (zona de mas riesgo, pero sigue siendo un nuevo listado spot real)."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from .common import Row, classify_asset_class, is_noise  # ejecuta el sys.path.insert necesario
from delistings import zendesk

log = logging.getLogger("newlistings.bingx")

EXCHANGE = "bingx"
BASE_URL = "https://bingxservice.zendesk.com"
LOCALE = "en-001"
PUBLIC_URL_TMPL = "https://bingx.com/en/support/articles/{id}/"

SECTIONS = [
    ("11257060005007", "spot"),
    ("13117025062927", "spot"),       # Innovation Listing -> tambien spot
    ("11257015822991", "futures"),
]

_SPOT_RE = re.compile(
    r"\(([A-Za-z0-9]{1,15})\)\s*(?:Coin\s+)?(?:Gets Listed|Will Be Listed) on BingX Spot", re.IGNORECASE,
)
_SPOT_MULTI_RE = re.compile(
    r"^(?:\[[^\]]*\]\s*)*(.*?)\s+Coins Get Listed on BingX Spot", re.IGNORECASE,
)
_MIGRATION_RE = re.compile(r"^(?:\[[^\]]*\]\s*)*([A-Z][A-Z0-9]{0,14})\s+Migration to BingX Spot")
_FUTURES_RE = re.compile(r"BingX Adds\s+(.*?)\s+for Perpetual Futures", re.IGNORECASE)
_FUTURES_WILL_LIST_RE = re.compile(
    r"BingX Perpetual Futures Will List\s+(.*?)(?:,?\s*and\s+More)?\s*$", re.IGNORECASE,
)
_FUTURES_STOPWORDS = {"MORE", "AND"}


def _parse_created_at(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _futures_tickers(segment: str) -> list[str]:
    parts = re.split(r",|/|&|\band\b", segment, flags=re.IGNORECASE)
    out = []
    for p in parts:
        tok = re.sub(r"[^A-Za-z0-9]", "", p).upper()
        if not tok or tok in _FUTURES_STOPWORDS:
            continue
        for quote in ("USDT", "USDC", "USD"):
            if tok.endswith(quote) and len(tok) > len(quote) + 1:
                tok = tok[: -len(quote)]
                break
        if tok and tok not in out:
            out.append(tok)
    return out


def fetch(max_pages: int = 3) -> list[Row]:
    rows: list[Row] = []
    for section_id, market in SECTIONS:
        articles = zendesk.fetch_section_articles(BASE_URL, section_id, LOCALE, max_pages=max_pages)
        for art in articles:
            title = art.get("title", "")
            if not title or is_noise(title):
                continue
            article_id = art.get("id")
            source_url = PUBLIC_URL_TMPL.format(id=article_id) if article_id else art.get("html_url", "")
            created_at = _parse_created_at(art.get("created_at", ""))
            asset_class = classify_asset_class(title)

            if market == "spot":
                m = _SPOT_RE.search(title)
                if m:
                    tickers = [m.group(1).upper()]
                else:
                    m = _SPOT_MULTI_RE.search(title)
                    if m:
                        tickers = _futures_tickers(m.group(1))
                    else:
                        m = _MIGRATION_RE.search(title)
                        tickers = [m.group(1).upper()] if m else []
            else:
                m = _FUTURES_RE.search(title)
                if m:
                    tickers = _futures_tickers(m.group(1))
                else:
                    m = _FUTURES_WILL_LIST_RE.search(title)
                    tickers = _futures_tickers(m.group(1)) if m else []

            if not tickers:
                log.warning(f"[bingx] no se pudieron sacar tickers de: {title!r} ({source_url})")
                continue

            for base in tickers:
                rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=source_url, title=title, asset_class=asset_class,
                    announced_at=created_at, market=market,
                ))
        log.info(f"[bingx] seccion {section_id} ({market}): {len(articles)} articulos")

    log.info(f"[bingx] {len(rows)} filas")
    return rows
