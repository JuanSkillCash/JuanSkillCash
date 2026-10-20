"""Blofin: HTML Next.js con __NEXT_DATA__, paginado (?page=N), confirmado en la
investigacion. Dos categorias separadas (Futures-Listing / Spot-Listing) - el market sale
directo de cual URL se consulto, no hace falta adivinar por texto."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

import requests

from .common import Row, DEFAULT_HEADERS, classify_asset_class_or_ticker, is_noise, split_run

log = logging.getLogger("newlistings.blofin")

EXCHANGE = "blofin"
SECTIONS = [
    ("https://blofin.com/en/support/Announcement/Futures-Listing", "futures"),
    ("https://blofin.com/en/support/Announcement/Spot-Listing", "spot"),
]

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_FUTURES_LIST_RE = re.compile(r"to List\s+(.*?)\s*:", re.IGNORECASE)
_SPOT_RE = re.compile(
    r"to List\s+([A-Z0-9]{1,15})/(?:USDT|USD|USDC)\s+for Spot Trading\s*(?:\((\d{4})-(\d{1,2})-(\d{1,2})\))?",
    re.IGNORECASE,
)


def _fetch_page(url: str, page: int) -> tuple[list[dict], int]:
    full_url = url if page == 1 else f"{url}?page={page}"
    resp = requests.get(full_url, headers=DEFAULT_HEADERS, timeout=30)
    if resp.status_code != 200:
        log.warning(f"[blofin] {full_url} respondio {resp.status_code}")
        return [], 1
    m = _NEXT_DATA_RE.search(resp.text)
    if not m:
        log.warning(f"[blofin] no se encontro __NEXT_DATA__ en {full_url}")
        return [], 1
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return [], 1
    page_props = ((data.get("props") or {}).get("pageProps") or {})
    return page_props.get("articles") or [], int(page_props.get("totalPages") or 1)


def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%B %d, %Y at %I:%M %p").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fetch(max_pages: int = 3) -> list[Row]:
    rows: list[Row] = []
    for base_url, market in SECTIONS:
        page = 1
        total_pages = 1
        while page <= total_pages and page <= max_pages:
            articles, total_pages = _fetch_page(base_url, page)
            if not articles:
                break

            for art in articles:
                title = (art.get("title") or "").strip()
                if not title or is_noise(title):
                    continue
                href = art.get("href", "")
                url = href if href.startswith("http") else "https://blofin.com" + href
                announced_at = _parse_date(art.get("date", ""))

                if market == "futures":
                    m = _FUTURES_LIST_RE.search(title)
                    tickers = split_run(m.group(1)) if m else []
                    listed_at = None
                else:
                    m = _SPOT_RE.search(title)
                    if m:
                        tickers = [m.group(1).upper()]
                        if m.group(2):
                            y, mo, d = int(m.group(2)), int(m.group(3)), int(m.group(4))
                            listed_at = datetime(y, mo, d, tzinfo=timezone.utc)
                        else:
                            listed_at = None
                    else:
                        tickers = []
                        listed_at = None

                if not tickers:
                    log.warning(f"[blofin] no se pudieron sacar tickers de: {title!r} ({url})")
                    continue

                for base in tickers:
                    asset_class = classify_asset_class_or_ticker(title, base)
                    rows.append(Row(
                        exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                        source_url=url, title=title, asset_class=asset_class,
                        announced_at=announced_at, listed_at=listed_at, market=market,
                    ))

            page += 1
            if page <= total_pages and page <= max_pages:
                time.sleep(0.5)

    log.info(f"[blofin] {len(rows)} filas")
    return rows
