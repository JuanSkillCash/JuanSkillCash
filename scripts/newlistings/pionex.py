"""Pionex: centro de ayuda Intercom (NO Zendesk), coleccion "New listings" (id 19449941).
La pagina de la coleccion lista TODOS los articulos en una sola pagina HTML, mas nuevos
primero (segun la investigacion), pero sin fecha visible en el listado - la fecha solo
esta dentro del cuerpo de cada articulo, y abrir los ~400 articulos uno por uno en cada
corrida horaria seria carisimo. Por diseno, announced_at queda en None aca (el frontend ya
sabe mostrar "Disponible" en vez de una fecha relativa cuando no hay announced_at)."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .common import Row, STOCK_TICKERS, classify_asset_class_or_ticker, fetch_html_with_fallback, is_noise

log = logging.getLogger("newlistings.pionex")

EXCHANGE = "pionex"
LIST_URL = "https://intercom.help/pionex/en/collections/19449941-new-listings"
_ARTICLE_HREF_SEL = 'a[href*="/en/articles/"]'

_LAUNCHED_USDT_RE = re.compile(r"has Launched the\s+(\S+?)USDT\b", re.IGNORECASE)
_PAREN_TICKER_RE = re.compile(r"\b([A-Za-z0-9一-鿿]{1,15})\s*\(")
_BARE_LISTED_RE = re.compile(r"[Hh]as [Ll]isted\s+([A-Za-z0-9一-鿿]{1,15})\s*$")


def _extract_tickers(title: str) -> list[str]:
    m = _LAUNCHED_USDT_RE.search(title)
    if m:
        return [m.group(1).upper()]
    parens = [m.group(1).upper() for m in _PAREN_TICKER_RE.finditer(title)]
    if parens:
        return parens
    m = _BARE_LISTED_RE.search(title)
    if m:
        return [m.group(1).upper()]
    return []


def fetch(max_pages: int = 1) -> list[Row]:
    html, method = fetch_html_with_fallback(LIST_URL, validate=lambda h: '/en/articles/' in h, wait_selector=_ARTICLE_HREF_SEL)
    log.info(f"[pionex] metodo usado: {method}")

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select(_ARTICLE_HREF_SEL)
    if not links:
        log.warning("[pionex] no se encontro ningun link de articulo")
        return []

    rows: list[Row] = []
    seen_urls = set()
    for a in links:
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not href or not title or is_noise(title):
            continue
        url = href if href.startswith("http") else "https://intercom.help" + href
        if url in seen_urls:
            continue
        seen_urls.add(url)

        tickers = _extract_tickers(title)
        if not tickers:
            log.warning(f"[pionex] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        market = "futures" if re.search(r"perpetual (futures|contract)", title, re.IGNORECASE) else "spot"
        for base in tickers:
            if not re.fullmatch(r"[A-Za-z0-9]{1,15}", base):
                continue  # descarta tickers con caracteres no latinos (chino, etc.) - no graficables
            asset_class = classify_asset_class_or_ticker(title, base)
            if asset_class == "crypto" and base.endswith("X") and len(base) > 2 and base[:-1] in STOCK_TICKERS:
                # convencion propia de Pionex: sufijo "X" = xStock tokenizado (CRMX, MSTUX, UMCX...)
                asset_class = "stock"
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title, asset_class=asset_class,
                announced_at=None, market=market,
            ))

    log.info(f"[pionex] {len(rows)} filas")
    return rows
