# Fase 4 — Validación del sistema con datos reales

**Fecha:** 2026-09-11
**Alcance:** igual que siempre — solo lectura, sin ejecutar operaciones, sin conectar wallets privadas, sin claves privadas, sin tocar FOMO, sin scraping agresivo, sin evadir protecciones.

---

## 0. Resultado honesto, antes que nada

**El criterio de éxito de esta fase — "tomamos una wallet real asociada a un trader público, detectamos una operación real en blockchain y nuestro sistema identificó correctamente que fue un BUY/SELL de X por ~Y USD" — NO se pudo demostrar en esta sesión.**

Razón: este sandbox bloquea todo el tráfico de red saliente hacia dominios externos (confirmado de nuevo, en vivo, para esta fase — ver sección 1). No hay forma de llamar al RPC público de Solana, al RPC público de Robinhood Chain, a Solscan, a Blockscout, ni a fomo.family desde este entorno. Esto es la misma limitación documentada en `INFORME_TECNICO_FOMO.md` (Fase 1) e `INFORME_MULTICHAIN.md` (Fase 3), reconfirmada específicamente para esta fase.

**Lo que sí se entrega, en vez de inventar resultados:**

1. Una investigación actualizada y con evidencia mucho más sólida del Paso 1 (FOMO → wallet), con hallazgos nuevos importantes (sección 1).
2. Tres scripts **completos, funcionales y probados** (`validate/fetch_and_validate_solana.py`, `validate/fetch_and_validate_robinhood.py`, `validate/measure_latency.py`) que hacen exactamente lo que pide el Paso 2/3/5 — verificados con RPC **mockeado** (ver sección 3) para probar que la herramienta en sí no tiene bugs, pero **nunca ejecutados contra la red real** porque no se pudo.
3. Investigación actualizada del Paso 4 (precio) con hallazgos nuevos sobre Chainlink Feed Registry.
4. Pruebas de robustez del Paso 6 que **sí se pudieron ejecutar de verdad en este sandbox** (son offline por diseño, no dependen de la red) — 2 casos nuevos (aprobación/allowance en Solana y en EVM) que se sumaron a los 49 tests existentes, dando **53 tests, 100% en verde**.
5. Instrucciones exactas y reproducibles para que, en una máquina con Internet, alguien corra los 3 scripts y complete las secciones 1, 4, 5, 6, 7, 8 (todas las que requieren datos reales) de este mismo documento.

**No se avanza a ranking ni a copy-trading** — tal como pidió el encargo si no se puede demostrar el criterio de éxito.

---

## 1. Verificación de conectividad (repetida para esta fase)

```
$ curl -sS -m 8 -o /dev/null -w "HTTP %{http_code}\n" https://api.mainnet-beta.solana.com/ -X POST ...
curl: (56) CONNECT tunnel failed, response 403
HTTP 000

$ curl -sS -m 8 -o /dev/null -w "HTTP %{http_code}\n" https://rpc.mainnet.chain.robinhood.com/ -X POST ...
curl: (56) CONNECT tunnel failed, response 403
HTTP 000

$ curl -sS -m 8 -o /dev/null -w "HTTP %{http_code}\n" https://robinhoodchain.blockscout.com/
curl: (56) CONNECT tunnel failed, response 403
HTTP 000
```

El proxy de egress del sandbox (`/root/.ccr/README.md`) es explícito: *"403/407 from the proxy... do not retry or route around it — report the blocked host."* Se reporta aquí, no se intentó eludir.

---

## PASO 1 — FOMO → Wallet: confirmado / inferencia / no obtenible

Se repitió esta investigación con más profundidad que en la Fase 3, y esta vez apareció un hallazgo que **cierra una laguna** que había quedado abierta: si fomo.family muestra o no la wallet directamente.

### A. Confirmado (con múltiples fuentes independientes)

- **fomo.family NO muestra la wallet address en su interfaz, de forma deliberada.** Cita textual encontrada: *"fomo.family displays only masked/partial addresses. Wallet addresses are not displayed anywhere in the app. This is intentional."* Esto está corroborado, no por una sola fuente, sino porque es precisamente el **problema que resuelven** al menos **cuatro herramientas de terceros independientes** encontradas en esta sesión: [FomoScan](https://www.fomoscan.sh/) (extensión de Chrome que "surfaces that account's full, on-chain-verified public wallet address — right on the page"), [Fomo Wallet Finder](https://fomowalletfinder.com/) ("paste a fomo.family profile link to instantly get that trader's Solana and EVM wallet addresses... one-click links into Solscan or Etherscan"), [CopyFomo](https://www.copyfomo.com/traders) ("fomo traders: wallet addresses, pnl, and how to copy each one"), y un bot documentado en [docs.raybot.app](https://docs.raybot.app/start/use-cases/use-cases/how-to-find-fomo-wallets). Que cuatro productos comerciales distintos existan específicamente para resolver "FOMO no te da la wallet" es la evidencia más fuerte posible sin poder abrir fomo.family directamente.
- **El leaderboard de FOMO es una superficie pública** que muestra handle + métricas (PnL, ROI, win rate, volumen) — confirmado en la Fase 1, reconfirmado aquí.
- **Un método 100% manual, público y no automatizado existe**, descrito en una guía pública (Scribe): abrir el perfil del trader en FOMO, anotar su "cash balance" (mostrado en USD dentro de la app), y cruzarlo contra la página pública de **holders de USDC en Solscan**, filtrando por ese monto — permite, con suerte y para balances poco comunes, identificar la wallet exacta sin usar ninguna herramienta de terceros ni automatización. Es lento, no siempre da un resultado único (dos wallets podrían compartir un balance parecido), pero es genuinamente legítimo: solo mirar dos páginas públicas y comparar a ojo.
- **FOMO opera en Robinhood Chain** (confirmado con URLs reales de `fomo.family/tokens/robinhood/0x...`, Fase 3) y usa wallets embebidas de **Privy** (Fase 1).

### B. Inferencia (razonada, no verificada empíricamente)

- **La wallet EVM de un trader de FOMO debería ser la misma en todas las chains EVM que soporta** (Base, BNB Chain, Monad, Robinhood Chain), por la derivación HD estándar (BIP-44, `coin_type` 60) que usa Privy — establecido en la Fase 3, sigue sin verificarse contra una cuenta real.
- Los cuatro servicios de terceros mencionados en A probablemente combinan: (a) el propio trader firmando un mensaje o vinculando su wallet voluntariamente con su cuenta de FOMO (un flujo de "verificación" que estos servicios ofrecerían), y/o (b) heurísticas de indexación on-chain (patrones de actividad, timing, montos) para proponer candidatos — **no se pudo confirmar el mecanismo exacto de ninguno de los cuatro**, y no corresponde intentar probarlo aquí (implicaría usarlos o inspeccionar su tráfico, fuera de alcance).

### C. No obtenible (al menos no de forma oficial/documentada, ni siquiera con herramientas de terceros)

- **Una API oficial de FOMO Labs que devuelva "wallet de tal handle"** — sigue sin existir, confirmado otra vez.
- **Certeza de que la wallet propuesta por un servicio de terceros es efectivamente la correcta** — ninguno de los cuatro es FOMO Labs; todos son productos comerciales de terceros con su propio modelo de negocio y sin garantía pública de exactitud. Usarlos para "Paso 1" de este proyecto es razonable como punto de partida, pero el dato debe tratarse como **una hipótesis a confirmar on-chain** (por ejemplo, viendo si esa wallet efectivamente interactúa con contratos de FOMO/Privy conocidos, o si su patrón de actividad es consistente con el perfil público del trader), no como un hecho.

**Conclusión práctica del Paso 1:** la ruta más limpia y reproducible para conseguir una wallet real de prueba es **la manual** (perfil de FOMO + Solscan USDC holders) o, aceptando el riesgo de depender de un tercero no verificado, usar uno de los cuatro servicios listados. Ninguna de las dos requiere automatizar FOMO ni evadir ninguna protección — ambas son exactamente lo que el encargo permite ("fuentes públicas legítimas").

---

## PASO 2 y 3 — Wallet → Transacciones → Validar el parser

### Scripts entregados (`research/fomo-monitor/validate/`)

| Script | Qué hace | Métodos RPC que usa (todos oficiales, sin credenciales) |
|---|---|---|
| `fetch_and_validate_solana.py` | Dada una wallet, trae sus últimas N transacciones reales y las interpreta | `getSignaturesForAddress`, `getTransaction` |
| `fetch_and_validate_robinhood.py` | Dada una wallet, trae sus últimas N transferencias ERC-20 reales (en un rango de bloques) y las interpreta | `eth_blockNumber`, `eth_getLogs`, `eth_getTransactionByHash`, `eth_getTransactionReceipt`, `eth_getBlockByNumber`, `eth_call` |
| `measure_latency.py` | Deja el monitor corriendo en vivo y mide la latencia de cada operación nueva que detecta | Los mismos de `chains/solana_adapter.py` / `chains/robinhood_adapter.py` (Fase 3) |

Ninguno de los tres inventa un endpoint nuevo: todos reutilizan exactamente los mismos métodos RPC ya documentados y citados en `INFORME_TECNICO_FOMO.md` (Solana) e `INFORME_MULTICHAIN.md` (Robinhood Chain), y ninguno reimplementa la lógica de interpretación — todos importan `transaction_parser.py` / `evm_parser.py` tal cual quedaron en las Fases 2 y 3.

### Qué se pudo probar en este sandbox (y qué no)

**No se pudo probar:** que estos scripts traigan datos reales de una wallet real — eso exige la red bloqueada (sección 1).

**Sí se pudo probar, y se probó:** que los scripts funcionan correctamente de punta a punta — construyen las llamadas RPC correctas, procesan la respuesta, corren el parser sin modificarlo, y producen la comparación RAW vs PARSER — usando un RPC **mockeado** (`unittest.mock`, misma técnica que ya se usaba en `tests/test_chain_adapters.py` desde la Fase 3) sobre los mismos fixtures sintéticos del proyecto. Esto está en `tests/test_validate_scripts.py` (4 tests nuevos, incluidos en los 53 verdes).

Ejemplo real de la salida de `fetch_and_validate_solana.py` corriendo contra el fixture `jupiter_buy_sol_to_token.json` (offline, con RPC mockeado — **no es una wallet real**, es la misma prueba sintética de la Fase 2, mostrada aquí solo para ilustrar el formato de salida que tendrá el script cuando corra con red real):

```
RAW:
{
  "signature": "DemoSig1JupiterBuySOLtoTOKENxxx...",
  "blockTime": 1786000000,
  "err": null,
  "fee_lamports": 5000,
  "sol_pre_lamports": 5000000000,
  "sol_post_lamports": 3497955720,
  "token_balance_changes": [
    {"mint": "DemoMemecoinMintOneHHH...", "pre_amount": null, "post_amount": "1000000"}
  ],
  "top_level_program_ids": ["ComputeBudget...", "ComputeBudget...", "JUP6LkbZbjS1jKK..."]
}
PARSER:
{
  "wallet": "DemoWalletJupiterBuyerAAA...",
  "action": "BUY",
  "token_in": "So1111...112",
  "token_in_amount": 1.50203928,
  "token_out": "DemoMemecoinMintOneHHH...",
  "token_out_amount": 1000000.0,
  "protocol": "Jupiter Aggregator v6",
  "confidence": 0.95,
  ...
}
```

**Esto NO cumple el Paso 3 tal como se pidió** (5 operaciones reales de Solana + 5 de Robinhood Chain) — es la prueba de que la herramienta funciona, no la validación con datos reales. Para completar el Paso 3 de verdad:

```bash
# en una maquina con Internet:
cd research/fomo-monitor
python validate/fetch_and_validate_solana.py <WALLET_SOLANA_REAL> --limit 5 --json-out validate/out/solana_results.json
python validate/fetch_and_validate_robinhood.py <WALLET_0x_REAL> --limit 5 --json-out validate/out/robinhood_results.json
```

y pegar la salida de cada uno (o el contenido de los `.json`) en esta misma sección, reemplazando este aviso.

---

## PASO 4 — Precio: qué se puede determinar y qué no

Sin cambios respecto a lo ya documentado en `INFORME_TECNICO_FOMO.md` (Fase 2, Solana) e `INFORME_MULTICHAIN.md` (Fase 3, Robinhood Chain) en cuanto al diseño (`estimated_price`/`usd_value` = `None` si no hay una fuente sólida, nunca inventado) — esta fase agrega un hallazgo nuevo relevante:

- **Chainlink Feed Registry** (contrato que permite consultar `latestRoundData(base, quote)` para cualquier par sin conocer la dirección del feed específico, documentado en [docs.chain.link/data-feeds/feed-registry](https://docs.chain.link/data-feeds/feed-registry)) **existe como patrón, pero está confirmado solo en Ethereum mainnet** (dirección `0x47Fb2585D2C56Fe188D0E6ec628a38b74fCeeeDf`) — **no se encontró confirmación de que este Registry (u otro equivalente) esté desplegado en Robinhood Chain**. Si lo estuviera, sería la solución ideal (leer el precio de cualquier token directamente on-chain, sin hardcodear direcciones de feed individuales) — pero no se puede asumir que existe sin verificarlo, así que **no se implementó**. Con acceso a red, el primer paso sería consultar `docs.robinhood.com/chain/oracles-and-price-feeds` directamente para confirmar si hay Feed Registry o solo feeds individuales por par.
- Para **Solana**, la fuente recomendada sigue siendo la misma de la Fase 2: stablecoins (USDC/USDT) tratadas ~1:1 con USD sin necesitar oráculo, y un precio SOL/USD externo (Pyth es el oráculo nativo del ecosistema Solana, no investigado en profundidad en ninguna fase todavía) para el resto.
- **Ningún precio se inventa**: donde no hay una pata stablecoin ni se proveyó un precio externo, el campo queda `null` con una nota explicando por qué — comportamiento ya verificado en los 53 tests (por ejemplo, `TestUniswapV2Sell.test_no_usd_value_without_price_oracle` y `TestOrcaTokenToTokenSwap.test_no_usd_value_without_quote_leg`).

**Qué falta (requiere red):** confirmar si Robinhood Chain tiene Feed Registry; si no, obtener las direcciones individuales de los feeds ETH/USD y USDG/USD desde `docs.robinhood.com/chain/oracles-and-price-feeds` o desde el propio explorador, y cablear un `native_usd_price` real (hoy es un parámetro manual) leyendo `latestRoundData()` en vivo.

---

## PASO 5 — Latencia: metodología lista, sin números reales todavía

`validate/measure_latency.py` implementa exactamente la medición pedida: para cada operación nueva detectada e interpretada, calcula

```
latencia_total = ahora() - trade.timestamp   (trade.timestamp = blockTime/timestamp de bloque real, dato on-chain)
```

Probado (mockeado, offline) en `tests/test_validate_scripts.py::TestMeasureLatency` — confirma que el cálculo no falla ni con timestamp presente ni ausente.

**No se pudo ejecutar en vivo** (requiere red + una wallet operando en tiempo real mientras el script corre). En su lugar, una estimación **teórica** basada en los tiempos de bloque ya documentados (no medida, marcada como tal):

| Chain | Tiempo de bloque documentado | Estimación teórica de latencia total |
|---|---|---|
| Solana | Confirmación "confirmed" típicamente en el orden de ~1 slot (~400ms) a pocos segundos | Con WebSocket (`logsSubscribe`, push inmediato) + 1 llamada `getTransaction`: probablemente **sub-segundo a pocos segundos**, dominado por la latencia de red hacia el RPC público, no por el parser (el parser en sí corre en milisegundos, ver `rpc_fetch_ms` que ya imprime `fetch_and_validate_solana.py`) |
| Robinhood Chain | ~100ms por bloque (documentado, Fase 3) | Con el **polling** por defecto (`--poll-interval`, 5s de default): la latencia está **dominada por el intervalo de polling**, no por la chain — en el peor caso, hasta `poll_interval` segundos adicionales sobre el tiempo de confirmación real. Con `eth_subscribe` (WSS, requiere proveedor propio con API key) la latencia bajaría a un orden similar a Solana |

**Qué falta (requiere red):** correr `measure_latency.py` contra una wallet real y activa en cada chain, y reemplazar la tabla de arriba con números medidos.

---

## PASO 6 — Robustez: sí ejecutado, con resultados reales de esta sesión

A diferencia de los pasos anteriores, **esto no depende de la red** — se pudo ejecutar de verdad. Se agregaron dos casos nuevos a la batería de tests offline (que ya cubría BUY/SELL/SWAP/transferencia simple/multi-hop/tx fallida desde las Fases 2 y 3):

| Caso nuevo | Chain | Fixture | Resultado obtenido | Correcto? |
|---|---|---|---|---|
| `approve` (delegación SPL, sin transferencia) | Solana | `tests/fixtures/spl_token_approve_no_transfer.json` | `action=UNKNOWN`, `confidence=0.0` | ✅ No se confundió con una compra |
| `Approval` (allowance ERC-20, sin `Transfer`) | Robinhood Chain | `tests/fixtures/evm/erc20_approve_no_transfer.json` | `action=UNKNOWN`, `confidence=0.0`, `protocol=None` | ✅ No se confundió con una compra |

Ejecutado en `tests/test_robustness_paso6.py` (3 tests) más los ya existentes de `TestManifestFixtures` en ambos parsers (que corren automáticamente sobre cualquier fixture nuevo agregado al manifest). **Resultado: 53/53 tests en verde**, cubriendo ahora:

- Compra (BUY) — Solana y Robinhood Chain
- Venta (SELL) — Solana y Robinhood Chain
- Swap sin activo de referencia (SWAP) — ambas chains
- Multi-hop ambiguo — ambas chains
- Transferencia simple — ambas chains
- Transacción fallida — ambas chains
- **Aprobación/allowance (nuevo, Fase 4)** — ambas chains
- ERC-4337 UserOperation (EntryPoint) — Robinhood Chain
- ETH nativo vía `tx.value` — Robinhood Chain
- Bonding curve (Pump.fun) — Solana

**Lo que falta para robustez "real":** correr los mismos dos scripts del Paso 2/3 contra wallets reales con actividad variada, y confirmar que ninguna transferencia real ni ningún `approve`/`Approval` real se clasifica incorrectamente como BUY/SELL — los fixtures prueban que la *lógica* es correcta, pero no reemplazan la confirmación contra datos reales.

---

## PASO 7 — Informe (síntesis de los 14 puntos pedidos)

1. **Trader utilizado:** ninguno — no se pudo acceder a fomo.family para elegir uno (sección 1). Ver Paso 1 para cómo elegir uno con acceso a red.
2. **Wallet utilizada:** ninguna wallet real — se usaron los fixtures sintéticos ya existentes (Fases 2/3) solo para probar que los scripts funcionan (sección 3).
3. **Blockchain:** Solana y Robinhood Chain, ambas cubiertas por el diseño; ninguna probada con datos reales en esta sesión.
4. **Transacciones analizadas:** 0 reales. 2 sintéticas nuevas (aprobación, ambas chains) + reuso de las ~13 sintéticas de fases anteriores, todas offline.
5. **Resultado RAW:** ver formato exacto (y ejemplo sintético) en la sección Paso 2/3.
6. **Resultado del parser:** ídem, formato `NormalizedTrade` (Fase 3), ejemplo en la misma sección.
7. **Diferencias:** no aplica todavía — no hay un "resultado esperado por inspección manual de un explorador" contra el cual comparar, porque no hubo datos reales.
8. **Precisión:** no medible todavía contra datos reales. Contra los 53 tests offline (que sí son una medida de precisión de la *lógica*, no del sistema contra el mundo real): 53/53 (100%) — con la salvedad importante de que "offline" significa que los fixtures fueron construidos para producir el resultado esperado, así que esto mide "¿la lógica hace lo que se diseñó que hiciera?", no "¿acierta contra la realidad?".
9. **Precio:** ver Paso 4 — mecanismo listo (stablecoins, `native_usd_price` manual), Chainlink Feed Registry pendiente de confirmar en Robinhood Chain.
10. **USD value:** ídem — `null` cuando no hay fuente sólida, nunca inventado (verificado por tests).
11. **Protocolo:** detectable para Jupiter/Raydium/Orca/Pump.fun/Meteora (Solana) y Uniswap V2/V3 (Robinhood Chain) — sin datos reales que confirmen que la detección funciona fuera de los fixtures sintéticos.
12. **Latencia:** metodología y herramienta listas (`measure_latency.py`), sin número medido — ver Paso 5 para la estimación teórica.
13. **Problemas encontrados:**
    - El bloqueo de red del sandbox impidió completar el objetivo central de esta fase (validación con datos reales).
    - Robinhood Chain no tiene un equivalente a `getSignaturesForAddress` de Solana — hay que estimar un rango de bloques (`--lookback-blocks`), lo cual es menos preciso y puede requerir varios intentos con rangos más grandes si la wallet no tuvo actividad reciente.
    - No se confirmó si Robinhood Chain tiene Chainlink Feed Registry desplegado.
14. **Qué falta solucionar:**
    - Ejecutar los 3 scripts de `validate/` contra wallets reales desde una máquina con Internet (instrucciones exactas en `validate/README.md`), y completar las secciones 1, 4, 5 y 7 (puntos 1-12) de este documento con los resultados reales.
    - Confirmar Chainlink Feed Registry (o las direcciones de feed individuales) en Robinhood Chain para cerrar el Paso 4 de verdad.
    - Considerar Pyth como fuente de precio SOL/USD para Solana (no investigado todavía).
    - Repetir el Paso 6 contra transacciones reales variadas (no solo fixtures).

---

## Criterio de éxito — estado final

> *"Tomamos una wallet real asociada a un trader público, detectamos una operación real en blockchain y nuestro sistema identificó correctamente que fue un BUY/SELL del activo X por aproximadamente Y USD."*

**No se puede decir esta frase todavía.** Lo que sí se puede decir, honestamente, al cierre de esta fase:

*"Construimos y probamos (con RPC mockeado, offline) tres herramientas que hacen exactamente esto — traer una transacción real por su firma/hash, interpretarla con el parser ya validado en 53 tests, y mostrar BUY/SELL/SWAP con cantidad, precio y USD value — pero no pudimos ejecutarlas contra la red real porque este entorno de ejecución bloquea todo el tráfico saliente. La demostración con datos reales queda lista para correr en cualquier máquina con Internet, con instrucciones exactas y reproducibles en `validate/README.md`."*

Por instrucción explícita del encargo, **no se avanza a ranking de traders ni a copy-trading** hasta que esta demostración se complete con datos reales.
