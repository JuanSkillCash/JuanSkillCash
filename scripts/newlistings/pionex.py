"""Pionex: centro de ayuda Intercom (NO Zendesk), coleccion "New listings" (id 19449941).
La pagina de la coleccion lista TODOS los articulos en una sola pagina HTML, mas nuevos
primero (segun la investigacion), pero sin fecha visible en el listado - la fecha solo
esta dentro del cuerpo de cada articulo, y abrir los ~400 articulos uno por uno en cada
corrida horaria seria carisimo. Por diseno, announced_at queda en None aca (el frontend ya
sabe mostrar "Disponible" en vez de una fecha relativa cuando no hay announced_at)."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .common import Row, STOCK_TICKERS, classify_asset_class_or_ticker, fetch_html_with_fallback, is_noise

log = logging.getLogger("newlistings.pionex")

EXCHANGE = "pionex"
LIST_URL = "https://intercom.help/pionex/en/collections/19449941-new-listings"
_ARTICLE_HREF_SEL = 'a[href*="/en/articles/"]'

# Los avisos de deslistado (y algun producto no relacionado) se cuelan en la misma
# coleccion de Intercom de "New listings" - esto es propio de como Pionex organiza su
# centro de ayuda, no vale compartirlo con otros exchanges.
_PIONEX_NOISE_RE = re.compile(
    r"Will Delist|Notice of Removal of (?:Spot )?Trading Pairs|Dual Investment Upgrade",
    re.IGNORECASE,
)

# "MEME Guru New Coin Listing: ANI" (un ticker) o "...: 修仙、MEMERUSH and PUP" / "...:
# 币安人生, PALU, and GIGGLE" (lista mixta china/ascii, separador a veces es "、" no coma) -
# se captura toda la cola y se tokeniza igual que un "Has Listed", los tokens en chino se
# descartan solos mas abajo (no pasan el filtro ascii final).
_MEME_GURU_RE = re.compile(r"MEME Guru New Coin Listing:\s*(.+)$", re.IGNORECASE)
# "Pionex has/had Launched [the] ..." cubre cuatro formas vistas en produccion:
#   singular sufijo:  "...the ERAUSDT Margined Perpetual Futures"
#   plural con ':':    "...the Margined Perpetual Futures: ERAUSDT 1-25x Leverage, DNAUSDT ..."
#   prefijo USDT:      "...the USDTPEPE 1-50x Leverage Margined Perpetual Futures"
#   sin "the":         "Has Launched KITEUSDT, PIGGYUSDT, ATUSDT, OLUSDT Perpetual Futures"
# en los cuatro casos alcanza con aislar el tramo entre "Launched" y el final/":" y
# tokenizar por comas - _strip_quote_any() se encarga de pelar el USDT este antes o despues.
_LAUNCHED_TAIL_RE = re.compile(r"(?:has|had)\s+Launched\s+(?:the\s+)?(.+)$", re.IGNORECASE)
_TRAILING_FUTURES_RE = re.compile(r"\s*Margined Perpetual Futures\b.*$", re.IGNORECASE)
_PAREN_TICKER_RE = re.compile(r"\b([A-Za-z0-9一-鿿]{1,15})\s*\(")
_HAS_LISTED_RE = re.compile(r"(?:[Hh]as|had)\s+[Ll]isted\s+(.+)$")

_QUOTE_PREFIX_RE = re.compile(r"^(USDT|USDC|USD)([A-Z0-9]{2,15})$")
_QUOTE_SUFFIXES = ("USDT", "USDC", "USD", "BNB", "BTC")


def _strip_quote_any(tok: str) -> str:
    tok = tok.upper()
    m = _QUOTE_PREFIX_RE.match(tok)
    if m:
        return m.group(2)
    for q in _QUOTE_SUFFIXES:
        if tok.endswith(q) and len(tok) > len(q) + 1:
            return tok[: -len(q)]
    return tok


def _first_token(segment: str) -> str | None:
    m = re.match(r"\s*([A-Za-z0-9一-鿿]{1,15})", segment)
    return m.group(1) if m else None


def _split_ticker_run(segment: str) -> list[str]:
    """Separa listas tipo "A, B and C" / "A, B, and C" / "A、B and C" (el separador chino
    "、" aparece en algunos titulos de MEME Guru) tolerando basura al final de cada parte
    (leverage, "Tokenized Stocks", "RWA", etc.) - solo se queda con el primer token
    alfanumerico de cada tramo."""
    parts = re.split(r",|，|、|\band\b", segment, flags=re.IGNORECASE)
    out = []
    for p in parts:
        tok = _first_token(p)
        if not tok:
            continue
        tok = _strip_quote_any(tok)
        if tok and tok not in out:
            out.append(tok)
    return out


def _launched_tickers(title: str) -> list[str]:
    m = _LAUNCHED_TAIL_RE.search(title)
    if not m:
        return []
    tail = m.group(1)
    if ":" in tail:
        tail = tail.split(":", 1)[1]
    else:
        tail = _TRAILING_FUTURES_RE.sub("", tail)
    return _split_ticker_run(tail)


def _extract_tickers(title: str) -> list[str]:
    m = _MEME_GURU_RE.search(title)
    if m:
        tickers = _split_ticker_run(m.group(1))
        if tickers:
            return tickers

    tickers = _launched_tickers(title)
    if tickers:
        return tickers

    parens = [m.group(1).upper() for m in _PAREN_TICKER_RE.finditer(title)]
    if parens:
        return parens

    m = _HAS_LISTED_RE.search(title)
    if m:
        return _split_ticker_run(m.group(1))

    return []


def fetch(max_pages: int = 1) -> list[Row]:
    html, method = fetch_html_with_fallback(LIST_URL, validate=lambda h: '/en/articles/' in h, wait_selector=_ARTICLE_HREF_SEL)
    log.info(f"[pionex] metodo usado: {method}")

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select(_ARTICLE_HREF_SEL)
    if not links:
        log.warning("[pionex] no se encontro ningun link de articulo")
        return []

    rows: list[Row] = []
    seen_urls = set()
    for a in links:
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not href or not title or is_noise(title) or _PIONEX_NOISE_RE.search(title):
            continue
        url = href if href.startswith("http") else "https://intercom.help" + href
        if url in seen_urls:
            continue
        seen_urls.add(url)

        tickers = _extract_tickers(title)
        if not tickers:
            log.warning(f"[pionex] no se pudieron sacar tickers de: {title!r} ({url})")
            continue

        market = "futures" if re.search(r"perpetual (futures|contract)", title, re.IGNORECASE) else "spot"
        for base in tickers:
            if not re.fullmatch(r"[A-Za-z0-9]{1,15}", base):
                continue  # descarta tickers con caracteres no latinos (chino, etc.) - no graficables
            asset_class = classify_asset_class_or_ticker(title, base)
            if asset_class == "crypto" and base.endswith("X") and len(base) > 2 and base[:-1] in STOCK_TICKERS:
                # convencion propia de Pionex: sufijo "X" = xStock tokenizado (CRMX, MSTUX, UMCX...)
                asset_class = "stock"
            rows.append(Row(
                exchange=EXCHANGE, symbol=f"{base}USDT", pair_base=base,
                source_url=url, title=title, asset_class=asset_class,
                announced_at=None, market=market,
            ))

    log.info(f"[pionex] {len(rows)} filas")
    return rows
