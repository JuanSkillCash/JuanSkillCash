"""Bitget: API v2 oficial y publica (sin auth). Ojo: el path real tiene un typo
("annoucements", sin la segunda "n") - confirmado en la investigacion, no es un error de
quien escribio esto."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from .common import (
    Row, DEFAULT_HEADERS, extract_delist_date_from_body, extract_tickers, detect_market,
    is_noise, is_delay_notice, html_to_text, parse_delist_datetime,
)

log = logging.getLogger("delistings.bitget")

EXCHANGE = "bitget"
LIST_URL = "https://api.bitget.com/api/v2/public/annoucements"  # typo real de la API


def _epoch_ms_to_dt(s) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _fetch_article_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[bitget] articulo {url} respondio {resp.status_code}")
            return ""
        return html_to_text(resp.text)
    except requests.RequestException as e:
        log.warning(f"[bitget] fallo trayendo articulo {url}: {e}")
        return ""


def fetch(max_requests: int = 10) -> list[Row]:
    rows: list[Row] = []
    cursor = None
    n_requests = 0

    while n_requests < max_requests:
        params = {"language": "en_US", "annType": "symbol_delisting", "limit": 10}
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

            if is_delay_notice(title):
                # regla comun #5: esto actualiza el delist_at de una fila ya existente, no
                # crea una fila nueva - el orquestador decide que hacer con esto (por ahora
                # se deja pasar igual que cualquier otro anuncio: el upsert por
                # (exchange,symbol,source_url) de todas formas no pisa la fila original
                # porque source_url es distinto; se deja registrado para revisar a mano)
                log.info(f"[bitget] aviso de retraso de deslistado (revisar a mano): {title!r}")

            body_text = _fetch_article_text(url) if url else ""
            delist_at = extract_delist_date_from_body(body_text, announced_at) if body_text else None
            if delist_at is None:
                delist_at = parse_delist_datetime(title)

            market = detect_market(title)
            tickers = extract_tickers(title)
            if not tickers:
                log.warning(f"[bitget] no se pudieron sacar tickers de: {title!r} ({url})")
                continue

            for base in tickers:
                rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=url or f"bitget:{ann_id}", title=title,
                    announced_at=announced_at, delist_at=delist_at, market=market,
                ))
            time.sleep(0.5)

        cursor = str(items[-1].get("annId", "")) if len(items) == 10 else None
        if not cursor:
            break
        time.sleep(1)

    log.info(f"[bitget] {len(rows)} filas")
    return rows
