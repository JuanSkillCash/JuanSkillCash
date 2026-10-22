"""
Firma y llama al "Partnership System API" de Bitunix (panel de afiliados), para automatizar
dos cosas de la cajita "Rango de Manada":

1. Validar que un UID que alguien conecto en el sitio en verdad es un referido de Juan en
   Bitunix (endpoint validateUser) - sin esto, la conexion queda "pendiente" hasta que Juan
   la revise a mano.
2. Leer el volumen de trading real (en USD) de cada referido ya conectado (endpoint
   transAmountList), para calcular su rango.

Documentacion oficial entregada por el gerente de cuenta de Bitunix (PDF "Bitunix -
Partnership System API"). Flujo de firma (igual al ejemplo en Python del propio PDF):
    1. A cada llamada se le agrega el parametro "timestamp" (segundos, UTC).
    2. Se ordenan los parametros: primero los que empiezan con digito, luego los que
       empiezan con minuscula, luego el resto; dentro de cada grupo, por la suma de los
       valores ASCII del nombre del parametro (asi lo pide el PDF, no es un typo).
    3. Se concatenan SOLO LOS VALORES (no los nombres) en ese orden, se le pega el
       ApiSecret al final, y se saca el SHA1 en hexadecimal - esa es la firma.
    4. Se mandan apiKey y signature como headers.

Limite de la API: 30 llamadas cada 10 segundos (documentado por Bitunix) - este modulo no
hace throttling propio, lo maneja quien lo llame si hace falta.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any
from urllib.parse import urlencode

import requests

log = logging.getLogger("bitunix_api")

BASE_URL = "https://partners.bitunix.com"


def _parameter_type(key: str) -> int:
    first = key[0]
    if first.isdigit():
        return 1
    if first.islower():
        return 2
    return 3


def _sort_params(params: dict[str, Any]) -> dict[str, Any]:
    sorted_keys = sorted(params.keys(), key=lambda k: (_parameter_type(k), sum(ord(c) for c in k)))
    return {k: params[k] for k in sorted_keys}


def _sign(sorted_params: dict[str, Any], api_secret: str) -> str:
    concatenated = "".join(str(v) for v in sorted_params.values())
    return hashlib.sha1((concatenated + api_secret).encode("utf-8")).hexdigest()


def call(
    method: str,
    path: str,
    params: dict[str, Any],
    api_key: str,
    api_secret: str,
    timeout: int = 20,
) -> dict | None:
    """Llama un endpoint del Partner API de Bitunix. `params` no debe incluir "timestamp" -
    se agrega aca mismo. Devuelve el dict de `result` si la respuesta vino con code "0", o
    None si algo fallo (se deja un warning en el log, nunca se lanza una excepcion para no
    tumbar al robot que llama a esto)."""
    full_params = {**params, "timestamp": int(time.time())}
    sorted_params = _sort_params(full_params)
    signature = _sign(sorted_params, api_secret)
    headers = {"apiKey": api_key, "signature": signature}

    try:
        if method.upper() == "GET":
            query = urlencode(sorted_params)
            resp = requests.get(f"{BASE_URL}{path}?{query}", headers=headers, timeout=timeout)
        else:
            headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
            resp = requests.post(f"{BASE_URL}{path}", headers=headers, data=sorted_params, timeout=timeout)
    except requests.RequestException as e:
        log.warning(f"fallo llamando a Bitunix {path}: {e}")
        return None

    if resp.status_code != 200:
        log.warning(f"Bitunix {path} respondio {resp.status_code}: {resp.text[:300]}")
        return None

    try:
        body = resp.json()
    except ValueError:
        log.warning(f"Bitunix {path} no devolvio JSON valido: {resp.text[:300]}")
        return None

    if str(body.get("code")) != "0":
        log.warning(f"Bitunix {path} devolvio error ({body.get('code')}): {body.get('msg')}")
        return None

    return body.get("result")


def validate_user(uid: str, api_key: str, api_secret: str) -> dict | None:
    """True/False si el UID es un referido real de Juan (y cuanto tiene depositado). None si
    la llamada fallo (no confundir con "no es referido" - eso es result=False)."""
    return call("POST", "/partner/api/v2/openapi/validateUser", {"account": uid}, api_key, api_secret)


def trans_amount_list_page(
    uid: str, start_time: str, end_time: str, page: int, api_key: str, api_secret: str, page_size: int = 100,
) -> dict | None:
    """Una pagina del volumen de trading (por par) de un UID en un rango de fechas (max 180
    dias por llamada - lo pagina y acumula quien llame a esto en ventanas mas chicas si hace
    falta cubrir mas rango). Formato de fechas: "yyyy-MM-ddTHH:mm:ssZ"."""
    return call(
        "GET",
        "/partner/api/v1/openapi/transAmountList",
        {"uid": uid, "startTime": start_time, "endTime": end_time, "page": page, "pageSize": page_size},
        api_key, api_secret,
    )


def query_pnl_and_trade_cnt_page(
    start_time: str, end_time: str, page_no: int, api_key: str, api_secret: str, page_size: int = 100,
) -> dict | None:
    """Una pagina de volumen+conteo de operaciones de TODOS los referidos directos de Juan en
    un rango de fechas (max 180 dias) - un solo llamado cubre a todo el mundo, no hace falta
    pedir uno por uid. Cada item trae: uid, tradeCnt (operaciones), tradeAmount (volumen en
    USD), pnl. Formato de fechas: "yyyy-MM-ddTHH:mm:ssZ"."""
    return call(
        "GET",
        "/partner/api/v2/openapi/queryPnlAndTradeCnt",
        {"startTime": start_time, "endTime": end_time, "pageNo": page_no, "pageSize": page_size},
        api_key, api_secret,
    )


def query_pnl_and_trade_cnt_all(start_time: str, end_time: str, api_key: str, api_secret: str) -> dict[str, dict] | None:
    """Junta todas las paginas de query_pnl_and_trade_cnt_page en un dict {uid: {tradeCnt,
    tradeAmount, pnl, nickName}}. None si alguna pagina fallo."""
    by_uid: dict[str, dict] = {}
    page_no = 1
    while True:
        result = query_pnl_and_trade_cnt_page(start_time, end_time, page_no, api_key, api_secret)
        if result is None:
            return None
        items = result.get("items") or []
        for item in items:
            uid = str(item.get("uid"))
            by_uid[uid] = item
        if len(items) < 100 or page_no * 100 >= int(result.get("total") or 0):
            break
        page_no += 1
    return by_uid


def sum_volume_usd(uid: str, start_time: str, end_time: str, api_key: str, api_secret: str) -> float | None:
    """Suma transVolumeUsd de todas las paginas/pares de un UID en el rango dado. None si
    alguna pagina fallo (mejor no guardar un numero parcial que subestime el volumen real)."""
    total = 0.0
    page = 1
    while True:
        result = trans_amount_list_page(uid, start_time, end_time, page, api_key, api_secret)
        if result is None:
            return None
        items = result.get("items") or []
        for item in items:
            try:
                total += float(item.get("transVolumeUsd") or 0)
            except (TypeError, ValueError):
                continue
        if len(items) < 100 or page * 100 >= int(result.get("total") or 0):
            break
        page += 1
    return total
