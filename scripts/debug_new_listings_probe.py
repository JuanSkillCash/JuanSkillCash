"""Diagnostico manual (no toca Supabase), ronda 2: ya confirmamos (ronda 1) las categorias
reales de "Nuevos Listados" para OKX, Bitget, KuCoin y Binance, y el section_id de Bitunix.
Esta ronda saca mas muestra de titulos reales (para disenar el parser y la clasificacion de
asset_class) y resuelve lo que falto: seccion de Bitunix en detalle, cual de las 3 secciones
de BingX usar, el slug real de MEXC (via Playwright, igual que el scraper de deslistados) y
las URLs candidatas de Kraken para "nuevos listados"."""

from __future__ import annotations

import logging
import os
import sys
import time

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))  # para que "delistings" se importe como paquete
from delistings.common import DEFAULT_HEADERS
from delistings import zendesk


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("probe2")


def _get_json(url, params=None, label=""):
    try:
        resp = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=30)
        log.info(f"  -> {resp.status_code} {resp.url}")
        if resp.status_code != 200:
            log.info(f"     body (primeros 300): {resp.text[:300]!r}")
            return None
        return resp.json()
    except Exception as e:
        log.info(f"  -> EXCEPCION {label}: {e}")
        return None


def probe_bitunix_new_listings():
    log.info("\n=== Bitunix: seccion 'New Listings' (13762039477017) ===")
    arts = zendesk.fetch_section_articles(
        "https://support.bitunix.com", "13762039477017", "en-us", max_pages=1,
    )
    log.info(f"  {len(arts)} articulos")
    for a in arts[:25]:
        log.info(f"    - {a.get('title')!r}")


def probe_bingx_listing_sections():
    for sid, name in [
        ("11257060005007", "Spot Listing"),
        ("11257015822991", "Futures Listing"),
        ("13117025062927", "Innovation Listing"),
    ]:
        log.info(f"\n=== BingX: seccion '{name}' ({sid}) ===")
        arts = zendesk.fetch_section_articles("https://bingxservice.zendesk.com", sid, "en-001", max_pages=1)
        log.info(f"  {len(arts)} articulos")
        for a in arts[:15]:
            log.info(f"    - {a.get('title')!r}")
        time.sleep(1)


def probe_okx_more():
    log.info("\n=== OKX: mas muestra de announcements-new-listings (pagina 2) ===")
    data = _get_json(
        "https://www.okx.com/api/v5/support/announcements",
        {"annType": "announcements-new-listings", "page": 2}, "okx-p2",
    )
    if data and data.get("code") == "0":
        details = (data.get("data") or [{}])[0].get("details", [])
        for d in details[:20]:
            log.info(f"    - {d.get('title')!r}  url={d.get('url')}")


def probe_bitget_more():
    log.info("\n=== Bitget: mas muestra de coin_listings (cursor) ===")
    cursor = None
    seen = 0
    for _ in range(4):
        params = {"language": "en_US", "annType": "coin_listings", "limit": 15}
        if cursor:
            params["cursor"] = cursor
        data = _get_json("https://api.bitget.com/api/v2/public/annoucements", params, "bitget-more")
        if not data or data.get("code") != "00000":
            break
        items = data.get("data") or []
        if not items:
            break
        for it in items:
            log.info(f"    - {it.get('annTitle')!r}")
            seen += 1
        cursor = str(items[-1].get("annId", "")) if len(items) == 15 else None
        if not cursor:
            break
        time.sleep(1)
    log.info(f"  total visto: {seen}")


def probe_kucoin_more():
    log.info("\n=== KuCoin: mas muestra de new-listings (pagina 2) ===")
    data = _get_json(
        "https://api.kucoin.com/api/v3/announcements",
        {"annType": "new-listings", "lang": "en_US", "pageSize": 20, "currentPage": 2}, "kucoin-p2",
    )
    if data:
        items = (data.get("data") or {}).get("items", [])
        for it in items:
            log.info(f"    - {it.get('annTitle')!r} (annType real={it.get('annType')})")


def probe_binance_more():
    log.info("\n=== Binance: mas muestra de catalogId=48 (pagina 2) ===")
    data = _get_json(
        "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query",
        {"type": 1, "catalogId": 48, "pageNo": 2, "pageSize": 20}, "binance-p2",
    )
    if data:
        catalogs = (data.get("data") or {}).get("catalogs") or []
        if catalogs:
            for a in (catalogs[0].get("articles") or []):
                log.info(f"    - {a.get('title')!r}  code={a.get('code')}  releaseDate={a.get('releaseDate')}")


def probe_mexc_playwright():
    log.info("\n=== MEXC: navegar /announcements con Playwright para ver categorias reales ===")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.info("  playwright no instalado en esta corrida")
        return
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"])
        try:
            page.goto("https://www.mexc.com/announcements", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            html = page.content()
        except Exception as e:
            log.info(f"  fallo cargando /announcements: {e}")
            browser.close()
            return
        soup = BeautifulSoup(html, "html.parser")
        hrefs = sorted(set(
            a.get("href") for a in soup.select('a[href*="/announcements/"]') if a.get("href")
        ))
        log.info(f"  {len(hrefs)} hrefs unicos bajo /announcements/:")
        for h in hrefs[:60]:
            log.info(f"    {h}")

        # si hay un link que suene a "new listing", entrar y confirmar que carga con articulos reales
        candidate = next((h for h in hrefs if "listing" in h.lower() or "new-coin" in h.lower()
                           or "new_coin" in h.lower()), None)
        if candidate:
            url = candidate if candidate.startswith("http") else "https://www.mexc.com" + candidate
            log.info(f"  probando candidato: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_selector('a[href*="/announcements/article/"]', timeout=15000)
                soup2 = BeautifulSoup(page.content(), "html.parser")
                links = soup2.select('a[href*="/announcements/article/"]')
                log.info(f"  {len(links)} articulos encontrados en {url}")
                for a in links[:15]:
                    log.info(f"    - {a.get_text(strip=True)!r}")
            except Exception as e:
                log.info(f"  fallo confirmando candidato: {e}")
        browser.close()


def probe_kraken_candidates():
    log.info("\n=== Kraken: URLs candidatas para 'nuevos listados' ===")
    candidates = [
        "https://support.kraken.com/en/sections/new-listings",
        "https://support.kraken.com/en/sections/new-asset-listings",
        "https://support.kraken.com/en/sections/asset-listings",
        "https://support.kraken.com/hc/en-us/sections/new-listings",
        "https://support.kraken.com/en/sections/delistings",  # control: sabemos que esta SI existe
    ]
    for url in candidates:
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
            log.info(f"  {url} -> {resp.status_code} (len={len(resp.text)})")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.select('a[href*="/articles/"]')
                log.info(f"    {len(links)} links de articulo")
                for a in links[:10]:
                    log.info(f"      - {a.get_text(strip=True)!r}")
        except Exception as e:
            log.info(f"  {url} -> EXCEPCION {e}")
        time.sleep(0.5)


if __name__ == "__main__":
    probe_bitunix_new_listings()
    probe_bingx_listing_sections()
    probe_okx_more()
    probe_bitget_more()
    probe_kucoin_more()
    probe_binance_more()
    probe_mexc_playwright()
    probe_kraken_candidates()
