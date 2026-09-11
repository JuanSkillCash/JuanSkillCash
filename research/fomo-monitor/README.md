# fomo-monitor

Investigación técnica + prototipos de **solo lectura** para un futuro monitor
de traders públicos en Solana, motivado originalmente por FOMO
(fomo.family) pero completamente independiente de esa plataforma (ver
`INFORME_TECNICO_FOMO.md`, Fase 1: FOMO no tiene API pública, y sus Términos
de Servicio prohíben scraping/bots — todo lo construido aquí habla
únicamente con infraestructura pública de blockchain, nunca con FOMO).

**Ninguna fase de este proyecto ejecuta operaciones, conecta wallets
privadas, usa claves privadas, ni se conecta a FOMO.**

## Estructura

```
research/fomo-monitor/
├── prototype/
│   ├── wallet_monitor.py       # Fase 1: detecta firmas nuevas de wallets via RPC público
│   ├── transaction_parser.py   # Fase 2: interpreta esas firmas como BUY/SELL/SWAP/UNKNOWN
│   └── README.md               # detalle de la Fase 1
├── tests/
│   ├── test_transaction_parser.py
│   └── fixtures/                # transacciones de ejemplo (sintéticas, ver fixtures/README.md)
├── README.md                    # este archivo
└── INFORME_TECNICO_FOMO.md      # informe técnico completo (Fase 1 + Fase 2)
```

## Fase 1 — Monitor on-chain (`wallet_monitor.py`)

Se conecta al WebSocket JSON-RPC público de Solana y se suscribe
(`logsSubscribe`) a una lista de wallets indicada por el usuario. Cuando
detecta una firma nueva, la imprime (firma, estado, logs) — sin interpretar
todavía qué operación representa. Ver `prototype/README.md`.

## Fase 2 — Interpretación de operaciones (`transaction_parser.py`)

Toma una transacción ya confirmada (obtenida con `getTransaction`) y la
convierte en un evento normalizado:

```json
{
  "wallet": "...",
  "signature": "...",
  "timestamp": "...",
  "action": "BUY",
  "token_in": "...",
  "token_in_amount": 0,
  "token_out": "...",
  "token_out_amount": 0,
  "estimated_price": 0,
  "estimated_usd_value": 0,
  "protocol": "...",
  "confidence": 0.0
}
```

La lógica **nunca asume** que un cambio de balance es una compra o venta:
compara `preTokenBalances`/`postTokenBalances` (SPL) y `preBalances`/
`postBalances` (SOL) antes y después de la transacción, y solo clasifica
como BUY/SELL/SWAP cuando exactamente dos activos cambiaron de forma neta
para esa wallet. Cualquier otro caso (transacción fallida, una sola pata,
más de dos activos, wallet no involucrada) se marca `UNKNOWN` en vez de
inventar un resultado. Ver los comentarios extensos en el propio
`transaction_parser.py` y la sección 2 (Fase 2) de `INFORME_TECNICO_FOMO.md`
para el razonamiento completo.

### Ejecutar

```bash
cd prototype
python transaction_parser.py
```

Sin argumentos corre en **modo demo offline**: interpreta los 7 fixtures de
`tests/fixtures/` y muestra la salida legible de cada uno — no requiere red.

Con una transacción real (requiere salida a Internet hacia el RPC público
de Solana):

```bash
python transaction_parser.py <SIGNATURE> <WALLET_ADDRESS> [sol_usd_price]
```

### Conectar Fase 1 + Fase 2

```bash
pip install websockets
python wallet_monitor.py --interpret --sol-usd-price 150.0 <WALLET_1> [WALLET_2 ...]
```

Pipeline exacto que implementa `--interpret`:

```
NUEVA TRANSACCIÓN (logsNotification del WebSocket)
        ↓
OBTENER DETALLES (getTransaction, RPC HTTP público)
        ↓
INTERPRETAR (transaction_parser.interpret_transaction)
        ↓
BUY / SELL / SWAP / UNKNOWN
        ↓
MOSTRAR ALERTA (consola)
```

Sin `--interpret`, `wallet_monitor.py` se comporta exactamente igual que en
la Fase 1 (compatibilidad hacia atrás intencional).

## Tests

```bash
python -m unittest discover -s tests -v
```

24 tests, 100% offline, contra los fixtures documentados en
`tests/fixtures/README.md` (que también explica por qué son sintéticos y
cómo reemplazarlos por transacciones reales en un entorno con red).

## Limitaciones conocidas

Ver `INFORME_TECNICO_FOMO.md` sección 0 (Fase 1) y la sección de Fase 2
correspondiente: este proyecto se desarrolló en un sandbox sin salida de
red a servicios externos, así que nada aquí fue probado contra el RPC real
de Solana en vivo — solo contra fixtures que replican fielmente el esquema
oficial documentado. Antes de usarlo contra wallets reales, validar con al
menos algunas transacciones reales descargadas fuera de este sandbox.
