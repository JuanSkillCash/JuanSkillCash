"""Blofin: misma pagina de soporte Next.js/__NEXT_DATA__ que newlistings/blofin.py, pero
categoria "Announcement/Delisting" (confirmada por diagnostico real: 10 articulos reales
en pagina 1, totalPages=35). El titulo siempre trae el/los tickers en MAYUSCULA pegados a
"Will Delist" ("Will Delist NFP for Spot Trading", "Will Delist TOWNS, EUL, RLS, ALKIMI,
IKA and KYO for Spot Trading", "Will Delist EPICUSDT Perpetual Contract") - un token 100%
mayuscula tras ese verbo basta para sacarlos sin tener que separar "for"/"on" a mano, y de
paso descarta solo los avisos de deslistado de pares de Copy Trading ("Will Delist 33 Copy
Trading Pairs", "to Remove 29 Perpetual Contract Pairs from Copy Trading") que no nombran
ningun activo real deslistado del spot/futuros - ahi ningun token queda en mayuscula."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

import requests

from .common import (
    Row, DEFAULT_HEADERS, ExchangeBlocked, extract_delist_date_from_body,
    extract_tickers_from_body, detect_market, html_to_text, is_noise, parse_delist_datetime,
    classify_asset_class, fetch_known_delist_dates,
)

log = logging.getLogger("delistings.blofin")

EXCHANGE = "blofin"
LIST_URL = "https://blofin.com/en/support/Announcement/Delisting"
BASE = "https://blofin.com"

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_WILL_DELIST_TAIL_RE = re.compile(r"Will Delist\s+(.+)$", re.IGNORECASE)
_CAPS_TOKEN_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,14})\b")
_QUOTE_SUFFIXES = ("USDT", "USDC", "USD")


def _strip_quote(tok: str) -> str:
    for q in _QUOTE_SUFFIXES:
        if tok.endswith(q) and len(tok) > len(q) + 1:
            return tok[: -len(q)]
    return tok


def _extract_tickers(title: str) -> list[str]:
    m = _WILL_DELIST_TAIL_RE.search(title)
    tail = m.group(1) if m else title
    out = []
    for tok in _CAPS_TOKEN_RE.findall(tail):
        tok = _strip_quote(tok)
        if tok not in out:
            out.append(tok)
    return out


def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%B %d, %Y at %I:%M %p").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _fetch_page(page: int) -> tuple[list[dict], int]:
    url = LIST_URL if page == 1 else f"{LIST_URL}?page={page}"
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
    if resp.status_code != 200:
        raise ExchangeBlocked(f"[blofin] {url} respondio {resp.status_code}")
    m = _NEXT_DATA_RE.search(resp.text)
    if not m:
        raise ExchangeBlocked(f"[blofin] {url}: no se encontro __NEXT_DATA__")
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        raise ExchangeBlocked(f"[blofin] {url}: __NEXT_DATA__ invalido")
    page_props = ((data.get("props") or {}).get("pageProps") or {})
    return page_props.get("articles") or [], int(page_props.get("totalPages") or 1)


def _fetch_article_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=12)
        if resp.status_code != 200:
            return ""
        return html_to_text(resp.text)
    except requests.RequestException as e:
        log.warning(f"[blofin] fallo trayendo articulo {url}: {e}")
        return ""


def fetch(max_pages: int = 3) -> list[Row]:
    rows: list[Row] = []
    body_fetches_left = 15
    known_dates = fetch_known_delist_dates(EXCHANGE)
    page = 1
    total_pages = 1
    while page <= total_pages and page <= max_pages:
        try:
            articles, total_pages = _fetch_page(page)
        except ExchangeBlocked:
            if page == 1:
                raise
            break
        if not articles:
            break

        for art in articles:
            title = (art.get("title") or "").strip()
            if not title or is_noise(title):
                continue
            href = art.get("href", "")
            url = href if href.startswith("http") else BASE + href
            announced_at = _parse_date(art.get("date", ""))

            tickers = _extract_tickers(title)

            delist_at = known_dates.get(url)
            fetched_body = False
            if url not in known_dates and body_fetches_left > 0 and (delist_at is None or not tickers):
                body_fetches_left -= 1
                fetched_body = True
                body_text = _fetch_article_text(url)
                if delist_at is None:
                    delist_at = extract_delist_date_from_body(body_text, announced_at) if body_text else None
                if not tickers and body_text:
                    tickers = extract_tickers_from_body(body_text)
            if delist_at is None:
                delist_at = parse_delist_datetime(title)

            if not tickers:
                log.warning(f"[blofin] no se pudieron sacar tickers de: {title!r} ({url})")
                continue

            market = detect_market(title)
            for base in tickers:
                rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=url, title=title, asset_class=classify_asset_class(title),
                    announced_at=announced_at, delist_at=delist_at, market=market,
                ))
            if fetched_body:
                time.sleep(0.3)

        page += 1
        if page <= total_pages and page <= max_pages:
            time.sleep(0.5)

    log.info(f"[blofin] {len(rows)} filas")
    return rows
