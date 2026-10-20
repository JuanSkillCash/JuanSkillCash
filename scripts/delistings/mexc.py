"""MEXC: HTML plano (sin API ni __NEXT_DATA__ visible en la investigacion), paginado con
?page=N. Selectores CSS tomados de un scraper publico de terceros (kukapay/mexc-
announcements-mcp) - marcados como INFERIDOS, pueden cambiar con cualquier rediseno del
sitio; si no matchean nada, se deja un volcado de diagnostico (misma leccion que con Gate:
mejor ver el HTML real que seguir adivinando a ciegas)."""

from __future__ import annotations

import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from .common import (
    Row, DEFAULT_HEADERS, extract_tickers, detect_market, is_noise, parse_delist_datetime,
)

log = logging.getLogger("delistings.mexc")

EXCHANGE = "mexc"
BASE = "https://www.mexc.com"
LIST_URL_TMPL = "https://www.mexc.com/announcements/delistings?page={page}"

_ITEM_SEL = '[class*="SearchResultItem_searchResultItem-community"]'
_HEADER_SEL = '[class*="SearchResultItem_header-community"]'


def fetch(max_pages: int = 3) -> list[Row]:
    rows: list[Row] = []
    for page in range(1, max_pages + 1):
        resp = requests.get(LIST_URL_TMPL.format(page=page), headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[mexc] pagina {page} respondio {resp.status_code}")
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(_ITEM_SEL)
        if not cards:
            if page == 1:
                log.warning("[mexc] no se encontro ningun item con el selector esperado")
                ids = re.findall(r'<script[^>]*\bid="([^"]+)"', resp.text)
                log.info(f"[mexc] DEBUG titulo <title>: {(soup.title.string if soup.title else None)!r}")
                log.info(f"[mexc] DEBUG primeros 1500 chars del HTML: {resp.text[:1500]!r}")
                log.info(f"[mexc] DEBUG ids de <script> encontrados: {ids}")
            break

        for card in cards:
            header = card.select_one(_HEADER_SEL)
            a = header.select_one("a[href]") if header else card.select_one("a[href]")
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or is_noise(title):
                continue
            href = a.get("href", "")
            url = href if href.startswith("http") else BASE + href

            delist_at = parse_delist_datetime(title)
            market = detect_market(title)
            tickers = extract_tickers(title)
            if not tickers:
                log.warning(f"[mexc] no se pudieron sacar tickers de: {title!r} ({url})")
                continue

            for base in tickers:
                rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=url, title=title,
                    announced_at=None, delist_at=delist_at, market=market,
                ))
        time.sleep(1)

    log.info(f"[mexc] {len(rows)} filas")
    return rows
