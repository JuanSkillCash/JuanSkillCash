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
import os
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


class ExchangeBlocked(Exception):
    """El scraper detecto una respuesta de bloqueo real (403/429 persistente despues de
    reintentar, "Access Denied" de un WAF, CloudFront geo-bloqueado, etc.) - distinto de
    "no hay nada nuevo que mostrar". El orquestador la distingue de un 0 filas comun para
    marcar el exchange como "problema de red" en vez de "sin datos" (el usuario pidio
    poder diferenciar ambos casos en el panel)."""
    pass


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
    asset_class: str = "crypto"     # 'crypto' | 'stock' | 'index' | 'commodity'

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
            "asset_class": self.asset_class,
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

# "2026-10-28 03:00 (UTC)" (Binance, Bitunix) o "2026-10-23 14:00 UTC" sin parentesis (Kraken)
_RE_ISO_HM_UTC = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})(?::\d{2})?\s*(?:AM|PM)?\s*\(?UTC\)?",
    re.IGNORECASE,
)

# "03:00 UTC on May 6, 2026"  -> Gate
_RE_HM_UTC_ON_MONTH = re.compile(
    r"(\d{1,2}):(\d{2})\s*UTC\s*on\s*([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)

# "[Oct 20, 2026, 07:00 (UTC)]"  -> MEXC (con o sin corchetes). El AM/PM opcional cubre
# "November 6, 2026, 10:00 AM (UTC)" (visto en Bitget) - sin esto la fecha real de
# deslistado no matcheaba NINGUN regex en modo strict y extract_delist_date_from_body
# terminaba agarrando por error alguna otra fecha suelta del cuerpo (ej. la de publicacion
# del aviso), confirmado con el caso real de BRETT/USDT en Bitget.
_RE_MONTH_DD_YYYY_HM_UTC = re.compile(
    r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),\s*(\d{4}),\s*(\d{1,2}):(\d{2})\s*(AM|PM)?\s*\(UTC\)",
    re.IGNORECASE,
)

# "October 23, 2026, 14:00 UTC"  -> Kraken (prosa, sin parentesis)
_RE_MONTH_DD_YYYY_HM_UTC_PROSE = re.compile(
    r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4}),?\s+(\d{1,2}):(\d{2})\s*(AM|PM)?\s*UTC",
    re.IGNORECASE,
)

# fallback para titulo: "(2026-10-10)" o "on 2026-10-16"  -> KuCoin/Bitget/BingX/OKX
_RE_DATE_ONLY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _month_num(name: str) -> Optional[int]:
    return _MONTHS.get(name.strip().lower()[:3])


def _hour_24(h: str, ampm: Optional[str]) -> int:
    """Convierte una hora de 12h + AM/PM (si vino) a 24h - 'ampm' es None cuando el texto
    ya trae la hora en 24h (no tenia AM/PM), en cuyo caso se usa tal cual."""
    hour = int(h)
    if not ampm:
        return hour
    ampm = ampm.upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    return hour


def parse_delist_datetime(text: str, strict: bool = False) -> Optional[datetime]:
    """Intenta sacar una fecha/hora UTC de un texto (titulo o cuerpo), probando los
    formatos documentados en la investigacion, del mas especifico (con hora) al menos
    especifico (solo fecha, sin hora -> queda a medianoche UTC). strict=True desactiva el
    fallback de dateutil (ver nota abajo: ese fallback puede "inventar" un dia 1 de un
    texto que solo trae mes y anio, como el titulo "... - October 2026")."""
    if not text:
        return None

    m = _RE_ISO_HM_UTC.search(text)
    if m:
        y, mo, d, h, mi = (int(x) for x in m.groups())
        return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)

    m = _RE_MONTH_DD_YYYY_HM_UTC.search(text)
    if m:
        mon, d, y, h, mi, ampm = m.groups()
        mo = _month_num(mon)
        if mo:
            return datetime(int(y), mo, int(d), _hour_24(h, ampm), int(mi), tzinfo=timezone.utc)

    m = _RE_HM_UTC_ON_MONTH.search(text)
    if m:
        h, mi, mon, d, y = m.groups()
        mo = _month_num(mon)
        if mo:
            return datetime(int(y), mo, int(d), int(h), int(mi), tzinfo=timezone.utc)

    m = _RE_MONTH_DD_YYYY_HM_UTC_PROSE.search(text)
    if m:
        mon, d, y, h, mi, ampm = m.groups()
        mo = _month_num(mon)
        if mo:
            return datetime(int(y), mo, int(d), _hour_24(h, ampm), int(mi), tzinfo=timezone.utc)

    m = _RE_DATE_ONLY.search(text)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        try:
            return datetime(y, mo, d, tzinfo=timezone.utc)
        except ValueError:
            return None

    if strict:
        return None

    # ultimo recurso: dateutil tolera prosa rara que los regex de arriba no cubren - pero
    # tambien "adivina" un dia 1 de un texto que solo trae mes+anio sin dia real (confirmado
    # con Kraken: el titulo "... - October 2026" se colaba como si fuera 2026-10-01, pisando
    # la fecha real y precisa que si estaba en el cuerpo) - por eso extract_delist_date_from_body
    # SIEMPRE llama primero en modo strict a todos los candidatos, y solo usa este fallback
    # como ultimo recurso si NINGUN chunk del texto completo trajo una fecha con formato exacto
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

    def _scan(strict: bool):
        best_dt, best_score, best_has_time = None, None, False
        for chunk in chunks:
            dt = parse_delist_datetime(chunk, strict=strict)
            if not dt:
                continue
            score = 0
            if _PRIMARY_DATE_CTX.search(chunk):
                score += 2
            if _SECONDARY_DATE_CTX.search(chunk):
                score += 1
            if _EXCLUDE_DATE_CTX.search(chunk):
                score -= 3
            # metadata de la pagina (ej. "ultima actualizacion"/fecha de publicacion, mostrada
            # suelta cerca del titulo) a veces queda en su propio chunk sin ninguna palabra
            # clave alrededor (separado por una etiqueta HTML inline), empatando en score con
            # la fecha real de deslistado si esta TAMBIEN quedo aislada de su contexto por el
            # mismo motivo - en ese empate, a igual score, se prefiere el candidato que trajo
            # una hora explicita (viene de un patron mas especifico, no del fallback de "solo
            # fecha" que ignora cualquier hora que haya al lado) - confirmado con el caso real
            # de BRETT/USDT en Bitget, donde la fecha de publicacion ("2026-10-30 10:00", sin
            # "UTC" al lado asi que cae al patron de solo-fecha) aparecia antes en el texto que
            # la fecha real del deslistado y le ganaba el empate solo por orden
            has_time = not (dt.hour == 0 and dt.minute == 0)
            if best_score is None or score > best_score or (score == best_score and has_time and not best_has_time):
                best_score, best_dt, best_has_time = score, dt, has_time
        return best_dt, best_score

    # dos pasadas: primero solo fechas con formato EXACTO (strict=True) en todos los chunks;
    # el fallback de dateutil (fuzzy) solo se intenta si NINGUN chunk del texto completo trajo
    # una fecha exacta - evita que un "... - October 2026" del titulo (sin dia real) le gane a
    # la fecha precisa que si esta en el cuerpo, solo por tener mejor contexto (caso Kraken)
    best_dt, best_score = _scan(strict=True)
    if best_dt is None:
        best_dt, best_score = _scan(strict=False)
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
# Clasificacion de asset_class - compartida con newlistings/common.py (ese modulo la
# importa de aca). Heuristica por palabras clave vistas en la investigacion (xStocks/
# bStocks, "Stock Index Perpetual", acciones taiwanesas, XAUT/oro). Todo lo que no
# matchee una de estas categorias queda como 'crypto' (default) - nunca se inventa un
# activo tradicional que el titulo no mencione.
# ---------------------------------------------------------------------------------------

_COMMODITY_RE = re.compile(
    r"\bgold\b|\bsilver\b|\bgoldx?\b|\bxau\w*\b|\bxag\w*\b|\boil\b|\bwti\b|\bcommodit",
    re.IGNORECASE,
)
_INDEX_RE = re.compile(r"\bstock index\b|\bindices?\b|\bindex\b", re.IGNORECASE)
_STOCK_RE = re.compile(
    r"\bstocks?\b|\bbstocks?\b|\bxstocks?\b|\(adr\)|tokenized securit|\bhot stock\b|\bstock perps?\b|"
    r"\bpre-ipo\b|\btradfi\b",
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


_BODY_PAIR_TICKER_RE = re.compile(r"\b([A-Z0-9]{2,15})/(?:USDT|USDC|USD|BTC|ETH|BNB)\b")


def extract_tickers_from_body(body_text: str) -> list[str]:
    """Respaldo para titulos genericos tipo 'Notice of Delisting 6 Spot Trading Pairs on
    November 6, 2026' (visto en Bitget desde fines de octubre 2026) donde el titulo no trae
    ningun ticker, solo la cantidad - la lista real vive en el cuerpo del aviso, como
    'Details are as follows: CHILLGUY/USDT; ZIG/USDT; BRETT/USDT; ...'. Busca pares
    TICKER/QUOTE en todo el texto en vez de depender de esa frase exacta, por si el
    exchange cambia la redaccion de nuevo."""
    out: list[str] = []
    for m in _BODY_PAIR_TICKER_RE.finditer(body_text or ""):
        tok = m.group(1).upper()
        if tok in _STOPWORDS or tok in out:
            continue
        out.append(tok)
    return out


def rows_from_title(
    exchange: str, title: str, source_url: str,
    announced_at: Optional[datetime] = None, delist_at: Optional[datetime] = None,
    quote: str = "USDT",
) -> list[Row]:
    """Atajo comun: construye una Row por cada ticker detectado en el titulo."""
    market = detect_market(title)
    asset_class = classify_asset_class(title)
    rows = []
    for base in extract_tickers(title):
        rows.append(Row(
            exchange=exchange, symbol=f"{base}{quote}", pair_base=base,
            source_url=source_url, title=title, asset_class=asset_class,
            announced_at=announced_at, delist_at=delist_at, market=market,
        ))
    return rows


# ---------------------------------------------------------------------------------------
# Cache de fechas ya conocidas - evita volver a abrir el cuerpo de un articulo viejo en
# cada corrida horaria solo para sacar una fecha que YA tenemos guardada y que no cambia
# (la fecha de cese de un deslistado pasado es fija). Los scrapers que abren el cuerpo de
# cada aviso para extraer delist_at (bybit, blofin, lbank, coinw, weex, pionex) la usan para
# saltarse el fetch cuando el articulo ya esta en Supabase con una fecha resuelta - el
# presupuesto de cuerpos-por-corrida queda entonces solo para avisos genuinamente nuevos.
# ---------------------------------------------------------------------------------------

def fetch_known_delist_dates(exchange: str) -> dict[str, Optional[datetime]]:
    """{source_url: delist_at} de lo que ya esta guardado para este exchange. Nunca debe
    tumbar una corrida: si Supabase no responde bien (tabla recien creada, credenciales
    faltantes, etc.) devuelve {} y el scraper simplemente vuelve a pedir los cuerpos como
    antes - mas lento esta vez, pero nunca mas filas perdidas."""
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not supabase_key:
        return {}
    try:
        url = f"{supabase_url}/rest/v1/{TABLE}?exchange=eq.{exchange}&select=source_url,delist_at&limit=5000"
        headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            return {}
        out: dict[str, Optional[datetime]] = {}
        for row in resp.json():
            source_url = row.get("source_url")
            if not source_url:
                continue
            delist_at_raw = row.get("delist_at")
            if delist_at_raw:
                try:
                    out[source_url] = datetime.fromisoformat(delist_at_raw.replace("Z", "+00:00"))
                except ValueError:
                    out[source_url] = None
            else:
                out.setdefault(source_url, None)
        return out
    except requests.RequestException:
        return {}


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


STATUS_TABLE = "exchange_scraper_status"


def upsert_scraper_status(supabase_url: str, supabase_key: str, radar: str, statuses: dict[str, tuple[str, Optional[str]]]):
    """statuses: {exchange: (status, detail)} con status 'ok' | 'blocked'. Un registro por
    (exchange, radar), siempre pisando el anterior - el panel solo le interesa el estado de
    la corrida MAS RECIENTE, no un historial."""
    if not statuses:
        return
    url = f"{supabase_url.rstrip('/')}/rest/v1/{STATUS_TABLE}?on_conflict=exchange,radar"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    checked_at = datetime.now(timezone.utc).isoformat()
    payload = [
        {"exchange": exchange, "radar": radar, "status": status, "detail": (detail or "")[:500], "checked_at": checked_at}
        for exchange, (status, detail) in statuses.items()
    ]
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase ({STATUS_TABLE}) respondio {resp.status_code}: {resp.text[:500]}")


# ---------------------------------------------------------------------------------------
# WebSocket oficial de anuncios de Gate (wss://api.gateio.ws/ws/v4/ann) - fuente alternativa
# a www.gate.com, bloqueado por Akamai (403 "Access Denied") desde la IP compartida de los
# runners de GitHub Actions. Confirmado con un diagnostico real que este WebSocket (API de
# trading, infraestructura separada de la del sitio web) SI es alcanzable desde el runner:
# conecta y responde al instante. Al suscribirse, el servidor manda primero el ULTIMO aviso
# cacheado de ese canal (no historial completo) y despues empuja los nuevos mientras la
# conexion siga abierta - con la cadencia horaria de este proyecto alcanza con escuchar una
# ventana corta cada corrida; lo que se pierda en un hueco raro de mas de un aviso por hora
# para el mismo canal se acepta igual que el resto de los scrapers de este proyecto (ningun
# otro trae historial completo tampoco, todos son snapshots horarios acumulados).
GATE_WS_URL = "wss://api.gateio.ws/ws/v4/ann"


def fetch_gate_ws_items(channel: str, listen_seconds: int = 30) -> list[dict]:
    """Se conecta al WebSocket, se suscribe a un solo canal (ej. "announcement.summary_listing"
    o "announcement.summary_delisting") y devuelve la lista de `result` de cada mensaje tipo
    "update" recibido en esa ventana (el aviso cacheado inicial + cualquier push nuevo)."""
    import json
    import time as _time

    import websocket

    try:
        ws = websocket.create_connection(GATE_WS_URL, timeout=15)
    except Exception as e:
        raise ExchangeBlocked(f"[gate-ws] no se pudo conectar a {GATE_WS_URL}: {e}")

    items: list[dict] = []
    try:
        ws.send(json.dumps({
            "time": int(_time.time()), "channel": channel, "event": "subscribe", "payload": ["en"],
        }))
        deadline = _time.time() + listen_seconds
        while _time.time() < deadline:
            remaining = deadline - _time.time()
            ws.settimeout(max(1, remaining))
            try:
                raw = ws.recv()
            except Exception:
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("channel") == channel and msg.get("event") == "update" and isinstance(msg.get("result"), dict):
                items.append(msg["result"])
    finally:
        ws.close()

    return items
