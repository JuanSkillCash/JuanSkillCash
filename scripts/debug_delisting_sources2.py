"""Ronda 2 del diagnostico de fuentes de deslistados - profundiza en los 3 exchanges que
la ronda 1 (debug_delisting_sources.py) no resolvio del todo: LBank (ningun codigo de
categoria conocido trae deslistados), Weex (los ids de seccion encontrados eran el menu
completo, no el de la categoria real) y CoinW (la pagina raiz de announcement-center no
mostro ningun link de deslistado)."""

from __future__ import annotations

import re
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, "scripts")
from newlistings.common import DEFAULT_HEADERS, fetch_html_with_fallback  # noqa: E402

_DELIST_WORD_RE = re.compile(r"delist|removal of.*trading pair|remove.*trading pair", re.IGNORECASE)


def banner(title: str):
    print(f"\n{'=' * 10} {title} {'=' * 10}")


def debug_lbank_bruteforce():
    banner("LBank - bruteforce de categorias")
    url = "https://www.lbank.com/lbk-api/huamao-media-center/notice/category/noticeList"
    for n in range(40, 66):
        code = f"CO000000{n}"
        try:
            resp = requests.post(url, json={"categoryCode": code, "pageNo": 1, "pageSize": 10}, headers=DEFAULT_HEADERS, timeout=20)
        except requests.RequestException as e:
            print(f"[lbank] {code}: error {e}")
            continue
        if resp.status_code != 200:
            continue
        payload = resp.json()
        items = ((payload.get("data") or {}).get("resultList")) or []
        if not items:
            continue
        titles = [it.get("title", "") for it in items]
        hit = any(_DELIST_WORD_RE.search(t) for t in titles)
        marker = " <-- DESLISTADOS AQUI" if hit else ""
        print(f"[lbank] {code}: {len(items)} items{marker}")
        for t in titles[:3]:
            print(f"    - {t!r}")


def debug_weex_section_names():
    banner("Weex - nombres de seccion")
    html, method = fetch_html_with_fallback("https://www.weex.com/help", validate=lambda h: "/help/sections/" in h)
    print(f"[weex] raiz /help (metodo {method}), {len(html)} chars")
    soup = BeautifulSoup(html, "html.parser")
    pairs = []
    for a in soup.select('a[href*="/help/sections/"]'):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        pairs.append((href, text))
    seen = set()
    for href, text in pairs:
        if href in seen:
            continue
        seen.add(href)
        marker = " <-- DESLISTADOS?" if _DELIST_WORD_RE.search(text or "") else ""
        print(f"  {href} -> {text!r}{marker}")

    # Ver si el articulo de deslistado de prueba ya esta en las secciones que hoy se
    # scrapean (spot=18540509241753, futures=47660531875481) pero se descarta en silencio.
    known_delist_article = "a2ps5uth3igcomm5g939vd9u"
    for sec_id, label in (("18540509241753", "spot"), ("47660531875481", "futures")):
        sec_url = f"https://www.weex.com/help/sections/{sec_id}"
        sec_html, sec_method = fetch_html_with_fallback(sec_url, validate=lambda h: "/help/articles/" in h, wait_selector='a[href*="/help/articles/"]')
        present = known_delist_article in sec_html
        print(f"[weex] seccion {label} ({sec_id}, metodo {sec_method}): articulo de deslistado de prueba presente = {present}")
        if present:
            sec_soup = BeautifulSoup(sec_html, "html.parser")
            links = sec_soup.select('a[href*="/help/articles/"]')
            delist_like = [a.get_text(strip=True) for a in links if _DELIST_WORD_RE.search(a.get_text(strip=True) or "")]
            print(f"[weex]   {len(delist_like)} titulos tipo deslistado en esta misma seccion (de {len(links)} totales)")
            for t in delist_like[:10]:
                print(f"    - {t!r}")


def debug_coinw_more():
    banner("CoinW - pagina /more")
    url = "https://www.coinw.com/help-center/announcement-center/more"
    html, method = fetch_html_with_fallback(url, validate=lambda h: "announcement-center" in h)
    print(f"[coinw] {url} (metodo {method}), {len(html)} chars")
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)
    relevant = [a for a in links if "announcement" in a["href"] or "delist" in (a.get_text(strip=True) or "").lower()]
    print(f"[coinw] {len(relevant)} links relevantes de {len(links)} totales")
    seen = set()
    for a in relevant[:60]:
        href = a["href"]
        text = a.get_text(strip=True)
        key = (href, text)
        if key in seen:
            continue
        seen.add(key)
        marker = " <-- DESLISTADO" if _DELIST_WORD_RE.search(text or "") else ""
        print(f"  {href} -> {text!r}{marker}")


if __name__ == "__main__":
    for fn in (debug_coinw_more, debug_weex_section_names, debug_lbank_bruteforce):
        try:
            fn()
        except Exception as e:
            print(f"!! fallo {fn.__name__}: {e!r}")
