"""
Diagnostico unico (no se corre en produccion) para investigar si Bybit y Gate se pueden
destrabar desde el runner de GitHub Actions - no hay forma de probar esto desde el sandbox
de desarrollo (sin acceso a internet real), asi que se corre directo via workflow_dispatch
y se lee el log.

Bybit: la API oficial (api.bybit.com/v5/announcements/index) da 403 "Amazon CloudFront
distribution is configured to block access from your country" - bloqueo geografico a nivel
de borde, no un challenge de bot. Se prueban URLs alternativas (paginas publicas de
anuncios, no la API de trading) a ver si tienen una configuracion de CloudFront distinta.

Gate: la pagina de nuevos listados (Next.js) nunca trae <script id="__NEXT_DATA__"> via
Playwright con domcontentloaded+networkidle-aparte, pero delistings/gate.py SI lo logra con
page.goto(url, wait_until="networkidle") de una sola vez. Se prueba esa forma exacta sobre
la URL de nuevos listados para confirmar si el problema era el wait_until en dos pasos.
"""

import logging
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("debug_access")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

BYBIT_URLS = [
    ("api.bybit.com v5 announcements (ya conocido)", "https://api.bybit.com/v5/announcements/index?locale=en-US&type=new_crypto&limit=5"),
    ("bybit.com help-center new-crypto (pagina publica)", "https://www.bybit.com/en/help-center/article/new-crypto-listing"),
    ("bybit.com announcement-info new-crypto", "https://www.bybit.com/en/announcement-info/new-crypto/"),
    ("announcements.bybit.com", "https://announcements.bybit.com/en/"),
    ("bybit.com (home, control)", "https://www.bybit.com/en/"),
]


def check_requests(label: str, url: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        body_snippet = resp.text[:300].replace("\n", " ")
        log.info(f"[requests] {label}: {resp.status_code} -- {body_snippet!r}")
    except requests.RequestException as e:
        log.info(f"[requests] {label}: EXCEPCION {e}")


def check_playwright(label: str, url: str, wait_until: str = "networkidle", timeout_ms: int = 45000):
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            try:
                resp = page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                status = resp.status if resp else None
                title = page.title()
                html = page.content()
                log.info(
                    f"[playwright] {label}: status={status} titulo={title!r} "
                    f"largo_html={len(html)} snippet={html[:300]!r}"
                )
                return html
            finally:
                browser.close()
    except Exception as e:
        log.info(f"[playwright] {label}: EXCEPCION {e}")
        return None


def main():
    log.info("=== BYBIT: requests ===")
    for label, url in BYBIT_URLS:
        check_requests(label, url)
        time.sleep(0.5)

    log.info("=== BYBIT: playwright (por si el bloqueo fuera solo para requests, no navegador real) ===")
    for label, url in BYBIT_URLS:
        check_playwright(label, url)
        time.sleep(0.5)

    log.info("=== GATE: playwright goto(wait_until=networkidle) en una sola llamada, igual que delistings/gate.py ===")
    html = check_playwright(
        "gate.com newlisted (metodo probado de delistings/gate.py)",
        "https://www.gate.com/announcements/newlisted?page=1",
        wait_until="networkidle",
        timeout_ms=45000,
    )
    if html:
        has_next_data = '__NEXT_DATA__' in html
        log.info(f"[gate] tiene __NEXT_DATA__? {has_next_data}")

    log.info("=== GATE: control - delistados (deberia funcionar, para comparar) ===")
    html2 = check_playwright(
        "gate.com delisted (control, deberia funcionar)",
        "https://www.gate.com/announcements/delisted",
        wait_until="networkidle",
        timeout_ms=45000,
    )
    if html2:
        log.info(f"[gate control] tiene __NEXT_DATA__? {'__NEXT_DATA__' in html2}")


if __name__ == "__main__":
    main()
