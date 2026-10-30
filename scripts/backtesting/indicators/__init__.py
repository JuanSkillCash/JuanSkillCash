"""Registro de indicadores disponibles para el motor de backtesting (scripts/backtest.py).

Para agregar uno nuevo:
  1. Crea scripts/backtesting/indicators/tu_indicador.py con una función
     detect_signals(candles, **params) -> list[{"idx", "direction": "long"|"short", "price", "t"}]
     (candles ya viene como lista de dicts open/high/low/close/volume/t, en orden cronológico)
  2. Agrégalo abajo al diccionario INDICATORS.
Eso es todo - scripts/backtest.py, la descarga de datos y el conteo de aciertos no cambian.
"""
from . import premium_discount

INDICATORS = {
    "premium_discount": {
        "detect_signals": premium_discount.detect_signals,
        "default_params": premium_discount.DEFAULT_PARAMS,
        "description": "Premium and Discount Pivot Matrix [BigBeluga] - reversión en resistencia/soporte de pivots",
    },
}
