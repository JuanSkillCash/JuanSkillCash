"""Pionex: los avisos de deslistado viven en la MISMA coleccion de Intercom de "nuevos
listados" que ya usa newlistings/pionex.py (confirmado por diagnostico real: 10 titulos
"Will Delist"/"Notice of Removal..." en una sola pagina de 428 links) - ese scraper los
descarta a proposito via _PIONEX_NOISE_RE porque ahi son ruido; aca son exactamente lo que
se busca. Los tickers reales siempre van en MAYUSCULA en el titulo ("Will Delist PRQ",
"Will Delist BADGERUSDT 1-25x Leverage") - las palabras descriptivas (Leverage, Coins,
Spot, Some, Tokens) van en minuscula/capitalizada, asi que un token 100% mayuscula es un
filtro confiable sin tener que separar por comas/"and" a mano. Algunos titulos son avisos
genericos sin ticker especifico ("Will Delist Spot Coins & MEME Guru Coins", "Notice of
Removal of Spot Trading Pairs") - esos se descartan explicitamente, no se inventa un
ticker de una palabra suelta que matchee por casualidad."""

from __future__ import annotations

import logging
import re
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
from newlistings.common import fetch_html_with_fallback  # noqa: E402

from bs4 import BeautifulSoup

from .common import (
    Row, ExchangeBlocked, extract_delist_date_from_body, extract_tickers_from_body,
    detect_market, is_noise, classify_asset_class, parse_delist_datetime,
    fetch_known_delist_dates,
)

log = logging.getLogger("delistings.pionex")

EXCHANGE = "pionex"
LIST_URL = "https://intercom.help/pionex/en/collections/19449941-new-listings"
_ARTICLE_HREF_SEL = 'a[href*="/en/articles/"]'

_DELIST_TITLE_RE = re.compile(r"Will Delist|Notice of Removal of (?:Spot )?Trading Pairs", re.IGNORECASE)
_VAGUE_BATCH_RE = re.compile(r"Spot Coins|MEME Guru Coins|Leveraged Tokens", re.IGNORECASE)
_WILL_DELIST_TAIL_RE = re.compile(r"Will Delist\s+(.+)$", re.IGNORECASE)
_CAPS_TOKEN_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,14})\b")
_QUOTE_SUFFIXES = ("USDT", "USDC", "USD")


def _strip_quote(tok: str) -> str:
    for q in _QUOTE_SUFFIXES:
        if tok.endswith(q) and len(tok) > len(q) + 1:
            return tok[: -len(q)]
    return tok


def _extract_tickers(title: str) -> list[str]:
    if _VAGUE_BATCH_RE.search(title):
        return []
    m = _WILL_DELIST_TAIL_RE.search(title)
    tail = m.group(1) if m else title
    out = []
    for tok in _CAPS_TOKEN_RE.findall(tail):
        tok = _strip_quote(tok)
        if tok not in out:
            out.append(tok)
    return out


def fetch(max_pages: int = 1) -> list[Row]:
    try:
        html, method = fetch_html_with_fallback(LIST_URL, validate=lambda h: '/en/articles/' in h, wait_selector=_ARTICLE_HREF_SEL)
    except Exception as e:
        raise ExchangeBlocked(f"[pionex] no se pudo cargar la coleccion de avisos: {e}")
    log.info(f"[pionex] metodo usado: {method}")

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select(_ARTICLE_HREF_SEL)
    if not links:
        raise ExchangeBlocked("[pionex] no se encontro ningun link de articulo")

    rows: list[Row] = []
    seen_urls = set()
    body_fetches_left = 15
    known_dates = fetch_known_delist_dates(EXCHANGE)
    for a in links:
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not href or not title or is_noise(title) or not _DELIST_TITLE_RE.search(title):
            continue
        url = href if href.startswith("http") else "https://intercom.help" + href
        if url in seen_urls:
            continue
        seen_urls.add(url)

        tickers = _extract_tickers(title)

        delist_at = known_dates.get(url)
        fetched_body = False
        if url not in known_dates and body_fetches_left > 0 and (delist_at is None or not tickers):
            body_fetches_left -= 1
            fetched_body = True
            art_text = None
            try:
                art_html, _ = fetch_html_with_fallback(url, timeout=12)
                art_text = BeautifulSoup(art_html, "html.parser").get_text(separator="\n")
            except Exception as e:
                log.warning(f"[pionex] no se pudo leer el articulo {url}: {e}")
            if delist_at is None and art_text:
                delist_at = extract_delist_date_from_body(art_text)
            if not tickers and art_text:
                tickers = extract_tickers_from_body(art_text)
        if delist_at is None:
            delist_at = parse_delist_datetime(title)

        if not tickers:
            log.warning(f"[pionex] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        market = detect_market(title)
        for base in tickers:
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title, asset_class=classify_asset_class(title),
                announced_at=None, delist_at=delist_at, market=market,
            ))
        if fetched_body:
            time.sleep(0.3)

    log.info(f"[pionex] {len(rows)} filas")
    return rows
