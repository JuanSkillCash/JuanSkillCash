"""
Utilidades compartidas por los scrapers de "Radar de Nuevos Listados" (scripts/newlistings/,
un modulo por exchange). Hermano de scripts/delistings/ - mismo exchange, misma fuente
(centro de soporte/API publica), pero categoria "nuevos listados" en vez de "deslistados".

A diferencia de los deslistados (una sola frase "Delist X" en casi todos los exchanges), el
anuncio de un nuevo listado tiene una redaccion muy distinta por exchange ("X (TICKER) Coin
Gets Listed", "will launch X/USD", "to list X (Name)", "Will Add X bStocks..."), asi que cada
exchange trae su propio extractor de tickers en su modulo (igual que ya hacia kraken.py en
delistings/ para su caso particular) - aca solo vive lo genuinamente compartido: el dataclass
de fila, el upsert a Supabase, el helper de parentesis, y la clasificacion de asset_class.

Variables de entorno requeridas (las lee update_new_listings.py, no este archivo):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

from __future__ import annotations

import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # repo scripts/ en sys.path
from delistings.common import (  # noqa: E402
    DEFAULT_HEADERS, html_to_text, parse_delist_datetime, classify_asset_class,
)

log = logging.getLogger("newlistings")

TABLE = "exchange_new_listings"

_STOCK_TICKERS_PATH = os.path.join(os.path.dirname(__file__), "stock_tickers.txt")


def _load_stock_tickers() -> set[str]:
    try:
        with open(_STOCK_TICKERS_PATH, encoding="utf-8") as f:
            return {
                line.strip().upper() for line in f
                if line.strip() and not line.strip().startswith("#")
            }
    except FileNotFoundError:
        return set()


STOCK_TICKERS = _load_stock_tickers()


def fetch_html_with_fallback(url: str, validate=None, wait_selector: str | None = None, timeout: int = 30) -> tuple[str, str]:
    """`requests` primero (rapido, sin dependencias pesadas); si responde con algo que huele
    a bloqueo de bot (403/429/503/521, challenge de Cloudflare) o `validate(html)` dice que
    el contenido no sirve (ej. no trae ningun link de articulo), cae a Playwright (navegador
    real, mas lento pero pasa casi cualquier antibot basado en TLS fingerprint). Devuelve
    (html, metodo) para poder loguear cual funciono en cada corrida - importante porque la
    investigacion que encontro estas fuentes la hizo desde un navegador real, no desde
    `requests`, asi que no hay garantia de que esta ultima pase el antibot en la IP del
    runner de GitHub Actions."""
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        looks_blocked = (
            resp.status_code in (403, 429, 503, 521)
            or "checking your browser" in resp.text.lower()
            or "cf-browser-verification" in resp.text.lower()
        )
        if not looks_blocked and resp.status_code == 200 and (validate is None or validate(resp.text)):
            return resp.text, "requests"
    except requests.RequestException:
        pass

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"])
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            if wait_selector:
                try:
                    # state="attached" alcanza con que exista en el DOM - no todas las
                    # paginas lo hacen visible (ej. un <script id="__NEXT_DATA__">).
                    page.wait_for_selector(wait_selector, timeout=timeout * 1000, state="attached")
                except Exception:
                    pass  # mejor usar lo que haya cargado que tirar toda la corrida
            else:
                try:
                    # espera a que la pagina termine de hidratar/pedir sus XHR - mas
                    # confiable que un sleep fijo para contenido armado client-side.
                    page.wait_for_load_state("networkidle", timeout=timeout * 1000)
                except Exception:
                    page.wait_for_timeout(3000)
            html_out = page.content()
        finally:
            browser.close()
    return html_out, "playwright"


def classify_asset_class_or_ticker(title: str, ticker: str) -> str:
    """Como classify_asset_class, pero con un fallback: si el titulo no trae ningun
    marcador explicito (ni "stock"/"index"/"commodity"/etc.), revisa si el ticker esta en
    stock_tickers.txt (mantenido a mano) antes de resignarse a 'crypto'. Util para
    exchanges donde el aviso de acciones se ve identico al de cripto (Blofin, Bitunix
    futuros, CoinW futuros)."""
    result = classify_asset_class(title)
    if result != "crypto":
        return result
    if (ticker or "").upper() in STOCK_TICKERS:
        return "stock"
    return "crypto"


@dataclass
class Row:
    exchange: str
    symbol: str                      # ej "AXISUSDT"
    pair_base: str                   # ej "AXIS"
    source_url: str
    title: str
    asset_class: str = "crypto"      # 'crypto' | 'stock' | 'index' | 'commodity'
    announced_at: Optional[datetime] = None
    listed_at: Optional[datetime] = None   # fecha/hora en que empieza a operar, si el aviso la trae
    market: Optional[str] = None     # 'spot' | 'futures' | None

    def status(self, now: Optional[datetime] = None) -> str:
        now = now or datetime.now(timezone.utc)
        if self.listed_at and self.listed_at > now:
            return "upcoming"
        return "live"

    def to_api_dict(self) -> dict:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "pair_base": self.pair_base,
            "market": self.market,
            "asset_class": self.asset_class,
            "announced_at": self.announced_at.isoformat() if self.announced_at else None,
            "listed_at": self.listed_at.isoformat() if self.listed_at else None,
            "title": self.title,
            "source_url": self.source_url,
            "status": self.status(),
        }


# classify_asset_class vive ahora en delistings/common.py (compartida por los dos radares,
# importada arriba) - aca solo queda lo que es genuinamente propio de "nuevos listados".

# ---------------------------------------------------------------------------------------
# Tickers entre parentesis: "Axis Robotics (AXIS)" / "Metaplex (MPLX)" - el nombre largo no
# es el ticker, el que va entre parentesis si (regla ya usada en delistings/common.py).
# ---------------------------------------------------------------------------------------

_PAREN_TICKER_RE = re.compile(r"\(([A-Za-z][A-Za-z0-9]{1,9})\)")
_PAREN_EXCLUDE = {
    "UTC", "AM", "PM", "US", "UK", "EU", "USDT", "USDC", "USD", "ADR", "SPOT", "ZONE",
}


def paren_tickers(text: str) -> list[str]:
    out = []
    for m in _PAREN_TICKER_RE.finditer(text or ""):
        tok = m.group(1).upper()
        if tok in _PAREN_EXCLUDE:
            continue
        if tok not in out:
            out.append(tok)
    return out


def _strip_quote_suffix(tok: str) -> str:
    tok = tok.upper()
    for q in ("USDT", "USDC", "USD"):
        if tok.endswith(q) and len(tok) > len(q) + 1:
            return tok[: -len(q)]
    return tok


# ---------------------------------------------------------------------------------------
# Extraccion de tickers de un titulo de "nuevo listado". A diferencia de los deslistados
# (una sola frase "Delist X" en todos los exchanges), cada exchange redacta su anuncio de
# forma distinta - esta funcion prueba varios patrones vistos en el sondeo real, del mas
# especifico al mas generico, y usa el primero que matchee. Un titulo que no matchee NINGUNO
# (ej. "OKX to list USD-margined expiry futures" o "KuCoin Futures Will List Multiple Stock
# Index Perpetual Contracts" sin nombrar cuales) no inventa un ticker - el caller debe
# loguear y descartar esa fila, igual que ya hacia delistings/common.py.
# ---------------------------------------------------------------------------------------

_PERP_CONTRACT_SINGULAR_RE = re.compile(r"\bperpetual contracts?\b", re.IGNORECASE)
_TICKER_QUOTE_RE = re.compile(r"\b([A-Z0-9]{2,15})(?:USDT|USDC|USD)\b")
_SLASH_QUOTE_RE = re.compile(r"\b([A-Z0-9][A-Z0-9]{1,14})/(?:USDT|USDC|USD)(?:[Ⓢⓒ])?\b")

# "to list X (Y)" / "lists X (Y)" / "listed X (Y)": distintos exchanges ponen el ticker real
# ANTES del parentesis (OKX: "to list MON (Monad)") o DENTRO (Bitget: "to list Axis Robotics
# (AXIS)") segun si el nombre completo cabe en una palabra o no - no hay forma de saberlo sin
# mirar ambos lados. _pick_ticker se queda con el candidato que esta todo en mayusculas (asi
# se escriben los tickers reales en estos titulos) y sin espacios (un nombre descriptivo como
# "Tether Gold" o "Virtuals Protocol" nunca lo es).
_VERB_PAREN_RE = re.compile(
    r"\blist(?:s|ed)?\s+([A-Za-z0-9][A-Za-z0-9 ]{0,30}?)\s*\(([A-Za-z0-9][A-Za-z0-9 ]{0,30}?)\)",
    re.IGNORECASE,
)


def _pick_ticker(pre: str, inside: str) -> str:
    pre, inside = pre.strip(), inside.strip()
    pre_tok, inside_tok = " " not in pre, " " not in inside
    pre_upper = pre_tok and pre.isupper()
    inside_upper = inside_tok and inside.isupper()
    if pre_upper and not inside_upper:
        return pre
    if inside_upper and not pre_upper:
        return inside
    if pre_tok and not inside_tok:
        return pre
    if inside_tok and not pre_tok:
        return inside
    return pre if len(pre) <= len(inside) else inside


_TO_LIST_COMMA_RE = re.compile(
    r"to list\s+([A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*(?:,?\s*and\s+[A-Z0-9]+)?)\s+for\s+spot\s+trading",
    re.IGNORECASE,
)
_WILL_LIST_ADD_RE = re.compile(r"\bWill (?:List|Add)\s+([A-Za-z][A-Za-z0-9]{1,14})\b")
_FILLER_WORDS = {
    "MULTIPLE", "SEVERAL", "SOME", "NEW", "THE", "A", "AN", "THIS", "THAT", "MORE",
    "ADDITIONAL", "SELECT", "CERTAIN",
}
_LISTED_PERPS_RUN_RE = re.compile(
    r"\blisted\s+([A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*(?:\s+and\s+[A-Z0-9]+)?)\s+(?:hot\s+)?(?:stock\s+)?perps?\b",
    re.IGNORECASE,
)
_LISTING_OF_RE = re.compile(r"[Ll]isting of\s+([A-Z0-9]{2,15})\b")
# "KuCoin Spot to List Tokenized Stocks: AAPLX, HOODX, MSTRX and SPCXX"
_TOKENIZED_STOCKS_RE = re.compile(
    r"Tokenized Stocks:\s*([A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*(?:,?\s*and\s+[A-Z0-9]+)?)", re.IGNORECASE,
)
# "Binance Adds ANTA, CBRS, DISK, FOTO, KMEM, QNT and STRC on Binance Stock Trading"
_ADDS_STOCK_TRADING_RE = re.compile(
    r"\bAdds\s+([A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*(?:,?\s*and\s+[A-Z0-9]+)?)\s+on\s+\w+\s+Stock Trading",
    re.IGNORECASE,
)


def split_run(segment: str) -> list[str]:
    parts = re.split(r",|\band\b", segment, flags=re.IGNORECASE)
    out = []
    for p in parts:
        tok = re.sub(r"[^A-Za-z0-9]", "", p).strip()
        if not tok:
            continue
        tok = _strip_quote_suffix(tok)
        if tok and tok not in out:
            out.append(tok)
    return out


def extract_tickers(title: str) -> list[str]:
    if not title:
        return []
    t = title

    if _PERP_CONTRACT_SINGULAR_RE.search(t) and "contracts" not in t.lower():
        m = _TICKER_QUOTE_RE.search(t)
        if m:
            return [m.group(1).upper()]

    parens = paren_tickers(t)
    if len(parens) >= 2:
        return parens

    m = _VERB_PAREN_RE.search(t)
    if m:
        picked = _pick_ticker(m.group(1), m.group(2)).upper()
        if picked and " " not in picked and picked not in _FILLER_WORDS:
            return [picked]

    if len(parens) == 1:
        return parens

    m = _SLASH_QUOTE_RE.search(t)
    if m:
        return [m.group(1).upper()]

    m = _TO_LIST_COMMA_RE.search(t)
    if m:
        return split_run(m.group(1))

    m = _WILL_LIST_ADD_RE.search(t)
    if m and m.group(1).upper() not in _FILLER_WORDS:
        return [_strip_quote_suffix(m.group(1))]

    m = _LISTED_PERPS_RUN_RE.search(t)
    if m:
        return split_run(m.group(1))

    m = _LISTING_OF_RE.search(t)
    if m:
        return [_strip_quote_suffix(m.group(1))]

    m = _TOKENIZED_STOCKS_RE.search(t)
    if m:
        return split_run(m.group(1))

    m = _ADDS_STOCK_TRADING_RE.search(t)
    if m:
        return split_run(m.group(1))

    return []


# ---------------------------------------------------------------------------------------
# Ruido comun a varios exchanges (no son anuncios de un nuevo listado real)
# ---------------------------------------------------------------------------------------

_NOISE_PATTERNS = [
    re.compile(r"copy trad\w* now supports", re.IGNORECASE),
    re.compile(r"completed? .*(token )?migration", re.IGNORECASE),
    re.compile(r"cash dividend distribution", re.IGNORECASE),
    re.compile(r"collateral ratio|collateral index price", re.IGNORECASE),
    re.compile(r"\bpromotion\b|\bgiveaway\b|\bcampaign\b|prize pool", re.IGNORECASE),
    re.compile(r"trading challenge|trading competition|trading carnival", re.IGNORECASE),
    re.compile(r"regarding the delay|will delay|delay the listing", re.IGNORECASE),
    re.compile(r"\bairdrop\b", re.IGNORECASE),
    re.compile(r"\beventx\b", re.IGNORECASE),
    re.compile(r"pre-market trading|pre-market deliver", re.IGNORECASE),
    re.compile(r"beginner'?s guide", re.IGNORECASE),
    re.compile(r"\bcashback\b|\bshards\b", re.IGNORECASE),
    re.compile(r"\d{4} review\b", re.IGNORECASE),
    re.compile(r"\btrade \d+ usdt\b", re.IGNORECASE),
    re.compile(r"handles existing", re.IGNORECASE),
    re.compile(r"token splash|prize pool", re.IGNORECASE),
    re.compile(r"dividend|resumed trading|due to stock split", re.IGNORECASE),
    re.compile(r"pre-market trading", re.IGNORECASE),
    re.compile(r"\bupcoming listing\b", re.IGNORECASE),
    re.compile(r"vip (trip|night)|blockchain week|token2049|after-?party", re.IGNORECASE),
    re.compile(r"\d+\s+New\s+(?:USDC-M|Coin-M|USDT-M)\s+Perpetual Futures Trading Pairs", re.IGNORECASE),
    re.compile(r"Perpetual Futures Trading Is Now Live on", re.IGNORECASE),
    re.compile(r"\bCFD Trading Pairs\b", re.IGNORECASE),
]


def is_noise(title: str) -> bool:
    return any(p.search(title or "") for p in _NOISE_PATTERNS)


def detect_market(title: str) -> Optional[str]:
    if re.search(r"\b(futures?|perpetual|contract|usd[Ⓢⓒ]?-m|usdt-m)\b", title or "", re.IGNORECASE):
        return "futures"
    return "spot"


# ---------------------------------------------------------------------------------------
# Supabase upsert (identico en forma al de delistings/common.py, tabla distinta)
# ---------------------------------------------------------------------------------------

def upsert_rows(supabase_url: str, supabase_key: str, rows: list[Row]):
    if not rows:
        return
    url = f"{supabase_url.rstrip('/')}/rest/v1/{TABLE}?on_conflict=exchange,symbol,source_url"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    deduped: dict[tuple, dict] = {}
    for r in rows:
        deduped[(r.exchange, r.symbol, r.source_url)] = r.to_api_dict()
    payload = list(deduped.values())
    BATCH = 500
    for i in range(0, len(payload), BATCH):
        batch = payload[i:i + BATCH]
        resp = requests.post(url, json=batch, headers=headers, timeout=60)
        if resp.status_code >= 300:
            raise RuntimeError(f"Supabase respondio {resp.status_code}: {resp.text[:500]}")


__all__ = [
    "Row", "TABLE", "DEFAULT_HEADERS", "html_to_text", "parse_delist_datetime",
    "classify_asset_class", "classify_asset_class_or_ticker", "STOCK_TICKERS",
    "fetch_html_with_fallback",
    "paren_tickers", "extract_tickers", "split_run", "is_noise",
    "detect_market", "upsert_rows",
]
