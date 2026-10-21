"""CoinW: no tiene una pagina de "solo deslistados" como latest-listings (confirmado en
diagnostico: la raiz de announcement-center no trae ningun link de deslistado) - los avisos
de deslistado viven mezclados con todo lo demas (mantenimiento, ajustes de precision,
politicas) en /help-center/announcement-center/more, paginada via ?page=N, con la fecha
codificada en la URL de cada aviso igual que en newlistings/coinw.py. El titulo trae el/los
tickers en MAYUSCULA justo despues de "Delisting of" ("Delisting of QNT, PANW, ... USDT-M
Perpetual Futures", "Announcement on the Delisting of the ULTIMA Trading Pair") - los avisos
vagos sin ticker especifico ("Announcement on the Delisting of Certain Trading Pairs") no
tienen ningun token en mayuscula ahi, asi que se descartan solos sin necesitar una lista de
palabras prohibidas."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

from bs4 import BeautifulSoup

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
from newlistings.common import DEFAULT_HEADERS, fetch_html_with_fallback  # noqa: E402

from .common import (
    Row, ExchangeBlocked, extract_delist_date_from_body, detect_market, html_to_text,
    is_noise, parse_delist_datetime, classify_asset_class,
)

log = logging.getLogger("delistings.coinw")

EXCHANGE = "coinw"
LIST_URL = "https://www.coinw.com/help-center/announcement-center/more"

_HREF_DATE_RE = re.compile(r"/more/(\d{4})-(\d{2})-(\d{2})/")
_DELISTING_OF_TAIL_RE = re.compile(r"Delisting of\s+(?:the\s+)?(.+?)(?:\s+USDT-M Perpetual Futures\b|\s+Trading Pairs?\b|$)", re.IGNORECASE)
_CAPS_TOKEN_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,14})\b")

MAX_BODY_FETCHES = 15


def _extract_tickers(title: str) -> list[str]:
    m = _DELISTING_OF_TAIL_RE.search(title)
    if not m:
        return []
    tail = m.group(1)
    out = []
    for tok in _CAPS_TOKEN_RE.findall(tail):
        if tok not in out:
            out.append(tok)
    return out


def _fetch_article_text(url: str) -> str:
    try:
        html, _ = fetch_html_with_fallback(url, timeout=12)
        return html_to_text(html)
    except Exception as e:
        log.warning(f"[coinw] fallo trayendo articulo {url}: {e}")
        return ""


def fetch(max_pages: int = 3) -> list[Row]:
    rows: list[Row] = []
    body_fetches_left = MAX_BODY_FETCHES
    for page in range(1, max_pages + 1):
        url = LIST_URL if page == 1 else f"{LIST_URL}?page={page}"
        try:
            html, method = fetch_html_with_fallback(url, validate=lambda h: "announcement-center" in h)
        except Exception as e:
            if page == 1:
                raise ExchangeBlocked(f"[coinw] {url} no cargo: {e}")
            break
        log.info(f"[coinw] pagina {page} - metodo usado: {method}")

        soup = BeautifulSoup(html, "html.parser")
        links = [a for a in soup.select('a[href*="/announcement-center/more/"]') if a.get("href", "").count("/") > 4]
        if not links:
            if page == 1:
                raise ExchangeBlocked("[coinw] no se encontro ningun link de aviso en /more")
            break

        for a in links:
            href = a.get("href", "")
            spans = a.find_all("span")
            title = spans[0].get_text(strip=True) if spans else a.get_text(strip=True)
            if not title or is_noise(title):
                continue

            tickers = _extract_tickers(title)
            if not tickers:
                continue  # mezcla mantenimiento/politicas/avisos vagos - no es ruido real, simplemente no es un deslistado reconocible

            url_full = href if href.startswith("http") else "https://www.coinw.com" + href

            announced_at = None
            dm = _HREF_DATE_RE.search(href)
            if dm:
                y, mo, d = (int(x) for x in dm.groups())
                announced_at = datetime(y, mo, d, tzinfo=timezone.utc)

            delist_at = None
            if body_fetches_left > 0:
                body_fetches_left -= 1
                body_text = _fetch_article_text(url_full)
                delist_at = extract_delist_date_from_body(body_text, announced_at) if body_text else None
            if delist_at is None:
                delist_at = parse_delist_datetime(title)

            market = detect_market(title)
            for base in tickers:
                rows.append(Row(
                    exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                    source_url=url_full, title=title, asset_class=classify_asset_class(title),
                    announced_at=announced_at, delist_at=delist_at, market=market,
                ))
            time.sleep(0.3)

        time.sleep(0.5)

    log.info(f"[coinw] {len(rows)} filas")
    return rows
