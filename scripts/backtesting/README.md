# Motor de backtesting de indicadores

Backtesting puntual (no un robot programado) contra historia real de Binance Spot, gratis y sin
llave. Se dispara a mano desde GitHub Actions (`.github/workflows/backtest-indicator.yml`) porque
el sandbox de Claude no tiene salida de red hacia Binance.

## Correrlo

```
python scripts/backtest.py --indicator premium_discount --symbol BTCUSDT \
  --interval 15m --years 6 --horizons 10,20 --param mode=reversion
```

O desde GitHub: pestaña **Actions** → "Backtest de indicador" → **Run workflow**, eligiendo
indicador, símbolo, temporalidad(es) (separadas por coma, ej. `3m,5m,15m,30m` - corre una por
una) y años de historia.

## Agregar un indicador nuevo

1. Crea `scripts/backtesting/indicators/tu_indicador.py` con:
   - `DEFAULT_PARAMS = {...}` (los parámetros y sus valores por defecto)
   - `def detect_signals(candles, **params) -> list[dict]:` que devuelva una lista de señales,
     cada una `{"idx": int, "direction": "long"|"short", "price": float, "t": int}` (`idx` es la
     posición de la vela en `candles`, en orden cronológico; `t` es el timestamp en ms).
2. Regístralo en `scripts/backtesting/indicators/__init__.py`:
   ```python
   from . import tu_indicador
   INDICATORS["tu_indicador"] = {
       "detect_signals": tu_indicador.detect_signals,
       "default_params": tu_indicador.DEFAULT_PARAMS,
       "description": "qué hace, en una línea",
   }
   ```
3. Ya aparece solo en `--indicator` del CLI y en el desplegable del workflow.

Nada más cambia: la descarga de velas (`backtesting/data.py`) y el conteo de aciertos/fallos
(`backtesting/engine.py`) son compartidos por todos los indicadores.
