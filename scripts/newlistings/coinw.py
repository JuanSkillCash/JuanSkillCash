"""CoinW: pagina HTML renderizada en servidor (Nuxt) - el listado de titulos/fechas esta en
el HTML inicial (no en window.__NUXT__), asi que se parsea directo con BeautifulSoup. La
fecha tambien queda codificada en la propia URL del aviso (/latest-listings/YYYY-MM-DD/...),
asi que se usa como respaldo si el titulo no trae una fecha mas precisa."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from .common import Row, STOCK_TICKERS, classify_asset_class_or_ticker, fetch_html_with_fallback, is_noise, split_run

log = logging.getLogger("newlistings.coinw")

EXCHANGE = "coinw"
LIST_URL = "https://www.coinw.com/help-center/announcement-center/new-listings/latest-listings"

_HREF_DATE_RE = re.compile(r"/latest-listings/(\d{4})-(\d{2})-(\d{2})/")
_FUTURES_LAUNCH_RE = re.compile(
    r"Launches\s+([A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*)\s+USDT-Margined Perpetual (?:Futures|Contract)",
    re.IGNORECASE,
)
_FUTURES_SOON_RE = re.compile(
    r"Will Soon Launch\s+([A-Z0-9]{1,15})\s+USDT-Margined Perpetual (?:Futures|Contract)",
    re.IGNORECASE,
)
_SPOT_PAREN_RE = re.compile(r"Will List\s+([A-Z0-9]{1,15})\s*\(", re.IGNORECASE)
_SPOT_PAIRS_RE = re.compile(
    r"^([A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*)\s+Spot Trading Pairs Will Be Launched on CoinW",
    re.IGNORECASE,
)
_INCLUDE_VERBS_RE = re.compile(r"Launches|Will List|Will Soon Launch|Trading Pairs Will Be Launched", re.IGNORECASE)
# "CoinW Launches CMOC(CMOC), DIS(Walt Disney), WUXIAPPTEC (WuXi AppTec)... USDT-TradFi
# Perpetual Futures" - varios pares TICKER(Nombre), el ticker real siempre va antes del
# parentesis (a veces pegado, a veces con espacio).
_FUTURES_TRADFI_MULTI_RE = re.compile(r"Launches\s+(.+?)\s+USDT-TradFi Perpetual Futures", re.IGNORECASE)
_TICKER_BEFORE_PAREN_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,14})\s*\(")


def _extract_tickers(title: str) -> tuple[list[str], str]:
    m = _FUTURES_TRADFI_MULTI_RE.search(title)
    if m:
        tickers = []
        for t in _TICKER_BEFORE_PAREN_RE.findall(m.group(1)):
            t = t.upper()
            if t not in tickers:
                tickers.append(t)
        if tickers:
            return tickers, "futures"
    m = _FUTURES_LAUNCH_RE.search(title)
    if m:
        return split_run(m.group(1)), "futures"
    m = _FUTURES_SOON_RE.search(title)
    if m:
        return [m.group(1).upper()], "futures"
    m = _SPOT_PAREN_RE.search(title)
    if m:
        return [m.group(1).upper()], "spot"
    m = _SPOT_PAIRS_RE.search(title)
    if m:
        return split_run(m.group(1)), "spot"
    return [], "spot"


def fetch(max_pages: int = 1) -> list[Row]:
    html, method = fetch_html_with_fallback(
        LIST_URL, validate=lambda h: "latest-listings" in h, wait_selector='a[href*="latest-listings"]',
    )
    log.info(f"[coinw] metodo usado: {method}")

    soup = BeautifulSoup(html, "html.parser")
    links = [a for a in soup.select('a[href*="/latest-listings/"]') if a.get("href", "").count("/") > 5]
    if not links:
        log.warning("[coinw] no se encontro ningun link de articulo")
        return []

    rows: list[Row] = []
    seen_urls = set()
    for a in links:
        href = a.get("href", "")
        spans = a.find_all("span")
        title = spans[0].get_text(strip=True) if spans else a.get_text(strip=True)
        if not title or not _INCLUDE_VERBS_RE.search(title) or is_noise(title):
            continue
        url = href if href.startswith("http") else "https://www.coinw.com" + href
        if url in seen_urls:
            continue
        seen_urls.add(url)

        announced_at = None
        dm = _HREF_DATE_RE.search(href)
        if dm:
            y, mo, d = (int(x) for x in dm.groups())
            announced_at = datetime(y, mo, d, tzinfo=timezone.utc)

        tickers, market = _extract_tickers(title)
        if not tickers:
            log.warning(f"[coinw] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        for base in tickers:
            asset_class = classify_asset_class_or_ticker(title, base)
            if asset_class == "crypto" and base.endswith("ON") and len(base) > 2 and base[:-2] in STOCK_TICKERS:
                # convencion propia de CoinW: sufijo "ON" = accion tokenizada Ondo (CSCOON, JPMON...)
                asset_class = "stock"
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title, asset_class=asset_class,
                announced_at=announced_at, market=market,
            ))

    log.info(f"[coinw] {len(rows)} filas")
    return rows
