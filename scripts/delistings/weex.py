"""Weex: su help center (ya no el Zendesk viejo, ver newlistings/weex.py) tiene secciones
dedicadas de deslistado confirmadas por diagnostico real via el texto de cada link de la
raiz /help - "Spot delistings/maintenance" (id 37576213158553) y "Futures
delistings/maintenance" (id 47660551001369); se deja afuera "Earn delistings/maintenance"
(12312367451234) porque es de productos de rendimiento, no de pares spot/futuros. Los
titulos de Weex no tienen un solo formato: a veces vienen con "TICKER/USDT" pegado
("WEEX delisting announcement: CLAN/USDT spot trading pair"), a veces varias parejas
separadas por "and" ("...SAYLORMOON/USDT and BISCOTTI/USDT spot trading pairs"), a veces
una lista simple separada por "/" sin pareja de quote ("Spot Market Temporarily Delists
GLOT/TRN/TS/LCE Trading Pairs"), y a veces el ticker va ANTES de "Spot Trading Pairs
Delisting Announcement" ("TORA, IROHA, ... and HOOK Spot Trading Pairs Delisting
Announcement") - de ahi que haya una regex por forma en vez de una sola generica."""

from __future__ import annotations

import logging
import re
import time

from bs4 import BeautifulSoup

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
from newlistings.common import DEFAULT_HEADERS, fetch_html_with_fallback  # noqa: E402

from .common import (
    Row, ExchangeBlocked, extract_delist_date_from_body, extract_tickers_from_body,
    html_to_text, is_noise, parse_delist_datetime, classify_asset_class,
    fetch_known_delist_dates,
)

log = logging.getLogger("delistings.weex")

EXCHANGE = "weex"
SECTIONS = [
    ("https://www.weex.com/help/sections/37576213158553", "spot"),
    ("https://www.weex.com/help/sections/47660551001369", "futures"),
]
_ARTICLE_HREF_SEL = 'a[href*="/help/articles/"]'

_QUOTES = {"USDT", "USDC", "USD", "BTC", "ETH"}

_COLON_LIST_RE = re.compile(r"delisting announcement:\s*(.+?)\s+spot trading pairs?\s*$", re.IGNORECASE)
_DELISTS_SLASH_RE = re.compile(r"[Dd]elists?\s+([A-Z0-9/]+)\s+Trading Pairs?", re.IGNORECASE)
_PREFIX_LIST_RE = re.compile(r"^(.+?)\s+Spot Trading Pairs?\s+Delisting Announcement$", re.IGNORECASE)
_CAPS_TOKEN_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,14})\b")

# acota cuantos cuerpos de articulo se van a pedir en una sola corrida - estas secciones
# acumulan meses/anios de avisos y pedir el cuerpo de CADA uno (con posible caida a
# Playwright por articulo) podria tardar demasiado; alcanza con los mas recientes, la
# corrida horaria siguiente cubre lo que falte
MAX_BODY_FETCHES = 15


def _tickers_from_slash_group(seg: str) -> list[str]:
    parts = [p.strip().upper() for p in seg.split("/") if p.strip()]
    if len(parts) > 1 and parts[-1] in _QUOTES:
        parts = parts[:-1]
    return [p for p in parts if re.fullmatch(r"[A-Z0-9]{1,15}", p)]


def _split_ticker_list(segment: str) -> list[str]:
    out = []
    for part in re.split(r",|\band\b", segment, flags=re.IGNORECASE):
        part = part.strip()
        if not part:
            continue
        for tok in (_tickers_from_slash_group(part) if "/" in part else [part.upper()]):
            tok = re.sub(r"[^A-Z0-9]", "", tok)
            if tok and re.fullmatch(r"[A-Z0-9]{1,15}", tok) and tok not in out:
                out.append(tok)
    return out


def _extract_tickers(title: str) -> list[str]:
    m = _COLON_LIST_RE.search(title)
    if m:
        return _split_ticker_list(m.group(1))
    m = _DELISTS_SLASH_RE.search(title)
    if m:
        return _tickers_from_slash_group(m.group(1))
    m = _PREFIX_LIST_RE.search(title)
    if m:
        return _split_ticker_list(m.group(1))
    # fallback generico: algun otro formato no visto todavia en la investigacion - solo se
    # queda con tokens 100% mayuscula, nunca con palabras sueltas del titulo
    return [tok for tok in _CAPS_TOKEN_RE.findall(title) if tok not in ("WEEX",)]


def _fetch_article_text(url: str) -> str:
    try:
        html, _ = fetch_html_with_fallback(url, timeout=12)
        return html_to_text(html)
    except Exception as e:
        log.warning(f"[weex] fallo trayendo articulo {url}: {e}")
        return ""


def fetch(max_pages: int = 1) -> list[Row]:
    rows: list[Row] = []
    any_section_ok = False
    body_fetches_left = MAX_BODY_FETCHES
    known_dates = fetch_known_delist_dates(EXCHANGE)
    for url, market in SECTIONS:
        try:
            html, method = fetch_html_with_fallback(
                url, validate=lambda h: "/help/articles/" in h, wait_selector=_ARTICLE_HREF_SEL,
            )
        except Exception as e:
            log.warning(f"[weex] seccion {market} no cargo: {e}")
            continue
        log.info(f"[weex] {market} - metodo usado: {method}")

        soup = BeautifulSoup(html, "html.parser")
        links = soup.select(_ARTICLE_HREF_SEL)
        if not links:
            continue
        any_section_ok = True

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
            if not title or is_noise(title):
                continue

            tickers = _extract_tickers(title)

            delist_at = known_dates.get(full_url)
            fetched_body = False
            if full_url not in known_dates and body_fetches_left > 0 and (delist_at is None or not tickers):
                body_fetches_left -= 1
                fetched_body = True
                body_text = _fetch_article_text(full_url)
                if delist_at is None:
                    delist_at = extract_delist_date_from_body(body_text) if body_text else None
                if not tickers and body_text:
                    tickers = extract_tickers_from_body(body_text)
            if delist_at is None:
                delist_at = parse_delist_datetime(title)

            if not tickers:
                log.warning(f"[weex] no se pudieron sacar tickers de: {title!r} ({full_url})")
                continue

            for base in tickers:
                rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=full_url, title=title, asset_class=classify_asset_class(title),
                    announced_at=None, delist_at=delist_at, market=market,
                ))
            if fetched_body:
                time.sleep(0.3)

    if not any_section_ok and not rows:
        raise ExchangeBlocked("[weex] ninguna de las 2 secciones de deslistado cargo articulos")

    log.info(f"[weex] {len(rows)} filas")
    return rows
