"""KuCoin: API v3 oficial y publica (sin auth). OJO (regla de la investigacion): sin
startTime/endTime explicitos la API devolvio resultados viejos/inconsistentes con lo que
mostraba la pagina web - por eso aca SIEMPRE se pasa una ventana de fechas."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import requests

from .common import (
    Row, DEFAULT_HEADERS, extract_delist_date_from_body, extract_tickers, detect_market,
    is_noise, html_to_text, parse_delist_datetime,
    classify_asset_class, fetch_known_delist_dates,
)

log = logging.getLogger("delistings.kucoin")

EXCHANGE = "kucoin"
LIST_URL = "https://api.kucoin.com/api/v3/announcements"

# ventana de la corrida normal (no backfill): cubre lo reciente + lo ya anunciado a futuro.
WINDOW_PAST_DAYS = 45
WINDOW_FUTURE_DAYS = 30
MAX_BODY_FETCHES = 15


def _epoch_ms_to_dt(s) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _fetch_article_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=12)
        if resp.status_code != 200:
            log.warning(f"[kucoin] articulo {url} respondio {resp.status_code}")
            return ""
        return html_to_text(resp.text)
    except requests.RequestException as e:
        log.warning(f"[kucoin] fallo trayendo articulo {url}: {e}")
        return ""


def fetch(max_pages: int = 5) -> list[Row]:
    now = datetime.now(timezone.utc)
    start_ms = int((now - timedelta(days=WINDOW_PAST_DAYS)).timestamp() * 1000)
    end_ms = int((now + timedelta(days=WINDOW_FUTURE_DAYS)).timestamp() * 1000)

    rows: list[Row] = []
    page = 1
    total_page = 1
    items: list[dict] = []

    while page <= total_page and page <= max_pages:
        params = {
            "annType": "delistings", "lang": "en_US", "pageSize": 50,
            "currentPage": page, "startTime": start_ms, "endTime": end_ms,
        }
        resp = requests.get(LIST_URL, params=params, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[kucoin] listado pagina {page} respondio {resp.status_code}: {resp.text[:300]}")
            break
        payload = resp.json()
        data = payload.get("data") or {}
        try:
            total_page = int(data.get("totalPage", 1))
        except (TypeError, ValueError):
            total_page = 1
        items.extend(data.get("items", []))
        page += 1
        if page <= total_page:
            time.sleep(1)

    log.info(f"[kucoin] {len(items)} anuncios en ventana de {WINDOW_PAST_DAYS}d atras / {WINDOW_FUTURE_DAYS}d adelante")

    body_fetches_left = MAX_BODY_FETCHES
    known_dates = fetch_known_delist_dates(EXCHANGE)
    for item in items:
        title = (item.get("annTitle") or "").strip()
        if not title or is_noise(title):
            continue
        url = item.get("annUrl", "")
        source_url = url or f"kucoin:{item.get('annId')}"
        announced_at = _epoch_ms_to_dt(item.get("cTime"))
        ann_types = item.get("annType") or []
        is_futures = "futures-announcements" in ann_types

        delist_at = known_dates.get(source_url)
        fetched_body = False
        if delist_at is None and url and source_url not in known_dates and body_fetches_left > 0:
            body_fetches_left -= 1
            fetched_body = True
            body_text = _fetch_article_text(url)
            delist_at = extract_delist_date_from_body(body_text, announced_at) if body_text else None
        if delist_at is None:
            delist_at = parse_delist_datetime(title)

        market = "futures" if is_futures else detect_market(title)
        tickers = extract_tickers(title)
        if not tickers:
            log.warning(f"[kucoin] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=source_url, title=title, asset_class=classify_asset_class(title),
                announced_at=announced_at, delist_at=delist_at, market=market,
            ))
        if fetched_body:
            time.sleep(0.4)

    log.info(f"[kucoin] {len(rows)} filas")
    return rows
