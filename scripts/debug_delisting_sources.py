"""Diagnostico de una sola corrida (GitHub Actions) para encontrar la fuente real de
deslistados en los 5 exchanges que hoy solo tienen scraper de nuevos listados: LBank,
Pionex, CoinW, Weex y Blofin. No escribe nada a Supabase - solo imprime en los logs lo
que hace falta para escribir el scraper real de cada uno."""

from __future__ import annotations

import json
import re
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, "scripts")
from newlistings.common import DEFAULT_HEADERS, fetch_html_with_fallback  # noqa: E402


def banner(title: str):
    print(f"\n{'=' * 10} {title} {'=' * 10}")


def debug_lbank():
    banner("LBank")
    url = "https://www.lbank.com/lbk-api/huamao-media-center/notice/category/noticeList"
    # CO00000053 es la categoria "madre" (mezcla todo, segun el comentario existente en
    # newlistings/lbank.py) - si los deslistados viven ahi, deberian aparecer con el patron
    # "Will Delist"/"Delisting"/"Removal" en el titulo.
    for code in ("CO00000053",):
        body = {"categoryCode": code, "pageNo": 1, "pageSize": 30}
        resp = requests.post(url, json=body, headers=DEFAULT_HEADERS, timeout=30)
        print(f"[lbank] categoria {code}: status {resp.status_code}")
        if resp.status_code != 200:
            print(resp.text[:500])
            continue
        payload = resp.json()
        items = ((payload.get("data") or {}).get("resultList")) or []
        print(f"[lbank] {len(items)} items en pagina 1")
        for it in items[:30]:
            print(f"  - {it.get('title')!r}")

    # intento de descubrir la lista completa de categorias (nombre de endpoint adivinado
    # por convencion con noticeList)
    for guess in ("category/list", "category/categoryList", "category/all"):
        guess_url = f"https://www.lbank.com/lbk-api/huamao-media-center/notice/{guess}"
        try:
            r = requests.get(guess_url, headers=DEFAULT_HEADERS, timeout=15)
            print(f"[lbank] GET {guess_url} -> {r.status_code} {r.text[:200]!r}")
        except requests.RequestException as e:
            print(f"[lbank] GET {guess_url} fallo: {e}")


def debug_pionex():
    banner("Pionex")
    url = "https://intercom.help/pionex/en/collections/19449941-new-listings"
    html, method = fetch_html_with_fallback(url, validate=lambda h: "/en/articles/" in h, wait_selector='a[href*="/en/articles/"]')
    print(f"[pionex] metodo usado: {method}, len html: {len(html)}")
    soup = BeautifulSoup(html, "html.parser")
    links = soup.select('a[href*="/en/articles/"]')
    noise_re = re.compile(r"Will Delist|Notice of Removal of (?:Spot )?Trading Pairs", re.IGNORECASE)
    delist_titles = [a.get_text(strip=True) for a in links if noise_re.search(a.get_text(strip=True) or "")]
    print(f"[pionex] {len(delist_titles)} titulos de deslistado en esta coleccion (de {len(links)} totales)")
    for t in delist_titles[:15]:
        print(f"  - {t!r}")
    if delist_titles:
        # probar a abrir el primer articulo para ver si el cuerpo trae fecha de deslistado
        first = next(a for a in links if noise_re.search(a.get_text(strip=True) or ""))
        href = first.get("href", "")
        art_url = href if href.startswith("http") else "https://intercom.help" + href
        art_html, art_method = fetch_html_with_fallback(art_url)
        print(f"[pionex] articulo de prueba {art_url} (metodo {art_method}), {len(art_html)} chars")
        art_soup = BeautifulSoup(art_html, "html.parser")
        body_text = art_soup.get_text(" ", strip=True)
        print(f"[pionex] primeros 500 chars del cuerpo: {body_text[:500]!r}")


def debug_coinw():
    banner("CoinW")
    root = "https://www.coinw.com/help-center/announcement-center"
    html, method = fetch_html_with_fallback(root, validate=lambda h: "announcement-center" in h)
    print(f"[coinw] metodo usado: {method}, len html: {len(html)}")
    soup = BeautifulSoup(html, "html.parser")
    links = sorted({a.get("href", "") for a in soup.select('a[href*="announcement-center"]')})
    print(f"[coinw] {len(links)} links unicos bajo announcement-center")
    for l in links[:40]:
        print(f"  - {l}")


def debug_weex():
    banner("Weex")
    # 1) HTML de un articulo real de deslistado conocido - buscar el link "de vuelta a la
    #    seccion" (breadcrumb) para sacar el section id.
    art_url = "https://www.weex.com/help/articles/a2ps5uth3igcomm5g939vd9u"
    html, method = fetch_html_with_fallback(art_url)
    print(f"[weex] articulo {art_url} (metodo {method}), {len(html)} chars")
    section_ids = sorted(set(re.findall(r"/help/sections/(\d+)", html)))
    print(f"[weex] section ids encontrados en el articulo: {section_ids}")

    # 2) pagina raiz de help center - listar todas las secciones visibles
    root_html, root_method = fetch_html_with_fallback("https://www.weex.com/help", validate=lambda h: "/help/sections/" in h)
    print(f"[weex] raiz /help (metodo {root_method}), {len(root_html)} chars")
    soup = BeautifulSoup(root_html, "html.parser")
    sec_links = sorted({a.get("href", "") for a in soup.select('a[href*="/help/sections/"]')})
    print(f"[weex] {len(sec_links)} links de seccion en la raiz")
    for l in sec_links[:40]:
        print(f"  - {l}")


def debug_blofin():
    banner("Blofin")
    url = "https://blofin.com/en/support/Announcement/Delisting"
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
    print(f"[blofin] {url} -> {resp.status_code}")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.S)
    if not m:
        print("[blofin] no se encontro __NEXT_DATA__")
        return
    data = json.loads(m.group(1))
    page_props = ((data.get("props") or {}).get("pageProps") or {})
    articles = page_props.get("articles") or []
    print(f"[blofin] {len(articles)} articulos, totalPages={page_props.get('totalPages')}")
    for a in articles[:15]:
        print(f"  - {a.get('title')!r} | {a.get('date')!r} | {a.get('href')!r}")


if __name__ == "__main__":
    for fn in (debug_blofin, debug_pionex, debug_weex, debug_coinw, debug_lbank):
        try:
            fn()
        except Exception as e:
            print(f"!! fallo {fn.__name__}: {e!r}")
