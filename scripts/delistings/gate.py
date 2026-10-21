"""Gate (gate.com, antes gate.io): pagina Next.js, los datos vienen embebidos en
<script id="__NEXT_DATA__"> dentro del HTML - no hay API JSON aparte. El sitio esta detras
de un challenge JS real de Cloudflare (confirmado: un simple requests.get con headers de
navegador da 403 desde la primera peticion) - igual que Farside en
update_etf_cost_basis_daily.py, hace falta un navegador de verdad (Playwright) para que el
challenge se resuelva solo."""

from __future__ import annotations

import json
import logging
import re
import time

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .common import (
    Row, DEFAULT_HEADERS, ExchangeBlocked, extract_delist_date_from_body, extract_tickers,
    detect_market, is_noise, is_completion_notice, html_to_text, parse_delist_datetime,
    classify_asset_class,
)
from datetime import datetime, timezone

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


def _goto_html(page, url: str) -> str:
    page.goto(url, wait_until="networkidle", timeout=45000)
    return page.content()


def fetch(max_pages: int = 2) -> list[Row]:
    # 2 paginas por defecto (no 5 como los demas): cada item necesita su propia pagina de
    # Playwright para el detalle (Cloudflare obliga a navegador real, no un simple GET), asi
    # que mas paginas = mucho mas tiempo de corrida por poca ganancia (lo reciente es lo que
    # importa para este indicador, no un backfill historico completo).
    items: list[dict] = []
    article_bodies: dict[str, str] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"])

        pages_fetched = 0
        for p in range(1, max_pages + 1):
            url = LIST_URL if p <= 1 else f"{LIST_URL}?page={p}"
            try:
                html = _goto_html(page, url)
            except Exception as e:
                if p == 1:
                    browser.close()
                    raise ExchangeBlocked(f"[gate] listado pagina {p} fallo: {e}")
                log.warning(f"[gate] listado pagina {p} fallo: {e}")
                break
            data = _extract_next_data(html)
            if not data:
                title_dbg = page.title()
                html_snippet = html[:300]
                ids = re.findall(r'<script[^>]*\bid="([^"]+)"', html)
                if p == 1:
                    browser.close()
                    raise ExchangeBlocked(
                        f"[gate] no se encontro __NEXT_DATA__ en la pagina {p} "
                        f"(titulo={title_dbg!r}, ids de script={ids}, html={html_snippet!r})"
                    )
                log.warning(f"[gate] no se encontro __NEXT_DATA__ en la pagina {p} (titulo={title_dbg!r})")
                break
            try:
                batch = data["props"]["pageProps"]["listData"]["list"]
            except (KeyError, TypeError):
                if p == 1:
                    browser.close()
                    raise ExchangeBlocked(f"[gate] estructura de __NEXT_DATA__ distinta a la esperada en la pagina {p}")
                log.warning(f"[gate] estructura de __NEXT_DATA__ distinta a la esperada en la pagina {p}")
                break
            if not batch:
                break
            items.extend(batch)
            pages_fetched = p

        log.info(f"[gate] {len(items)} anuncios en {pages_fetched} pagina(s)")

        for item in items:
            rel_url = item.get("url") or ""
            if not rel_url or "/en-au/" in rel_url:
                continue
            url = rel_url if rel_url.startswith("http") else BASE + rel_url
            try:
                article_bodies[url] = html_to_text(_goto_html(page, url))
            except Exception as e:
                log.warning(f"[gate] articulo {url} fallo: {e}")
                article_bodies[url] = ""
            time.sleep(0.3)

        browser.close()

    rows: list[Row] = []
    for item in items:
        title = (item.get("title") or "").strip()
        if not title or is_noise(title):
            continue
        rel_url = item.get("url") or ""
        if "/en-au/" in rel_url:
            continue
        url = rel_url if rel_url.startswith("http") else BASE + rel_url
        announced_at = _epoch_s_to_dt(item.get("release_timestamp"))
        body_text = article_bodies.get(url, "")

        body_pairs = sorted(set(m.group(1) for m in _PAIR_RE.finditer(body_text))) if body_text else []

        delist_at = extract_delist_date_from_body(body_text, announced_at) if body_text else None
        if delist_at is None:
            delist_at = parse_delist_datetime(title)
        if delist_at is None and is_completion_notice(title):
            delist_at = announced_at

        market = detect_market(title)
        tickers = body_pairs if body_pairs else extract_tickers(title)
        if not tickers:
            log.warning(f"[gate] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title, asset_class=classify_asset_class(title),
                announced_at=announced_at, delist_at=delist_at, market=market,
            ))

    log.info(f"[gate] {len(rows)} filas")
    return rows
