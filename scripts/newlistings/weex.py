"""Weex: su Zendesk viejo (weexsupport.zendesk.com) sigue respondiendo pero esta CONGELADO
desde 2026-05-15 - el sitio real migro a www.weex.com/help/, mismos IDs de seccion que tenia
el Zendesk ("Spot listings" / "Futures listings"), pero HTML propio (no API de Zendesk)."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .common import Row, _pick_ticker, classify_asset_class_or_ticker, fetch_html_with_fallback, is_noise, split_run

log = logging.getLogger("newlistings.weex")

EXCHANGE = "weex"
SECTIONS = [
    ("https://www.weex.com/help/sections/18540509241753", "spot"),
    ("https://www.weex.com/help/sections/47660531875481", "futures"),
]
_ARTICLE_HREF_SEL = 'a[href*="/help/articles/"]'

# Paginas de footer (Terminos, Privacidad, etc.) que aparecen listadas junto a los avisos
# reales en ambas secciones, y avisos "teaser" que solo anuncian una fecha sin decir el
# ticker todavia (ese se confirma despues en un aviso aparte que si matchea algun patron de
# abajo) - ninguno de los dos trae datos reales que extraer.
_WEEX_NOISE_RE = re.compile(
    r"^(?:Legal Statement|Risk Disclosure|Terms and Policies|Privacy Policy|"
    r"Whistleblower Notice|AML/CTF Policy|Law Enforcement|VIP Program|Affiliate T&C)$"
    r"|launch\s+USDT-M\s+(?:TradFi|Stock)\s+futures\s+on"
    r"|will be available on WEEX soon",
    re.IGNORECASE,
)

_SPOT_LISTING_RE = re.compile(
    r"(?:new|initial)\s+listing:?\s+(.+?)\s*\(([^()]{1,30})\)\s+now available", re.IGNORECASE,
)
_WILL_LIST_PAREN_RE = re.compile(r"Will List\s+(.+?)\s*\(([^()]{1,30})\)", re.IGNORECASE)
_FUTURES_SINGLE_RE = re.compile(r"to launch\s+([A-Z0-9]{2,15})\s+TradFi futures", re.IGNORECASE)
_FUTURES_STOCK_SINGLE_RE = re.compile(r"to launch\s+([A-Z0-9]{2,15})\s+stock futures", re.IGNORECASE)
_FUTURES_LIST_RE = re.compile(
    r"[Nn]ew listing:\s+([A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*).{0,40}?\bfutures\b", re.IGNORECASE | re.DOTALL,
)


def _extract_tickers(title: str, market: str) -> list[str]:
    if market == "spot":
        for pattern in (_SPOT_LISTING_RE, _WILL_LIST_PAREN_RE):
            m = pattern.search(title)
            if m:
                picked = _pick_ticker(m.group(1), m.group(2)).upper()
                if re.fullmatch(r"[A-Za-z0-9]{1,15}", picked):
                    return [picked]
        return []
    m = _FUTURES_SINGLE_RE.search(title)
    if m:
        return [m.group(1).upper()]
    m = _FUTURES_STOCK_SINGLE_RE.search(title)
    if m:
        return [m.group(1).upper()]
    m = _FUTURES_LIST_RE.search(title)
    if m:
        return split_run(m.group(1))
    return []


def fetch(max_pages: int = 1) -> list[Row]:
    rows: list[Row] = []
    for url, market in SECTIONS:
        html, method = fetch_html_with_fallback(
            url, validate=lambda h: "/help/articles/" in h, wait_selector=_ARTICLE_HREF_SEL,
        )
        log.info(f"[weex] {market} - metodo usado: {method}")

        soup = BeautifulSoup(html, "html.parser")
        links = soup.select(_ARTICLE_HREF_SEL)
        if not links:
            log.warning(f"[weex] no se encontro ningun link de articulo en {market}")
            continue

        seen_urls = set()
        for a in links:
            href = a.get("href", "")
            if not href:
                continue
            full_url = href if href.startswith("http") else "https://www.weex.com" + href
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            title = a.get_text(strip=True)
            title = re.sub(r"^Featured\s*", "", title).strip()
            if not title or is_noise(title) or _WEEX_NOISE_RE.search(title):
                continue

            tickers = _extract_tickers(title, market)
            if not tickers:
                log.warning(f"[weex] no se pudieron sacar tickers de: {title!r} ({full_url})")
                continue

            for base in tickers:
                asset_class = classify_asset_class_or_ticker(title, base)
                rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=full_url, title=title, asset_class=asset_class,
                    announced_at=None, market=market,
                ))

    log.info(f"[weex] {len(rows)} filas")
    return rows
