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
from delistings.common import DEFAULT_HEADERS, html_to_text, parse_delist_datetime  # noqa: E402

log = logging.getLogger("newlistings")

TABLE = "exchange_new_listings"


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


# ---------------------------------------------------------------------------------------
# Clasificacion de asset_class - heuristica por palabras clave vistas en la investigacion
# (xStocks/bStocks de Binance y BingX, "Stock Index Perpetual" de KuCoin, acciones taiwanesas
# de Bitget, XAUT/oro de OKX y BingX). Por diseno, nunca inventa un activo tradicional que no
# se mencione: todo lo que no matchee una de estas categorias queda como 'crypto' (default).
# ---------------------------------------------------------------------------------------

_COMMODITY_RE = re.compile(
    r"\bgold\b|\bsilver\b|\bgoldx?\b|\bxau\w*\b|\bxag\w*\b|\boil\b|\bwti\b|\bcommodit",
    re.IGNORECASE,
)
_INDEX_RE = re.compile(r"\bstock index\b|\bindices?\b|\bindex\b", re.IGNORECASE)
_STOCK_RE = re.compile(
    r"\bstocks?\b|\bbstocks?\b|\bxstocks?\b|\(adr\)|tokenized securit|\bhot stock\b|\bstock perps?\b",
    re.IGNORECASE,
)


def classify_asset_class(title: str) -> str:
    t = title or ""
    if _COMMODITY_RE.search(t):
        return "commodity"
    if _INDEX_RE.search(t):
        return "index"
    if _STOCK_RE.search(t):
        return "stock"
    return "crypto"


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
_SLASH_QUOTE_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,14})/(?:USDT|USDC|USD)(?:[Ⓢⓒ])?\b")
_TO_LIST_SINGLE_PAREN_RE = re.compile(r"to list\s+([A-Z][A-Za-z0-9]{1,14})\s*\(", re.IGNORECASE)
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
    if parens:
        return parens

    m = _SLASH_QUOTE_RE.search(t)
    if m:
        return [m.group(1).upper()]

    m = _TO_LIST_SINGLE_PAREN_RE.search(t)
    if m and m.group(1).upper() not in _FILLER_WORDS:
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

    return []


# ---------------------------------------------------------------------------------------
# Ruido comun a varios exchanges (no son anuncios de un nuevo listado real)
# ---------------------------------------------------------------------------------------

_NOISE_PATTERNS = [
    re.compile(r"copy trading now supports", re.IGNORECASE),
    re.compile(r"completed? .*(token )?migration", re.IGNORECASE),
    re.compile(r"cash dividend distribution", re.IGNORECASE),
    re.compile(r"collateral ratio|collateral index price", re.IGNORECASE),
    re.compile(r"\bpromotion\b|\bgiveaway\b|\bcampaign\b|prize pool", re.IGNORECASE),
    re.compile(r"trading challenge|trading competition|trading carnival", re.IGNORECASE),
    re.compile(r"vip (trip|night)|blockchain week|token2049|after-?party", re.IGNORECASE),
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
    "classify_asset_class", "paren_tickers", "extract_tickers", "split_run", "is_noise",
    "detect_market", "upsert_rows",
]
