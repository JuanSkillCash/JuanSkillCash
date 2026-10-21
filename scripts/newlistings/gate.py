"""Gate: www.gate.com esta bloqueado por Akamai (403 "Access Denied") desde la IP
compartida de los runners de GitHub Actions - confirmado por investigacion externa que es
reputacion de IP, no un cambio del sitio. Fuente primaria ahora: el WebSocket OFICIAL de
anuncios (wss://api.gateio.ws/ws/v4/ann, canal "announcement.summary_listing"), API de
trading con infraestructura separada de la del sitio web - SI alcanzable desde el runner
(confirmado con un diagnostico real). El scraper viejo por __NEXT_DATA__/Playwright-fallback
contra www.gate.com queda como respaldo si el WebSocket alguna vez deja de funcionar."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

from .common import Row, ExchangeBlocked, classify_asset_class_or_ticker, fetch_html_with_fallback, fetch_gate_ws_items, html_to_text, is_noise, detect_market

log = logging.getLogger("newlistings.gate")

EXCHANGE = "gate"
LIST_URL_TMPL = "https://www.gate.com/announcements/newlisted?page={page}"
WS_CHANNEL = "announcement.summary_listing"

_SPOT_CATE_ID = 38
_FUTURES_CATE_ID = 37
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S,
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.IGNORECASE)

_PAIR_RE = re.compile(r"\b([A-Z0-9]{2,15})_(USDT|USDC|USD)\b")
_TOKEN_SYMBOL_RE = re.compile(r"token\s*symbol[：:]\s*([A-Z0-9]{1,15})", re.IGNORECASE)
_CAPS_TOKEN_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,14})\b")
_WS_STOPWORDS = {"UTC", "USDT", "USDC", "USD", "GATE", "VIP", "API", "KYC", "AML", "NFT", "P2P", "FAQ", "ID", "IP"}


def _extract_tickers_ws(title: str, brief_text: str) -> list[str]:
    m = _TOKEN_SYMBOL_RE.search(brief_text) or _TOKEN_SYMBOL_RE.search(title)
    if m:
        return [m.group(1).upper()]
    pairs = sorted(set(m.group(1) for m in _PAIR_RE.finditer(brief_text)))
    if pairs:
        return pairs
    return [t for t in _CAPS_TOKEN_RE.findall(title) if t not in _WS_STOPWORDS]


def _fetch_via_websocket() -> list[Row]:
    items = fetch_gate_ws_items(WS_CHANNEL)
    if not items:
        raise ExchangeBlocked("[gate-ws] no llego ningun mensaje en la ventana de escucha")

    rows: list[Row] = []
    seen_urls = set()
    for item in items:
        title = (item.get("title") or "").strip()
        url = item.get("origin_url") or ""
        if not title or not url or url in seen_urls or is_noise(title):
            continue
        seen_urls.add(url)

        brief_text = html_to_text(item.get("brief") or "")
        try:
            announced_at = datetime.fromtimestamp(int(item.get("published_at")), tz=timezone.utc)
        except (TypeError, ValueError):
            announced_at = None

        tickers = _extract_tickers_ws(title, brief_text)
        if not tickers:
            log.warning(f"[gate-ws] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        market = detect_market(title)
        for base in tickers:
            asset_class = classify_asset_class_or_ticker(title, base)
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title, asset_class=asset_class,
                announced_at=announced_at, market=market,
            ))

    log.info(f"[gate-ws] {len(rows)} filas (de {len(items)} avisos)")
    return rows


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


def _fetch_via_scrape(max_pages: int = 5) -> list[Row]:
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


def fetch(max_pages: int = 5) -> list[Row]:
    try:
        return _fetch_via_websocket()
    except ExchangeBlocked as e:
        log.warning(f"[gate] WebSocket fallo ({e}), cae al scraper viejo por __NEXT_DATA__")
        return _fetch_via_scrape(max_pages)
