"""LBank: misma API de notice center que newlistings/lbank.py, pero la categoria de
deslistados confirmada por fuerza bruta en diagnostico real es CO00000057 (ninguna de las
ya conocidas - CO00000053 "madre", CO00000054 spot, CO00000055 futuros, CO00000056 copy
trading - trae avisos de deslistado). El/los tickers van en MAYUSCULA pegados a "Will
Delist" ("LBank Futures Will Delist AUDIO, BASECAT, BP and TMX Perpetual Contracts") o a
"Delisting of" ("Announcement on the Delisting of STAND Pre-Market Spot Trading and Asset
Buyback") - mismo truco de token 100% mayuscula que blofin.py/pionex.py para no tener que
separar "and"/"," a mano."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

import requests

from .common import (
    Row, DEFAULT_HEADERS, ExchangeBlocked, extract_delist_date_from_body,
    extract_tickers_from_body, detect_market, html_to_text, is_noise, parse_delist_datetime,
    classify_asset_class, fetch_known_delist_dates,
)

log = logging.getLogger("delistings.lbank")

EXCHANGE = "lbank"
LIST_URL = "https://www.lbank.com/lbk-api/huamao-media-center/notice/category/noticeList"
ARTICLE_URL_TMPL = "https://www.lbank.com/support/articles/{code}"
CATEGORY_CODE = "CO00000057"

_WILL_DELIST_TAIL_RE = re.compile(r"Will Delist\s+(.+)$", re.IGNORECASE)
_DELISTING_OF_TAIL_RE = re.compile(r"Delisting of\s+(?:the\s+)?(.+)$", re.IGNORECASE)
_CAPS_TOKEN_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,14})\b")
_QUOTE_SUFFIXES = ("USDT", "USDC", "USD")


def _strip_quote(tok: str) -> str:
    for q in _QUOTE_SUFFIXES:
        if tok.endswith(q) and len(tok) > len(q) + 1:
            return tok[: -len(q)]
    return tok


def _extract_tickers(title: str) -> list[str]:
    m = _WILL_DELIST_TAIL_RE.search(title) or _DELISTING_OF_TAIL_RE.search(title)
    tail = m.group(1) if m else title
    out = []
    for tok in _CAPS_TOKEN_RE.findall(tail):
        tok = _strip_quote(tok)
        if tok not in out:
            out.append(tok)
    return out


def _fetch_article_text(code) -> str:
    if not code:
        return ""
    try:
        resp = requests.get(ARTICLE_URL_TMPL.format(code=code), headers=DEFAULT_HEADERS, timeout=12)
        if resp.status_code != 200:
            return ""
        return html_to_text(resp.text)
    except requests.RequestException as e:
        log.warning(f"[lbank] fallo trayendo articulo {code}: {e}")
        return ""


def fetch(max_pages: int = 3) -> list[Row]:
    rows: list[Row] = []
    body_fetches_left = 15
    known_dates = fetch_known_delist_dates(EXCHANGE)
    for page in range(1, max_pages + 1):
        body = {"categoryCode": CATEGORY_CODE, "pageNo": page, "pageSize": 20}
        resp = requests.post(LIST_URL, json=body, headers=DEFAULT_HEADERS, timeout=30)
        if resp.status_code != 200:
            if page == 1:
                raise ExchangeBlocked(f"[lbank] {CATEGORY_CODE} pagina {page} respondio {resp.status_code}")
            break
        payload = resp.json()
        items = ((payload.get("data") or {}).get("resultList")) or []
        if not items:
            break

        for item in items:
            if item.get("langCode") and item["langCode"] != "en-US":
                continue
            title = (item.get("title") or "").strip()
            if not title or is_noise(title):
                continue
            code = item.get("code") or item.get("noticeId")
            url = ARTICLE_URL_TMPL.format(code=code) if code else ""
            source_url = url or f"lbank:{code}"
            try:
                announced_at = datetime.fromtimestamp(int(item.get("contentShowTime")) / 1000, tz=timezone.utc)
            except (TypeError, ValueError):
                announced_at = None

            tickers = _extract_tickers(title)

            delist_at = known_dates.get(source_url)
            fetched_body = False
            if source_url not in known_dates and body_fetches_left > 0 and (delist_at is None or not tickers):
                body_fetches_left -= 1
                fetched_body = True
                body_text = _fetch_article_text(code)
                if delist_at is None:
                    delist_at = extract_delist_date_from_body(body_text, announced_at) if body_text else None
                if not tickers and body_text:
                    tickers = extract_tickers_from_body(body_text)
            if delist_at is None:
                delist_at = parse_delist_datetime(title)

            if not tickers:
                log.warning(f"[lbank] no se pudieron sacar tickers de: {title!r} ({url})")
                continue

            market = detect_market(title)
            for base in tickers:
                rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=source_url, title=title, asset_class=classify_asset_class(title),
                    announced_at=announced_at, delist_at=delist_at, market=market,
                ))
            if fetched_body:
                time.sleep(0.3)

        if len(items) < 20:
            break
        time.sleep(0.5)

    log.info(f"[lbank] {len(rows)} filas")
    return rows
