"""KuCoin: misma API v3 publica que delistings/kucoin.py, categoria confirmada en el
sondeo: annType=new-listings. A diferencia de "delistings", esta categoria SI devolvio
resultados recientes y consistentes sin necesidad de pasar una ventana de fechas explicita
(confirmado en el sondeo), asi que no hace falta la ventana startTime/endTime que si
necesitaba el scraper de deslistados."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from .common import (
    Row, DEFAULT_HEADERS, classify_asset_class, extract_tickers, is_noise, parse_delist_datetime,
)

log = logging.getLogger("newlistings.kucoin")

EXCHANGE = "kucoin"
LIST_URL = "https://api.kucoin.com/api/v3/announcements"
ANN_TYPE = "new-listings"


def _epoch_ms_to_dt(s) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def fetch(max_pages: int = 5) -> list[Row]:
    rows: list[Row] = []
    page = 1
    total_page = 1
    items: list[dict] = []

    while page <= total_page and page <= max_pages:
        params = {"annType": ANN_TYPE, "lang": "en_US", "pageSize": 50, "currentPage": page}
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

    log.info(f"[kucoin] {len(items)} anuncios en {page - 1} pagina(s)")

    for item in items:
        title = (item.get("annTitle") or "").strip()
        if not title or is_noise(title):
            continue
        url = item.get("annUrl", "")
        announced_at = _epoch_ms_to_dt(item.get("cTime"))
        ann_types = item.get("annType") or []
        market = "futures" if "futures-announcements" in ann_types else "spot"

        tickers = extract_tickers(title)
        if not tickers:
            log.warning(f"[kucoin] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        asset_class = classify_asset_class(title)
        listed_at = parse_delist_datetime(title, strict=True)
        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url or f"kucoin:{item.get('annId')}", title=title, asset_class=asset_class,
                announced_at=announced_at, listed_at=listed_at, market=market,
            ))

    log.info(f"[kucoin] {len(rows)} filas")
    return rows
