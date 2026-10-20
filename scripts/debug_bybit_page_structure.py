"""Diagnostico unico: inspecciona la estructura real de las paginas publicas de Bybit que
SI respondieron 200 (confirmado en debug_bybit_gate_access.py) para ver si los anuncios
vienen embebidos en el HTML inicial (patron Nuxt __NUXT__) o si hay que llamar a una API
aparte. No se corre en produccion."""

import logging
import re

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("debug_bybit_structure")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

URLS = [
    "https://www.bybit.com/en/announcement-info/new-crypto/",
    "https://www.bybit.com/en/help-center/article/new-crypto-listing",
]


def main():
    for url in URLS:
        log.info(f"=== {url} ===")
        resp = requests.get(url, headers=HEADERS, timeout=20)
        html = resp.text
        log.info(f"status={resp.status_code} largo={len(html)}")

        has_nuxt = "__NUXT__" in html
        log.info(f"tiene __NUXT__? {has_nuxt}")
        if has_nuxt:
            idx = html.find("__NUXT__")
            log.info(f"contexto alrededor de __NUXT__: {html[idx-50:idx+2000]!r}")

        has_next_data = "__NEXT_DATA__" in html
        log.info(f"tiene __NEXT_DATA__? {has_next_data}")

        # buscar cualquier URL de API embebida en el HTML/JS (fetch/axios a un dominio
        # distinto o un path que suene a API)
        api_hints = re.findall(r'["\'](/[a-zA-Z0-9_\-/]*(?:api|announcement|listing|notice)[a-zA-Z0-9_\-/]*)["\']', html, re.IGNORECASE)
        api_hints = sorted(set(api_hints))[:40]
        log.info(f"posibles rutas de API encontradas en el HTML ({len(api_hints)}): {api_hints}")

        # buscar ids de <script> por si hay otro patron de embebido (ej __INITIAL_STATE__)
        ids = re.findall(r'<script[^>]*\bid="([^"]+)"', html)
        log.info(f"ids de <script> encontrados: {ids}")

        # buscar cualquier variable global tipo window.XXX = {...}
        globals_found = re.findall(r'window\.(\w+)\s*=', html)
        log.info(f"variables window.X encontradas: {sorted(set(globals_found))}")

        log.info(f"primeros 2000 chars del body (despues del head): {html[html.find('<body'):html.find('<body')+2000]!r}")
        log.info("")


if __name__ == "__main__":
    main()
