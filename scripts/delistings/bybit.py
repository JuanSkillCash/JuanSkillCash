"""Bybit: API v5 oficial (/v5/announcements/index), documentada pero NO confirmada en vivo
en la investigacion (peticion rechazada desde su entorno, posible bloqueo de IP de
datacenter o de EE.UU.). Se prueba igual desde el runner de GitHub Actions - si falla
tambien desde aqui, failures la marca y el orquestador sigue con los demas exchanges sin
que esto tumbe la corrida."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from .common import (
    Row, DEFAULT_HEADERS, extract_delist_date_from_body, extract_tickers, detect_market,
    is_noise, html_to_text, parse_delist_datetime,
)

log = logging.getLogger("delistings.bybit")

EXCHANGE = "bybit"
LIST_URL = "https://api.bybit.com/v5/announcements/index"


def _epoch_ms_to_dt(s) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
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


def fetch(max_pages: int = 5) -> list[Row]:
    rows: list[Row] = []
    page = 1
    items: list[dict] = []

    while page <= max_pages:
        params = {"locale": "en-US", "type": "delistings", "page": page, "limit": 50}
        resp = requests.get(LIST_URL, params=params, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[bybit] listado pagina {page} respondio {resp.status_code}: {resp.text[:300]}")
            break
        payload = resp.json()
        if payload.get("retCode") != 0:
            log.warning(f"[bybit] retCode!=0: {payload.get('retMsg')}")
            break
        result = payload.get("result") or {}
        batch = result.get("list") or []
        if not batch:
            break
        items.extend(batch)
        total = result.get("total", len(items))
        page += 1
        if len(items) >= total:
            break
        time.sleep(1)

    log.info(f"[bybit] {len(items)} anuncios traidos")

    for item in items:
        title = (item.get("title") or "").strip()
        if not title or is_noise(title):
            continue
        url = item.get("url", "")
        announced_at = _epoch_ms_to_dt(item.get("publishTime") or item.get("dateTimestamp"))

        body_text = _fetch_article_text(url) if url else ""
        delist_at = extract_delist_date_from_body(body_text, announced_at) if body_text else None
        if delist_at is None:
            delist_at = extract_delist_date_from_body(item.get("description", ""), announced_at)
        if delist_at is None:
            delist_at = parse_delist_datetime(title)

        market = detect_market(title)
        tickers = extract_tickers(title)
        if not tickers:
            log.warning(f"[bybit] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title,
                announced_at=announced_at, delist_at=delist_at, market=market,
            ))
        time.sleep(0.4)

    log.info(f"[bybit] {len(rows)} filas")
    return rows
