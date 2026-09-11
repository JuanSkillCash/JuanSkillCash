# fomo-monitor

Investigación técnica + prototipos de **solo lectura** para un futuro monitor
multichain de traders públicos (Solana + Robinhood Chain), motivado
originalmente por FOMO (fomo.family) pero completamente independiente de
esa plataforma (ver `INFORME_TECNICO_FOMO.md`, Fase 1: FOMO no tiene API
pública, y sus Términos de Servicio prohíben scraping/bots — todo lo
construido aquí habla únicamente con infraestructura pública de
blockchain, nunca con FOMO).

**Ninguna fase de este proyecto ejecuta operaciones, conecta wallets
privadas, usa claves privadas, ni se conecta a FOMO.**

## Estructura

```
research/fomo-monitor/
├── prototype/
│   ├── wallet_monitor.py         # Fase 1: detecta firmas nuevas en Solana via RPC público
│   ├── transaction_parser.py     # Fase 2: interpreta transacciones de Solana (BUY/SELL/SWAP/UNKNOWN)
│   ├── multichain_monitor.py     # Fase 3: CLI que ata Solana + Robinhood Chain
│   ├── models/
│   │   └── normalized_trade.py   # Fase 3: esquema comun a todas las chains
│   ├── parsers/
│   │   ├── solana_parser.py      # Fase 3: adapta transaction_parser.py -> NormalizedTrade
│   │   └── evm_parser.py         # Fase 3: interpreta transacciones EVM (Robinhood Chain)
│   ├── chains/
│   │   ├── solana_adapter.py     # Fase 3: envuelve wallet_monitor.py con interfaz uniforme
│   │   └── robinhood_adapter.py  # Fase 3: polling eth_getLogs (+ eth_subscribe opcional)
│   └── README.md                 # detalle de la Fase 1
├── validate/                     # Fase 4: scripts para validar con datos REALES (requieren Internet)
│   ├── fetch_and_validate_solana.py
│   ├── fetch_and_validate_robinhood.py
│   ├── measure_latency.py
│   └── README.md
├── tests/
│   ├── test_transaction_parser.py  # Fase 2 (Solana)
│   ├── test_evm_parser.py          # Fase 3 (Robinhood Chain)
│   ├── test_chain_adapters.py      # Fase 3 (integración, mockeada)
│   ├── test_validate_scripts.py    # Fase 4 (scripts de validate/, RPC mockeado)
│   ├── test_robustness_paso6.py    # Fase 4 (approve/Approval no confundido con trade)
│   └── fixtures/
│       ├── ...                     # transacciones de ejemplo de Solana (sintéticas)
│       └── evm/                    # transacciones de ejemplo EVM (sintéticas)
├── README.md                     # este archivo
├── INFORME_TECNICO_FOMO.md       # informe técnico Fase 1 + Fase 2 (FOMO, Solana)
├── INFORME_MULTICHAIN.md         # informe técnico Fase 3 (Robinhood Chain, arquitectura multichain)
└── FASE_4_VALIDACION_REAL.md     # informe Fase 4 (validación con datos reales: qué se pudo y qué no)
```

## Fase 1 — Monitor on-chain de Solana (`wallet_monitor.py`)

Se conecta al WebSocket JSON-RPC público de Solana y se suscribe
(`logsSubscribe`) a una lista de wallets indicada por el usuario. Cuando
detecta una firma nueva, la imprime (firma, estado, logs). Ver
`prototype/README.md`.

## Fase 2 — Interpretación de operaciones en Solana (`transaction_parser.py`)

Toma una transacción de Solana ya confirmada (`getTransaction`) y la
convierte en un evento normalizado (BUY/SELL/SWAP/UNKNOWN), comparando
`preTokenBalances`/`postTokenBalances`/`preBalances`/`postBalances` — nunca
decodificando instrucciones de cada DEX. Ver sección 2 (Fase 2) de
`INFORME_TECNICO_FOMO.md` para el razonamiento completo.

```bash
cd prototype && python transaction_parser.py            # modo demo offline
python transaction_parser.py <SIGNATURE> <WALLET> [sol_usd_price]  # transacción real
```

## Fase 3 — Arquitectura multichain: Solana + Robinhood Chain

**`transaction_parser.py` y `wallet_monitor.py` no se tocaron** (verificado
con `git diff`) — siguen funcionando exactamente igual que en la Fase 2.
Encima de ellos se agregó:

- **`models/normalized_trade.py`** — el esquema común a cualquier chain:

  ```json
  {
    "chain": "solana | robinhood",
    "wallet": "...", "signature": "...", "timestamp": "...",
    "action": "BUY | SELL | SWAP | UNKNOWN",
    "token_in": "...", "token_in_symbol": "...", "token_in_amount": 0,
    "token_out": "...", "token_out_symbol": "...", "token_out_amount": 0,
    "price": 0, "usd_value": 0, "protocol": "...", "confidence": 0.0
  }
  ```

- **`parsers/evm_parser.py`** — interpreta transacciones EVM (Robinhood
  Chain) con el mismo principio que Solana: compara eventos `Transfer`
  ERC-20 (`receipt.logs`) antes/después en vez de decodificar la
  instrucción de cada DEX (Uniswap V2/V3/V4/UniswapX coexisten en
  Robinhood Chain — ver `INFORME_MULTICHAIN.md`, sección 3). Identifica
  activos "quote" (ETH/WETH/USDG/USDC/USDT) **por símbolo** (`eth_call` a
  `symbol()`), no por dirección hardcodeada, porque esas direcciones no se
  pudieron verificar con la misma solidez que en Solana (ver limitaciones).

- **`chains/robinhood_adapter.py`** — monitoreo en tiempo real vía
  **polling `eth_getLogs`** contra el RPC público oficial
  (`rpc.mainnet.chain.robinhood.com`, sin API key), con un modo
  `eth_subscribe`/WebSocket opcional para cuando el usuario tenga su
  propio proveedor con su propia key (nunca hardcodeada aquí).

- **`chains/solana_adapter.py`** / **`parsers/solana_parser.py`** —
  envuelven la Fase 1/2 (sin modificarlas) para exponer la misma interfaz
  (`watch(addresses, on_trade)` → `NormalizedTrade`) que el lado EVM.

### Ejecutar

```bash
cd prototype
python multichain_monitor.py solana <WALLET_SOL_1> [WALLET_SOL_2 ...]
python multichain_monitor.py robinhood <WALLET_0x...> [--poll-interval 5] [--native-usd-price 3000]

# ambas chains a la vez:
python multichain_monitor.py --chain solana:<WALLET_SOL> --chain robinhood:<WALLET_0x>
```

Ver `INFORME_MULTICHAIN.md` para: qué es Robinhood Chain, cómo monitorearla,
qué protocolos se detectan, cómo relacionar la wallet EVM de un trader de
FOMO across chains, diferencias Solana vs. Robinhood Chain, limitaciones,
costos aproximados, escalabilidad (100–5.000 wallets) y la recomendación de
prioridad final.

## Fase 4 — Validación con datos reales (`validate/`)

Scripts listos para correr **con Internet real** (este sandbox no la tiene,
ver `FASE_4_VALIDACION_REAL.md` sección 0): traen transacciones reales de
una wallet (Solana vía `getSignaturesForAddress`+`getTransaction`,
Robinhood Chain vía `eth_getLogs`+`eth_getTransactionByHash`+`eth_getTransactionReceipt`),
las corren por los parsers sin modificarlos, y muestran **RAW vs PARSER**
lado a lado. Incluye también `measure_latency.py` (mide en vivo cuánto
tarda el sistema entre confirmación on-chain y interpretación completa).

```bash
python validate/fetch_and_validate_solana.py <WALLET_SOLANA> --limit 5
python validate/fetch_and_validate_robinhood.py <WALLET_0x...> --limit 5
python validate/measure_latency.py solana <WALLET_SOLANA>
```

Ver `validate/README.md` (cómo correrlos, cómo conseguir una wallet real de
un trader de FOMO de forma legítima) y `FASE_4_VALIDACION_REAL.md` (qué se
pudo y qué no se pudo validar en este sandbox, y por qué).

## Tests

```bash
python -m unittest discover -s tests -v
```

**53 tests, 100% offline** (24 Solana + 20 EVM + 2 de integración de chain
adapters + 4 de los scripts de `validate/` con RPC mockeado + 3 de
robustez Fase 4 — aprobación/allowance en ambas chains), contra fixtures
sintéticos documentados en `tests/fixtures/README.md` y
`tests/fixtures/evm/README.md` — ambos explican por qué son sintéticos y
cómo reemplazarlos por transacciones reales en un entorno con red.

## Limitaciones conocidas

Ver `INFORME_TECNICO_FOMO.md` sección 0 (Fase 1) e `INFORME_MULTICHAIN.md`
sección 9 (Fase 3): este proyecto se desarrolló en un sandbox sin salida de
red a servicios externos, así que nada aquí fue probado contra RPC real en
vivo (ni Solana ni Robinhood Chain) — solo contra fixtures que replican
fielmente el esquema oficial documentado. Antes de usarlo contra wallets
reales, validar con transacciones reales descargadas fuera de este sandbox.
