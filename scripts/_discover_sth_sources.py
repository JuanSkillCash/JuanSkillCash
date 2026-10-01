"""
Script DESCARTABLE de un solo uso - solo imprime la forma cruda de las respuestas de Bitview
(bitview.space) y bitcoin-data.com para el indicador STH-MVRV, antes de construir el pipeline
real. Se borra en cuanto se confirme la forma exacta de los endpoints (no tiene secretos, no
escribe nada en Supabase).
"""

import requests

print("=== BITVIEW: /api/series/search?q=sth ===")
try:
    r = requests.get("https://bitview.space/api/series/search", params={"q": "sth"}, timeout=30)
    print("status:", r.status_code)
    print(r.text[:6000])
except Exception as e:
    print("ERROR:", e)

print("\n=== BITVIEW: /api/series/search?q=realized ===")
try:
    r = requests.get("https://bitview.space/api/series/search", params={"q": "realized"}, timeout=30)
    print("status:", r.status_code)
    print(r.text[:6000])
except Exception as e:
    print("ERROR:", e)

print("\n=== BITVIEW: /api/series/search?q=mvrv ===")
try:
    r = requests.get("https://bitview.space/api/series/search", params={"q": "mvrv"}, timeout=30)
    print("status:", r.status_code)
    print(r.text[:6000])
except Exception as e:
    print("ERROR:", e)

print("\n=== BGEOMETRICS: /v1/sth-mvrv ===")
try:
    r = requests.get("https://bitcoin-data.com/v1/sth-mvrv", timeout=30)
    print("status:", r.status_code)
    print(r.text[:3000])
except Exception as e:
    print("ERROR:", e)

print("\n=== BGEOMETRICS: /v1/sth-realized-price ===")
try:
    r = requests.get("https://bitcoin-data.com/v1/sth-realized-price", timeout=30)
    print("status:", r.status_code)
    print(r.text[:3000])
except Exception as e:
    print("ERROR:", e)

print("\n=== BGEOMETRICS: /v1/sth-mvrv/last ===")
try:
    r = requests.get("https://bitcoin-data.com/v1/sth-mvrv/last", timeout=30)
    print("status:", r.status_code)
    print(r.text[:1000])
except Exception as e:
    print("ERROR:", e)

print("\n=== BITVIEW: /openapi.json (primeros 6000 chars) ===")
try:
    r = requests.get("https://bitview.space/openapi.json", timeout=30)
    print("status:", r.status_code)
    print(r.text[:6000])
except Exception as e:
    print("ERROR:", e)

for candidate in [
    "/api/vecs/sth_realized_price",
    "/api/series/sth_realized_price",
    "/api/vecs/sth-realized-price",
    "/api/sth_realized_price",
    "/api/series/sth_realized_price/values",
]:
    print(f"\n=== BITVIEW: {candidate} ===")
    try:
        r = requests.get("https://bitview.space" + candidate, timeout=30)
        print("status:", r.status_code)
        print(r.text[:1500])
    except Exception as e:
        print("ERROR:", e)
