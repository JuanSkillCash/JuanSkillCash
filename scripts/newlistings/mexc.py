"""MEXC: mismo enfoque que delistings/mexc.py (HTML via Playwright, requests simple da 403 -
confirmado de nuevo en el sondeo). Slug real confirmado: /announcements/new-listings (hermano
exacto de /announcements/delistings que ya usa el otro scraper)."""

from __future__ import annotations

import logging
import time

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .common import Row, DEFAULT_HEADERS, classify_asset_class, detect_market, extract_tickers, is_noise

log = logging.getLogger("newlistings.mexc")

EXCHANGE = "mexc"
BASE = "https://www.mexc.com"
LIST_URL_TMPL = "https://www.mexc.com/announcements/new-listings?page={page}"

_ARTICLE_HREF_SEL = 'a[href*="/announcements/article/"]'


def fetch(max_pages: int = 3) -> list[Row]:
    htmls: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page_obj = browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"])
        for page in range(1, max_pages + 1):
            try:
                page_obj.goto(LIST_URL_TMPL.format(page=page), wait_until="domcontentloaded", timeout=45000)
                page_obj.wait_for_selector(_ARTICLE_HREF_SEL, timeout=20000)
            except Exception as e:
                log.warning(f"[mexc] pagina {page} fallo esperando los links de articulo: {e}")
                htmls.append(page_obj.content())
                break
            htmls.append(page_obj.content())
            time.sleep(0.5)
        browser.close()

    rows: list[Row] = []
    for page_num, html in enumerate(htmls, start=1):
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select(_ARTICLE_HREF_SEL)
        if not links:
            if page_num == 1:
                log.warning("[mexc] no se encontro ningun link de articulo")
            break

        seen_urls = set()
        for a in links:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not href:
                continue
            url = href if href.startswith("http") else BASE + href
            if url in seen_urls or not title or is_noise(title):
                continue
            seen_urls.add(url)

            tickers = extract_tickers(title)
            if not tickers:
                log.warning(f"[mexc] no se pudieron sacar tickers de: {title!r} ({url})")
                continue

            market = detect_market(title)
            asset_class = classify_asset_class(title)
            for base in tickers:
                rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=url, title=title, asset_class=asset_class, market=market,
                ))
        time.sleep(1)

    log.info(f"[mexc] {len(rows)} filas")
    return rows
