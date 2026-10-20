"""Bybit: misma API v5 oficial que delistings/bybit.py (bloquea IPs de datacenter - ya
documentado ahi), categoria confirmada en la investigacion: type=new_crypto. Se filtra
por tag en vez de adivinar por palabras ("Spot Listings" -> spot, "Derivatives" -> futures).
"TradFi" marca un activo no cripto pero no dice CUAL (accion/indice/commodity) - se resuelve
con la lista stock_tickers.txt via classify_asset_class_or_ticker."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

import requests

from .common import Row, DEFAULT_HEADERS, classify_asset_class_or_ticker, is_noise

log = logging.getLogger("newlistings.bybit")

EXCHANGE = "bybit"
LIST_URL = "https://api.bybit.com/v5/announcements/index"

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_TITLE_DATE_RE = re.compile(
    r"on\s+([A-Za-z]{3,9})\.?\s+(\d{1,2}),\s*(\d{4}),\s*(\d{1,2}):(\d{2})\s*(AM|PM)\s*UTC",
    re.IGNORECASE,
)
_LISTING_OF_RE = re.compile(r"Listing of\s+([A-Z0-9]{2,15})\s+on Bybit", re.IGNORECASE)
_TO_LIST_PAREN_RE = re.compile(r"to List\s+\w+\s*\(([A-Z0-9]{1,15})\)\s+on Spot", re.IGNORECASE)


def _parse_listed_at(title: str) -> datetime | None:
    m = _TITLE_DATE_RE.search(title)
    if not m:
        return None
    mon, day, year, hour, minute, ampm = m.groups()
    mo = _MONTHS.get(mon.strip().lower()[:3])
    if not mo:
        return None
    hour = int(hour) % 12
    if ampm.upper() == "PM":
        hour += 12
    try:
        return datetime(int(year), mo, int(day), hour, int(minute), tzinfo=timezone.utc)
    except ValueError:
        return None


def _strip_quote(tok: str) -> str:
    tok = tok.upper()
    for q in ("USDT", "USDC", "USD"):
        if tok.endswith(q) and len(tok) > len(q) + 1:
            return tok[: -len(q)]
    return tok


def _extract_ticker(title: str) -> str | None:
    m = _LISTING_OF_RE.search(title)
    if m:
        return _strip_quote(m.group(1))
    m = _TO_LIST_PAREN_RE.search(title)
    if m:
        return m.group(1).upper()
    return None


def fetch(max_pages: int = 5) -> list[Row]:
    rows: list[Row] = []
    for page in range(1, max_pages + 1):
        params = {"locale": "en-US", "type": "new_crypto", "limit": 20, "page": page}
        resp = requests.get(LIST_URL, params=params, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[bybit] pagina {page} respondio {resp.status_code}: {resp.text[:300]}")
            break
        payload = resp.json()
        if payload.get("retCode") != 0:
            log.warning(f"[bybit] retCode!=0: {payload.get('retMsg')}")
            break
        items = (payload.get("result") or {}).get("list") or []
        if not items:
            break

        for item in items:
            title = (item.get("title") or "").strip()
            if not title or is_noise(title):
                continue
            url = item.get("url", "")
            tags = item.get("tags") or []
            announced_ms = item.get("publishTime") or item.get("dateTimestamp")
            try:
                announced_at = datetime.fromtimestamp(int(announced_ms) / 1000, tz=timezone.utc)
            except (TypeError, ValueError):
                announced_at = None

            base = _extract_ticker(title)
            if not base:
                log.warning(f"[bybit] no se pudieron sacar tickers de: {title!r} ({url})")
                continue

            if "Derivatives" in tags or "perpetual" in title.lower():
                market = "futures"
            elif "Spot Listings" in tags or "Spot" in tags:
                market = "spot"
            else:
                market = None

            listed_at = _parse_listed_at(title)
            asset_class = classify_asset_class_or_ticker(title, base)

            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title, asset_class=asset_class,
                announced_at=announced_at, listed_at=listed_at, market=market,
            ))

        if len(items) < 20:
            break
        time.sleep(0.5)

    log.info(f"[bybit] {len(rows)} filas")
    return rows
