# Fixtures de transacciones — de dónde salen y qué tan "reales" son

**Léase antes de confiar en estos datos.**

## Qué son

Cada `*.json` en esta carpeta es una respuesta **sintética** de
`getTransaction` (encoding `jsonParsed`, `maxSupportedTransactionVersion: 0`)
construida a mano para representar un caso realista y típico (compra
limpia, venta limpia, swap sin activo de referencia, transacción fallida,
transferencia simple, ruta multi-hop ambigua, compra en bonding curve).

Se construyeron siguiendo **al detalle el esquema oficial documentado por
Solana**:
- [`getTransaction`](https://solana.com/docs/rpc/http/gettransaction)
- [RPC JSON Structures](https://solana.com/docs/rpc/json-structures) (forma
  exacta de `meta.preTokenBalances`, `postTokenBalances`, `preBalances`,
  `postBalances`, `innerInstructions`, `loadedAddresses`)
- El comportamiento de `jsonParsed` con programas no reconocidos
  (instrucción "partially decoded": `{accounts, data, programId}`) está
  confirmado en el propio issue tracker de Solana:
  [`solana-labs/solana#31701`](https://github.com/solana-labs/solana/issues/31701)

Las direcciones de programa (Jupiter, Raydium, Orca, Pump.fun) y de mint
(USDC, USDT, SOL nativo/wrapped) usadas dentro de estos fixtures son
**reales y verificadas** — ver las citas en `transaction_parser.py` junto a
`KNOWN_PROGRAMS` y `QUOTE_ASSETS`. Las **wallets, cuentas de token, pools y
firmas** son **inventadas** (prefijo `Demo...`), precisamente para no dar a
entender que se está vigilando a ningún trader real.

## Qué NO son

**No son transacciones reales descargadas de la red.** El sandbox donde se
desarrolló este módulo bloquea todo el tráfico saliente a `api.mainnet-beta.solana.com`
(ver `INFORME_TECNICO_FOMO.md`, sección 0, y `prototype/README.md` de la
Fase 1) — no fue posible ejecutar `getTransaction` contra un nodo real ni
para investigar el formato ni para generar estos fixtures. Cada archivo
incluye un campo `_fixture_notes` explicando exactamente qué simula y por
qué los números dan lo que dan (no es un campo real de la respuesta RPC,
es solo documentación interna del fixture).

## Cómo reemplazarlos por transacciones reales

En un entorno con salida a Internet normal:

```bash
curl -s https://api.mainnet-beta.solana.com -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "getTransaction",
  "params": ["<UNA_FIRMA_REAL_AQUI>", {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
}' | python -m json.tool > tests/fixtures/real_example.json
```

Para conseguir una firma real de ejemplo: abrir cualquier wallet conocida
que opere en Jupiter/Raydium/Orca/Pump.fun en un explorador público
(Solscan, Solana Explorer, SolanaFM), copiar la firma de una operación
reciente, y usarla en el comando de arriba. Luego:
1. Añadir una entrada a `manifest.json` con el `wallet` correcto (el
   `owner` que aparece en `preTokenBalances`/`postTokenBalances`, o la
   `accountKeys[0]` si es la propia firmante).
2. Correr `python prototype/transaction_parser.py` (modo demo) para ver
   la interpretación y compararla manualmente contra lo que muestra el
   explorador — esa comparación manual es la validación real que este
   sandbox no pudo hacer.

## Por qué igual vale la pena tenerlos así

El objetivo de esta fase era demostrar y probar la **lógica de
interpretación** (comparación de balances, clasificación BUY/SELL/SWAP/
UNKNOWN, detección de protocolo, cálculo de confidence) contra el esquema
real y documentado de Solana — no depender de que este sandbox concreto
tuviera salida a Internet. Los fixtures cubren las ramas de código que
importan: swap limpio con protocolo reconocido, swap limpio sin protocolo
reconocido (no incluido aún, ver TODO abajo), swap sin activo de
referencia, transacción fallida, transferencia simple, y ruta multi-hop
ambigua. Antes de usar este módulo contra wallets reales, hay que validar
al menos un puñado de fixtures reales descargados como se explica arriba.

**TODO para quien continúe con acceso a red:** añadir un fixture de swap
limpio a través de un programa NO listado en `KNOWN_PROGRAMS` (para
ejercitar la rama `protocol is None` → confidence ~0.65) y un fixture con
una transacción **versionada** (v0) que use una Address Lookup Table real,
para validar el orden de `_resolve_account_keys` (marcado como el punto
más frágil del parser en su propio docstring).
