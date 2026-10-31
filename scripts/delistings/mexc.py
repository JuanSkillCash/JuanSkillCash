"""MEXC: HTML plano (React + Ant Design, sin __NEXT_DATA__), paginado con ?page=N. requests
simple no basta (una corrida real se quedo esperando "networkidle" sin resolver, trafico de
fondo constante) - con Playwright SI carga la pagina real (sin bloqueo, titulo real
confirmado), solo que los selectores de clase de un scraper de terceros (hashes que cambian
en cada deploy) no matchean el DOM actual. En vez de adivinar clases, se usan los links
<a href="/announcements/article/..."> directo - el patron de URL es estable aunque el CSS
cambie."""

from __future__ import annotations

import logging
import re
import time

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

import requests

from .common import (
    Row, DEFAULT_HEADERS, extract_tickers, extract_tickers_from_body, detect_market,
    is_noise, parse_delist_datetime, classify_asset_class, html_to_text,
)

log = logging.getLogger("delistings.mexc")

EXCHANGE = "mexc"
BASE = "https://www.mexc.com"
LIST_URL_TMPL = "https://www.mexc.com/announcements/delistings?page={page}"

_ARTICLE_HREF_SEL = 'a[href*="/announcements/article/"]'
MAX_BODY_FETCHES = 15


def _fetch_article_text(url: str) -> str:
    """Intento liviano por HTTP plano (no Playwright, para no pagar el costo de una
    navegacion completa por articulo) - best-effort: si la pagina necesita JS para
    renderizar el cuerpo, esto puede venir vacio y el llamador simplemente no gana nada,
    sin empeorar lo que ya habia (titulo sin tickers se descartaba igual antes de esto)."""
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=12)
        if resp.status_code != 200:
            return ""
        return html_to_text(resp.text)
    except requests.RequestException as e:
        log.warning(f"[mexc] fallo trayendo articulo {url}: {e}")
        return ""


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
                htmls.append(page_obj.content())  # se guarda igual, para el volcado de diagnostico
                break
            htmls.append(page_obj.content())
            time.sleep(0.5)
        browser.close()

    rows: list[Row] = []
    body_fetches_left = MAX_BODY_FETCHES
    for page_num, html in enumerate(htmls, start=1):
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select(_ARTICLE_HREF_SEL)
        if not links:
            if page_num == 1:
                log.warning("[mexc] no se encontro ningun link de articulo")
                ids = re.findall(r'<script[^>]*\bid="([^"]+)"', html)
                log.info(f"[mexc] DEBUG titulo <title>: {(soup.title.string if soup.title else None)!r}")
                log.info(f"[mexc] DEBUG primeros 1500 chars del HTML: {html[:1500]!r}")
                log.info(f"[mexc] DEBUG ids de <script> encontrados: {ids}")
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

            delist_at = parse_delist_datetime(title)
            market = detect_market(title)
            tickers = extract_tickers(title)
            if not tickers and body_fetches_left > 0:
                body_fetches_left -= 1
                body_text = _fetch_article_text(url)
                if body_text:
                    tickers = extract_tickers_from_body(body_text)
            if not tickers:
                log.warning(f"[mexc] no se pudieron sacar tickers de: {title!r} ({url})")
                continue

            for base in tickers:
                rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=url, title=title, asset_class=classify_asset_class(title),
                    announced_at=None, delist_at=delist_at, market=market,
                ))
        time.sleep(1)

    log.info(f"[mexc] {len(rows)} filas")
    return rows
