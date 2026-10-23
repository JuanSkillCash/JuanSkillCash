"""
Postea una vez al dia una imagen (gauge/velocimetro) con el Indice de Miedo y Codicia del
momento, directo al tema "Analisis Crypto" del grupo de Telegram @juanskll (chat_id publico
"@juanskll", message_thread_id=8549 - sacado del link que compartio Juan,
https://t.me/juanskll/8549, que en un grupo con "Temas" activados apunta directo a ese tema).

Fuente del valor: la misma tabla que ya alimenta el widget del dashboard en vivo
(cmc_fng_latest, actualizada cada hora por scripts/update_cmc_fng_latest.py) - no se vuelve a
pedir nada a CoinMarketCap aqui, solo se lee lo que ya esta guardado.

La imagen se genera con Pillow (sin librerias externas de graficos) imitando la paleta del
sitio (fondo azul marino oscuro, dorado, verdes/rojos del semaforo clasico del indice).

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    TELEGRAM_BOT_TOKEN
"""

from __future__ import annotations

import io
import logging
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("post_fng_telegram")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

FNG_TABLE = "cmc_fng_latest"

# grupo publico @juanskll ("SkillCash Zona Libre"), tema "Analisis Crypto" - ver link de
# arriba. Si algun dia se crea o se borra un tema, este numero hay que volver a sacarlo con
# el mismo metodo (compartir/copiar el link del tema) y actualizarlo aca.
TELEGRAM_CHAT = "@juanskll"
TELEGRAM_THREAD_ID = 8549

CLASS_ES = {
    "Extreme Fear": "Miedo Extremo",
    "Fear": "Miedo",
    "Neutral": "Neutral",
    "Greed": "Codicia",
    "Extreme Greed": "Codicia Extrema",
}

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

INDICATOR_URL = "https://juanskillcash.com/indicadores/indice-de-miedo-y-codicia"
LOGO_PATH = Path(__file__).resolve().parent.parent / "logo-skillcash-600.png"

# ---- estilo del gauge (mismos tonos de index.html: --bg, --white, --muted; el acento es
# --red, el rojo de marca de SkillCash - no dorado, que casi no se usa en la marca) ----
SCALE = 3
W, H = 1000 * SCALE, 870 * SCALE
BG = (8, 12, 32, 255)
ACCENT = (255, 47, 79, 255)
WHITE = (247, 246, 251, 255)
MUTED = (132, 126, 147, 255)
SEG_COLORS = [
    (214, 40, 57, 255),    # miedo extremo
    (255, 138, 61, 255),   # miedo
    (240, 178, 61, 255),   # neutral
    (160, 214, 110, 255),  # codicia
    (46, 204, 113, 255),   # codicia extrema
]
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_latest_fng() -> dict:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{FNG_TABLE}",
        params={"id": "eq.1", "select": "value,value_classification,update_time"},
        headers=_sb_headers(), timeout=20,
    )
    if resp.status_code != 200 or not resp.json():
        raise RuntimeError(f"no se pudo leer {FNG_TABLE} ({resp.status_code}): {resp.text[:300]}")
    return resp.json()[0]


def _ctext(d, cx, y, text, font, fill, anchor="mm", align="center"):
    d.text((cx, y), text, font=font, fill=fill, anchor=anchor, align=align)


def make_gauge_image(value: int, classification_es: str, date_label: str) -> bytes:
    img = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(img)

    f_title = ImageFont.truetype(FONT_BOLD, 36 * SCALE)
    _ctext(d, W / 2, 54 * SCALE, "ÍNDICE DE MIEDO Y CODICIA", f_title, ACCENT)
    f_sub = ImageFont.truetype(FONT_REG, 19 * SCALE)
    _ctext(d, W / 2, 90 * SCALE, "SkillCash Tools · Alertas cripto", f_sub, MUTED)

    class_color = SEG_COLORS[min(4, value * 5 // 100)]

    f_num = ImageFont.truetype(FONT_BOLD, 106 * SCALE)
    _ctext(d, W / 2, 188 * SCALE, str(value), f_num, WHITE)
    f_class = ImageFont.truetype(FONT_BOLD, 30 * SCALE)
    _ctext(d, W / 2, 258 * SCALE, classification_es.upper(), f_class, class_color)

    cx, cy = W / 2, 528 * SCALE
    R = 200 * SCALE
    THICK = 36 * SCALE
    n_seg = len(SEG_COLORS)
    seg_span = 180 / n_seg
    bbox = [cx - R, cy - R, cx + R, cy + R]
    for i, color in enumerate(SEG_COLORS):
        start = 180 + i * seg_span
        d.arc(bbox, start=start, end=start + seg_span, fill=color, width=THICK)

    angle_deg = 180 - (value / 100) * 180
    angle_rad = math.radians(angle_deg)
    needle_len = R - THICK / 2 - 8 * SCALE
    nx = cx + needle_len * math.cos(angle_rad)
    ny = cy - needle_len * math.sin(angle_rad)
    d.line([(cx, cy), (nx, ny)], fill=WHITE, width=int(7 * SCALE))
    pr = 14 * SCALE
    d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=WHITE, outline=ACCENT, width=int(3 * SCALE))

    f_lbl = ImageFont.truetype(FONT_REG, 17 * SCALE)
    d.text((cx - R - 8 * SCALE, cy + 2 * SCALE), "0\nMiedo Extremo", font=f_lbl, fill=MUTED, anchor="rm", align="right")
    d.text((cx + R + 8 * SCALE, cy + 2 * SCALE), "100\nCodicia Extrema", font=f_lbl, fill=MUTED, anchor="lm", align="left")

    f_date = ImageFont.truetype(FONT_REG, 21 * SCALE)
    _ctext(d, W / 2, 660 * SCALE, date_label, f_date, MUTED)

    # logo real de SkillCash (el mismo que ya usa el sitio) en vez de solo el texto de la url
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_h = 80 * SCALE
        logo_w = int(logo.width * (logo_h / logo.height))
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        logo_top = 700 * SCALE
        img.alpha_composite(logo, (int(W / 2 - logo_w / 2), int(logo_top)))
        f_foot = ImageFont.truetype(FONT_BOLD, 18 * SCALE)
        _ctext(d, W / 2, logo_top + logo_h + 26 * SCALE, "juanskillcash.com", f_foot, ACCENT)
    except (FileNotFoundError, OSError) as e:
        log.warning(f"no se pudo cargar el logo ({LOGO_PATH}): {e} - se deja solo el texto")
        f_foot = ImageFont.truetype(FONT_REG, 17 * SCALE)
        _ctext(d, W / 2, 698 * SCALE, "juanskillcash.com", f_foot, ACCENT)

    img = img.resize((W // SCALE, H // SCALE), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def send_photo(image_bytes: bytes, caption: str) -> None:
    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
        data={
            "chat_id": TELEGRAM_CHAT,
            "message_thread_id": TELEGRAM_THREAD_ID,
            "caption": caption,
        },
        files={"photo": ("fear_and_greed.png", image_bytes, "image/png")},
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Telegram respondio {resp.status_code} mandando la foto: {resp.text[:500]}")


def main() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.")
        sys.exit(1)
    if not TELEGRAM_BOT_TOKEN:
        log.error("Falta TELEGRAM_BOT_TOKEN en el entorno.")
        sys.exit(1)

    entry = fetch_latest_fng()
    value = int(entry["value"])
    classification_en = entry.get("value_classification") or ""
    classification_es = CLASS_ES.get(classification_en, classification_en or "—")

    now = datetime.now(timezone.utc)
    date_label = f"Hoy, {now.day} de {MESES[now.month - 1]} de {now.year}"

    log.info(f"Generando imagen del indice ({value} - {classification_es})...")
    image_bytes = make_gauge_image(value, classification_es, date_label)

    caption = (
        f"📊 Índice de Miedo y Codicia — {date_label}\n\n"
        f"😨 Valor: {value} — {classification_es}\n\n"
        f"🦈 Consulta el histórico aquí: {INDICATOR_URL}"
    )
    send_photo(image_bytes, caption)
    log.info("Imagen publicada en el tema de Análisis Crypto.")


if __name__ == "__main__":
    main()
