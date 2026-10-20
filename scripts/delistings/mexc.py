"""MEXC: HTML plano (sin API ni __NEXT_DATA__ visible en la investigacion), paginado con
?page=N. Selectores CSS tomados de un scraper publico de terceros (kukapay/mexc-
announcements-mcp) - marcados como INFERIDOS, pueden cambiar con cualquier rediseno del
sitio; si no matchean nada, se deja un volcado de diagnostico (misma leccion que con Gate:
mejor ver el HTML real que seguir adivinando a ciegas)."""

from __future__ import annotations

import logging
import re
import time

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

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
    # requests simple da 403 (confirmado en una corrida real) - mismo patron que Farside/Gate,
    # se usa un navegador de verdad para que el challenge de Cloudflare se resuelva solo
    rows: list[Row] = []
    htmls: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page_obj = browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"])
        for page in range(1, max_pages + 1):
            # "networkidle" nunca se cumple en MEXC (trafico de fondo constante - confirmado,
            # dio timeout de 45s sin resolver el challenge) - igual que Farside, se espera a
            # que el selector real aparezca en vez del estado de red
            try:
                page_obj.goto(LIST_URL_TMPL.format(page=page), wait_until="domcontentloaded", timeout=45000)
                page_obj.wait_for_selector(_ITEM_SEL, timeout=20000)
            except Exception as e:
                log.warning(f"[mexc] pagina {page} fallo esperando el selector: {e}")
                htmls.append(page_obj.content())  # igual se guarda lo que haya, para el volcado de diagnostico
                break
            htmls.append(page_obj.content())
            time.sleep(0.5)
        browser.close()

    for i, html in enumerate(htmls, start=1):
        page = i
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(_ITEM_SEL)
        if not cards:
            if page == 1:
                log.warning("[mexc] no se encontro ningun item con el selector esperado")
                ids = re.findall(r'<script[^>]*\bid="([^"]+)"', html)
                log.info(f"[mexc] DEBUG titulo <title>: {(soup.title.string if soup.title else None)!r}")
                log.info(f"[mexc] DEBUG primeros 1500 chars del HTML: {html[:1500]!r}")
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
