"""Kraken: su centro de ayuda NO tiene categoria de nuevos listados (se confirmo navegando
"Trading" entero - solo hay delistings). La fuente real es el blog oficial (WordPress),
categoria "Asset Listings" (id 1789, slug asset-listings): blog.kraken.com/wp-json/wp/v2/posts.
Patron unico y consistente: "{TICKER} is available for trading!" - todo spot cripto."""

from __future__ import annotations

import html
import logging
import re
import time
from datetime import datetime, timezone

import requests

from .common import Row, DEFAULT_HEADERS, ExchangeBlocked, is_noise

log = logging.getLogger("newlistings.kraken")

EXCHANGE = "kraken"
LIST_URL = "https://blog.kraken.com/wp-json/wp/v2/posts"
CATEGORY_ID = 1789  # "Asset Listings", confirmado via /wp-json/wp/v2/categories?slug=asset-listings

_TITLE_RE = re.compile(r"^([A-Za-z0-9]{1,15})\s+is available for trading!?$", re.IGNORECASE)


def _parse_date_gmt(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _get_with_retries(params: dict, max_retries: int = 3):
    resp = None
    for attempt in range(max_retries):
        resp = requests.get(LIST_URL, params=params, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 429:
            return resp
        wait = resp.headers.get("Retry-After")
        try:
            wait = float(wait)
        except (TypeError, ValueError):
            wait = 2 ** (attempt + 2)  # 4s, 8s, 16s
        log.warning(f"[kraken] 429, esperando {wait}s antes de reintentar (intento {attempt + 1}/{max_retries})")
        time.sleep(wait)
    return resp


def fetch(max_pages: int = 3) -> list[Row]:
    rows: list[Row] = []
    for page in range(1, max_pages + 1):
        params = {
            "categories": CATEGORY_ID, "per_page": 50, "page": page,
            "_fields": "date_gmt,title,link",
        }
        resp = _get_with_retries(params)
        if resp.status_code != 200:
            if page == 1:
                raise ExchangeBlocked(f"[kraken] pagina {page} respondio {resp.status_code}: {resp.text[:300]}")
            log.warning(f"[kraken] pagina {page} respondio {resp.status_code}: {resp.text[:300]}")
            break
        items = resp.json()
        if not items:
            break

        for item in items:
            raw_title = (item.get("title") or {}).get("rendered") or ""
            title = html.unescape(raw_title).strip()
            if not title or is_noise(title):
                continue
            url = item.get("link", "")
            announced_at = _parse_date_gmt(item.get("date_gmt", ""))

            m = _TITLE_RE.match(title)
            if not m:
                log.warning(f"[kraken] no se pudieron sacar tickers de: {title!r} ({url})")
                continue
            base = m.group(1).upper()

            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title, asset_class="crypto",
                announced_at=announced_at, market="spot",
            ))

        if len(items) < 50:
            break
        time.sleep(0.5)

    log.info(f"[kraken] {len(rows)} filas")
    return rows
