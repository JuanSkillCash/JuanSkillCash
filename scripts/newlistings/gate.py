"""Gate: mismo patron __NEXT_DATA__ que delistings/gate.py, pero la pagina madre
"newlisted" mezcla categorias (spot, futuros, eventos, ETF) - se filtra por cate_id a solo
las dos categorias confirmadas: 38 "New Spot Listings" y 37 "New Futures Listings".
El campo 'tags' trae los tickers YA separados por coma - no hace falta parsear el titulo
(que ademas viene truncado con "..." por el propio servidor)."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

from .common import Row, ExchangeBlocked, classify_asset_class_or_ticker, fetch_html_with_fallback, is_noise

log = logging.getLogger("newlistings.gate")

EXCHANGE = "gate"
LIST_URL_TMPL = "https://www.gate.com/announcements/newlisted?page={page}"

_SPOT_CATE_ID = 38
_FUTURES_CATE_ID = 37
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S,
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.IGNORECASE)


def _fetch_page(page: int) -> list[dict]:
    url = LIST_URL_TMPL.format(page=page)
    html, method = fetch_html_with_fallback(
        url, validate=lambda h: "__NEXT_DATA__" in h, wait_selector="script#__NEXT_DATA__",
        timeout=45,
    )
    log.info(f"[gate] pagina {page} - metodo usado: {method}")
    m = _NEXT_DATA_RE.search(html)
    if not m:
        # bloqueo de Akamai (reputacion de IP del runner, no un cambio del sitio - desde una
        # IP residencial real www.gate.com responde 200 normal) - distinguirlo del caso
        # generico da un mensaje mas util en el panel que un "no se encontro __NEXT_DATA__"
        if "access denied" in html.lower() or "edgesuite.net" in html.lower():
            ref_match = re.search(r"Reference #([\w.]+)", html)
            detail = "[gate] bloqueado por Akamai (403 Access Denied, IP del runner)"
            if ref_match:
                detail += f" - Reference #{ref_match.group(1)}"
            raise ExchangeBlocked(detail)
        # titulo+largo quedan en el detalle de ExchangeBlocked para no tener que adivinar en
        # la proxima corrida si fue un challenge, un "Access Denied" de WAF, u otra cosa.
        title_m = _TITLE_RE.search(html)
        title = title_m.group(1).strip() if title_m else "(sin <title>)"
        raise ExchangeBlocked(
            f"[gate] no se encontro __NEXT_DATA__ en pagina {page} "
            f"(titulo={title!r}, largo html={len(html)})"
        )
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        raise ExchangeBlocked(f"[gate] __NEXT_DATA__ invalido en pagina {page}")
    list_data = (((data.get("props") or {}).get("pageProps") or {}).get("listData") or {})
    return list_data.get("list") or []


def fetch(max_pages: int = 5) -> list[Row]:
    rows: list[Row] = []
    for page in range(1, max_pages + 1):
        try:
            items = _fetch_page(page)
        except ExchangeBlocked:
            if page == 1:
                raise
            break  # ya hay filas de paginas anteriores, no es un bloqueo total de la corrida
        if not items:
            break

        for item in items:
            cate_id = item.get("cate_id")
            if cate_id not in (_SPOT_CATE_ID, _FUTURES_CATE_ID):
                continue
            title = (item.get("title") or item.get("brief") or "").strip()
            if not title or is_noise(title):
                continue
            tags = item.get("tags") or ""
            tickers = [t.strip().upper() for t in tags.split(",") if t.strip()]
            if not tickers:
                log.warning(f"[gate] sin tags/tickers en: {title!r}")
                continue

            url = "https://www.gate.com" + item.get("url", "") if item.get("url", "").startswith("/") else item.get("url", "")
            try:
                announced_at = datetime.fromtimestamp(int(item.get("release_timestamp")), tz=timezone.utc)
            except (TypeError, ValueError):
                announced_at = None
            market = "futures" if cate_id == _FUTURES_CATE_ID else "spot"

            for base in tickers:
                asset_class = classify_asset_class_or_ticker(title, base)
                rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=url or f"gate:{item.get('id')}", title=title, asset_class=asset_class,
                    announced_at=announced_at, market=market,
                ))

        if len(items) < 15:
            break
        time.sleep(1)

    log.info(f"[gate] {len(rows)} filas")
    return rows
