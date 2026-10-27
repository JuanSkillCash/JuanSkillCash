# Referencia: Bitunix Partnership System API

PDF original entregado por el gerente de cuenta de Bitunix (guardado tal cual en
`docs/bitunix-partner-api.pdf` para no tener que volver a pedírselo a Juan): documenta el
**Partner API** (`https://partners.bitunix.com`), la API de afiliados que Juan ya usa con sus
propias credenciales (`BITUNIX_API_KEY`/`BITUNIX_API_SECRET`, las mismas de
`scripts/bitunix_api.py`). Firma: ver el docstring de `scripts/bitunix_api.py` (SHA1, orden de
parámetros por tipo+suma ASCII del nombre, concatenar solo valores + ApiSecret).

**Ojo**: esto es un API DISTINTO del que usa la Bitácora hoy
(`supabase/functions/trade-journal-sync`, que habla con `fapi.bitunix.com` usando una API key
de solo lectura PERSONAL de cada usuario, firma SHA256 nonce+timestamp+apiKey+params+body). El
Partner API de aquí abajo funciona por UID con las credenciales de Juan — no necesita que el
usuario cree ninguna clave propia.

Todos los endpoints de abajo que dicen "referrals"/"partner's referral" solo devuelven datos de
cuentas conectadas como referidos de Juan (lo mismo que ya exige "Rango de Manada" para conectar
Bitunix) — si el UID no es un referido, la API devuelve `result: false`.

## Ya implementados en `scripts/bitunix_api.py`
- `POST /partner/api/v2/openapi/validateUser` — confirma que un UID es referido real.
- `GET /partner/api/v1/openapi/transAmountList` — volumen de trading por par, paginado.
- `GET /partner/api/v2/openapi/queryPnlAndTradeCnt` — volumen+PnL+conteo de TODOS los referidos
  de una vez (no hace falta pedir uno por uid).

## Endpoints NO usados todavía (encontrados al leer el PDF completo)

### `GET /partner/api/v1/openapi/totalAssetValue`
Saldo total de un UID. Parámetro `uid` (si no se manda, devuelve `false`).
```json
{"code":"0","msg":"suc","result":{
  "uid":123456,"totalAssetValue":"12321.88829211",
  "spotAccounts":"8123.4467453","futuresAccounts":"102093.6769475",
  "copyAccount":"10013.9026497","leadAccount":"9982.8623786"}}
```
Suma spot + futuros + copy-trading + lead-trader en un solo número. **Útil para el "capital
inicial" de la Bitácora sin necesitar la API key personal del usuario** — Juan ya puede
consultar el saldo de cualquier referido con sus propias credenciales.

### `POST /partner/api/v1/openapi/futuresOpenPositions`
Body: `uid` (requerido), `page`, `pageSize` (máx 10000). Posiciones ABIERTAS de un referido:
`positionId, pair, category (LINEAR/INVERSE), side, leverage, marginMode, entryPrice, amount,
margin, timeOpened`.

### `POST /partner/api/v1/openapi/futuresPositionsHistory`
Body: `uid`, `startTime`, `endTime` (rango máx 180 días, formato `yyyy-MM-ddTHH:mm:ssZ`), `page`,
`pageSize`. Posiciones CERRADAS (y su estado), con exactamente lo que necesita
`trade_journal_trades`: `positionId, pair, category, side, leverage, marginMode,
unrealizedPnL, timeOpened, timeClosed, entryPrice, closePrice, positionPnl (realized), ROI,
maxHeld, closeQty, status (Open/Closed)`.
**Esto reemplazaría el `mapPosition()` de `trade-journal-sync/index.ts`, con nombres de campo
confirmados por Bitunix en vez de adivinados contra la doc pública de futuros.**

### `POST /partner/api/v1/openapi/futuresOrdersHistory`
Body: `uid`, `startTime`, `endTime`, `page`, `pageSize`. Historial de ÓRDENES (no posiciones):
`orderId, pair, category, orderType, side, leverage, orderPrice, orderQuantity, avgPrice,
filled, realizedPnL, fee, status, orderTime`. Trae `fee` por orden, pero **no trae
`positionId`** — no hay forma directa de sumar las comisiones de una posición específica desde
aquí (tocaría aproximar por par+ventana de tiempo, nada exacto).

### `POST /partner/api/v1/openapi/futuresTransactionsHistory`
Body: `uid`, `startTime`, `endTime`, `page`, `pageSize`. Fills/ejecuciones:
`orderId, pair, category, side, leverage, avgPrice, filled, closedValue, realizedPnL, fee,
role (MAKER/TAKER), time`. Mismo problema: `fee` sí, `positionId` no.
No se encontró ningún campo de **funding** en todo el documento (ni aquí ni en
`futuresPositionsHistory`) — si Bitunix lo expone, no es por el Partner API.

### Otros (no revisados en detalle, solo su propósito — ver el PDF si hace falta el resto de campos)
- `GET /partner/api/v2/openapi/depositList` — depósitos de los referidos (on-chain, P2P, tarjeta, SEPA, transferencia interna). Rango máx 180 días.
- `GET /partner/api/v1/openapi/activityList` / `communityRegistrationList` — actividades de comunidad que organiza el partner y quién se inscribió.
- `GET /partner/api/v1/openapi/totalCommission` — comisión que ha generado un referido (o todos) para Juan.
- `GET /partner/api/v1/openapi/totalTransaction` — volumen+fee+comisión total por referido, agrupado por tipo de moneda/trading.
- `GET /partner/api/v1/openapi/kycLevel` — estado de verificación KYC de los referidos.
- `POST /partner/api/v1/openapi/spotOrdersHistory` / `spotTransactionHistory` — lo mismo que las de futuros pero para Spot.
- `GET /partner/api/v1/openapi/volume-qualified` — qué referidos cumplieron una meta de volumen en un periodo.
- `GET /partner/api/v1/openapi/userList` — lista de referidos (ya tiene ejemplo de firma en Java dentro del PDF).

## Lo que esto cambia para la Bitácora (sin decidir todavía)

Con `futuresPositionsHistory` + `totalAssetValue`, **Juan podría llenar la Bitácora de
cualquier referido conectado sin que esa persona cree ninguna API key propia** — un robot
(Python + GitHub Actions, mismo patrón que `update_bitunix_volume.py`) con las credenciales de
Juan ya alcanza. Eso simplificaría bastante lo que ya existe (`trade_journal_secrets` cifrado,
Edge Function `trade-journal-sync`, flujo de conectar API key personal) — a cambio de depender
de campos que no incluyen comisiones por posición exacta ni funding. Pendiente decidir con Juan
si vale la pena migrar o dejar las dos rutas (el usuario que quiera más detalle conecta su
propia clave; el que no, igual aparece en la Bitácora por ser referido de Juan).
