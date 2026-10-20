"""Bitget: misma API v2 publica que delistings/bitget.py (mismo typo real "annoucements"),
categoria confirmada en el sondeo: annType=coin_listings. Trae de todo bajo este annType
(incluye ruido tipo "copy trading now supports N perpetual futures", filtrado por is_noise) -
aca es donde aparecen los casos reales de acciones taiwanesas/hot stock perps que confirmo
la investigacion (TWTSMUSDT = TSMC, CSTOCKUSDT, etc.)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from .common import (
    Row, DEFAULT_HEADERS, classify_asset_class, detect_market, extract_tickers, is_noise,
    parse_delist_datetime,
)

log = logging.getLogger("newlistings.bitget")

EXCHANGE = "bitget"
LIST_URL = "https://api.bitget.com/api/v2/public/annoucements"  # typo real de la API
ANN_TYPE = "coin_listings"


def _epoch_ms_to_dt(s) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def fetch(max_requests: int = 10) -> list[Row]:
    rows: list[Row] = []
    cursor = None
    n_requests = 0

    while n_requests < max_requests:
        params = {"language": "en_US", "annType": ANN_TYPE, "limit": 10}
        if cursor:
            params["cursor"] = cursor

        resp = requests.get(LIST_URL, params=params, headers=DEFAULT_HEADERS, timeout=30)
        n_requests += 1
        if resp.status_code != 200:
            log.warning(f"[bitget] listado respondio {resp.status_code}: {resp.text[:300]}")
            break
        payload = resp.json()
        if payload.get("code") != "00000":
            log.warning(f"[bitget] respuesta con code!=00000: {payload.get('msg')}")
            break
        items = payload.get("data") or []
        if not items:
            break

        for item in items:
            title = (item.get("annTitle") or "").strip()
            if not title or is_noise(title):
                continue
            url = item.get("annUrl", "")
            ann_id = item.get("annId")
            announced_at = _epoch_ms_to_dt(item.get("cTime"))

            tickers = extract_tickers(title)
            if not tickers:
                log.warning(f"[bitget] no se pudieron sacar tickers de: {title!r} ({url})")
                continue

            market = detect_market(title)
            asset_class = classify_asset_class(title)
            listed_at = parse_delist_datetime(title, strict=True)
            for base in tickers:
                rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=url or f"bitget:{ann_id}", title=title, asset_class=asset_class,
                    announced_at=announced_at, listed_at=listed_at, market=market,
                ))

        cursor = str(items[-1].get("annId", "")) if len(items) == 10 else None
        if not cursor:
            break
        time.sleep(1)

    log.info(f"[bitget] {len(rows)} filas")
    return rows
