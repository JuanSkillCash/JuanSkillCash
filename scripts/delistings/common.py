"""
Utilidades compartidas por todos los scrapers de "Radar de Deslistados" (un modulo por
exchange en esta misma carpeta). Separado de los robots de scripts/*.py porque este es un
sistema de varias fuentes con el mismo esquema de salida, no un solo indicador.

Variables de entorno requeridas (las lee update_exchange_delistings.py, no este archivo):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("delistings")

TABLE = "exchange_delistings"

# User-Agent de navegador real: varios exchanges devuelven 403/challenge a requests sin esto.
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/129 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class Row:
    exchange: str
    symbol: str                     # ej "EPICUSDT" (ya con el quote pegado)
    pair_base: str                  # ej "EPIC"
    source_url: str
    title: str
    announced_at: Optional[datetime] = None
    delist_at: Optional[datetime] = None
    market: Optional[str] = None    # 'spot' | 'futures' | None (no se pudo determinar)

    def status(self, now: Optional[datetime] = None) -> str:
        now = now or datetime.now(timezone.utc)
        if self.delist_at and self.delist_at <= now:
            return "completed"
        return "upcoming"

    def to_api_dict(self) -> dict:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "pair_base": self.pair_base,
            "market": self.market,
            "announced_at": self.announced_at.isoformat() if self.announced_at else None,
            "delist_at": self.delist_at.isoformat() if self.delist_at else None,
            "title": self.title,
            "source_url": self.source_url,
            "status": self.status(),
        }


# ---------------------------------------------------------------------------------------
# Parseo de fechas - un patron por formato visto en la investigacion (regla comun #2)
# ---------------------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# "2026-10-28 03:00 (UTC)"  -> Binance, Bitunix
_RE_ISO_HM_UTC = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})(?::\d{2})?\s*(?:AM|PM)?\s*\(UTC\)",
    re.IGNORECASE,
)

# "03:00 UTC on May 6, 2026"  -> Gate
_RE_HM_UTC_ON_MONTH = re.compile(
    r"(\d{1,2}):(\d{2})\s*UTC\s*on\s*([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)

# "[Oct 20, 2026, 07:00 (UTC)]"  -> MEXC (con o sin corchetes)
_RE_MONTH_DD_YYYY_HM_UTC = re.compile(
    r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),\s*(\d{4}),\s*(\d{1,2}):(\d{2})\s*\(UTC\)",
    re.IGNORECASE,
)

# "October 23, 2026, 14:00 UTC"  -> Kraken (prosa, sin parentesis)
_RE_MONTH_DD_YYYY_HM_UTC_PROSE = re.compile(
    r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4}),?\s+(\d{1,2}):(\d{2})\s*UTC",
    re.IGNORECASE,
)

# fallback para titulo: "(2026-10-10)" o "on 2026-10-16"  -> KuCoin/Bitget/BingX/OKX
_RE_DATE_ONLY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _month_num(name: str) -> Optional[int]:
    return _MONTHS.get(name.strip().lower()[:3])


def parse_delist_datetime(text: str) -> Optional[datetime]:
    """Intenta sacar una fecha/hora UTC de un texto (titulo o cuerpo), probando los
    formatos documentados en la investigacion, del mas especifico (con hora) al menos
    especifico (solo fecha, sin hora -> queda a medianoche UTC)."""
    if not text:
        return None

    m = _RE_ISO_HM_UTC.search(text)
    if m:
        y, mo, d, h, mi = (int(x) for x in m.groups())
        return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)

    m = _RE_MONTH_DD_YYYY_HM_UTC.search(text)
    if m:
        mon, d, y, h, mi = m.groups()
        mo = _month_num(mon)
        if mo:
            return datetime(int(y), mo, int(d), int(h), int(mi), tzinfo=timezone.utc)

    m = _RE_HM_UTC_ON_MONTH.search(text)
    if m:
        h, mi, mon, d, y = m.groups()
        mo = _month_num(mon)
        if mo:
            return datetime(int(y), mo, int(d), int(h), int(mi), tzinfo=timezone.utc)

    m = _RE_MONTH_DD_YYYY_HM_UTC_PROSE.search(text)
    if m:
        mon, d, y, h, mi = m.groups()
        mo = _month_num(mon)
        if mo:
            return datetime(int(y), mo, int(d), int(h), int(mi), tzinfo=timezone.utc)

    m = _RE_DATE_ONLY.search(text)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        try:
            return datetime(y, mo, d, tzinfo=timezone.utc)
        except ValueError:
            return None

    # ultimo recurso: dateutil tolera prosa rara que los regex de arriba no cubren
    try:
        from dateutil import parser as dateutil_parser
        dt = dateutil_parser.parse(text, fuzzy=True, default=datetime(1970, 1, 1, tzinfo=timezone.utc))
        if dt.year == 1970:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def html_to_text(html: str) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator="\n")


# un mismo aviso trae varias fechas (fin de copy-trading, liquidacion de futuros, fin de
# depositos, fin de spot, fin de retiros - regla comun #3): hay que quedarse con la fecha
# de CESE DE SPOT, no con cualquier fecha que aparezca en el cuerpo
_PRIMARY_DATE_CTX = re.compile(r"\bspot\b|cease\s+trading|delist|trading\s+pair", re.IGNORECASE)
_SECONDARY_DATE_CTX = re.compile(r"deposit", re.IGNORECASE)
_EXCLUDE_DATE_CTX = re.compile(r"futures?|perpetual|copy[- ]trading|withdraw", re.IGNORECASE)


def extract_delist_date_from_body(body_html: str, created_at: Optional[datetime] = None) -> Optional[datetime]:
    """Busca, frase por frase, la fecha asociada al cese de trading SPOT (no de futuros,
    no de copy-trading, no de retiros) dentro del cuerpo de un anuncio. Si la unica fecha
    que aparece esta en contexto excluido (solo futuros/retiros), devuelve None en vez de
    una fecha equivocada - el caller debe caer entonces al fallback del titulo."""
    text = html_to_text(body_html)
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    best_dt, best_score = None, None
    for chunk in chunks:
        dt = parse_delist_datetime(chunk)
        if not dt:
            continue
        score = 0
        if _PRIMARY_DATE_CTX.search(chunk):
            score += 2
        if _SECONDARY_DATE_CTX.search(chunk):
            score += 1
        if _EXCLUDE_DATE_CTX.search(chunk):
            score -= 3
        if best_score is None or score > best_score:
            best_score, best_dt = score, dt
    if best_score is None or best_score < 0:
        return None
    if best_dt and created_at and abs((best_dt - created_at).days) > 400:
        # fecha absurdamente lejos del anuncio -> probable error de parseo (caso SIDUS/ELX
        # mencionado en la investigacion); mejor no dar un dato incorrecto
        return None
    return best_dt


# ---------------------------------------------------------------------------------------
# Deteccion spot/futuros (regla comun #4)
# ---------------------------------------------------------------------------------------

_FUTURES_WORDS = re.compile(
    r"\b(futures?|perpetual|contract|usd[Ⓢⓒ]?-m|usdt-m|standard futures)\b",
    re.IGNORECASE,
)


def detect_market(title: str) -> Optional[str]:
    if _FUTURES_WORDS.search(title or ""):
        return "futures"
    return "spot"


# ---------------------------------------------------------------------------------------
# Ruido a excluir dentro de la categoria "Delisting" (regla comun #5) - devuelve True si
# el anuncio debe IGNORARSE por completo (no es un delisting real de un par).
# ---------------------------------------------------------------------------------------

_NOISE_PATTERNS = [
    re.compile(r"simple earn.*product", re.IGNORECASE),
    re.compile(r"disable lending feature", re.IGNORECASE),
    re.compile(r"cfd to discontinue", re.IGNORECASE),
    re.compile(r"binance alpha will remove", re.IGNORECASE),
    re.compile(r"stock futures", re.IGNORECASE),
]


def is_noise(title: str) -> bool:
    return any(p.search(title or "") for p in _NOISE_PATTERNS)


def is_completion_notice(title: str) -> bool:
    """'Gate Completes Delisting and Buyback of ...' -> ya paso, marcar completed en vez
    de generar una fila 'upcoming' nueva sin delist_at."""
    return bool(re.search(r"completes? delisting", title or "", re.IGNORECASE))


def is_delay_notice(title: str) -> bool:
    """'Bitget to delay the delisting of ...' -> actualiza delist_at de una fila existente,
    no crea una fila nueva (regla comun #5)."""
    return bool(re.search(r"delay(?:s|ed)?\s+the\s+delisting", title or "", re.IGNORECASE))


# ---------------------------------------------------------------------------------------
# Extraccion de tickers de un titulo tipo "... Delist EPIC, QUICK on ..." o
# "... Delist the WLUSDT Perpetual Contract ..." (regla comun #1)
# ---------------------------------------------------------------------------------------

_STOPWORDS = {
    "AND", "THE", "ON", "FOR", "FROM", "OTHER", "ASSETS", "MULTIPLE", "TOKENS",
    "PERPETUAL", "CONTRACT", "CONTRACTS", "FUTURES", "TRADING", "SPOT", "PAIR", "PAIRS",
    "MARKET", "MARKETS", "SERVICES", "USDT", "USDC", "USD", "SERVICE", "WILL", "DELIST",
    "DELISTS", "DELISTING", "OF", "TO", "A", "AN", "WITH", "STANDARD",
}


_PAREN_TICKER_RE = re.compile(r"\(([A-Za-z][A-Za-z0-9]{1,9})\)")
_PAREN_EXCLUDE = {"UTC", "AM", "PM", "US", "UK", "EU", "USDT", "USDC", "USD"}


def _paren_tickers(text: str) -> list[str]:
    """'Game by Virtual (GAME)' / 'Alpaca Finance (ALPACA) and Hifi Finance (HIFI)': el
    nombre largo del proyecto no es el ticker, el que va entre parentesis si. Excluye
    fechas ('(2026-10-28)' no matchea por empezar con digito) y palabras sueltas como
    '(UTC)' que a veces quedan en el mismo titulo."""
    out = []
    for m in _PAREN_TICKER_RE.finditer(text or ""):
        tok = m.group(1).upper()
        if tok in _PAREN_EXCLUDE or tok in _STOPWORDS:
            continue
        if tok not in out:
            out.append(tok)
    return out


def extract_tickers(title: str) -> list[str]:
    """Saca la lista de simbolos base de un titulo de aviso. Busca el tramo entre un verbo
    de delisting ('Delist'/'Delisting of'/'Will Remove') y el primer 'on'/'from'/'for'/'['
    que le siga, y separa por comas/'and'. Si el titulo trae un symbol pegado tipo
    'WLUSDT Perpetual Contract', le quita el sufijo USDT/USDC/USD. Si el titulo no tiene
    ninguno de esos verbos, no es un aviso de deslistado reconocible - no se inventan
    tickers partiendo el titulo entero en palabras (eso generaba basura con anuncios de
    otro tema, ej. suspensiones de margen, que por error terminaban en la categoria)."""
    if not title:
        return []

    t = title.replace("，", ",")  # coma china vista en Bitget (regla comun #5)

    # delist\w* cubre "Delist"/"Delists"/"Delisting" (BingX usa "Delists", sin will/to);
    # "the " opcional despues del verbo cubre "Delist the WLUSDT ..." sin dejarlo pegado al ticker
    m = re.search(
        r"(?:delist\w*(?:\s+of)?|will remove)\s+(?:the\s+)?(.*?)(?:\s+(?:on|from|for)\s|\s*\[|\s*\(|$)",
        t, re.IGNORECASE,
    )

    paren_tickers = _paren_tickers(t)
    if not m:
        return paren_tickers
    if paren_tickers:
        return paren_tickers

    segment = m.group(1)

    # numero suelto al inicio ("8 Assets Including NoLimit, ..." -> "8" quedaba pegado al
    # primer ticker si no se saca aparte)
    segment = re.sub(r"^\s*\d+\s*", "", segment)

    # corta ruido que queda pegado al tramo capturado: sufijos de mercado/par ("Perpetual
    # Futures Pairs", "USDT-M"), frases de relleno ("and related services", "Buy Back",
    # "Including") que si no se quitan dejan basura como token suelto despues de separar
    # por comas/"and"
    segment = re.sub(
        r"\b(perpetual|futures?|contracts?|pairs?|trading|market|service|services|spot|"
        r"related|standard|usdt-m|usd1-m|other|assets?|multiple|tokens?|coins?|including|"
        r"buys?\s*backs?)\b",
        "", segment, flags=re.IGNORECASE,
    )

    parts = re.split(r",|/|&|\band\b", segment, flags=re.IGNORECASE)
    tickers: list[str] = []
    for p in parts:
        tok = re.sub(r"[^A-Za-z0-9]", "", p).upper()
        if not tok or tok in _STOPWORDS:
            continue
        # "WLUSDT" -> "WL" (symbol pegado al quote, caso 'Will Delist the WLUSDT Perpetual Contract')
        for quote in ("USDT", "USDC", "USD"):
            if tok.endswith(quote) and len(tok) > len(quote) + 1:
                tok = tok[: -len(quote)]
                break
        if tok and tok not in _STOPWORDS and tok not in tickers:
            tickers.append(tok)
    return tickers


def rows_from_title(
    exchange: str, title: str, source_url: str,
    announced_at: Optional[datetime] = None, delist_at: Optional[datetime] = None,
    quote: str = "USDT",
) -> list[Row]:
    """Atajo comun: construye una Row por cada ticker detectado en el titulo."""
    market = detect_market(title)
    rows = []
    for base in extract_tickers(title):
        rows.append(Row(
            exchange=exchange, symbol=f"{base}{quote}", pair_base=base,
            source_url=source_url, title=title,
            announced_at=announced_at, delist_at=delist_at, market=market,
        ))
    return rows


# ---------------------------------------------------------------------------------------
# Supabase upsert
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

    # Postgres rechaza el batch entero si dos filas del mismo POST comparten la clave de
    # conflicto (exchange,symbol,source_url) - "ON CONFLICT DO UPDATE command cannot affect
    # row a second time" (confirmado con MEXC: una pagina listada dos veces produjo la misma
    # fila repetida). Deduplicar aca, a nivel de infraestructura, protege contra esto sin
    # importar que exchange lo cause.
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
