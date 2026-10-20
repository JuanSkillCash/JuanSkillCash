"""Diagnostico unico: inspecciona https://announcements.bybit.com/en/?category=...&page=N
(confirmado por el usuario como la URL real de anuncios, __NEXT_DATA__ igual que otras
paginas Next.js ya soportadas) para encontrar el valor de categoria correcto para "nuevos
listados" y la forma exacta del JSON embebido. No se corre en produccion."""

import json
import logging
import re

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("debug_bybit_structure2")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

# candidatos de categoria: "new_crypto" era el "type" de la API vieja (api.bybit.com),
# probamos variantes razonables de slug para la web nueva
CANDIDATES = [
    "https://announcements.bybit.com/en/",
    "https://announcements.bybit.com/en/?category=new_crypto",
    "https://announcements.bybit.com/en/?category=new_crypto&page=1",
    "https://announcements.bybit.com/en/?category=latest_bybit_news",
]


def dump(url: str):
    log.info(f"=== {url} ===")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    log.info(f"status={resp.status_code} largo={len(resp.text)}")
    m = _NEXT_DATA_RE.search(resp.text)
    if not m:
        log.info("NO tiene __NEXT_DATA__")
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        log.info(f"__NEXT_DATA__ invalido: {e}")
        return None
    log.info(f"claves top-level: {list(data.keys())}")
    props = data.get("props", {})
    page_props = props.get("pageProps", {})
    log.info(f"claves de pageProps: {list(page_props.keys())}")
    # dump completo pero acotado (no queremos un log gigante)
    dumped = json.dumps(page_props, ensure_ascii=False)
    log.info(f"pageProps (primeros 6000 chars): {dumped[:6000]}")
    return data


def main():
    for url in CANDIDATES:
        try:
            dump(url)
        except Exception as e:
            log.info(f"EXCEPCION en {url}: {e}")
        log.info("")


if __name__ == "__main__":
    main()
