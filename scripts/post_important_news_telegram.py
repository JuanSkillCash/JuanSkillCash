"""
Manda a Telegram TODAS las noticias cripto nuevas de news_archive (Juan, 23-nov-2026: "quiero que
envíes todas las noticias crypto al telegram menos las que dice: Esto es lo que sucedió en Crypto
hoy..." - antes este script solo mandaba las que la IA del Worker clasificaba "importancia: alta";
ese filtro se quitó).

Lee de news_archive (ya poblada cada 30 min por update_news_archive.py) en vez de pedirle de nuevo
al Worker - evita gastar cupo de Workers AI dos veces y reusa el mismo historial que ya alimenta
el buscador del sitio.

Dos filtros de TÍTULO (ninguno usa IA, a propósito - más confiable que pedirle a un modelo que lo
adivine, y Juan los puede ampliar en cualquier momento):

1. Monedas excluidas (pedido explícito de Juan, 20-nov-2026): si el título menciona XRP, Stellar
   (XLM), Hedera (HBAR) o Flare/Songbird (FLR/SGB), se descarta - lista fija en EXCLUDED_KEYWORDS.
2. Resumen diario "Esto es lo que sucedió en Crypto hoy..." (pedido explícito de Juan,
   23-nov-2026): un titular recurrente de resumen del día (no es una noticia puntual) se descarta -
   patrón en EXCLUDED_TITLE_PATTERN.

"telegram_enviado" se marca en true tanto si la noticia se mandó de verdad como si se descartó por
cualquiera de los dos filtros - en los dos casos ya se "resolvió" esa fila y no hace falta
revisarla de nuevo en la próxima corrida.

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    TELEGRAM_BOT_TOKEN
"""

from __future__ import annotations

import logging
import os
import re
import sys

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("post_important_news_telegram")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TABLE = "news_archive"

# Mismo chat que ya usa el boletín diario (post_crypto_bulletin_telegram.py). El tema/hilo es OTRO
# (el de "Análisis Crypto" es 8549, usado por el boletín) - Juan pasó el link de este, el de
# noticias: https://t.me/juanskll/8540
TELEGRAM_CHAT = "@juanskll"
TELEGRAM_THREAD_ID = 8540

# Palabras que descartan una noticia aunque la IA la haya marcado "alta" (pedido explícito de
# Juan, 20-nov-2026: "excluir todo lo relacionado con xrp, xlm, hbar, Flare... cryptos ISO").
# \b = límite de palabra, para no hacer match a mitad de otra palabra.
EXCLUDED_KEYWORDS = ["xrp", "ripple", "xlm", "stellar", "hbar", "hedera", "flr", "sgb", "flare", "songbird"]
EXCLUDED_PATTERN = re.compile(r"\b(?:" + "|".join(EXCLUDED_KEYWORDS) + r")\b", re.IGNORECASE)

# Resumen diario tipo "Esto es lo que sucedió en Crypto hoy..." (Juan, 23-nov-2026) - no es una
# noticia puntual, es un recap. "sucedió|pasó" cubre variaciones del mismo titular día a día.
EXCLUDED_TITLE_PATTERN = re.compile(r"esto es lo que (?:sucedi[oó]|pas[oó]) en crypto hoy", re.IGNORECASE)

MAX_PER_RUN = 8  # tope de seguridad - si algo saliera mal y hubiera un montón pendiente, no inundar el canal de una


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_pendientes() -> list[dict]:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        params={
            "category": "eq.crypto",
            "telegram_enviado": "eq.false",
            "select": "id,title,resumen,resumen_largo,source,imagen",
            "order": "published_at.asc",
            "limit": str(MAX_PER_RUN),
        },
        headers=_sb_headers(), timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"no se pudo leer {TABLE} ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


def marca_resuelta(row_id: int) -> None:
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        params={"id": f"eq.{row_id}"},
        json={"telegram_enviado": True},
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        timeout=20,
    )
    if resp.status_code >= 300:
        log.warning(f"no se pudo marcar telegram_enviado en la fila {row_id} ({resp.status_code}): {resp.text[:300]}")


def build_caption(row: dict) -> str:
    # Juan, 20-nov-2026, segundo pedido (el primero fue "que el texto no sea tan largo", por eso
    # antes se usaba "resumen" corto + el link al final): ahora pidió lo contrario - "que no
    # traigan el link y tuviera un poco más de detalles claves el texto, está muy simple" y luego
    # "quizás un poquito más largo" todavía. Se quita el link del todo y se usan LOS DOS campos que
    # ya arma la misma llamada a Workers AI (no son llamadas nuevas): "resumen" (la frase corta de
    # contexto) seguido de "resumen_largo" (el párrafo de 50-90 palabras que también alimenta la
    # "vista detallada" del sitio) - juntos dan más cuerpo al mensaje sin tocar esa llamada a la
    # IA. "Fuente" al final da de dónde salió la noticia sin que sea un link clickeable.
    titulo = (row.get("title") or "").strip()
    resumen = (row.get("resumen") or "").strip()
    detalle = (row.get("resumen_largo") or "").strip()
    fuente = (row.get("source") or "").strip()
    partes = [f"🚨 {titulo}"]
    if resumen:
        partes.append(resumen)
    if detalle and detalle != resumen:
        partes.append(detalle)
    if fuente:
        partes.append(f"Fuente: {fuente}")
    return "\n\n".join(partes)


def send_to_telegram(caption: str, imagen: str | None) -> None:
    base = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if imagen:
        # Telegram acepta mandarle la URL de la foto directo (sendPhoto con photo=<url>), no hace
        # falta descargarla y subirla nosotros - mismo truco que usan sitios con bots de noticias
        resp = requests.post(
            f"{base}/sendPhoto",
            data={"chat_id": TELEGRAM_CHAT, "message_thread_id": TELEGRAM_THREAD_ID, "photo": imagen, "caption": caption[:1024]},
            timeout=30,
        )
        if resp.status_code >= 300:
            # la URL de la imagen puede fallar (medio la borró, timeout del lado de Telegram al
            # descargarla, etc.) - no es motivo para perder la noticia entera, se reintenta como
            # mensaje de texto plano antes de darse por vencido
            log.warning(f"sendPhoto falló ({resp.status_code}): {resp.text[:300]} - reintentando como texto")
            resp = requests.post(
                f"{base}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT, "message_thread_id": TELEGRAM_THREAD_ID, "text": caption},
                timeout=30,
            )
    else:
        resp = requests.post(
            f"{base}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT, "message_thread_id": TELEGRAM_THREAD_ID, "text": caption},
            timeout=30,
        )
    if resp.status_code >= 300:
        raise RuntimeError(f"Telegram respondió {resp.status_code}: {resp.text[:500]}")


def main() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)
    if not TELEGRAM_BOT_TOKEN:
        log.error("Falta TELEGRAM_BOT_TOKEN en el entorno.")
        sys.exit(1)
    if TELEGRAM_THREAD_ID is None:
        log.error(
            "TELEGRAM_THREAD_ID sigue sin configurar (ver TODO en este archivo) - "
            "falta que Juan pase el link del tema de Telegram donde van estas alertas."
        )
        sys.exit(1)

    pendientes = fetch_pendientes()
    if not pendientes:
        log.info("sin noticias cripto nuevas - nada que mandar.")
        return

    enviadas, excluidas_moneda, excluidas_recap = 0, 0, 0
    for row in pendientes:
        titulo = row.get("title") or ""
        if EXCLUDED_PATTERN.search(titulo):
            log.info(f"excluida por filtro de monedas (fila {row['id']}): {titulo[:80]}")
            marca_resuelta(row["id"])
            excluidas_moneda += 1
            continue
        if EXCLUDED_TITLE_PATTERN.search(titulo):
            log.info(f"excluida por ser el recap diario (fila {row['id']}): {titulo[:80]}")
            marca_resuelta(row["id"])
            excluidas_recap += 1
            continue
        try:
            send_to_telegram(build_caption(row), row.get("imagen"))
            marca_resuelta(row["id"])
            enviadas += 1
        except Exception as e:  # noqa: BLE001 - un fallo puntual de Telegram no debe tumbar el resto del lote
            log.warning(f"no se pudo mandar la fila {row['id']} ({titulo[:80]}): {e}")

    log.info(
        f"Listo. {enviadas} mandadas, {excluidas_moneda} excluidas por filtro de monedas, "
        f"{excluidas_recap} excluidas por ser el recap diario, {len(pendientes)} revisadas."
    )


if __name__ == "__main__":
    main()
