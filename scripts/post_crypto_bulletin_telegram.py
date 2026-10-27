"""Boletin cripto diario UNICO (reemplaza a post_dominance_telegram.py + post_fng_telegram.py,
que posteaban dos imagenes separadas) - una sola imagen con dominancia BTC/USDT (en vivo, misma
fuente que el sitio: CoinGecko /api/v3/global) + el Indice de Miedo y Codicia (el mismo dato que
ya alimenta el widget del dashboard, leido de cmc_fng_latest), un solo link al final que va
directo a la pagina principal (juanskillcash.com, no a un indicador especifico) - pedido
explicito de Juan.

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
log = logging.getLogger("post_crypto_bulletin_telegram")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

TELEGRAM_CHAT = "@juanskll"
TELEGRAM_THREAD_ID = 8549

COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
COIN_IDS = {"BTC": "bitcoin", "USDT": "tether"}
FNG_TABLE = "cmc_fng_latest"

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

SCALE = 3
W, H = 1000 * SCALE, 1260 * SCALE
BG = (8, 12, 32, 255)
WHITE = (247, 246, 251, 255)
MUTED = (132, 126, 147, 255)
ACCENT = (255, 47, 79, 255)
BTC_COLOR = (247, 147, 26, 255)
USDT_COLOR = (38, 161, 123, 255)
SEG_COLORS = [
    (214, 40, 57, 255), (255, 138, 61, 255), (240, 178, 61, 255),
    (160, 214, 110, 255), (46, 204, 113, 255),
]
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
LOGO_PATH = Path(__file__).resolve().parent.parent / "logo-skillcash-600.png"


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_dominance() -> tuple[float, float]:
    resp = requests.get(COINGECKO_GLOBAL_URL, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"CoinGecko respondio {resp.status_code}: {resp.text[:300]}")
    pct = (resp.json().get("data") or {}).get("market_cap_percentage") or {}
    if "btc" not in pct or "usdt" not in pct:
        raise RuntimeError(f"CoinGecko no trajo btc/usdt en market_cap_percentage: {pct}")
    return float(pct["btc"]), float(pct["usdt"])


def fetch_coin_icons() -> dict[str, Image.Image]:
    icons: dict[str, Image.Image] = {}
    try:
        resp = requests.get(COINGECKO_MARKETS_URL, params={"vs_currency": "usd", "ids": "bitcoin,tether"}, timeout=20)
        if resp.status_code != 200:
            log.warning(f"CoinGecko markets respondio {resp.status_code}, se sigue sin iconos")
            return icons
        for item in resp.json():
            coin_id, image_url = item.get("id"), item.get("image")
            if not coin_id or not image_url:
                continue
            try:
                img_resp = requests.get(image_url, timeout=15)
                if img_resp.status_code == 200:
                    icons[coin_id] = Image.open(io.BytesIO(img_resp.content)).convert("RGBA")
            except (requests.RequestException, OSError) as e:
                log.warning(f"no se pudo descargar el icono de {coin_id}: {e}")
    except requests.RequestException as e:
        log.warning(f"no se pudieron traer los iconos de CoinGecko: {e}")
    return icons


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


def make_bulletin_image(btc_pct: float, usdt_pct: float, fng_value: int, fng_class_es: str,
                         date_label: str, icons: dict[str, Image.Image] | None = None) -> bytes:
    icons = icons or {}
    img = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(img)

    f_title = ImageFont.truetype(FONT_BOLD, 36 * SCALE)
    _ctext(d, W / 2, 54 * SCALE, "BOLETÍN CRIPTO DIARIO", f_title, WHITE)
    f_sub = ImageFont.truetype(FONT_REG, 19 * SCALE)
    _ctext(d, W / 2, 92 * SCALE, "SkillCash Tools · Alertas cripto", f_sub, MUTED)

    f_lbl_sec = ImageFont.truetype(FONT_BOLD, 21 * SCALE)
    _ctext(d, W / 2, 140 * SCALE, "DOMINANCIA DEL MERCADO", f_lbl_sec, MUTED)

    cards = [("BTC", COIN_IDS["BTC"], btc_pct, BTC_COLOR), ("USDT", COIN_IDS["USDT"], usdt_pct, USDT_COLOR)]
    card_w, card_h = 380 * SCALE, 290 * SCALE
    gap = 40 * SCALE
    total_w = card_w * 2 + gap
    x0 = (W - total_w) / 2
    y0 = 170 * SCALE
    for name, coin_id, pct, color in cards:
        x = x0
        d.rounded_rectangle([x, y0, x + card_w, y0 + card_h], radius=24 * SCALE, fill=BG, outline=color, width=int(4 * SCALE))
        icon = icons.get(coin_id)
        if icon is not None:
            icon_size = 66 * SCALE
            icon_sq = icon.resize((icon_size, icon_size), Image.LANCZOS)
            img.alpha_composite(icon_sq, (int(x + card_w / 2 - icon_size / 2), int(y0 + 24 * SCALE)))
        else:
            f_name = ImageFont.truetype(FONT_BOLD, 30 * SCALE)
            _ctext(d, x + card_w / 2, y0 + 56 * SCALE, name, f_name, color)
        f_pct = ImageFont.truetype(FONT_BOLD, 76 * SCALE)
        _ctext(d, x + card_w / 2, y0 + 172 * SCALE, f"{pct:.1f}%", f_pct, WHITE)
        f_lbl = ImageFont.truetype(FONT_REG, 22 * SCALE)
        _ctext(d, x + card_w / 2, y0 + 240 * SCALE, "del mercado total", f_lbl, MUTED)
        x0 += card_w + gap

    gauge_top = y0 + card_h + 56 * SCALE
    _ctext(d, W / 2, gauge_top, "ÍNDICE DE MIEDO Y CODICIA", f_lbl_sec, MUTED)

    class_color = SEG_COLORS[min(4, fng_value * 5 // 100)]
    f_num = ImageFont.truetype(FONT_BOLD, 96 * SCALE)
    _ctext(d, W / 2, gauge_top + 108 * SCALE, str(fng_value), f_num, WHITE)
    f_class = ImageFont.truetype(FONT_BOLD, 28 * SCALE)
    _ctext(d, W / 2, gauge_top + 172 * SCALE, fng_class_es.upper(), f_class, class_color)

    cx = W / 2
    cy = gauge_top + 432 * SCALE
    R = 200 * SCALE
    THICK = 36 * SCALE
    n_seg = len(SEG_COLORS)
    seg_span = 180 / n_seg
    bbox = [cx - R, cy - R, cx + R, cy + R]
    for i, color in enumerate(SEG_COLORS):
        start = 180 + i * seg_span
        d.arc(bbox, start=start, end=start + seg_span, fill=color, width=THICK)

    angle_deg = 180 - (fng_value / 100) * 180
    angle_rad = math.radians(angle_deg)
    needle_len = R - THICK / 2 - 8 * SCALE
    nx = cx + needle_len * math.cos(angle_rad)
    ny = cy - needle_len * math.sin(angle_rad)
    d.line([(cx, cy), (nx, ny)], fill=WHITE, width=int(7 * SCALE))
    pr = 14 * SCALE
    d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=WHITE, outline=ACCENT, width=int(3 * SCALE))

    f_glbl = ImageFont.truetype(FONT_REG, 17 * SCALE)
    d.text((cx - R - 8 * SCALE, cy + 2 * SCALE), "0\nMiedo Extremo", font=f_glbl, fill=MUTED, anchor="rm", align="right")
    d.text((cx + R + 8 * SCALE, cy + 2 * SCALE), "100\nCodicia Extrema", font=f_glbl, fill=MUTED, anchor="lm", align="left")

    f_date = ImageFont.truetype(FONT_REG, 21 * SCALE)
    _ctext(d, W / 2, cy + 56 * SCALE, date_label, f_date, MUTED)

    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_h = 80 * SCALE
        logo_w = int(logo.width * (logo_h / logo.height))
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        logo_top = cy + 90 * SCALE
        img.alpha_composite(logo, (int(W / 2 - logo_w / 2), int(logo_top)))
        f_foot = ImageFont.truetype(FONT_BOLD, 19 * SCALE)
        _ctext(d, W / 2, logo_top + logo_h + 28 * SCALE, "juanskillcash.com", f_foot, WHITE)
    except (FileNotFoundError, OSError) as e:
        log.warning(f"no se pudo cargar el logo ({LOGO_PATH}): {e} - se deja solo el texto")
        f_foot = ImageFont.truetype(FONT_REG, 18 * SCALE)
        _ctext(d, W / 2, cy + 120 * SCALE, "juanskillcash.com", f_foot, WHITE)

    img = img.resize((W // SCALE, H // SCALE), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def send_photo(image_bytes: bytes, caption: str) -> None:
    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
        data={"chat_id": TELEGRAM_CHAT, "message_thread_id": TELEGRAM_THREAD_ID, "caption": caption},
        files={"photo": ("boletin.png", image_bytes, "image/png")},
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

    btc_pct, usdt_pct = fetch_dominance()
    icons = fetch_coin_icons()

    entry = fetch_latest_fng()
    fng_value = int(entry["value"])
    fng_class_en = entry.get("value_classification") or ""
    fng_class_es = CLASS_ES.get(fng_class_en, fng_class_en or "—")

    now = datetime.now(timezone.utc)
    date_label = f"Hoy, {now.day} de {MESES[now.month - 1]} de {now.year}"

    log.info(f"Generando boletin (BTC {btc_pct:.1f}% / USDT {usdt_pct:.1f}% / F&G {fng_value} {fng_class_es})...")
    image_bytes = make_bulletin_image(btc_pct, usdt_pct, fng_value, fng_class_es, date_label, icons)

    caption = (
        f"📊 Boletín cripto diario — {date_label}\n\n"
        f"Bitcoin: {btc_pct:.1f}% · USDT: {usdt_pct:.1f}% del mercado\n"
        f"Miedo y Codicia: {fng_value} — {fng_class_es}\n\n"
        f"🦈 Entérate de más en juanskillcash.com"
    )
    send_photo(image_bytes, caption)
    log.info("Boletin publicado en el tema de Análisis Crypto.")


if __name__ == "__main__":
    main()
