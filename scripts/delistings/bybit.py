"""Bybit: la API oficial (api.bybit.com/v5/announcements/index) esta bloqueada por
CloudFront ("configured to block access from your country") - confirmado con requests Y
con Playwright, bloqueo geografico de borde, no un challenge de bot. La pagina publica de
anuncios (announcements.bybit.com, Next.js con __NEXT_DATA__) SI responde 200 normal y
tiene categoria propia de deslistados (pageEntry.categoryConnection -> "Delistings" = key
"delistings", confirmada junto con "New Listings" al investigar newlistings/bybit.py).
/en/ es el locale principal (mas avisos); /es-MX/ solo de respaldo si /en/ falla del todo -
la url relativa del articulo es identica entre locales asi que el upsert no duplica nada."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

import requests

from .common import (
    Row, DEFAULT_HEADERS, ExchangeBlocked, extract_delist_date_from_body, extract_tickers,
    detect_market, is_noise, html_to_text, parse_delist_datetime, classify_asset_class,
)

log = logging.getLogger("delistings.bybit")

EXCHANGE = "bybit"
BASE = "https://announcements.bybit.com"
LOCALES = ["en", "es-MX"]
CATEGORY = "delistings"

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _epoch_s_to_dt(s) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(s), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _fetch_article_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[bybit] articulo {url} respondio {resp.status_code}")
            return ""
        return html_to_text(resp.text)
    except requests.RequestException as e:
        log.warning(f"[bybit] fallo trayendo articulo {url}: {e}")
        return ""


def _fetch_page(locale: str, page: int) -> list[dict]:
    params = {"category": CATEGORY}
    if page > 1:
        params["page"] = page
    resp = requests.get(f"{BASE}/{locale}/", params=params, headers=DEFAULT_HEADERS, timeout=30)
    if resp.status_code != 200:
        raise ExchangeBlocked(f"[bybit] {locale} pagina {page} respondio {resp.status_code}")
    m = _NEXT_DATA_RE.search(resp.text)
    if not m:
        raise ExchangeBlocked(f"[bybit] {locale} pagina {page}: no se encontro __NEXT_DATA__")
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        raise ExchangeBlocked(f"[bybit] {locale} pagina {page}: __NEXT_DATA__ invalido")
    page_props = (data.get("props") or {}).get("pageProps") or {}
    return (page_props.get("articleInitEntity") or {}).get("list") or []


def fetch(max_pages: int = 10) -> list[Row]:
    rows: list[Row] = []
    seen_urls: set[str] = set()
    blocked_errors: list[ExchangeBlocked] = []

    for locale in LOCALES:
        locale_rows: list[Row] = []
        locale_ok = False

        for page in range(1, max_pages + 1):
            try:
                items = _fetch_page(locale, page)
            except ExchangeBlocked as e:
                if page == 1:
                    blocked_errors.append(e)
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

                tickers = extract_tickers(title)
                if not tickers:
                    log.warning(f"[bybit] no se pudieron sacar tickers de: {title!r} ({rel_url})")
                    continue
                seen_urls.add(rel_url)

                full_url = BASE + rel_url if rel_url.startswith("/") else rel_url
                announced_at = _epoch_s_to_dt(item.get("publish_time"))

                body_text = _fetch_article_text(full_url)
                delist_at = extract_delist_date_from_body(body_text, announced_at) if body_text else None
                if delist_at is None:
                    delist_at = extract_delist_date_from_body(item.get("description", ""), announced_at)
                if delist_at is None:
                    delist_at = parse_delist_datetime(title)

                market = detect_market(title)
                for base in tickers:
                    locale_rows.append(Row(
                        exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                        source_url=full_url, title=title, asset_class=classify_asset_class(title),
                        announced_at=announced_at, delist_at=delist_at, market=market,
                    ))
                time.sleep(0.3)

            time.sleep(0.5)

        log.info(f"[bybit] locale {locale}: {len(locale_rows)} filas")
        rows.extend(locale_rows)
        if locale_ok:
            break  # el locale principal funciono, no hace falta el de respaldo

    if not rows and blocked_errors:
        raise blocked_errors[0]

    log.info(f"[bybit] {len(rows)} filas")
    return rows
