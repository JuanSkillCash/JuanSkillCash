"""
Genera las variantes de color (skins) del tiburon de Colmillos a partir de
assets/mascot/source/base_original.png, rotando el matiz (hue) en espacio HSL y
dejando intactos los pixeles casi sin saturacion (blancos/negros/contornos) para que
no se tiñan - asi la pose queda pixel por pixel identica entre variantes, solo cambia
el color. No usa IA: es 100% determinista.

Uso: python3 scripts/mascot_recolor.py
"""

import colorsys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets/mascot/source/base_original.png"
OUT_DIR = ROOT / "assets/mascot/variants"

# hue en grados (0-360). gold y red calculados de las variables --gold/--red del sitio
# para que combinen con la marca; el resto son 10 tonos repartidos por toda la rueda de
# color para que la tienda tenga variedad real.
VARIANTS = {
    "skin_gold": 39,
    "skin_red": 351,
    "skin_abyss": 265,
    "skin_emerald": 150,
    "skin_cyan": 188,
    "skin_pink": 325,
    "skin_orange": 25,
    "skin_ice": 205,
    "skin_lime": 95,
    "skin_violet": 290,
}

NEUTRAL_SATURATION_THRESHOLD = 0.12
# la base tiene saturacion baja (azul apagado) - se sube para que el dorado/rojo/morado
# se vean vivos en vez de quedar como tonos tierra lavados
SATURATION_BOOST = 1.6


def recolor(img: Image.Image, hue_deg: float, saturation_boost: float = SATURATION_BOOST) -> Image.Image:
    target_hue = (hue_deg % 360) / 360.0
    img = img.convert("RGBA")
    out = img.copy()
    px_in = img.load()
    px_out = out.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px_in[x, y]
            if a == 0:
                continue
            h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            if s < NEUTRAL_SATURATION_THRESHOLD:
                continue
            new_s = min(1.0, s * saturation_boost)
            nr, ng, nb = colorsys.hls_to_rgb(target_hue, l, new_s)
            px_out[x, y] = (round(nr * 255), round(ng * 255), round(nb * 255), a)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = Image.open(SOURCE)
    base_alpha = base.convert("RGBA").split()[-1]
    for name, hue in VARIANTS.items():
        variant = recolor(base, hue)
        # la pose (canal alfa) debe quedar identica pixel por pixel a la base
        assert list(variant.split()[-1].getdata()) == list(base_alpha.getdata()), (
            f"{name}: el canal alfa no coincide con la base - la pose cambio"
        )
        out_path = OUT_DIR / f"shark_{name}.png"
        variant.save(out_path)
        print(f"{name}: guardado en {out_path}")


if __name__ == "__main__":
    main()
