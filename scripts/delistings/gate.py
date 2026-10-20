"""Gate (gate.com, antes gate.io): pagina Next.js, los datos vienen embebidos en
<script id="__NEXT_DATA__"> dentro del HTML - no hay API JSON aparte. El detalle del
articulo (pares BASE_QUOTE) esta server-rendered en texto plano dentro de esa misma pagina."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from .common import (
    Row, DEFAULT_HEADERS, extract_delist_date_from_body, extract_tickers, detect_market,
    is_noise, is_completion_notice, html_to_text, parse_delist_datetime,
)

log = logging.getLogger("delistings.gate")

EXCHANGE = "gate"
LIST_URL = "https://www.gate.com/announcements/delisted"
BASE = "https://www.gate.com"

# pares escritos BASE_QUOTE en el cuerpo de los articulos (ej "GOVI_USDT") - mas confiable
# que partir el titulo en palabras, cuando aparece
_PAIR_RE = re.compile(r"\b([A-Z0-9]{2,15})_(USDT|USDC|USD)\b")


def _epoch_s_to_dt(s) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(s), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _extract_next_data(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except (json.JSONDecodeError, TypeError):
        return None


def _fetch_list_page(page: int) -> list[dict]:
    url = LIST_URL if page <= 1 else f"{LIST_URL}?page={page}"
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
    if resp.status_code != 200:
        log.warning(f"[gate] listado pagina {page} respondio {resp.status_code}")
        return []
    data = _extract_next_data(resp.text)
    if not data:
        log.warning(f"[gate] no se encontro __NEXT_DATA__ en la pagina {page}")
        return []
    try:
        return data["props"]["pageProps"]["listData"]["list"]
    except (KeyError, TypeError):
        log.warning(f"[gate] estructura de __NEXT_DATA__ distinta a la esperada en la pagina {page}")
        return []


def _fetch_article_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"[gate] articulo {url} respondio {resp.status_code}")
            return ""
        return html_to_text(resp.text)
    except requests.RequestException as e:
        log.warning(f"[gate] fallo trayendo articulo {url}: {e}")
        return ""


def fetch(max_pages: int = 5) -> list[Row]:
    items: list[dict] = []
    pages_fetched = 0
    for page in range(1, max_pages + 1):
        batch = _fetch_list_page(page)
        if not batch:
            break
        items.extend(batch)
        pages_fetched = page
        time.sleep(1)

    log.info(f"[gate] {len(items)} anuncios en {pages_fetched} pagina(s)")

    rows: list[Row] = []
    for item in items:
        title = (item.get("title") or "").strip()
        if not title or is_noise(title):
            continue
        rel_url = item.get("url") or ""
        if "/en-au/" in rel_url:
            continue  # variante regional, mismo contenido que el global
        url = rel_url if rel_url.startswith("http") else BASE + rel_url
        announced_at = _epoch_s_to_dt(item.get("release_timestamp"))

        body_text = _fetch_article_text(url) if url else ""

        # los pares BASE_USDT escritos en el cuerpo son mas confiables que partir el
        # titulo en palabras (titulos tipo "Gate to Delist 22 Coins Including XFI and
        # MAIGA" no listan los 22, solo 2 de ejemplo - el cuerpo si trae la lista completa)
        body_pairs = sorted(set(m.group(1) for m in _PAIR_RE.finditer(body_text))) if body_text else []

        delist_at = extract_delist_date_from_body(body_text, announced_at) if body_text else None
        if delist_at is None:
            delist_at = parse_delist_datetime(title)
        if delist_at is None and is_completion_notice(title):
            delist_at = announced_at  # ya paso, lo mejor que hay es la fecha del aviso

        market = detect_market(title)
        tickers = body_pairs if body_pairs else extract_tickers(title)
        if not tickers:
            log.warning(f"[gate] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title,
                announced_at=announced_at, delist_at=delist_at, market=market,
            ))
        time.sleep(0.4)

    log.info(f"[gate] {len(rows)} filas")
    return rows
