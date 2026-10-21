"""Bybit: la API oficial (api.bybit.com/v5/announcements/index) esta bloqueada por
CloudFront ("configured to block access from your country") desde el runner de GitHub
Actions - confirmado con requests Y con Playwright, es un bloqueo geografico de borde, no
un challenge de bot. La pagina publica de anuncios (announcements.bybit.com) SI responde
200 normal, es Next.js con __NEXT_DATA__ (mismo patron que otros exchanges), y trae los
avisos en props.pageProps.articleInitEntity.list. Categoria confirmada navegando
pageEntry.categoryConnection: "New Listings" = key "new_crypto" (coincide con el "type"
que ya usaba la API vieja). /en/ es el locale principal (mas avisos, ~1800 vs ~1200 en
/es-MX/); /es-MX/ solo se usa de respaldo si /en/ falla del todo - la url relativa del
articulo es identica entre locales, asi que el upsert (dedupea por source_url) no duplica
nada si alguna vez se usan los dos."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

import requests

from .common import Row, DEFAULT_HEADERS, classify_asset_class_or_ticker, is_noise

log = logging.getLogger("newlistings.bybit")

EXCHANGE = "bybit"
BASE = "https://announcements.bybit.com"
LOCALES = ["en", "es-MX"]  # es-MX solo como respaldo
CATEGORY = "new_crypto"  # "New Listings" en pageEntry.categoryConnection

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

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
# "New listing: CTUSDT Perpetual Contract, with up to 20x leverage" / "...TLTUSDT TradFi
# Perpetual Contract..." - formato sin "Listing of X on Bybit", el ticker va pegado antes
# de "USDT" directo despues de "New listing:".
_NEW_LISTING_USDT_RE = re.compile(r"New listing:\s+([A-Z0-9]{1,15})USDT\s+(?:TradFi\s+)?Perpetual Contract", re.IGNORECASE)


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
    m = _NEW_LISTING_USDT_RE.search(title)
    if m:
        return m.group(1).upper()
    m = _TO_LIST_PAREN_RE.search(title)
    if m:
        return m.group(1).upper()
    return None


def _fetch_page(locale: str, page: int) -> tuple[list[dict], bool]:
    """Devuelve (items, ok). ok=False corta la paginacion de este locale (403/bloqueo/
    __NEXT_DATA__ ausente) en vez de reintentar a ciegas."""
    params = {"category": CATEGORY}
    if page > 1:
        params["page"] = page
    resp = requests.get(f"{BASE}/{locale}/", params=params, headers=DEFAULT_HEADERS, timeout=30)
    if resp.status_code != 200:
        log.warning(f"[bybit] {locale} pagina {page} respondio {resp.status_code}")
        return [], False
    m = _NEXT_DATA_RE.search(resp.text)
    if not m:
        log.warning(f"[bybit] {locale} pagina {page}: no se encontro __NEXT_DATA__")
        return [], False
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        log.warning(f"[bybit] {locale} pagina {page}: __NEXT_DATA__ invalido")
        return [], False
    page_props = (data.get("props") or {}).get("pageProps") or {}
    items = (page_props.get("articleInitEntity") or {}).get("list") or []
    return items, True


def fetch(max_pages: int = 10) -> list[Row]:
    rows: list[Row] = []
    seen_urls: set[str] = set()

    for locale in LOCALES:
        locale_rows: list[Row] = []
        locale_ok = False

        for page in range(1, max_pages + 1):
            items, ok = _fetch_page(locale, page)
            if not ok:
                break
            if not items:
                break
            locale_ok = True

            for item in items:
                if (item.get("category") or {}).get("key") != CATEGORY:
                    continue
                title = (item.get("title") or "").strip()
                if not title or is_noise(title):
                    continue
                rel_url = item.get("url") or ""
                if not rel_url or rel_url in seen_urls:
                    continue

                base = _extract_ticker(title)
                if not base:
                    log.warning(f"[bybit] no se pudieron sacar tickers de: {title!r} ({rel_url})")
                    continue
                seen_urls.add(rel_url)

                full_url = BASE + rel_url if rel_url.startswith("/") else rel_url
                try:
                    announced_at = datetime.fromtimestamp(int(item.get("publish_time")), tz=timezone.utc)
                except (TypeError, ValueError):
                    announced_at = None

                topics = item.get("topics") or []
                if "Derivatives" in topics or "perpetual" in title.lower():
                    market = "futures"
                elif "Spot Listings" in topics or "Spot" in topics:
                    market = "spot"
                else:
                    market = None

                listed_at = _parse_listed_at(title)
                asset_class = classify_asset_class_or_ticker(title, base)

                locale_rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=full_url, title=title, asset_class=asset_class,
                    announced_at=announced_at, listed_at=listed_at, market=market,
                ))

            time.sleep(0.5)

        log.info(f"[bybit] locale {locale}: {len(locale_rows)} filas")
        rows.extend(locale_rows)
        if locale_ok:
            break  # el locale principal funciono, no hace falta el de respaldo

    log.info(f"[bybit] {len(rows)} filas")
    return rows
