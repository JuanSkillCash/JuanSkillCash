"""Kraken: HTML server-rendered, sin API de anuncios (segun la investigacion) - pero la URL
exacta que probaron dio 404 en una corrida real, asi que primero se prueban varias rutas
candidatas (incluida la posibilidad de que el soporte de Kraken tambien corra sobre Zendesk,
como Bitunix/BingX, mucho mas confiable que adivinar HTML) y se usa la primera que responda
200, dejando un log de que paso con cada una para poder ajustar con datos reales."""

from __future__ import annotations

import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from .common import (
    Row, DEFAULT_HEADERS, extract_delist_date_from_body, extract_tickers, detect_market,
    is_noise, html_to_text,
    classify_asset_class, fetch_known_delist_dates,
)

log = logging.getLogger("delistings.kraken")

EXCHANGE = "kraken"

_CANDIDATE_SECTION_URLS = [
    "https://support.kraken.com/en/sections/delistings",
    "https://support.kraken.com/hc/en-us/sections/delistings",
    "https://support.kraken.com/en-us/sections/delistings",
    "https://support.kraken.com/sections/delistings",
]
_ZENDESK_CATEGORIES_URL = "https://support.kraken.com/api/v2/help_center/en-us/categories.json"
_ZENDESK_SECTIONS_URL = "https://support.kraken.com/api/v2/help_center/en-us/sections.json"

_TICKER_RUN_RE = re.compile(
    r"\b[A-Z][A-Z0-9]{0,9}\b(?:\s*,\s*\b[A-Z][A-Z0-9]{0,9}\b){1,}"
    r"(?:\s*(?:,\s*)?(?:and|&)\s*\b[A-Z][A-Z0-9]{0,9}\b)?"
)
_TICKER_TOKEN_RE = re.compile(r"[A-Z][A-Z0-9]{0,9}")

_EXTRA_STOPWORDS = {"UTC", "FAQ", "API", "EEA", "UAE", "USD", "USDT", "USDC", "KYC", "AML", "UK", "US", "EU"}


def _extract_ticker_run(text: str) -> list[str]:
    best: list[str] = []
    for m in _TICKER_RUN_RE.finditer(text):
        tokens = [t for t in _TICKER_TOKEN_RE.findall(m.group(0)) if t not in _EXTRA_STOPWORDS]
        if len(tokens) > len(best):
            best = tokens
    return best


def _find_working_section_url() -> str | None:
    for url in _CANDIDATE_SECTION_URLS:
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        except requests.RequestException as e:
            log.info(f"[kraken] DEBUG {url} fallo: {e}")
            continue
        log.info(f"[kraken] DEBUG {url} -> {resp.status_code}")
        if resp.status_code == 200:
            return url
    return None


def _probe_zendesk() -> None:
    """Solo diagnostico: si support.kraken.com corre sobre Zendesk (como Bitunix/BingX),
    esto lo confirma y lista las secciones reales para encontrar el id de 'Delistings'."""
    try:
        resp = requests.get(_ZENDESK_CATEGORIES_URL, headers=DEFAULT_HEADERS, timeout=20)
    except requests.RequestException as e:
        log.info(f"[kraken] DEBUG zendesk categories.json fallo: {e}")
        return
    log.info(f"[kraken] DEBUG zendesk categories.json -> {resp.status_code}")
    if resp.status_code != 200:
        return
    try:
        resp2 = requests.get(_ZENDESK_SECTIONS_URL, headers=DEFAULT_HEADERS, timeout=20,
                              params={"per_page": 100})
        data = resp2.json()
        sections = [(s.get("id"), s.get("name")) for s in data.get("sections", [])]
        delisting_sections = [s for s in sections if "delist" in (s[1] or "").lower()]
        log.info(f"[kraken] DEBUG zendesk SI corre aca - secciones con 'delist' en el nombre: {delisting_sections}")
        if not delisting_sections:
            log.info(f"[kraken] DEBUG primeras 20 secciones (para ubicar 'Delistings' a mano): {sections[:20]}")
    except Exception as e:
        log.info(f"[kraken] DEBUG fallo listando secciones zendesk: {e}")


def _fetch_article_links(list_url: str) -> list[tuple[str, str]]:
    resp = requests.get(list_url, headers=DEFAULT_HEADERS, timeout=30)
    if resp.status_code != 200:
        log.warning(f"[kraken] {list_url} respondio {resp.status_code}")
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    links: list[tuple[str, str]] = []
    seen = set()
    for a in soup.select('a[href*="/articles/"]'):
        href = a.get("href", "")
        title = a.get_text(strip=True)
        if not href or not title or href in seen:
            continue
        seen.add(href)
        url = href if href.startswith("http") else "https://support.kraken.com" + href
        links.append((title, url))
    return links


def _fetch_article_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=12)
        if resp.status_code != 200:
            log.warning(f"[kraken] articulo {url} respondio {resp.status_code}")
            return ""
        return html_to_text(resp.text)
    except requests.RequestException as e:
        log.warning(f"[kraken] fallo trayendo articulo {url}: {e}")
        return ""


def fetch(max_articles: int = 15) -> list[Row]:
    section_url = _find_working_section_url()
    if not section_url:
        log.warning("[kraken] ninguna URL candidata respondio 200 - probando si el soporte corre sobre Zendesk")
        _probe_zendesk()
        return []

    log.info(f"[kraken] usando {section_url}")
    links = _fetch_article_links(section_url)
    log.info(f"[kraken] {len(links)} articulos en la seccion actual")

    # a diferencia de los demas exchanges, aca el ticker tambien sale del cuerpo del
    # articulo (no solo la fecha) - asi que un articulo ya resuelto antes (con fecha o sin
    # ella) se salta por completo: su fila ya quedo guardada en Supabase la primera vez, no
    # hace falta volver a pedir el cuerpo solo para repetir el mismo ticker.
    known_dates = fetch_known_delist_dates(EXCHANGE)
    rows: list[Row] = []
    for title, url in links[:max_articles]:
        if not title or is_noise(title):
            continue
        if url in known_dates:
            continue
        time.sleep(0.5)
        body_text = _fetch_article_text(url)
        if not body_text:
            continue

        tickers = _extract_ticker_run(body_text)
        if not tickers:
            tickers = extract_tickers(title) or extract_tickers(body_text[:500])
        if not tickers:
            log.warning(f"[kraken] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        delist_at = extract_delist_date_from_body(body_text)
        market = detect_market(title)

        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title, asset_class=classify_asset_class(title),
                announced_at=None, delist_at=delist_at, market=market,
            ))

    log.info(f"[kraken] {len(rows)} filas")
    return rows
