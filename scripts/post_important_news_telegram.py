"""
Manda a Telegram las noticias cripto que la IA del Worker de noticias (workers/rss-news/worker.js)
clasificó como "importancia: alta" - lo que Juan pidió: que SOLO las noticias cripto clave (ETF,
SEC/regulación, Fed, hackeo grande, quiebra/fraude grande, movimiento de precio fuerte, adopción
institucional, país adoptando cripto, upgrade de red grande, empresa grande no-cripto con producto
cripto, ballena grande, figura política) lleguen al canal, no todo lo que sale en Noticias.

Lee de news_archive (ya poblada cada 30 min por update_news_archive.py, que ahora también guarda
"importancia") en vez de pedirle de nuevo al Worker - evita gastar cupo de Workers AI dos veces y
reusa el mismo historial que ya alimenta el buscador del sitio.

Filtro de monedas excluidas (pedido explícito de Juan): aunque una noticia salga "alta", si el
TÍTULO menciona XRP, Stellar (XLM), Hedera (HBAR) o Flare/Songbird (FLR/SGB), se descarta. Esto es
un filtro de palabras simple (no IA) a propósito - es una lista fija de nombres propios, mucho más
confiable que pedirle a un modelo que lo adivine, y Juan la puede ampliar en cualquier momento
solo pidiendo que se agregue un nombre a EXCLUDED_KEYWORDS.

"telegram_enviado" se marca en true tanto si la noticia se mandó de verdad como si se descartó por
el filtro de monedas excluidas - en los dos casos ya se "resolvió" esa fila y no hace falta
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

# Mismo chat que ya usa el boletín diario (post_crypto_bulletin_telegram.py) - sacado del link
# que compartió Juan ese día. El tema/hilo de "noticias" es OTRO, todavía no lo tenemos: Juan dijo
# "al canal que ya tenemos de noticias" pero ese thread_id nunca se guardó en el código (solo
# existe el de "Análisis Crypto", usado para el boletín). Falta que Juan pase el link del tema de
# noticias (t.me/juanskll/<numero>) para completar TELEGRAM_THREAD_ID - hasta entonces este script
# se niega a correr, a propósito, para no arriesgarse a mandar en el tema equivocado.
TELEGRAM_CHAT = "@juanskll"
TELEGRAM_THREAD_ID = None  # TODO Juan: reemplazar con el ID real del tema "noticias"

# Palabras que descartan una noticia aunque la IA la haya marcado "alta" (pedido explícito de
# Juan, 20-nov-2026: "excluir todo lo relacionado con xrp, xlm, hbar, Flare... cryptos ISO").
# \b = límite de palabra, para no hacer match a mitad de otra palabra.
EXCLUDED_KEYWORDS = ["xrp", "ripple", "xlm", "stellar", "hbar", "hedera", "flr", "sgb", "flare", "songbird"]
EXCLUDED_PATTERN = re.compile(r"\b(?:" + "|".join(EXCLUDED_KEYWORDS) + r")\b", re.IGNORECASE)

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
            "importancia": "eq.alta",
            "telegram_enviado": "eq.false",
            "select": "id,title,resumen,link,imagen",
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
    # corto a propósito (pedido de Juan: "que el texto no sea tan largo") - título + una frase +
    # link, nada de resumen_largo aquí
    titulo = (row.get("title") or "").strip()
    resumen = (row.get("resumen") or "").strip()
    link = row.get("link") or ""
    partes = [f"🚨 {titulo}"]
    if resumen:
        partes.append(resumen)
    partes.append(link)
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
        log.info("sin noticias nuevas de importancia alta - nada que mandar.")
        return

    enviadas, excluidas = 0, 0
    for row in pendientes:
        titulo = row.get("title") or ""
        if EXCLUDED_PATTERN.search(titulo):
            log.info(f"excluida por filtro de monedas (fila {row['id']}): {titulo[:80]}")
            marca_resuelta(row["id"])
            excluidas += 1
            continue
        try:
            send_to_telegram(build_caption(row), row.get("imagen"))
            marca_resuelta(row["id"])
            enviadas += 1
        except Exception as e:  # noqa: BLE001 - un fallo puntual de Telegram no debe tumbar el resto del lote
            log.warning(f"no se pudo mandar la fila {row['id']} ({titulo[:80]}): {e}")

    log.info(f"Listo. {enviadas} mandadas, {excluidas} excluidas por filtro de monedas, {len(pendientes)} revisadas.")


if __name__ == "__main__":
    main()
