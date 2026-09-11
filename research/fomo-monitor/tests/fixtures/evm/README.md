# Fixtures EVM (Robinhood Chain) — de dónde salen y qué tan "reales" son

Mismo enfoque y misma honestidad que `tests/fixtures/README.md` (Solana):
**estos fixtures son sintéticos**, construidos a mano siguiendo el esquema
estándar de `eth_getTransactionByHash` / `eth_getTransactionReceipt`
documentado en [ethereum.org/developers/docs/apis/json-rpc](https://ethereum.org/en/developers/docs/apis/json-rpc/)
(métodos universales de EVM, no específicos de Robinhood Chain). **No se
descargaron en vivo** — el mismo bloqueo de red de este sandbox que impidió
hacerlo para Solana (ver `INFORME_TECNICO_FOMO.md`, sección 0) tampoco
permitió alcanzar `rpc.mainnet.chain.robinhood.com`.

## Qué SÍ es real y verificado

- El **formato exacto** de `tx` y `receipt` (campos `hash`, `from`, `to`,
  `value`, `status`, `logs[].address/topics/data`).
- El **topic0 del evento `Transfer(address,address,uint256)`** ERC-20:
  `0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef`
  (constante universal de EVM, confirmada vía búsqueda web).
- El **topic0 del evento `Swap` de Uniswap V3**:
  `0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67`
  (confirmado vía búsqueda web).
- La **dirección canónica del EntryPoint ERC-4337 v0.7**:
  `0x0000000071727De22E5E9d8BAf0edAc6f37da032` (desplegada de forma
  determinística, misma dirección en cualquier chain EVM que la tenga —
  confirmado vía búsqueda web, aunque no se verificó por consulta RPC
  directa que ya esté desplegada en Robinhood Chain específicamente).
- Que Robinhood Chain (chain ID 4663) es EVM-compatible y que Uniswap
  v2/v3/v4 + UniswapX están desplegados ahí desde el lanzamiento —
  confirmado vía `blog.uniswap.org/robinhood-chain-is-live` y
  `developers.uniswap.org`.

## Qué NO es real / qué está marcado como incierto

- **Todas las direcciones de wallet, tokens (USDG/WETH/MEME de ejemplo),
  pools y router** son inventadas (prefijos `0x1111...`, `0xaaaa...`,
  etc.) — no representan ninguna wallet ni contrato real.
- El **topic0 del evento `Swap` de Uniswap V2**
  (`0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822`,
  usado en `uniswap_v2_sell_token_to_weth.json`) **no se confirmó con una
  fuente que mostrara el hash explícito** en esta sesión — viene de
  conocimiento de entrenamiento, marcado así también en
  `prototype/parsers/evm_parser.py`. Antes de confiar en él en producción,
  verificar contra [github.com/otterscan/topic0](https://github.com/otterscan/topic0)
  o directamente contra una transacción real de Uniswap V2.
- **Ninguna dirección de contrato específica de Robinhood Chain** (el
  USDG real, el WETH real, el router/factory real de Uniswap en esa
  chain) se usa en el código de `evm_parser.py` — por diseño (ver el
  docstring del módulo): la identificación de "quote assets" se hace por
  **símbolo** (`USDG`, `WETH`, `USDC`, `USDT`, `ETH`), no por dirección,
  precisamente porque esas direcciones no se pudieron confirmar con
  suficiente solidez en este sandbox. Los fixtures reflejan eso: cada uno
  trae un `token_registry` en `manifest.json` que simula la resolución de
  `symbol()`/`decimals()` (como si ya se hubiera hecho un `eth_call` real),
  en vez de depender de una tabla de direcciones fija.
- `erc4337_userop_buy.json` simula una UserOperation, pero el log del
  EntryPoint usa un `topic0` inventado (no el hash real de
  `UserOperationEvent`) — el código de `evm_parser.py` no depende de ese
  hash para detectar el EntryPoint (solo mira `log.address`), así que no
  afecta la validez del test, pero tampoco hay que asumir que ese topic0
  es el real.

## Cómo reemplazarlos por transacciones reales

```bash
curl -s https://rpc.mainnet.chain.robinhood.com -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionByHash", "params": ["<HASH_REAL>"]
}' | python -m json.tool

curl -s https://rpc.mainnet.chain.robinhood.com -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionReceipt", "params": ["<HASH_REAL>"]
}' | python -m json.tool
```

Una firma real de ejemplo puede obtenerse abriendo cualquier transacción
reciente en el explorador oficial (`robinhoodchain.blockscout.com`),
copiando su hash. Para el `token_registry`, resolver `symbol()`/`decimals()`
en vivo es exactamente lo que hace
`prototype.parsers.evm_parser.make_rpc_token_resolver(rpc_url)` — se puede
usar ese mismo resolver contra un fixture real para poblar el registro
automáticamente antes de fijarlo en el JSON de test.

## TODO para quien continúe con acceso a red

- Confirmar el topic0 real de `Swap` de Uniswap V2 contra una transacción
  real (o contra `otterscan/topic0`).
- Añadir un fixture de Uniswap V4 (arquitectura de singleton `PoolManager`,
  evento `Swap` distinto y emitido por una sola dirección para todos los
  pools) y de UniswapX (settlement basado en "Reactor" contracts) — ninguno
  de los dos está cubierto todavía por `KNOWN_EVENT_SIGNATURES`, ver
  limitación documentada en `INFORME_MULTICHAIN.md`.
- Confirmar contra el explorador oficial las direcciones reales de USDG,
  WETH y los routers/factories de Uniswap en Robinhood Chain mainnet (no
  testnet), y decidir si vale la pena añadirlas como *hint* opcional junto
  a la resolución por símbolo (nunca como reemplazo de ella).
