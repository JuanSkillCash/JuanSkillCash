"""
Postea cada mañana (7:00 hora Colombia / 12:00 UTC) una imagen con la dominancia de BTC y
USDT en el mercado cripto, directo al tema "Analisis Crypto" del grupo de Telegram @juanskll
(mismo chat_id/message_thread_id que ya usa post_fng_telegram.py).

A diferencia de cryptocap_history (que solo trae la vela YA CERRADA de TradingView, una vez
al dia a las 00:30 UTC), aca se pide el valor EN VIVO a la API publica de CoinGecko
(/api/v3/global, sin llave) - la misma fuente que ya usa el sitio para el numero "ahora mismo"
(ver fetchGlobalDominancePct en index.html) - para que el dato de las 7am sea el real de ese
momento, no el cierre de la medianoche anterior.

Variables de entorno requeridas:
    TELEGRAM_BOT_TOKEN
"""

from __future__ import annotations

import io
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("post_dominance_telegram")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

TELEGRAM_CHAT = "@juanskll"
TELEGRAM_THREAD_ID = 8549

COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
# id de CoinGecko -> que tarjeta es (mismo orden/colores que CARDS en make_dominance_image)
COIN_IDS = {"BTC": "bitcoin", "USDT": "tether"}

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

SCALE = 3
W, H = 1000 * SCALE, 860 * SCALE
BG = (8, 12, 32, 255)
ACCENT = (255, 47, 79, 255)  # rojo de marca de SkillCash (--red en index.html) - no dorado
WHITE = (247, 246, 251, 255)
MUTED = (132, 126, 147, 255)
BTC_COLOR = (247, 147, 26, 255)
USDT_COLOR = (38, 161, 123, 255)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
LOGO_PATH = Path(__file__).resolve().parent.parent / "logo-skillcash-600.png"


def fetch_dominance() -> tuple[float, float]:
    resp = requests.get(COINGECKO_GLOBAL_URL, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"CoinGecko respondio {resp.status_code}: {resp.text[:300]}")
    pct = (resp.json().get("data") or {}).get("market_cap_percentage") or {}
    if "btc" not in pct or "usdt" not in pct:
        raise RuntimeError(f"CoinGecko no trajo btc/usdt en market_cap_percentage: {pct}")
    return float(pct["btc"]), float(pct["usdt"])


def fetch_coin_icons() -> dict[str, Image.Image]:
    """Trae los logos reales de BTC/USDT desde CoinGecko (mismo CDN que ya usa el sitio para
    los iconos del portafolio). Si algo falla (red, formato raro), devuelve lo que sí se pudo
    descargar - make_dominance_image cae de vuelta al nombre en texto para la moneda que falte,
    nunca rompe la imagen completa por un icono."""
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


def _ctext(d, cx, y, text, font, fill, anchor="mm", align="center"):
    d.text((cx, y), text, font=font, fill=fill, anchor=anchor, align=align)


def make_dominance_image(btc_pct: float, usdt_pct: float, date_label: str, icons: dict[str, Image.Image] | None = None) -> bytes:
    img = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(img)
    icons = icons or {}

    f_title = ImageFont.truetype(FONT_BOLD, 34 * SCALE)
    _ctext(d, W / 2, 54 * SCALE, "DOMINANCIA DEL MERCADO CRIPTO", f_title, ACCENT)
    f_sub = ImageFont.truetype(FONT_REG, 19 * SCALE)
    _ctext(d, W / 2, 90 * SCALE, "SkillCash Tools · Alertas cripto", f_sub, MUTED)

    cards = [("BTC", COIN_IDS["BTC"], btc_pct, BTC_COLOR), ("USDT", COIN_IDS["USDT"], usdt_pct, USDT_COLOR)]
    card_w, card_h = 380 * SCALE, 320 * SCALE
    gap = 40 * SCALE
    total_w = card_w * 2 + gap
    x0 = (W - total_w) / 2
    y0 = 200 * SCALE
    for name, coin_id, pct, color in cards:
        x = x0
        # mismo fondo exacto que el resto de la imagen - solo el borde lleva el color de la
        # moneda, para que no se note un "cuadro azul" distinto detras
        d.rounded_rectangle([x, y0, x + card_w, y0 + card_h], radius=24 * SCALE, fill=BG, outline=color, width=int(4 * SCALE))

        icon = icons.get(coin_id)
        if icon is not None:
            icon_size = 78 * SCALE
            icon_sq = icon.resize((icon_size, icon_size), Image.LANCZOS)
            img.alpha_composite(icon_sq, (int(x + card_w / 2 - icon_size / 2), int(y0 + 28 * SCALE)))
        else:
            f_name = ImageFont.truetype(FONT_BOLD, 32 * SCALE)
            _ctext(d, x + card_w / 2, y0 + 66 * SCALE, name, f_name, color)

        f_pct = ImageFont.truetype(FONT_BOLD, 80 * SCALE)
        _ctext(d, x + card_w / 2, y0 + 205 * SCALE, f"{pct:.1f}%", f_pct, WHITE)
        f_lbl = ImageFont.truetype(FONT_REG, 23 * SCALE)
        _ctext(d, x + card_w / 2, y0 + 278 * SCALE, "del mercado total", f_lbl, MUTED)
        x0 += card_w + gap

    f_date = ImageFont.truetype(FONT_REG, 21 * SCALE)
    _ctext(d, W / 2, y0 + card_h + 60 * SCALE, date_label, f_date, MUTED)

    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_h = 80 * SCALE
        logo_w = int(logo.width * (logo_h / logo.height))
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        logo_top = y0 + card_h + 98 * SCALE
        img.alpha_composite(logo, (int(W / 2 - logo_w / 2), int(logo_top)))
        f_foot = ImageFont.truetype(FONT_BOLD, 18 * SCALE)
        _ctext(d, W / 2, logo_top + logo_h + 26 * SCALE, "juanskillcash.com", f_foot, ACCENT)
    except (FileNotFoundError, OSError) as e:
        log.warning(f"no se pudo cargar el logo ({LOGO_PATH}): {e} - se deja solo el texto")
        f_foot = ImageFont.truetype(FONT_REG, 17 * SCALE)
        _ctext(d, W / 2, y0 + card_h + 110 * SCALE, "juanskillcash.com", f_foot, ACCENT)

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
        files={"photo": ("dominancia.png", image_bytes, "image/png")},
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Telegram respondio {resp.status_code} mandando la foto: {resp.text[:500]}")


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        log.error("Falta TELEGRAM_BOT_TOKEN en el entorno.")
        sys.exit(1)

    btc_pct, usdt_pct = fetch_dominance()
    now = datetime.now(timezone.utc)
    date_label = f"Hoy, {now.day} de {MESES[now.month - 1]} de {now.year}"

    icons = fetch_coin_icons()

    log.info(f"Generando imagen de dominancia (BTC {btc_pct:.1f}% / USDT {usdt_pct:.1f}%)...")
    image_bytes = make_dominance_image(btc_pct, usdt_pct, date_label, icons)

    caption = (
        f"📊 Dominancia del mercado cripto — {date_label}\n\n"
        f"Bitcoin: {btc_pct:.1f}%\n"
        f"USDT: {usdt_pct:.1f}%\n\n"
        f"🦈 Entérate de más en juanskillcash.com"
    )
    send_photo(image_bytes, caption)
    log.info("Imagen publicada en el tema de Análisis Crypto.")


if __name__ == "__main__":
    main()
