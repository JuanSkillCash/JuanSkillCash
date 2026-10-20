"""Binance: mismo endpoint bapi que delistings/binance.py, catalogId confirmado en el
sondeo: 48 = "New Cryptocurrency Listing" (catalogName real devuelto por la API, no un
numero adivinado). Aca aparecen los bStocks (acciones tokenizadas) y los perpetuos TradFi
que confirmo la investigacion."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from .common import (
    Row, DEFAULT_HEADERS, classify_asset_class, detect_market, extract_tickers, is_noise,
    parse_delist_datetime,
)

log = logging.getLogger("newlistings.binance")

EXCHANGE = "binance"
CATALOG_ID = "48"  # "New Cryptocurrency Listing", confirmado en el sondeo (catalogName real)
LIST_URL = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
DETAIL_URL_TMPL = "https://www.binance.com/en/support/announcement/detail/{code}"


def _epoch_ms_to_dt(s) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def fetch(max_pages: int = 5) -> list[Row]:
    items: list[dict] = []
    page = 1
    total = None
    while page <= max_pages and (total is None or len(items) < total):
        params = {"type": 1, "catalogId": CATALOG_ID, "pageNo": page, "pageSize": 20}
        resp = requests.get(LIST_URL, params=params, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[binance] catalogo {CATALOG_ID} pagina {page} respondio {resp.status_code}: {resp.text[:300]}")
            break
        payload = resp.json()
        data = payload.get("data") or {}
        catalogs = data.get("catalogs") or []
        if not catalogs:
            break
        cat = catalogs[0]
        total = cat.get("total", 0)
        batch = cat.get("articles") or []
        if not batch:
            break
        items.extend(batch)
        page += 1
        if page <= max_pages:
            time.sleep(1)

    log.info(f"[binance] {len(items)} anuncios (catalogId={CATALOG_ID})")
    rows: list[Row] = []

    for item in items:
        title = (item.get("title") or "").strip()
        if not title or is_noise(title):
            continue
        code = item.get("code")
        url = DETAIL_URL_TMPL.format(code=code) if code else ""
        announced_at = _epoch_ms_to_dt(item.get("releaseDate"))

        tickers = extract_tickers(title)
        if not tickers:
            log.warning(f"[binance] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        market = detect_market(title)
        asset_class = classify_asset_class(title)
        listed_at = parse_delist_datetime(title, strict=True)
        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url or f"binance:{code}", title=title, asset_class=asset_class,
                announced_at=announced_at, listed_at=listed_at, market=market,
            ))

    log.info(f"[binance] {len(rows)} filas")
    return rows
