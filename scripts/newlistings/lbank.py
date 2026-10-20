"""LBank: API propia (POST JSON), categorias confirmadas por separado para que el market
salga directo sin adivinar: CO00000054 "Spot Listings", CO00000055 "Futures Listings".
NO usar CO00000053 (la madre, mezcla todo) ni CO00000056 (Copy Trading, es ruido)."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

import requests

from .common import Row, DEFAULT_HEADERS, classify_asset_class_or_ticker, is_noise, split_run

log = logging.getLogger("newlistings.lbank")

EXCHANGE = "lbank"
LIST_URL = "https://www.lbank.com/lbk-api/huamao-media-center/notice/category/noticeList"
ARTICLE_URL_TMPL = "https://www.lbank.com/support/articles/{code}"

CATEGORIES = [
    ("CO00000054", "spot"),
    ("CO00000055", "futures"),
]

_PAREN_TICKER_RE = re.compile(r"\b([A-Za-z0-9]{1,15})\s*\(")
_COMMA_LIST_RE = re.compile(
    r"Listing of\s+([A-Z0-9]+(?:USDT)?(?:\s*,\s*[A-Z0-9]+(?:USDT)?)*)\s+"
    r"(?:24H\s+)?(?:Stock Futures|Energy Index Futures|Index Futures)",
    re.IGNORECASE,
)


def _strip_quote(tok: str) -> str:
    tok = tok.upper()
    for q in ("USDT", "USDC", "USD"):
        if tok.endswith(q) and len(tok) > len(q) + 1:
            return tok[: -len(q)]
    return tok


def _extract_tickers(title: str) -> list[str]:
    m = _COMMA_LIST_RE.search(title)
    if m:
        return split_run(m.group(1))
    m = _PAREN_TICKER_RE.search(title)
    if m:
        return [m.group(1).upper()]
    return []


def fetch(max_pages: int = 3) -> list[Row]:
    rows: list[Row] = []
    seen: set[tuple] = set()  # (exchange, pair_base, market) - dedup "Soon"/definitivo

    for category_code, market in CATEGORIES:
        for page in range(1, max_pages + 1):
            body = {"categoryCode": category_code, "pageNo": page, "pageSize": 20}
            resp = requests.post(LIST_URL, json=body, headers=DEFAULT_HEADERS, timeout=30)
            if resp.status_code != 200:
                log.warning(f"[lbank] {category_code} pagina {page} respondio {resp.status_code}: {resp.text[:300]}")
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
                try:
                    announced_at = datetime.fromtimestamp(int(item.get("contentShowTime")) / 1000, tz=timezone.utc)
                except (TypeError, ValueError):
                    announced_at = None

                tickers = _extract_tickers(title)
                if not tickers:
                    log.warning(f"[lbank] no se pudieron sacar tickers de: {title!r} ({url})")
                    continue

                for base in tickers:
                    base = _strip_quote(base)
                    dedup_key = (EXCHANGE, base, market)
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    asset_class = classify_asset_class_or_ticker(title, base)
                    rows.append(Row(
                        exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                        source_url=url or f"lbank:{code}", title=title, asset_class=asset_class,
                        announced_at=announced_at, market=market,
                    ))

            if len(items) < 20:
                break
            time.sleep(0.5)

    log.info(f"[lbank] {len(rows)} filas")
    return rows
