# Informe técnico — Fase 3: arquitectura multichain (Solana + Robinhood Chain)

**Fecha:** 2026-09-11
**Alcance:** igual que las fases anteriores — solo lectura, sin ejecutar operaciones, sin conectar wallets privadas, sin claves privadas, sin tocar sistemas privados de FOMO, sin scraping, sin evadir protecciones. Todo el código nuevo habla únicamente con RPC público/oficial de cada blockchain.

**Metodología y misma limitación de siempre:** este informe se preparó en el mismo sandbox sin salida de red a dominios externos documentado en `INFORME_TECNICO_FOMO.md` (sección 0). Toda la investigación de Robinhood Chain viene de búsqueda web (snippets), citando fuente en cada afirmación técnica. Donde no hay confirmación sólida (sobre todo direcciones de contrato específicas), se dice explícitamente en vez de inventar — igual que se hizo con los program IDs de Solana en la Fase 2.

---

## 1. Robinhood Chain — qué es, exactamente

- **Red:** Robinhood Chain, lanzada en mainnet el 1 de julio de 2026 (anuncio "The World is Flat", Londres). [Robinhood Newsroom](https://robinhood.com/us/en/newsroom/robinhood-accelerates-global-expansion-robinhood-chain-mainnet-stock-tokens-agentic-trading/), [Forbes](https://www.forbes.com/sites/ninabambysheva/2026/07/01/robinhood-launches-its-own-blockchain-new-stock-tokens-and-defi-products/)
- **¿Es una L2 de Ethereum?** Sí. Es una **L2 construida con el stack de Arbitrum (Arbitrum Orbit)**, que **liquida en Ethereum L1** usando *blob data availability*. No es una sidechain independiente ni una L1 propia. [Chainstack](https://chainstack.com/what-is-robinhood-chain/), [Decrypt](https://decrypt.co/resources/what-robinhood-chain-ethereum-layer-2-network-tokenized-stocks), [TechTimes](https://www.techtimes.com/articles/318895/20260623/social-crypto-trading-app-fomo-raises-75m-sec-clears-non-custodial-wallets-operate.htm)
- **Chain ID: `4663`** — confirmado de forma consistente en múltiples fuentes independientes (Dwellir, TrustSwap, Chainstack, QuickNode). [Dwellir](https://www.dwellir.com/networks/robinhood), [TrustSwap](https://trustswap.com/robinhood/network-details)
- **Gas:** ETH nativo (no un token propio de gas). [Dwellir Blog](https://www.dwellir.com/blog/what-is-robinhood-chain)
- **Velocidad:** bloques de ~100ms (con pre-confirmaciones a 100ms), descrito como "20x más rápido que Base, 120x más rápido que Ethereum L1". [Chainstack](https://chainstack.com/what-is-robinhood-chain/)
- **RPC público oficial:** `https://rpc.mainnet.chain.robinhood.com` — gratuito, **sin API key**, pero con rate limit y **sin SLA** (documentado explícitamente así). [docs.robinhood.com/chain/connecting](https://docs.robinhood.com/chain/connecting/) (vía búsqueda)
- **Explorador oficial:** [robinhoodchain.blockscout.com](https://robinhoodchain.blockscout.com/) — corre **Blockscout** (software open-source, con una API estilo Etherscan v2). Existe también un explorador de testnet separado (`explorer.testnet.chain.robinhood.com`) y un explorador de terceros, HoodScan.
- **Compatibilidad EVM:** **Total**. "Fully EVM-compatible... Hardhat, Foundry, ethers.js, viem, Wagmi funcionan out of the box." Cualquier wallet/dapp con JSON-RPC estándar se conecta directo. [docs.robinhood.com/chain](https://docs.robinhood.com/chain/) (vía búsqueda)
- **Account abstraction nativa:** soporte "de primera clase" para **ERC-4337** (UserOperations, EntryPoint, paymasters, session keys) y también **EIP-7702** (EOAs que delegan a código de smart account). [docs.robinhood.com/chain/account-abstraction](https://docs.robinhood.com/chain/account-abstraction/) (vía búsqueda)
- **Stablecoin nativa: USDG (Global Dollar)**, no USDC — decisión explícita de Robinhood para compartir el yield de las reservas con la red en vez de quedarse Circle/Tether con él. USDC sigue siendo accesible vía *bridging*. [KuCoin](https://www.kucoin.com/news/flash/robinhood-chain-selects-usdg-as-native-stablecoin-aiming-to-share-yield-with-network-participants), [CryptoBriefing](https://cryptobriefing.com/robinhood-chain-usdg-stablecoin-yield-sharing/)
- **DeFi desde el día 1:** **Uniswap (v2, v3, v4, y UniswapX) y Chainlink** están desplegados desde el lanzamiento — Uniswap como "el AMM público primario desde el día uno". [blog.uniswap.org/robinhood-chain-is-live](https://blog.uniswap.org/robinhood-chain-is-live), [Genfinity](https://genfinity.io/2026/07/01/robinhood-chain-mainnet-launch-chainlink-oracle-integration/)
- **Caso de uso principal:** **Stock Tokens** — acciones/ETFs tokenizados como **ERC-20 estándar**, emitidos por Robinhood Assets (Jersey) Limited, dando exposición económica (no derechos legales/beneficiarios) sobre el subyacente. [docs.robinhood.com/chain/stock-tokens](https://docs.robinhood.com/chain/stock-tokens/) (vía búsqueda)

**Confirmación directa de relevancia para este proyecto:** fomo.family **ya soporta Robinhood Chain** — se encontraron URLs reales indexadas del propio sitio con tokens de Robinhood Chain: `fomo.family/tokens/robinhood/0x020bfc650a365f8bb26819deaabf3e21291018b4` y `fomo.family/tokens/robinhood/0xc2362aff2a2a4cc1f48cf3dab2c4e2605eb94ba3`. Esto confirma, con evidencia directa (no inferencia), que la investigación del usuario está bien dirigida: los traders de FOMO efectivamente operan en Robinhood Chain, y (según otra fuente) esa integración ocurrió en julio de 2026, "trayendo acciones tokenizadas al mismo feed que las memecoins".

**Advertencia de seguridad no solicitada pero relevante:** una búsqueda relacionada encontró un sitio *fomoo.family* (con doble "o") descrito como una **estafa que vacía wallets**, distinto del sitio oficial *fomo.family*. Vale la pena que el usuario lo tenga presente para no confundirlos.

---

## 2. Cómo monitorear Robinhood Chain (RPC/eventos)

### Métodos JSON-RPC (estándar de Ethereum, no específicos de Robinhood Chain)

Documentados en [ethereum.org/developers/docs/apis/json-rpc](https://ethereum.org/en/developers/docs/apis/json-rpc/) — Robinhood Chain los soporta por ser "fully EVM-compatible":

| Método | Para qué |
|---|---|
| `eth_getTransactionByHash` | Detalles de la transacción (`from`, `to`, `value`, `input`) |
| `eth_getTransactionReceipt` | Resultado (`status`) y **logs** (eventos emitidos) |
| `eth_getLogs` | Buscar eventos por rango de bloques + filtro de `topics`/`address` |
| `eth_blockNumber` | Bloque actual (para saber hasta dónde ya se procesó) |
| `eth_getBlockByNumber` | Timestamp del bloque (la receipt NO trae timestamp — hay que pedirlo aparte) |
| `eth_call` | Lectura de estado de un contrato sin gastar gas — se usa aquí para `symbol()`/`decimals()` de tokens ERC-20 |
| `eth_subscribe` (solo WebSocket) | Suscripción push a `newHeads` o `logs` |

### Tiempo real: ¿WebSocket o polling?

Investigado explícitamente. El **RPC público HTTP** de Robinhood Chain no tiene garantizado un WebSocket público sin API key. Los proveedores que sí ofrecen `eth_subscribe` (Dwellir, QuickNode, Chainstack) lo hacen **con API key del usuario**. Como esta fase no debe usar credenciales propias, el diseño implementado (`chains/robinhood_adapter.py`) usa **polling con `eth_getLogs`** contra el RPC público como modo por defecto (cero credenciales), y deja el modo `eth_subscribe` disponible como función separada (`watch_via_websocket`) para cuando el usuario decida usar su propio proveedor con su propia key — nunca se hardcodea ninguna.

### Cómo se detecta "actividad de una wallet" en EVM (a diferencia de Solana)

Solana tiene `logsSubscribe` con un filtro `mentions: [wallet]` que devuelve cualquier transacción que toque esa dirección. **EVM estándar no tiene un equivalente directo.** Lo más cercano y estándar es filtrar por el evento `Transfer(address indexed from, address indexed to, uint256 value)` de cada token ERC-20, usando la posición del address dentro de los `topics` del log:

- `topics = [TRANSFER_TOPIC0, [wallet], null]` → la wallet aparece como **emisora** (`from`)
- `topics = [TRANSFER_TOPIC0, null, [wallet]]` → la wallet aparece como **receptora** (`to`)

(JSON-RPC no permite "OR entre posiciones distintas de topic" en un solo filtro, así que son **dos filtros** por wallet — implementado así en `robinhood_adapter._get_logs_for_wallets`.) Esto detecta cualquier swap que mueva tokens ERC-20 hacia/desde la wallet, sin importar qué DEX se usó — no depende de conocer la dirección del router.

---

## 3. Cómo interpretar operaciones en EVM (mismo principio que Solana, mecánica distinta)

Fase 2 estableció el principio: **no decodificar la instrucción/calldata específica de cada DEX — comparar balances antes/después.** Este principio se sostiene perfectamente en EVM, con una razón añadida y muy concreta:

Al igual que `getTransaction(jsonParsed)` de Solana no decodifica instrucciones de programas custom, **el nodo RPC de Ethereum no decodifica el `input` (calldata) de una transacción** salvo que el cliente tenga el ABI del contrato. Peor aún: en Robinhood Chain, **Uniswap v2, v3, v4 y UniswapX conviven simultáneamente** ([blog.uniswap.org/robinhood-chain-is-live](https://blog.uniswap.org/robinhood-chain-is-live)) — cuatro arquitecturas de swap distintas, con `UniversalRouter` como "el entrypoint preferido actual" reemplazando a `SwapRouter02`. Intentar decodificar cada una a nivel de calldata sería frágil y quedaría desactualizado con cada nueva versión.

**La solución implementada (`prototype/parsers/evm_parser.py`) es idéntica en espíritu a Solana:**

1. Se recorren los `logs` del `receipt` de la transacción.
2. Se decodifican los eventos `Transfer(address,address,uint256)` (topic0 universal de EVM, confirmado vía búsqueda: `0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef`).
3. Se suman los montos donde `to == wallet` (entró) y se restan donde `from == wallet` (salió), por cada contrato de token.
4. Se compara con `tx.value` (ETH nativo enviado directamente por la wallet, cuando ella es la firmante) para la pata nativa.
5. El `topic0` de eventos `Swap` conocidos (Uniswap V3, Uniswap V2) presentes en los logs **solo se usa para nombrar el protocolo**, nunca para inferir montos — exactamente el mismo rol que cumplían los `programId` en Solana.

Esto es **agnóstico al router/agregador**: funciona igual si el swap pasó por `UniversalRouter`, por un contrato viejo `SwapRouter02`, por UniswapX, o por un agregador que todavía no existe — porque ninguno de esos detalles importa para "qué entró y qué salió de la wallet".

### Diferencia clave de "ruido" entre las dos chains

- **Solana:** el ruido es el **rent** de abrir/cerrar una cuenta de token asociada (ATA) — una pequeña salida de SOL que no es parte real del precio del swap. Se filtra con una heurística de umbral (`RENT_NOISE_LAMPORTS_THRESHOLD`).
- **EVM/Robinhood Chain:** el "ruido" análogo sería el **gas** — pero el diseño implementado usa `tx.value` (lo que el firmante decidió enviar explícitamente), que **ya excluye el gas por naturaleza** (el gas se paga aparte, no es parte de `value`). Por eso `evm_parser.py` **no necesita** un filtro de ruido equivalente al de Solana — es una simplificación real, no una omisión.

---

## 4. Protocolos/DEX detectables en Robinhood Chain

Igual que en Solana, la detección de protocolo se hace por **firma de evento** (topic0), no por dirección de router — así sobrevive a cualquier agregador o wrapper:

| Protocolo | Cómo se detecta | Confianza de la fuente |
|---|---|---|
| **Uniswap V3** (y forks compatibles) | topic0 del evento `Swap` de un pool V3 (`0xc42079f9...fbcca67`) | Confirmado vía búsqueda web |
| **Uniswap V2** (y forks compatibles) | topic0 del evento `Swap` de un par V2 (`0xd78ad95f...840159d822`) | **No confirmado con fuente explícita en esta sesión** — viene de conocimiento de entrenamiento, marcado así en el código; recomendado re-verificar contra [otterscan/topic0](https://github.com/otterscan/topic0) antes de producción |
| **ERC-4337 (UserOperation)** | presencia del contrato `EntryPoint` (v0.6 `0x5FF137D4...a026d2789` o v0.7 `0x0000000071727De2...6f37da032`, direcciones canónicas desplegadas de forma determinística) entre los logs — se anota como metadato, no reemplaza al protocolo del DEX | Direcciones confirmadas vía búsqueda; su despliegue específico en Robinhood Chain **no** se verificó por RPC directo |

**No cubierto todavía** (documentado como limitación, no inventado):
- **Uniswap V4** — arquitectura de singleton `PoolManager` (todas las pools viven en un solo contrato, con un evento `Swap` distinto y una lógica de "hooks"). Requiere la dirección del `PoolManager` en Robinhood Chain, que no se pudo confirmar en este sandbox.
- **UniswapX** — settlement basado en contratos "Reactor" (subastas off-chain, liquidación on-chain), arquitectura de eventos distinta a un AMM clásico.
- Cualquier otro DEX/agregador que se despliegue después de esta investigación.

---

## 5. Cómo obtener precios y valor en USD

**Mismo principio de la Fase 2: no inventar un precio si no hay una fuente sólida.**

- **Si una de las dos patas del swap es un stablecoin conocido** (`USDG`, `USDC`, `USDT` — identificados por **símbolo**, ver sección 6) → se asume ~1:1 con USD (aproximación, ignora *depeg*).
- **Si una pata es ETH nativo/WETH** → se necesita un precio ETH/USD externo, que el código acepta como parámetro opcional (`native_usd_price`) pero **no consulta por sí mismo**. Robinhood Chain trae **Chainlink** integrado desde el lanzamiento, con feeds documentados tanto para cripto como para las propias Stock Tokens tokenizadas ([docs.robinhood.com/chain/oracles-and-price-feeds](https://docs.robinhood.com/chain/oracles-and-price-feeds/), [docs.chain.link/data-feeds/tokenized-equity-feeds/robinhood](https://docs.chain.link/data-feeds/tokenized-equity-feeds/robinhood)) — la interfaz estándar es `AggregatorV3Interface.latestRoundData()`. **Esta es la fuente recomendada para la siguiente fase**: leer el feed de Chainlink on-chain (lectura pública, sin credenciales) en vez de depender de un proveedor externo de precios. No se implementó en este sandbox porque no se pudo confirmar la dirección específica del feed ETH/USD en Robinhood Chain (mismo problema de direcciones no verificadas, ver sección 9).
- **Swap token-a-token puro** (ninguna pata es quote asset) → sin precio USD posible sin un oráculo externo de al menos uno de los dos tokens; se marca `usd_value=None` explícitamente.

**Precio de ejecución:** se calcula siempre como el ratio entre las dos patas (`price = cantidad_gastada / cantidad_recibida` o viceversa según BUY/SELL), expresado en la unidad de la pata "quote" — igual que en Solana. El campo `price_unit` deja explícito en qué está denominado, porque **no siempre es USD**.

---

## 6. Cómo relacionar wallets (identificación de tokens y de traders)

### 6.1 Identificación de tokens: por símbolo, no por dirección

**Decisión de diseño deliberada, y la diferencia más importante frente a Solana.** En Solana se pudo confirmar con múltiples fuentes independientes la dirección exacta de USDC, USDT y SOL nativo. En Robinhood Chain, **no se pudo confirmar con la misma solidez** la dirección mainnet de WETH, USDG, ni de los routers de Uniswap (solo se encontró una dirección de WETH de **testnet**, que sería incorrecta usar en mainnet). Antes que arriesgarse a "inventar" una dirección de contrato — exactamente lo que el encargo prohíbe — el parser EVM identifica activos "quote" **consultando `symbol()` del propio contrato** (llamada `eth_call` estándar de cualquier token ERC-20, sin autenticación) y comparando el string devuelto contra una lista corta (`ETH`, `WETH`, `USDG`, `USDC`, `USDT`). Es más lento (una llamada RPC extra por token nuevo) pero **no depende de ninguna dirección no verificada**.

### 6.2 Identificación de wallets: EOA vs. Smart Account (ERC-4337)

Con account abstraction nativa, una operación puede llegar on-chain de dos formas:
- Una transacción EOA normal, `tx.from == wallet_del_trader`.
- Una **UserOperation** empaquetada por un *bundler* y enviada al `EntryPoint`; en ese caso **`tx.from`/`tx.to` de nivel superior son del bundler/EntryPoint, no de la wallet del trader**. La wallet del trader (su *smart account*) solo aparece dentro de los logs internos (como `from`/`to` de los `Transfer`).

El diseño implementado **no depende de `tx.from`/`tx.to`** para identificar a la wallet observada — siempre busca la wallet directamente en los logs `Transfer` (ver sección 3), así que **funciona igual en ambos casos**, sin necesitar tratar el ERC-4337 como un caso especial para la clasificación BUY/SELL. Sí se anota en `notes` cuando se detecta el `EntryPoint`, como metadato informativo.

### 6.3 La pregunta crítica: ¿se puede identificar de forma fiable la wallet on-chain de un trader de FOMO en Robinhood Chain?

**Respuesta corta: sí, con alta probabilidad — pero indirectamente, no porque FOMO lo publique.**

Razonamiento (con fuentes citadas, no inventado):

1. Fase 1 ya estableció que FOMO usa **wallets embebidas provistas por Privy** en las chains EVM que soporta (Base, BNB Chain, y ahora Robinhood Chain).
2. Se investigó específicamente cómo Privy deriva esas wallets: son **wallets HD (Hierarchical Deterministic)** que siguen el estándar **BIP-44**, con el mismo *coin type* (`60`, el de Ethereum) para **todas** las chains EVM. [docs.privy.io/guide/react/wallets/embedded/hd-wallets](https://docs.privy.io/guide/react/wallets/embedded/hd-wallets) (vía búsqueda)
3. **Consecuencia directa:** la wallet EVM de un usuario de FOMO debería ser **la misma dirección** en Base, BNB Chain, Monad y Robinhood Chain — una sola dirección, no una por chain. (Solana usa una curva y una derivación distintas, así que la wallet de Solana de un trader sigue siendo una dirección aparte, tal como ya se documentó en la Fase 1.)
4. Esto significa que **si se logra identificar la wallet EVM de un trader de FOMO en CUALQUIER chain EVM que soporte** (por autodeclaración del propio trader, o vía un servicio de verificación como FomoScan, descrito en la Fase 1, que ya declara resolver "Solana **y EVM** wallets" — en singular, consistente con esta hipótesis), **esa misma dirección debería servir para monitorearlo también en Robinhood Chain**, sin necesitar un mapeo separado por chain.

**Importante — esto es una inferencia razonada, no un hecho verificado directamente.** No se probó contra ninguna cuenta real de FOMO (fuera de alcance: "no intentes acceder a información privada"). Antes de confiar en esto en producción, habría que confirmarlo empíricamente con un trader real que haya publicado voluntariamente su handle de FOMO y su(s) wallet(s): comprobar si la dirección EVM que aparece en Base/BNB es exactamente la misma que aparece en sus operaciones de Robinhood Chain.

**Lo que sigue sin existir:** una forma oficial y documentada de que FOMO entregue "aquí está la wallet on-chain del trader X" — ni en Solana ni en EVM. La vía legítima sigue siendo la misma de la Fase 1: autodeclaración del trader, o un servicio de verificación de terceros aceptado bajo el propio criterio/riesgo del usuario.

---

## 7. Diferencias Solana vs. Robinhood Chain (resumen técnico)

| Aspecto | Solana | Robinhood Chain |
|---|---|---|
| Tipo de red | L1 propia (no EVM) | L2 de Ethereum (Arbitrum Orbit), EVM |
| Cómo se identifica "una operación de la wallet" | `preTokenBalances`/`postTokenBalances` + `preBalances`/`postBalances` de la transacción | Eventos `Transfer` en `receipt.logs` + `tx.value` |
| Decodificación de instrucciones de DEX | No disponible para programas custom (jsonParsed solo decodifica programas nativos) | No disponible sin el ABI de cada contrato (mismo problema, y agravado por 4 versiones de Uniswap coexistiendo) |
| Cómo se identifica el protocolo | `programId` (nivel superior + inner instructions) | `topic0` del evento `Swap` en los logs |
| "Ruido" a filtrar | Rent de abrir/cerrar cuentas de token (heurística de umbral) | Ninguno equivalente necesario (`tx.value` ya excluye el gas) |
| Activos "quote" | Por **dirección de mint** (verificadas con múltiples fuentes) | Por **símbolo** (`eth_call` a `symbol()`) — direcciones no verificadas con la misma solidez |
| WebSocket público sin credenciales | Sí (`wss://api.mainnet-beta.solana.com`, `logsSubscribe`) | No confirmado — proveedores con WSS requieren API key propia |
| Filtro "todo lo que toca esta wallet" | `logsSubscribe` con `mentions: [wallet]` | No existe filtro equivalente; se arma con 2 filtros de `Transfer` (como emisor / como receptor) |
| Ejecución de la operación | Wallet embebida (Privy) con Shamir's Secret Sharing | Wallet embebida (Privy, misma dirección que en otras EVM) o smart account ERC-4337 |
| Cuenta que "aparece" en la transacción de nivel superior | Siempre la wallet real (firmante) | Puede ser el `EntryPoint`/bundler si se usó ERC-4337 (UserOperation) — la wallet solo aparece en logs internos |

---

## 8. Arquitectura multichain implementada

```
                    ┌── Solana (wallet_monitor.py, Fase 1, SIN TOCAR)
Trader wallet ──────┤
                    └── Robinhood Chain (chains/robinhood_adapter.py, NUEVO)
                              │
                              ▼
                     Chain Adapter (interfaz uniforme: watch(addresses, on_trade, ...))
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
   parsers/solana_parser.py       parsers/evm_parser.py
   (envuelve transaction_parser.py   (NUEVO: logs Transfer +
    de la Fase 2, intacto)            topic0 de Swap conocidos)
                │                           │
                └─────────────┬─────────────┘
                              ▼
                models/normalized_trade.py
                (NormalizedTrade: chain, wallet, signature,
                 timestamp, action, token_in/out (+symbol),
                 amounts, price, usd_value, protocol, confidence)
                              │
                              ▼
                     BUY / SELL / SWAP / UNKNOWN
                              │
                              ▼
                  Alerta en consola (multichain_monitor.py)
                  -- base de datos: fuera de alcance de esta
                     fase, ver seccion 11 --
```

**Archivos nuevos/modificados:**

```
research/fomo-monitor/
├── prototype/
│   ├── wallet_monitor.py            # Fase 1 -- SIN CAMBIOS
│   ├── transaction_parser.py        # Fase 2 -- SIN CAMBIOS
│   ├── models/
│   │   └── normalized_trade.py      # NUEVO: esquema comun a todas las chains
│   ├── parsers/
│   │   ├── solana_parser.py         # NUEVO: adapta TradeEvent -> NormalizedTrade (envuelve, no reimplementa)
│   │   └── evm_parser.py            # NUEVO: logica de interpretacion EVM
│   ├── chains/
│   │   ├── solana_adapter.py        # NUEVO: envuelve wallet_monitor.py con la interfaz uniforme
│   │   └── robinhood_adapter.py     # NUEVO: polling eth_getLogs (+ eth_subscribe opcional)
│   └── multichain_monitor.py        # NUEVO: CLI de demo, ata todo sin infraestructura extra
├── tests/
│   ├── test_transaction_parser.py   # Fase 2 -- SIN CAMBIOS (24 tests, siguen pasando)
│   ├── test_evm_parser.py           # NUEVO (20 tests)
│   ├── test_chain_adapters.py       # NUEVO (2 tests de integracion, mockeados)
│   └── fixtures/
│       ├── ... (Solana, sin cambios)
│       └── evm/                     # NUEVO: fixtures sinteticos EVM + generador + README
├── README.md
├── INFORME_TECNICO_FOMO.md          # Fases 1+2 -- sin cambios
└── INFORME_MULTICHAIN.md            # este documento
```

Verificado con `git diff --stat` que `transaction_parser.py` y `wallet_monitor.py` quedaron **byte-idénticos** al commit de la Fase 2.

**46 tests en total, 100% offline, todos en verde** (24 Solana + 20 EVM + 2 de integración de adapters).

---

## 9. Limitaciones

1. **Direcciones de contrato de Robinhood Chain no verificadas con la misma solidez que Solana.** No hay dirección confirmada de WETH/USDG mainnet, ni de los routers/factories de Uniswap, ni del `PoolManager` de V4, ni de los Reactors de UniswapX, ni del feed Chainlink ETH/USD. Mitigado (no resuelto) con identificación por símbolo vía `eth_call` en vez de direcciones hardcodeadas.
2. **Uniswap V2 topic0 sin confirmación explícita en esta sesión** (viene de conocimiento de entrenamiento) — marcado así en el código y en los fixtures.
3. **Uniswap V4 y UniswapX no cubiertos** — arquitecturas de evento distintas, requieren investigación adicional con acceso a red.
4. **ETH nativo RECIBIDO (al vender) no se detecta.** Un swap "token → ETH nativo" típicamente envuelve/desenvuelve WETH internamente dentro del router, y el ETH final se entrega vía una llamada interna que no es ni un evento `Transfer` ni parte de `tx.value` (que solo refleja lo que el firmante *envió*). Documentado como limitación conocida, con una solución propuesta (vigilar el evento `Withdrawal(address,uint256)` de WETH9) no implementada aún.
5. **No hay WebSocket público sin credenciales confirmado** para Robinhood Chain — el modo por defecto es polling HTTP, con la latencia que eso implica (configurable, pero nunca tan inmediato como una suscripción push).
6. **La identificación de wallet EVM de un trader de FOMO vía "misma dirección en todas las chains EVM" es una inferencia razonada, no verificada empíricamente** (sección 6.3).
7. **Nada de esto se probó contra el RPC real de Robinhood Chain** — mismo bloqueo de red del sandbox que en las fases anteriores. Los tests corren contra fixtures sintéticos fieles al esquema oficial, no transacciones reales descargadas.
8. **Rate limit del RPC público** ("sin SLA", según su propia documentación) — no apto para monitorear muchas wallets en producción sin un proveedor dedicado (ver sección 11).

---

## 10. Costos aproximados de infraestructura (si se escala más allá de esta fase)

Cifras de las propias páginas de pricing de cada proveedor (vía búsqueda web), como orden de magnitud — **no una cotización**, y sujetas a cambio:

| Proveedor | Free tier | Primer plan pago |
|---|---|---|
| **Helius** (Solana) | 1M créditos/mes, 10 RPS | ~$49/mes (más créditos, más RPS) |
| **QuickNode** (Solana + Robinhood Chain, ambas soportadas) | Sin free tier permanente, solo prueba de 7 días (10M créditos) | ~$49/mes |
| **Alchemy** (EVM, incluido Robinhood Chain — proveedor recomendado por la propia documentación oficial) | Free plan para desarrollo/bajo tráfico | Pay-as-you-go: $0.45 por millón de *compute units* (primeros 300M/mes), luego $0.40/M |
| **fomoapi.io** (referencia de la Fase 1, no oficial) | 60 req/min sin key | $49/mes (150 req/min) → $599/mes (600 req/min + stream on-chain) → $1500/mes |

Para 100-1000 wallets monitoreadas de forma continua, un plan gratuito casi con certeza no alcanza (ver sección 11) — el rango realista, solo de RPC/indexación, está probablemente entre **$50 y $600/mes** dependiendo del volumen, sin contar cómputo propio (workers, cola, base de datos) ni un eventual proveedor de datos de precio adicional.

---

## 11. Escalabilidad: 100 / 500 / 1.000 / 5.000 wallets

**No se implementó nada de esto en esta fase** (instrucción explícita del encargo) — esto es investigación de qué haría falta, no código.

### Por qué el diseño actual no escala tal cual

- **Solana:** una suscripción `logsSubscribe` por wallet sobre una única conexión WebSocket — con cientos/miles de wallets, el RPC público gratuito puede limitar o cerrar la conexión (documentado ya en `INFORME_TECNICO_FOMO.md`, Fase 2, punto 15.5).
- **Robinhood Chain:** el polling actual hace **2 llamadas `eth_getLogs`** por ciclo, sin importar cuántas wallets se observen (los filtros ya agrupan todas las direcciones en un solo array por posición de topic) — esto escala razonablemente bien en el *fetch* de logs, pero cada transacción detectada dispara además: 1 `eth_getTransactionByHash` + 1 `eth_getTransactionReceipt` + 1 `eth_getBlockByNumber` + hasta 2 `eth_call` por token nuevo (symbol+decimals) — con mucho volumen, esto sí puede saturar un RPC público rápido.

### Qué se necesitaría (en orden de prioridad)

1. **RPC dedicado de pago** (Helius/QuickNode/Alchemy con plan pagado) — imprescindible a partir de ~100 wallets activas, por el volumen de llamadas, no solo por las suscripciones.
2. **gRPC / streaming dedicado** en vez de WebSocket JSON-RPC clásico, donde el proveedor lo ofrezca (Helius LaserStream, Yellowstone gRPC en el ecosistema Solana; proveedores EVM equivalentes) — mucho más eficiente para alto volumen que mantener miles de suscripciones lógicas.
3. **Suscripción a nivel de programa/protocolo, no por wallet:** en vez de N suscripciones (una por wallet), suscribirse a *todos* los eventos `Transfer`/`Swap` de los DEX relevantes y filtrar en el propio proceso contra la lista de wallets de interés — es exactamente lo que hacen en la práctica indexadores como los mencionados en la Fase 1 (Solana Tracker, FomoScan). Esto convierte el problema de "verificar cuidado la programación de escala en credenciales por wallet" en un problema de *throughput* de un solo stream, mucho más manejable.
4. **Cola de procesamiento (worker pool):** separar "detectar una firma/tx nueva" de "descargar+interpretar" — con reintentos y backoff, para no bloquear la detección mientras se interpreta.
5. **Cache/estado en Redis** (o similar) para deduplicación de transacciones ya vistas y para el registro de "última firma/bloque procesado por wallet" — hoy vive solo en memoria del proceso (`seen_tx_hashes`, `last_block`), se pierde al reiniciar.
6. **Base de datos (PostgreSQL)** para persistir cada `NormalizedTrade` generado — necesario para cualquier análisis histórico, ranking de traders, o cálculo de PnL propio (ver Fase 3 propuesta al final de `INFORME_TECNICO_FOMO.md`).
7. **Procesamiento asíncrono end-to-end:** el código actual ya es `async` (asyncio) en ambos adapters, lo cual es la base correcta — pero para 1.000-5.000 wallets probablemente haga falta repartir la carga entre varios procesos/workers (no solo corrutinas de un solo proceso), coordinados vía la cola mencionada en el punto 4.

### Orden de magnitud esperado por escala

| Wallets | RPC | Arquitectura |
|---|---|---|
| ~100 | RPC dedicado, plan de entrada (~$49/mes) | El diseño actual (polling/suscripción + interpretación in-process) probablemente alcanza, ajustando el intervalo de polling |
| ~500 | RPC dedicado, plan medio | Empieza a justificarse una cola simple + un worker separado para interpretación |
| ~1.000 | RPC dedicado + streaming (gRPC/LaserStream) | Suscripción a nivel de protocolo (punto 3) casi obligatoria; Redis para dedupe/estado |
| ~5.000 | RPC dedicado de alto volumen + streaming | Arquitectura completa: cola + varios workers + Postgres + monitoreo de la propia infraestructura |

---

## 12. Qué falta para la siguiente fase

1. **Validar contra transacciones reales** (Solana y Robinhood Chain) en un entorno con acceso a Internet normal — el punto más importante y el primero que hay que hacer antes de confiar en este código con wallets reales.
2. **Confirmar las direcciones de contrato de Robinhood Chain** (WETH, USDG, routers/factories de Uniswap V2/V3/V4, Reactors de UniswapX, feed Chainlink ETH/USD) contra el explorador oficial o la documentación completa (`docs.robinhood.com/chain/protocol-contracts`, no accesible desde este sandbox).
3. **Añadir soporte para Uniswap V4 y UniswapX** una vez confirmadas sus direcciones/arquitectura de eventos.
4. **Implementar la detección de ETH nativo recibido** (vigilar `Withdrawal` de WETH9), cerrando la limitación #4 de la sección 9.
5. **Integrar el oráculo de precio de Chainlink on-chain** (lectura pública, sin credenciales) para completar `usd_value` sin depender de un parámetro manual.
6. **Verificar empíricamente la hipótesis de "misma wallet EVM en todas las chains"** (sección 6.3) con un trader real que haya publicado su información voluntariamente.
7. **Decidir e implementar la capa de persistencia** (Postgres) y el mecanismo de escalado (sección 11) según cuántas wallets se quieran monitorear realmente.
8. Seguir **sin** avanzar hacia ejecución/copy-trading automático — eso permanece fuera de alcance hasta que el usuario lo pida explícitamente, y aun entonces, contra una API oficial de un exchange/DEX elegido por el usuario con sus propias credenciales, nunca contra la cuenta de FOMO ni de Robinhood.

---

## 13. Recomendación de prioridad para Robinhood Chain

**Prioridad: MEDIA.**

**A favor de invertir en ella (no BAJA):**
- Confirmado con evidencia directa que **FOMO ya opera en Robinhood Chain** (URLs reales de `fomo.family/tokens/robinhood/...`), no es una apuesta especulativa.
- Es **totalmente EVM-compatible** — el trabajo de ingeniería hecho aquí (`evm_parser.py`, `robinhood_adapter.py`) es en gran parte **reutilizable para cualquier otra chain EVM** que FOMO soporte (Base, BNB Chain, Monad), con solo ajustar el RPC endpoint y el registro de protocolos conocidos. No es una inversión de un solo uso.
- Tiene **Uniswap y Chainlink integrados desde el día uno**, lo cual da un camino claro para completar precios/USD en el futuro sin depender de terceros no verificados.
- El account abstraction nativo (ERC-4337) coincide con la arquitectura de wallets que FOMO ya usa en otras chains EVM — no es una sorpresa arquitectónica.

**En contra de tratarla como ALTA ahora mismo:**
- **Ninguna dirección de contrato específica de Robinhood Chain se pudo verificar con solidez** en este sandbox — a diferencia de Solana, donde los program IDs de Jupiter/Raydium/Orca se confirmaron con múltiples fuentes cruzadas. Construir más encima de esto sin esa validación es más riesgoso.
- **Cuatro versiones de Uniswap coexistiendo** (V2/V3/V4/UniswapX) es más complejidad de protocolo que todo el ecosistema de Solana cubierto en la Fase 2 junto — y dos de las cuatro (V4, UniswapX) quedan explícitamente sin cubrir todavía.
- **No hay WebSocket público sin credenciales** — cualquier monitoreo en tiempo real de verdad (no polling) ya requiere que el usuario consiga y pague un proveedor de RPC, algo que Solana no exige para empezar.
- Es una chain **mucho más nueva** (mainnet desde julio de 2026) — menos herramientas de terceros maduras, menos volumen histórico, y la propia FOMO probablemente tiene todavía menos traders activos ahí que en Solana (que es donde nació el producto).

**Conclusión práctica:** vale la pena **mantener y madurar** lo construido en esta fase (ya funciona y está testeado), pero el **siguiente esfuerzo de validación con red real** debería priorizarse en el orden: (1) confirmar que Solana sigue funcionando contra transacciones reales — es la chain con más actividad de FOMO y la que tiene el diseño más sólido — y (2) recién después, confirmar direcciones de contrato reales de Robinhood Chain para subir su prioridad a ALTA con confianza. Subir Robinhood Chain a ALTA *antes* de esa validación sería construir sobre una base que este informe no pudo verificar del todo — justo lo que el encargo pidió evitar.
