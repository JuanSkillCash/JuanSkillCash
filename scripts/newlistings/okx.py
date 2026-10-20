"""OKX: misma API v5 oficial que delistings/okx.py, categoria confirmada en el sondeo:
annType=announcements-new-listings. El ticker en OKX siempre va ANTES del separador ("to
list TICKER (Name)" / "will launch TICKER/USD"), al reves que la mayoria de los otros
exchanges (donde va DENTRO del parentesis) - por eso usa su propio extractor en vez del
generico de common.py (que asumiria mal "to list MON (Monad)" -> "MONAD")."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

import requests

from .common import Row, DEFAULT_HEADERS, classify_asset_class, detect_market, is_noise, split_run

log = logging.getLogger("newlistings.okx")

EXCHANGE = "okx"
LIST_URL = "https://www.okx.com/api/v5/support/announcements"
ANN_TYPE = "announcements-new-listings"

_LAUNCH_SLASH_RE = re.compile(r"will launch\s+([A-Z][A-Z0-9]{1,14})/", re.IGNORECASE)
_LIST_BEFORE_SLASH_RE = re.compile(r"to list\s+([A-Z][A-Z0-9]{1,14})/", re.IGNORECASE)
_LIST_BEFORE_PAREN_RE = re.compile(r"to list\s+([A-Z][A-Za-z0-9]{1,14})\s*\(", re.IGNORECASE)
_LIST_COMMA_RE = re.compile(
    r"to list\s+([A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*(?:,?\s*and\s+[A-Z0-9]+)?)\s+for\s+spot\s+trading",
    re.IGNORECASE,
)


def _extract_okx_tickers(title: str) -> list[str]:
    for rx in (_LAUNCH_SLASH_RE, _LIST_BEFORE_SLASH_RE, _LIST_BEFORE_PAREN_RE):
        m = rx.search(title)
        if m:
            return [m.group(1).upper()]
    m = _LIST_COMMA_RE.search(title)
    if m:
        return split_run(m.group(1))
    return []


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

        tickers = _extract_okx_tickers(title)
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
