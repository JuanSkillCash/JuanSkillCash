# Prototipo: monitor on-chain de solo lectura

Complementa `research/fomo-monitor/INFORME_TECNICO_FOMO.md`. Lee ese informe
primero, en especial la sección 0 (limitaciones) y la 11 (por qué el
prototipo es genérico y no específico de FOMO).

## Qué es

Un script (`wallet_monitor.py`) que se conecta **únicamente** al endpoint
WebSocket JSON-RPC público oficial de Solana
(`wss://api.mainnet-beta.solana.com`, sin API key) y usa el método estándar
`logsSubscribe` para recibir en tiempo real las firmas de transacción que
mencionan una o más direcciones de wallet indicadas por el usuario.

Es la única pieza de la cadena de valor "detectar operaciones de un trader"
que se pudo construir contra un endpoint **público, oficial y documentado**
(la infraestructura RPC de la propia red Solana), sin asumir ni inventar
ningún endpoint de fomo.family.

## Qué NO hace

- No se conecta a fomo.family, a `fomoapi.io`, a `fomoscan.sh` ni a ningún
  otro servicio no verificado directamente en esta investigación.
- No firma transacciones, no ejecuta órdenes, no requiere clave privada,
  seed phrase ni API key de ningún tipo.
- No decide automáticamente qué wallets observar — eso lo decide el
  usuario, fuera de este script, con la información que considere legítima
  (ver sección 10.4 del informe).

## Requisitos

```bash
pip install websockets
```

## Uso

```bash
python wallet_monitor.py <WALLET_1> [WALLET_2 ...]
```

Ejemplo de humo (smoke test) con una dirección pública conocida
(el System Program de Solana, solo para comprobar que la conexión y el
parseo de eventos funcionan — no es la wallet de ningún trader):

```bash
python wallet_monitor.py 11111111111111111111111111111111
```

## Nota sobre pruebas

**Este script no se pudo ejecutar dentro del sandbox usado para esta
investigación**, porque su política de red bloquea el tráfico saliente a
dominios externos (incluido `api.mainnet-beta.solana.com`) — ver sección 0
del informe técnico para el detalle del bloqueo. El código sigue el
protocolo JSON-RPC/WebSocket documentado oficialmente por Solana
(`solana.com/docs/rpc/websocket/logssubscribe`), pero debe validarse en un
entorno con salida a Internet normal antes de darlo por bueno en
producción.

## Siguiente paso lógico (no implementado aquí)

Para convertir esto en un monitor de "traders de FOMO" real, falta —y es
una decisión explícita del usuario, no algo que deba resolverse en este
prototipo— una fuente **legítima** de mapeo *handle de FOMO → dirección de
wallet* (autodeclaración del trader, o un servicio de verificación de
terceros aceptado bajo su propio riesgo). Ese mapeo es el único insumo que
falta para reutilizar este mismo script con wallets reales de traders de
FOMO, sin tocar en ningún momento los sistemas privados de FOMO.
