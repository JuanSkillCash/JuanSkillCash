# Fase 4 — validación con datos reales: cómo correr esto

**Estos scripts requieren salida real a Internet.** El sandbox donde se
construyó todo este proyecto (Fases 1–4) la tiene bloqueada por política
del entorno (verificado de nuevo en la Fase 4, ver
`FASE_4_VALIDACION_REAL.md` sección 0) — por eso este directorio contiene
herramientas **listas para correr en tu propia máquina con Internet**, no
resultados ya ejecutados. Ningún script de aquí pide una clave privada, una
seed phrase ni una API key: todos hablan solo con RPC público/oficial.

## Requisitos

```bash
pip install websockets   # solo si vas a usar wallet_monitor.py / robinhood_adapter.py en vivo
```

Los scripts de este directorio (`fetch_and_validate_*.py`) solo usan la
librería estándar de Python (`urllib`), sin dependencias extra.

## 1) Encontrar una wallet real de un trader de FOMO

Ver `FASE_4_VALIDACION_REAL.md`, Paso 1, para el detalle completo (qué está
confirmado, qué es inferencia, qué no se puede obtener). Resumen accionable:

1. Abrí la app/web de FOMO (`fomo.family`), andá al leaderboard, elegí un
   trader.
2. Si su perfil muestra directamente una wallet o un enlace a un
   explorador — usá esa dirección directamente, es la fuente más sólida.
3. Si no, usá un servicio de verificación de terceros bajo tu propio
   criterio de riesgo (ver Fase 1 del proyecto: FomoScan, `fomoapi.io`) que
   resuelve *handle de FOMO → wallet verificada*, **o** el método manual
   documentado públicamente de cruzar el "cash balance" mostrado en el
   perfil de FOMO contra la página de holders de USDC en Solscan (citado en
   `FASE_4_VALIDACION_REAL.md`).
4. Para Robinhood Chain: si el trader ya te dio (o confirmaste de otra
   forma) su wallet EVM en Base/BNB/Monad, la hipótesis razonada de la Fase
   3 (derivación HD de Privy, mismo `coin_type` 60 para todo EVM) dice que
   debería ser la misma dirección en Robinhood Chain — pero **confirmalo**
   viendo si esa dirección tiene actividad real en
   `https://robinhoodchain.blockscout.com/address/<0x...>` antes de asumirlo.

## 2) Validar Solana

```bash
cd research/fomo-monitor
python validate/fetch_and_validate_solana.py <WALLET_SOLANA> --limit 5 --json-out validate/out/solana_results.json
```

Qué hace: `getSignaturesForAddress` (últimas `--limit` firmas confirmadas) →
por cada una, `getTransaction` (mismo RPC público que usa `wallet_monitor.py`)
→ `transaction_parser.interpret_transaction` (Fase 2, sin modificar) →
imprime **RAW vs PARSER** lado a lado y guarda un JSON con todo, listo para
pegar en la sección 5/6 de `FASE_4_VALIDACION_REAL.md`.

## 3) Validar Robinhood Chain

```bash
python validate/fetch_and_validate_robinhood.py <WALLET_0x...> --lookback-blocks 500000 --limit 5 --json-out validate/out/robinhood_results.json
```

Qué hace: `eth_getLogs` (eventos `Transfer` donde la wallet es `from` o
`to`, en el rango de bloques indicado) → por cada transacción única,
`eth_getTransactionByHash` + `eth_getTransactionReceipt` + `eth_getBlockByNumber`
(mismos métodos que usa `robinhood_adapter.py`) → `evm_parser.interpret_transaction`
(Fase 3, sin modificar) → RAW vs PARSER + JSON de salida.

`--lookback-blocks` es necesario porque, a diferencia de Solana (que tiene
`getSignaturesForAddress`, un índice por dirección), **EVM estándar no
tiene una forma de pedir "todo el historial de esta wallet" directamente**
— hay que decirle a `eth_getLogs` un rango de bloques. Con bloques de
~100ms, 500.000 bloques son ~14 horas; subilo si la wallet no tuvo
actividad reciente (atención al límite de 1.000 resultados por consulta
de `eth_getLogs`, documentado para Robinhood Chain).

## 4) Medir latencia (Paso 5)

```bash
# Solana:
python prototype/wallet_monitor.py --interpret --sol-usd-price 150 <WALLET_SOLANA>
# Robinhood Chain:
python -m chains.robinhood_adapter <WALLET_0x...> --poll-interval 5
```

Dejalo corriendo y esperá a que el trader observado haga una operación real
(o probá con una wallet muy activa). Metodología de latencia, con las
marcas de tiempo que **ya imprime el código existente**, sin necesitar
ningún script nuevo:

```
latencia_deteccion       = timestamp del log "--- Nueva transaccion detectada ---"
                            (Solana) / primer log de la firma en el polling (Robinhood)
                            MENOS
                            trade.timestamp (el blockTime/timestamp de bloque real)

latencia_interpretacion  = timestamp del log "=== ALERTA (interpretacion) ==="
                            MENOS
                            timestamp del log "--- Nueva transaccion detectada ---"

latencia_total           = latencia_deteccion + latencia_interpretacion
```

Ver `FASE_4_VALIDACION_REAL.md`, Paso 5, para el razonamiento sobre qué
número esperar en cada chain (basado en los tiempos de bloque documentados,
no medido en este sandbox).

## 5) Robustez con transacciones reales (Paso 6)

Los dos scripts de este directorio no filtran por tipo de operación: van a
mostrar tal cual lo que encuentren, incluidas transferencias simples,
approvals, swaps fallidos, etc., si la wallet elegida los tuvo. Correlos
contra una wallet con variedad de actividad y revisá que:
- Las transferencias simples y los `approve`/`Approval` salgan `UNKNOWN`
  (no que se inventen un BUY/SELL).
- Las transacciones fallidas salgan `UNKNOWN` con `confidence=0.0`.
- Los swaps limpios salgan `BUY`/`SELL`/`SWAP` con `confidence` alta.

(Los 49 tests offline del proyecto ya prueban estos mismos casos con
fixtures sintéticos — ver `tests/`. Esto es la confirmación con datos
reales que los tests no pueden dar por sí solos.)
