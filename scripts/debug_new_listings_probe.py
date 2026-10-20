"""Diagnostico manual (no toca Supabase): para cada exchange ya integrado en el Radar de
Deslistados, intenta ubicar la categoria/seccion equivalente de "Nuevos Listados" en la
MISMA fuente que ya usamos (no se agrega ninguna plataforma externa), e imprime nombres de
seccion/categoria + un punado de titulos reales recientes para poder disenar el parser
(verbos distintos a "delist", y clasificacion de asset_class para los que listan
acciones/indices/commodities en futuros, estilo xStock)."""

from __future__ import annotations

import logging
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(__file__))  # para que "delistings" se importe como paquete
from delistings.common import DEFAULT_HEADERS

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("probe")


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


def probe_zendesk(name, base_url, locale):
    log.info(f"\n=== {name} (Zendesk {base_url}) ===")
    data = _get_json(f"{base_url}/api/v2/help_center/{locale}/sections.json", {"per_page": 100}, name)
    if not data:
        return
    sections = [(s.get("id"), s.get("name")) for s in data.get("sections", [])]
    log.info(f"  total secciones: {len(sections)}")
    for sid, sname in sections:
        log.info(f"  [{sid}] {sname}")


def probe_okx():
    log.info("\n=== OKX ===")
    candidates = [
        "announcements-new-listings",
        "announcements-new-currency-listings",
        "announcements-new-trading-pairs",
        "announcements-latest-announcements",
    ]
    for ann in candidates:
        data = _get_json("https://www.okx.com/api/v5/support/announcements", {"annType": ann, "page": 1}, ann)
        if not data or data.get("code") != "0":
            continue
        details = (data.get("data") or [{}])[0].get("details", [])
        log.info(f"  annType={ann} -> {len(details)} items")
        for d in details[:8]:
            log.info(f"    - {d.get('title')!r}")
        time.sleep(1)


def probe_bitget():
    log.info("\n=== Bitget ===")
    candidates = ["coin_listings", "new_coin_listings", "new_listings", "symbol_online", "new_fiat_listings"]
    for ann in candidates:
        data = _get_json(
            "https://api.bitget.com/api/v2/public/annoucements",
            {"language": "en_US", "annType": ann, "limit": 10}, ann,
        )
        if not data or data.get("code") != "00000":
            continue
        items = data.get("data") or []
        log.info(f"  annType={ann} -> {len(items)} items")
        for it in items[:8]:
            log.info(f"    - {it.get('annTitle')!r}")
        time.sleep(1)


def probe_kucoin():
    log.info("\n=== KuCoin ===")
    candidates = ["new-listings", "new-coin-listings", "latest-announcements", "activities"]
    for ann in candidates:
        data = _get_json(
            "https://api.kucoin.com/api/v3/announcements",
            {"annType": ann, "lang": "en_US", "pageSize": 10, "currentPage": 1}, ann,
        )
        if not data:
            continue
        items = (data.get("data") or {}).get("items", [])
        log.info(f"  annType={ann} -> {len(items)} items")
        for it in items[:8]:
            log.info(f"    - {it.get('annTitle')!r} (annType real={it.get('annType')})")
        time.sleep(1)


def probe_binance():
    log.info("\n=== Binance ===")
    # candidatos de catalogId: 161 es "Delisting" (confirmado, lo usamos ya); se prueban
    # varios vecinos documentados en integraciones de terceros para "New Cryptocurrency
    # Listing" sin darlos por ciertos - el nombre impreso abajo (si el catalogo trae uno)
    # es lo que decide, no el numero en si
    for cid in [48, 49, 160, 162]:
        data = _get_json(
            "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query",
            {"type": 1, "catalogId": cid, "pageNo": 1, "pageSize": 10}, f"catalogId={cid}",
        )
        if not data:
            continue
        catalogs = (data.get("data") or {}).get("catalogs") or []
        if not catalogs:
            log.info(f"  catalogId={cid} -> sin catalogs en la respuesta")
            continue
        cat = catalogs[0]
        log.info(f"  catalogId={cid} -> catalogName={cat.get('catalogName')!r} total={cat.get('total')}")
        for a in (cat.get("articles") or [])[:8]:
            log.info(f"    - {a.get('title')!r}")
        time.sleep(1)

    # fallback: feed general sin filtro de catalogo, para ver si algun titulo reciente
    # menciona "will list"/"launches" aunque no se identifique el catalogId exacto
    data = _get_json(
        "https://www.binance.com/bapi/composite/v1/public/market/notice/get",
        {"page": 1, "rows": 20}, "feed-general",
    )
    if data:
        batch = ((data.get("data") or {}).get("catalogs") or [{}])[0].get("articles")
        if batch is None:
            batch = data.get("data") if isinstance(data.get("data"), list) else []
        log.info(f"  feed general -> {len(batch or [])} items (titulos crudos, sin filtrar)")
        for a in (batch or [])[:15]:
            log.info(f"    - {a.get('title')!r}")


def probe_mexc():
    log.info("\n=== MEXC ===")
    log.info("  (usa Playwright en el scraper real; aca solo se deja constancia de las URLs candidatas)")
    for slug in ["new-listings", "new-coin-listings", "latest-news"]:
        url = f"https://www.mexc.com/announcements/{slug}?page=1"
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
            log.info(f"  {url} -> status {resp.status_code}, len={len(resp.text)}")
        except Exception as e:
            log.info(f"  {url} -> EXCEPCION {e}")


def probe_kraken():
    log.info("\n=== Kraken ===")
    data = _get_json("https://support.kraken.com/api/v2/help_center/en-us/sections.json", {"per_page": 100}, "kraken")
    if not data:
        log.info("  zendesk no respondio 200 en sections.json")
        return
    sections = [(s.get("id"), s.get("name")) for s in data.get("sections", [])]
    log.info(f"  total secciones: {len(sections)}")
    for sid, sname in sections:
        log.info(f"  [{sid}] {sname}")


if __name__ == "__main__":
    probe_zendesk("Bitunix", "https://support.bitunix.com", "en-us")
    probe_zendesk("BingX", "https://bingxservice.zendesk.com", "en-001")
    probe_okx()
    probe_bitget()
    probe_kucoin()
    probe_binance()
    probe_mexc()
    probe_kraken()
