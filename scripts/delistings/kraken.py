"""Kraken: HTML server-rendered, sin API de anuncios. Toda la seccion "Delistings" (+ su
archivo) son avisos de deslistado, no hace falta filtrar por categoria. A diferencia de los
demas exchanges, los tickers NO estan en el titulo del aviso (titulos tipo "Asset delistings
- October 2026", sin simbolos) sino listados en prosa dentro del cuerpo - se buscan como la
corrida mas larga de tokens tipo-ticker separados por comas (patron real confirmado en la
investigacion: "BMB, ELX, APU, BDXN, DUCK, BOS, U, OBOL, IDEX, FIS, UXLINK, ALTHEA, NOBODY")."""

from __future__ import annotations

import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from .common import (
    Row, DEFAULT_HEADERS, extract_delist_date_from_body, extract_tickers, detect_market,
    is_noise, html_to_text,
)

log = logging.getLogger("delistings.kraken")

EXCHANGE = "kraken"
SECTION_URL = "https://support.kraken.com/en/sections/delistings"
ARCHIVE_URL = "https://support.kraken.com/en/sections/delistings-archive"

_TICKER_RUN_RE = re.compile(
    r"\b[A-Z][A-Z0-9]{0,9}\b(?:\s*,\s*\b[A-Z][A-Z0-9]{0,9}\b){1,}"
    r"(?:\s*(?:,\s*)?(?:and|&)\s*\b[A-Z][A-Z0-9]{0,9}\b)?"
)
_TICKER_TOKEN_RE = re.compile(r"[A-Z][A-Z0-9]{0,9}")

_EXTRA_STOPWORDS = {"UTC", "FAQ", "API", "EEA", "UAE", "USD", "USDT", "USDC", "KYC", "AML", "UK", "US", "EU"}


def _extract_ticker_run(text: str) -> list[str]:
    """La lista real de tickers del aviso: la corrida mas larga de tokens separados por
    comas (asi se evita confundir siglas sueltas tipo "UTC"/"FAQ" con una lista real)."""
    best: list[str] = []
    for m in _TICKER_RUN_RE.finditer(text):
        tokens = [t for t in _TICKER_TOKEN_RE.findall(m.group(0)) if t not in _EXTRA_STOPWORDS]
        if len(tokens) > len(best):
            best = tokens
    return best


def _fetch_article_links(list_url: str) -> list[tuple[str, str]]:
    resp = requests.get(list_url, headers=DEFAULT_HEADERS, timeout=30)
    if resp.status_code != 200:
        log.warning(f"[kraken] {list_url} respondio {resp.status_code}")
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    links: list[tuple[str, str]] = []
    seen = set()
    for a in soup.select('a[href*="/en/articles/"]'):
        href = a.get("href", "")
        title = a.get_text(strip=True)
        if not href or not title or href in seen:
            continue
        seen.add(href)
        url = href if href.startswith("http") else "https://support.kraken.com" + href
        links.append((title, url))

    if not links:
        log.warning(f"[kraken] no se encontro ningun link de articulo en {list_url}")
        ids = re.findall(r'<a[^>]*href="([^"]+)"', resp.text)[:40]
        log.info(f"[kraken] DEBUG titulo <title>: {(soup.title.string if soup.title else None)!r}")
        log.info(f"[kraken] DEBUG primeros hrefs encontrados: {ids}")

    return links


def _fetch_article_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[kraken] articulo {url} respondio {resp.status_code}")
            return ""
        return html_to_text(resp.text)
    except requests.RequestException as e:
        log.warning(f"[kraken] fallo trayendo articulo {url}: {e}")
        return ""


def fetch(max_articles: int = 15) -> list[Row]:
    links = _fetch_article_links(SECTION_URL)
    log.info(f"[kraken] {len(links)} articulos en la seccion actual")

    rows: list[Row] = []
    for title, url in links[:max_articles]:
        if not title or is_noise(title):
            continue
        time.sleep(0.5)
        body_text = _fetch_article_text(url)
        if not body_text:
            continue

        tickers = _extract_ticker_run(body_text)
        if not tickers:
            # algunos avisos son de un solo activo (ej "RAIN Delisting") - sin lista en
            # prosa, pero el titulo puede traer el ticker igual que en otros exchanges
            tickers = extract_tickers(title) or extract_tickers(body_text[:500])
        if not tickers:
            log.warning(f"[kraken] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        delist_at = extract_delist_date_from_body(body_text)
        market = detect_market(title)

        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title,
                announced_at=None, delist_at=delist_at, market=market,
            ))

    log.info(f"[kraken] {len(rows)} filas")
    return rows
