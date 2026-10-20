"""OKX: misma API v5 oficial que delistings/okx.py, categoria confirmada en el sondeo:
annType=announcements-new-listings. El extractor compartido (common.extract_tickers) ya
resuelve tanto "will launch TICKER/USD" como "to list TICKER (Name)" / "to list Name
(TICKER)" (la ambiguedad ticker-antes-o-dentro-del-parentesis la resuelve _pick_ticker)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from .common import Row, DEFAULT_HEADERS, classify_asset_class, detect_market, extract_tickers, is_noise

log = logging.getLogger("newlistings.okx")

EXCHANGE = "okx"
LIST_URL = "https://www.okx.com/api/v5/support/announcements"
ANN_TYPE = "announcements-new-listings"


def _epoch_ms_to_dt(s) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def fetch(max_pages: int = 5) -> list[Row]:
    rows: list[Row] = []
    page = 1
    total_page = 1
    items = []
    while page <= total_page and page <= max_pages:
        resp = requests.get(
            LIST_URL, params={"annType": ANN_TYPE, "page": page}, headers=DEFAULT_HEADERS, timeout=30,
        )
        if resp.status_code != 200:
            log.warning(f"[okx] listado pagina {page} respondio {resp.status_code}: {resp.text[:300]}")
            break
        payload = resp.json()
        if payload.get("code") != "0":
            log.warning(f"[okx] respuesta con code!=0: {payload.get('msg')}")
            break
        data = (payload.get("data") or [{}])[0]
        try:
            total_page = int(data.get("totalPage", 1))
        except (TypeError, ValueError):
            total_page = 1
        items.extend(data.get("details", []))
        page += 1
        if page <= total_page:
            time.sleep(1)

    log.info(f"[okx] {len(items)} anuncios en {page - 1} pagina(s) (totalPage={total_page})")

    for item in items:
        title = item.get("title", "")
        url = item.get("url", "")
        if not title or is_noise(title):
            continue
        announced_at = _epoch_ms_to_dt(item.get("businessPTime") or item.get("pTime"))

        tickers = extract_tickers(title)
        if not tickers:
            log.warning(f"[okx] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        market = detect_market(title)
        asset_class = classify_asset_class(title)
        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title, asset_class=asset_class,
                announced_at=announced_at, market=market,
            ))

    log.info(f"[okx] {len(rows)} filas")
    return rows
