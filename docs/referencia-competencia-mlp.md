# Referencia técnica: Arsenal, Rangos y Gamificación de Marines Live Platform (melapela.ai)

> Investigación de código en vivo (navegador real, DevTools: pestaña Network + Sources) hecha
> por Juan en su propia cuenta de esa plataforma, noviembre 2026. Complementa a
> `docs/inspiracion-melapela.md` (que son ideas/diseño de alto nivel): este documento trae
> endpoints reales, campos JSON tal cual los devuelve su API, y fórmulas/constantes copiadas
> literal de su bundle de JS minificado donde fue legible.
>
> **Esto es material de referencia para diseñar la versión propia de SkillCash — no se copia
> texto, imágenes, nombres propios ni código de ellos.** Lo marcado "NO CONFIRMADO" es
> inferencia o no se pudo verificar; no tratarlo como hecho al diseñar nada sobre esto.

---

Quiero construir en mi sitio SkillCash un sistema de herramientas desbloqueables por volumen de trading, rangos por volumen mensual y una economía de puntos gamificada, tomando como referencia el análisis técnico que hice de la plataforma "Marines Live Platform" (melapela.ai), donde tengo cuenta propia. Abajo está TODO lo que se observó: endpoints, campos JSON reales, constantes y fórmulas extraídas del bundle de JS del cliente. Lo marcado "NO CONFIRMADO" es inferencia o no se pudo ver; no lo trates como hecho.

Usa esto como especificación de referencia para diseñar mi propia versión (mis nombres, mi marca, mis umbrales). No copies textos, imágenes ni nombres propios de ellos.

---

## 0. Arquitectura observada

- Frontend: Next.js (App Router, build Turbopack, chunks en `/_next/static/immutable/chunks/*.js`, minificados). Analítica: Microsoft Clarity + Vercel Insights.
- Backend: API REST separada en `https://api.melapela.ai` (estilo NestJS: errores `{"statusCode":401,"message":"Unauthorized","path":...,"timestamp":...}`).
- Auth: JWT en header `Authorization: Bearer <token>` guardado en memoria del cliente (NO por cookie: un fetch con `credentials:'include'` sin header da 401). Hay `GET /auth/refresh` al cargar. El rol se lee decodificando el payload del JWT en el cliente (`role`: `guest | user | mod | admin | dev | soporte | soporte_bitget | streamer`).
- Data fetching tipo React Query (hooks por recurso). Polling: `/sorteo/ruleta/active` se consulta aprox. cada ~12 s.
- Al cargar `/panel` se hacen en paralelo: `/auth/refresh`, `/notifications`, `/notifications/unread-count`, `/sorteo/ruleta/active`, `/bitget-transition/mine`, `/promo-banners/active`, `/directos`, `/cubierta/me`, `/auth/onboarding/status`, `/telegram/users/monthly`, `/telegram/users`, `/referrals/boosts/me`, `/sorteo/race/check-in`, `/users/{id}/avatar`, `/users/me/exchanges`, `/telegram/users/trial-status`. También prefetch de rutas RSC (`/panel/radar`, `/panel/bitacora`, `/panel/cubierta`, `/panel/noticias`, `/panel/boosts`, `/panel/games`).
- Rutas del panel encontradas en el bundle: `/panel`, `/panel/radar`, `/panel/radar/seguimiento`, `/panel/bitacora`, `/panel/cubierta` (+ `/i/`, `/p/`, `/u/`), `/panel/noticias`, `/panel/boosts`, `/panel/bonos`, `/panel/games`, `/panel/games/btc-5-minutos`, `/panel/carrera`, `/panel/prediccion`, `/panel/rangos`, `/panel/referidos`, `/panel/sorteo`, `/panel/sorteo/ruleta`, `/panel/ganadores`, `/panel/votaciones`, `/panel/bitget`, `/panel/faq`, `/panel/soporte`, `/panel/tickets` (y admin: `/panel/usuarios`, `/panel/kanban`, `/panel/metrics`, `/panel/metrics/tokenomics`).

---

## 1. Volumen: de dónde sale el número que desbloquea todo

### Endpoints
- `GET /telegram/users` → `{"items":[{"id","telegramChatId","bitunixUid","tradingviewUsername","thisMonthVolume","allVolume","volumeMonth":"2026-07","volumeUpdatedAt","monthlyVolumes":[],"createdAt","updatedAt"}],"total","page","pageSize"}` — volumen REAL reportado por el exchange (Bitunix) vía UID de afiliado.
- `GET /telegram/users/monthly` (volumen mensual; cuerpo no capturado, requiere Bearer).
- `GET /auth/onboarding/status` → incluye `volumeReal`, `volumeBoost`, `volumeEffective`, `previousMonthEffective`, `lastTradeAt`, `almiranteVitalicio` (bool: rango máximo vitalicio), `bitunixVerified`, `bitgetStatus`, `tradingViewUser`, `telegramLinked`, `telegramBot`, `role`, `roleId`, `referredBy`, `youtubeChannelId`, `micaConsent`, `status:"completed"`.
- `GET /referrals/boosts/me` → `{"realVolume":0,"boostVolume":0,"effectiveVolume":0,"period":"2026-07","active":[]}`
- `GET /referrals/boosts/me/history` → `{"userId","summary":{realVolume,boostVolume,effectiveVolume,period},"active":[],"history":[]}`
- `GET /users/me/exchanges` (exchanges vinculados; cuerpo no capturado).

### Fórmula del volumen efectivo (código legible del bundle)
```js
function resolveVolume({ boostsEffective, statusVolumeEffective, realVolume }) {
  return typeof boostsEffective === "number" && boostsEffective >= 0 ? boostsEffective
       : typeof statusVolumeEffective === "number" && statusVolumeEffective >= 0 ? statusVolumeEffective
       : realVolume;
}
// currentVolume = resolveVolume({
//   boostsEffective: /referrals/boosts/me .effectiveVolume,
//   statusVolumeEffective: /auth/onboarding/status .volumeEffective,
//   realVolume: /telegram/users items[0].thisMonthVolume })
```
- `effectiveVolume = realVolume + boostVolume` (texto UI: "Volumen real (lo que el exchange reporta) + Boost extra (referidos y promociones) = Total efectivo (lo que desbloquea herramientas)"). El boost solo existe en el panel/bot; no cambia comisiones.
- Todo es MENSUAL (campo `period`/`volumeMonth` = `YYYY-MM`). Reset el día 1, 00:00 UTC. Se suma volumen de Bitunix + el "contabilizado" de Bitget.
- NO CONFIRMADO: frecuencia de sincronización con el exchange (se ve `volumeUpdatedAt`, parece batch, no tiempo real).

---

## 2. Arsenal (herramientas desbloqueables)

### Constante exacta del bundle
```js
const TOOLS = [
  { id: "calculadora", name: "Calculadora",     unlockAt: 0 },
  { id: "radar",       name: "Radar",           unlockAt: 1 },       // "1 trade al mes"
  { id: "cubierta",    name: "La Cubierta",     unlockAt: 1 },       // "1 trade al mes"
  { id: "bitacora",    name: "Bitácora",        unlockAt: 10000 },
  { id: "mapa",        name: "Mapa Tendencial", unlockAt: 50000 },
  { id: "sniper",      name: "Sniper",          unlockAt: 100000 },  // señales de 1m
  { id: "tendencial",  name: "Tendencial",      unlockAt: 150000 },
  { id: "tactical",    name: "Tactical",        unlockAt: 300000 },
];
const unlockedTools = vol => TOOLS.filter(t => vol >= t.unlockAt);
```
- El contador "5/7 herramientas" EXCLUYE la Calculadora (siempre libre). El Arsenal del Home usa otra lista de 7 (ids `radar, cubierta, bitacora, mapa-btc, sniper, tendencial, tactical`) con imágenes por estado `active | disabled | paused`.
- "1 trade" se modela como umbral `unlockAt: 1` (USD 1 de volumen).
- Estado de cada herramienta (código):
```js
status = starterActive ? "active" : currentVolume >= unlockAt ? "paused" : "disabled";
```
  NO CONFIRMADO qué es exactamente `starterActive` (parece ligado al bot de Telegram / trial: existe `/telegram/users/trial-status`). Observado: con volumen $0 la UI mostraba Radar y La Cubierta como "Activo".

### Ventana libre de inicio de mes (código + texto UI)
- Días 1 a 3 de cada mes: Bitácora, Mapa Tendencial, Sniper y La Cubierta (publicar/comentar) abiertos 72 h sin volumen mínimo; cierra 00:00 UTC del día 4.
- En código: `FREE_WINDOW_TOOLS = new Set(["bitacora","mapa-btc","sniper"])`; si la ventana está activa y la próxima herramienta está en ese set, el mensaje es "freeWindow" en vez de "te faltan $X".
- NO CONFIRMADO si el servidor o el cliente decide la ventana (no se encontró el cálculo de fecha; probablemente servidor).

### Anillo "Tu progreso" (código)
```js
const next = TOOLS_7.find(t => vol < t.unlockAt);
const target = next?.unlockAt ?? 300000;
const pct = Math.min(100, Math.round(vol / target * 100));
// SVG: circunferencia = 2*Math.PI*52; strokeDashoffset = C*(1 - pct/100)
```
Mensajes: si la próxima es radar → "Te falta 1 trade para desbloquear Radar y La Cubierta"; si no → "toUnlockTool {amount: next.unlockAt - vol, tool}". Formato de montos: `>=1e6 → $X.XM`, `>=1e3 → $XK`, si no `$X`.

### Barra de volumen del Home
Hitos dibujados: 1 trade · 10.000 · 50.000 · 100.000 · 150.000 · 300.000 (con ícono de cada herramienta).

---

## 3. Herramientas una por una

### 3.1 Radar (unlockAt 1) — señales en vivo
- Rutas: `/panel/radar` (Radar en Vivo) y `/panel/radar/seguimiento` (Operaciones Activas).
- `GET /telegram/signals/active` → array de señales:
  `id, opId, symbol, timeframe, action, entryPrice, slPrice, leverage, tpList[{price,timeframe,profit_pct}], dca{e1_pct,e2_pct,e3_pct,enabled,e1_price,e2_price,e3_price,num_entries}, winrate, points, createdAt, expiresAt, currentEntryPrice, beReached, tpsHit[], dcaFills[], lastEventAt, captainOpen`
  Ejemplo real: `{"symbol":"PONSUSDT.P","timeframe":"1m","action":"LONG","entryPrice":0.2027,"slPrice":0.2016262148,"leverage":50,"tpList":[{"timeframe":"1h","profit_pct":6.96},{"timeframe":"4h","profit_pct":22.2},{"timeframe":"1d","profit_pct":79.97}],"dca":{"e1_pct":20,"e2_pct":30,"e3_pct":50,"enabled":true,"num_entries":3},"winrate":67,"points":"3/3"}`
- `GET /telegram/operations/closures?days=7` → `opId, symbol, timeframe, action, tpsHitAtClose[], beReachedAtClose, dcaFillsAtClose[] (ej. ["E2"]), closedReason ("sl" | "time" observados), expiresAt, createdAt, closedAt`.
- `GET /telegram/signals/locked` → `[]` (señales bloqueadas por rango/volumen; vacío en mi cuenta).
- `GET /telegram/signals/recent-count` → número (ej. `832`).
- `GET /telegram/cryptos-detected?page=1&pageSize=100` → `{"items":[{"id","symbol","createdAt","lastSignalAt"}],"total":54,...}` (universo de 54 pares vigilados).
- `GET /telegram/crypto-votings/active` y `/latest-banner` (votación de cryptos a vigilar; vacío).
- `GET /signal-subscriptions` → `{"items":[]}` (suscripciones a alertas por par).
- Patrones medidos en 8 señales activas (DERIVADO de los datos, no del código):
  - `leverage` siempre 50. Timeframes vistos: 1m, 3m, 5m.
  - `opId` = `SYMBOL_TF_SIDE_<unixSeconds>_<random>`.
  - Expiración: 1m → 30 min; 5m → 60 min.
  - DCA: 3 entradas con pesos fijos 20/30/50 %; E2 y E3 equiespaciadas (E3 = 2× la distancia de E2), distancia variable por señal (0,035 %–0,56 %) → probablemente basada en volatilidad/ATR (NO CONFIRMADO).
  - SL a ~2,3–3,3× la distancia de un paso DCA desde la entrada (0,095 %–1,85 %).
  - TPs = niveles de timeframes superiores (1h/4h/1d); `profit_pct` = % de movimiento de precio sin apalancamiento. Se omiten TPs que no aplican.
  - `points: "3/3"` coincide con el "pts x/3" del Mapa Tendencial (confluencia).
  - Cierres en 7 días (muestra): 15 por `sl`, 4 por `time`.

### 3.2 La Cubierta (unlockAt 1) — red social de trading
- `GET /cubierta/me` → `{"user":{id,username},"canPost":true,"canComment":true,"canCreateItercom":false,"itercomLock":{"reason":"rank"},"effectiveVolume":0,"rank":{"name":"Polizonte","min":0},"followerCount","followingCount","telegramLinked","latestPostAt","maxReservableRankMin":300000,"canPostLinks":false}` → los permisos vienen calculados del servidor según rango/volumen.
- `GET /cubierta/feed` → `{"posts":[{id, body, hasImage, hasImage2, hasImage3, imageToken, createdAt, editedAt, exclusiveRank{name,min}, locked, author{username, avatarUrl, rank, rankMin, followerCount, hitRate, followedByMe, notifyEnabled, referralCode}, likeCount, likedByMe, commentCount, donationTotal, isMine, canDelete, canSetExclusivity, reportedByMe, call, poll, repostCount, impressionCount, reachCount, repostedByMe, repostOfId, repostOf}]}` → posts exclusivos por rango (`exclusiveRank`, `locked`), donaciones, "calls" con hitRate del autor, encuestas, reposts.
- `GET /cubierta/calls/best` → `[{postId,userId,username,name,avatarUrl,symbol,direction,entryPrice,horizon:"7d",openedAt,closedAt,pnlPct,exclusive}]` (ranking de mejores calls).
- `GET /cubierta/calls/open` → `[]`. Otros en bundle: `/cubierta/calls/symbols`, `/calls/prices`, `/calls/price/{sym}`, `/calls/mine`, `/calls/best-traders`, `/calls/stats/{user}`, `/cubierta/me/earnings`, `/cubierta/impressions`, `/cubierta/follow/{id}`, `/cubierta/comments/{id}`, `/cubierta/users/search`.
- Itercom (salas en vivo): `GET /cubierta/itercom/live` → `{"items":[],"scheduled":[{id,title,mode:"abierto",minRank:1,minRankName:"Grumete",status:"scheduled",host{...,rank,rankMin},participantCount,startedAt,expiresAt,scheduledFor,endedAt,endReason,isHost,canModerate,canEnd,canJoin,participants[]}]}` → acceso a salas filtrado por índice de rango mínimo; crear sala bloqueado por rango (`itercomLock.reason:"rank"`). NO CONFIRMADO desde qué rango se puede crear (`maxReservableRankMin: 300000` sugiere que se puede reservar exclusividad hasta Teniente).

### 3.3 Bitácora (unlockAt 10.000) — diario de trading
- `GET /bitacora/trades` → `[]` (diario propio).
- `GET /bitacora/capitals` → `[{"yearMonth":"2026-08","capital":84,"updatedAt"}]` (capital declarado por mes).
- `GET /bitacora/capitan?month=YYYY-MM` → bitácora del "Capitán" (trader líder) para copiar:
  `{"enabled","subscribed","telegramLinked","telegramSubscribed","month","isCurrentMonth","capital":{"inicial":100000,"actual":99104,"pnlMes":-896},"trades":[{id,crypto,type:"LONG",tf:"1m",margin,risk,leverage,capUsed,riskAmount,opId,openDate,closeDate,result:"LOSS",pnl,closed,protected,partialPnl,closedAt,createdAt,updatedAt}]}`
- Fórmulas DERIVADAS de los valores reales:
  - `riskAmount = capital.inicial * risk / 100` (100000 × 0,5 % = 500; × 0,33 % = 330).
  - `capUsed = margin`.
  - `pnl` se guarda en valor absoluto y el signo lo da `result` (WIN/LOSS): `pnlMes = Σ(±pnl)` → −(496 + 400) = −896; `actual = inicial + pnlMes`.
  - `opId` enlaza el trade con la señal del Radar.

### 3.4 Mapa Tendencial (unlockAt 50.000) — confluencia multi-timeframe
- `GET /telegram/mtf-map/{SYMBOL}` (ej. `BTCUSDT.P`) → `{"symbol","currentPrice":"77590.40","bullScore":4,"bearScore":4,"bullPct":"50.00","bearPct":"50.00","sentiment":"NEUTRAL","timeframes":[{"tf":"1m","dir":"BEAR","pts":0,"signal":"ESPERANDO","tendencial_price":77667.63}, ... 3m,5m,15m,1h,4h,8h,1d],"updatedAt"}`
- `GET /telegram/mtf-map/{SYMBOL}/klines?interval=1h&limit=200[&endTime=]` → `[{time(unix s),open,high,low,close,...}]` para el gráfico (TradingView Lightweight Charts).
- Lógica VERIFICADA con los datos: `dir = currentPrice > tendencial_price ? "BULL" : "BEAR"` en los 8 TF; `bullScore = #TF en BULL`; `bullPct = bullScore/8*100`. El gráfico dibuja una línea horizontal por TF en `tendencial_price` con etiqueta `"<tf> <pts>/3"` (verde si BULL, rojo si BEAR).
- `pts` (0–3) y `signal` ("ESPERANDO" | "LONG" | …): se ve `1d pts 1 → LONG`. NO CONFIRMADO cómo se acumulan los 3 puntos ni los umbrales de `sentiment` (BULLISH/BEARISH) más allá de 50 % = NEUTRAL. NO CONFIRMADO qué cálculo produce `tendencial_price` (parece una media/línea de tendencia por TF, calculada en servidor).

### 3.5 Sniper (unlockAt 100.000) — señales de 1 minuto
- No aparece como tarjeta en el grid del Arsenal, sí como ícono (🎯) en la fila de herramientas. Liberado en la ventana de días 1–3.
- NO CONFIRMADO endpoint propio: lo más probable es que sean las señales `timeframe:"1m"` de `/telegram/signals/active` filtradas por permiso (y `/telegram/signals/locked` para las bloqueadas).

### 3.6 Tendencial (unlockAt 150.000) y 3.7 Tactical (unlockAt 300.000)
- Bloqueadas en mi cuenta: la tarjeta no abre nada ni dispara llamadas.
- En el bundle existen `POST /telegram/users/indicators/deliver`, `GET .../indicators/delivery-status`, `.../indicators/clear`, `.../indicators/tv-invalid` y `/auth/tradingview/check` + el campo `tradingViewUser`. Inferencia (NO CONFIRMADO): estas dos herramientas son indicadores de TradingView que se entregan concediendo acceso al usuario de TradingView cuando el volumen supera el umbral.

### 3.8 Calculadora (unlockAt 0)
- Botón flotante "Calculadora" siempre disponible. No se observó llamada API (cálculo local, NO CONFIRMADO).

---

## 4. Rangos (volumen efectivo MENSUAL)

### Constante exacta del bundle (`MARINE_RANKS`)
```js
const MARINE_RANKS = [
  { name: "Polizonte",       min: 0,        icon: "🎒", color: "#525252" },
  { name: "Grumete",         min: 1,        icon: "🪖", color: "#737373" },
  { name: "Marinero",        min: 10000,    icon: "⚓", color: "#A3A3A3" },
  { name: "Cabo",            min: 50000,    icon: "🔱", color: "#22C55E" },
  { name: "Sargento",        min: 100000,   icon: "⚔️", color: "#3B82F6" },
  { name: "Suboficial",      min: 150000,   icon: "🛡️", color: "#8B5CF6" },
  { name: "Teniente",        min: 300000,   icon: "🎖️", color: "#06B6D4" },
  { name: "Mayor",           min: 500000,   icon: "🏅", color: "#F59E0B" },
  { name: "Comandante",      min: 1000000,  icon: "⭐", color: "#F97316" },
  { name: "Contraalmirante", min: 3000000,  icon: "🌟", color: "#EF4444" },
  { name: "Vicealmirante",   min: 5000000,  icon: "💫", color: "#EC4899" },
  { name: "Almirante",       min: 10000000, icon: "👑", color: "#FFD700" },
];
// Validación en código: lanza Error si "Teniente" no existe ("Verificá que no fue renombrado o eliminado") → Teniente (300k) se usa como umbral clave.
```
- Los umbrales de rango coinciden con los de herramientas (10k Bitácora=Marinero, 50k Mapa=Cabo, 100k Sniper=Sargento, 150k Tendencial=Suboficial, 300k Tactical=Teniente).
- Rangos especiales (no por volumen, `min: Infinity`): Capitán 🏴‍☠️ #FFD700, Oficial 🎖️ #38BDF8, Kraken 🐙 #A855F7, Streamer 📡 #F43F5E, y de exchange "Bitunix" (#C4E83E) y "Bitget" (#00E6D3) con logo. Además flag `almiranteVitalicio` en el usuario.
- Bono por rango (constante `Q` del bundle, USDT de "Bono de Futuros en Bitunix", 50 % de deducción, válido para usuarios nuevos y existentes):
  `{ Marinero: 2, Cabo: 5, Sargento: 10, Suboficial: 15, Teniente: 25, Mayor: 30, Comandante: 80, Contraalmirante: 180, Vicealmirante: 350, Almirante: 600 }`
- Progreso de rango (código):
```js
const current = rankFor(vol);                 // último rank con vol >= min
const next = MARINE_RANKS[idx(current) + 1] ?? null;
const pct = next ? Math.min(100, Math.round((vol - current.min) / (next.min - current.min) * 100)) : 100;
```
  Modal "Rangos Marinos": por rango muestra "Volumen requerido: $min — $(nextMin−1)", "Te faltan $X", y el bono 🎁. Las insignias SVG tienen gradiente `rank-grad-<Nombre>` y glow `rank-glow-<Nombre>`; glow más intenso desde Teniente (intensidad: Suboficial .6, Teniente .55, Mayor .75, Comandante .9, Contraalmirante 1.05, Vicealmirante 1.15, Almirante 1.3, Capitán 1.3, Kraken 1.4 — ×6 px).
- Rango actual viene del servidor en `/cubierta/me` (`rank:{name,min}`) y en el feed (`author.rank`, `author.rankMin`). NO se encontró un endpoint que devuelva la tabla de umbrales: está hardcodeada en el cliente.

---

## 5. Bonos y Boosts (`/panel/boosts`)

### Pestaña "Bonos"
- `GET /bonos` → `[{id, exchange:"bitunix"|"bitget", kind:"campaign", title, description, startDate, endDate, amount, url, hasImage, active, createdBy, createdAt, updatedAt}]` → catálogo de campañas del exchange (torneos, bonos de depósito). Resumen UI: "Bonos actuales" y "Pool total".

### Pestaña "Mis Boosts" (programa de volumen)
- Endpoints: `/referrals/boosts/me`, `/referrals/boosts/me/history`, `GET /referrals/me` → `{"code":"XXXXX","totalCount","last30dCount","last7dCount","referredBy"}`, `GET /sorteo/my-prizes` → `[]`, `POST /referrals/apply` (aplicar código).
- Boost por referidos (tabla de niveles): 1–10 referidos verificados → +5 % del volumen del referido; 11 o más → +10 %. Solo cuentan referidos con UID verificado y solo el volumen generado después de usar el código.
- Boost por depósito (una vez al mes, al acumular ≥ $100 de depósitos en el mes; dura 72 h; si cruza fin de mes se recorta al último día 23:00 UTC). Multiplica SOLO el volumen incremental generado dentro de la ventana:
  | Depósito acumulado del mes | Multiplicador |
  |---|---|
  | ≥ $30.000 | ×2 |
  | $10.000 – $30.000 | ×1,5 |
  | $3.000 – $10.000 | ×1,4 |
  | $1.000 – $3.000 | ×1,3 |
  | $300 – $1.000 | ×1,2 |
  | $100 – $300 | ×1,1 |
  Depósitos dentro de la ventana pueden subir el multiplicador; retiros lo bajan; si los depósitos netos caen bajo $100 se desactiva (y vuelve si se superan otra vez, dentro de la ventana). Nada extiende la ventana.
  Fórmula implícita: `boostVolume += (volumenAhora − volumenAlActivar) × (multiplicador − 1)`. NO CONFIRMADO el cálculo exacto (es servidor).

---

## 6. Economía $MLP (moneda interna) — `GET /sorteo/race/store`

Respuesta: `{ powers[], balance, earned, season:"2026-11", maxPowersPerRace:5, inventory:{}, volumeMilestones[], earnStatus{} }`
- Saldo y mochila se reinician el día 1, 00:00 UTC. `earned` (total ganado en la temporada) alimenta el ranking aunque luego se gaste.
- `earnStatus`: `{loginToday, bitacoraToday, commentToday, raceToday, predictionActive, predictedCurrentGame, uidVerified, bitgetUidVerified, achievements, predictionAchievement, volumeMilestones, referrals, achievementsTotal:7}` → la UI muestra "1 de 9 objetivos completados".
- Formas de ganar:
  - Login diario: 10/día + hitos de racha día 7 +50, día 15 +120, día 30 +300 (la racha reinicia después del día 30). `GET /sorteo/race/check-in` se llama al cargar el panel (registra el login).
  - Anotar en la bitácora: 10/día (1 vez/día).
  - Comentar en un directo de YouTube: 25/día.
  - Carrera: participar 50–180 según puesto; predecir el podio: fondo común (1° paga más que 2° y 3°).
  - Predicción BTC: 40–160 (requiere Bitget verificado; más si quedas entre los 3 más cercanos).
  - Verificar UID: 100 por exchange (una vez).
  - Logros: 40–300, 7 hitos únicos (primera inscripción, primer poder usado, primer podio, primera victoria, primera predicción, usar los 10 poderes, ganar 3 veces).
  - Invitar amigos: 200 cuando el invitado verifica UID y opera $1.000 reales.
  - Hitos de volumen mensual (`volumeMilestones` = [usd → mlp], acumulativos, 18 hitos):
    `1k→50, 5k→100, 10k→150, 25k→250, 50k→400, 100k→600, 150k→800, 200k→1000, 300k→1300, 400k→1600, 500k→2000, 750k→2400, 1M→2800, 1.5M→3400, 2M→4000, 3M→5000, 4M→6000, 5M→7000`
- Poderes de la Carrera (`powers[]`: `type, name, emoji, price, amount, requiresTarget, description, example`), máx. 5 por carrera:
  Niebla 80 (oculta tu posición 20 % de la carrera, se apaga a 1 min del final) · Sonar 120 (revela quién tiene Escudo/Espejo) · Escudo 150 (bloquea el próximo Bombardeo/Maremoto/Drenaje; el Misil lo atraviesa) · Turbo 250 (5 min: si sube, sube más; si baja, baja menos) · Bombardeo 300 (objetivo: empeora su resultado) · Espejo 350 (devuelve Bombardeo/Misil) · Sobrecarga 400 (×1,5 tu resultado 5 min, para bien o mal) · Drenaje 450 (objetivo: le quitas parte del avance y lo sumas al tuyo) · Misil 500 (objetivo: deja su resultado en 1/4, atraviesa Escudo; solo Espejo lo frena) · Maremoto 600 (golpea a todos los demás; Escudo protege).
- Ranking: `GET /sorteo/race/mlp-leaderboard` → top 20 `[{userId, earned, name, youtubeHandle}]` ordenado por `earned` de la temporada (pestañas "Esta temporada" / "Mes anterior"; top 3 en podio).

## 7. MLP Games (`/panel/games`)
- **Carrera** (patrocinio Bitunix): `GET /sorteo/race/status` → `{host, session, hasLiveSession, hasTicket, ticket{estado,price:200}, myEntry, participants[], corredores[{symbol,name}], takenCorredores[], result, myUserId, mlpBalance, powerUses[], hiddenUserIds[], drainedUserIds[], sonarReveal, myPrediction, betting}` → cada jugador elige un "corredor" cripto; gana el mayor % de cambio de precio; poderes alteran resultados; se juega durante los directos.
- **Predicción BTC** (patrocinio Bitget): `GET /sorteo/prediction/status` → `{game, myPrediction, eligible:false, btcPrice, hasLiveSession}` → gana la predicción más cercana al precio de cierre del temporizador.
- **BTC 5 Minutos** (`/panel/games/btc-5-minutos`): `GET /sorteo/btc5/status` → `{btcPrice, config{edge:0.04, sigma, mu, durationMinutes:5, thresholds[{index,pct,probUp,probDn,payoutUp,payoutDn,maxStake:500}]}, balance, openRound, recent[]}`; `GET /sorteo/btc5/history` → `[{at, price}]`.
  - VERIFICADO con dos lecturas: `probUp = Φ(mu / sigma)` (normal estándar; ej. mu 2.94e-5, sigma 1.097e-3 → 0,5107), `probDn = 1 − probUp`. `mu`/`sigma` se recalculan en vivo desde el histórico (primera lectura: mu 0, sigma 0.0015).
  - Pago: con p=0,5 → 1,89×; p=0,5107 → 1,851×; p=0,4893 → 1,9307×. Aproxima `payout ≈ (1 − edge) / (p × 1,016)` ≈ `1/(p + ~0,029)`. NO CONFIRMADO la fórmula exacta (el servidor la entrega ya calculada; margen real ~5,5 % pese a `edge` 0,04).
  - Montos rápidos 50/100/250 $MLP, una posición a la vez, el precio se fija al abrir. Lo ganado aquí NO cuenta para el ranking mensual de $MLP.
- **Ruleta del Capitán** (botón flotante): `GET /sorteo/ruleta/active` (polling) → `{"live":true,"round":null,"me":{"saldo":0,"max":5,"price":200,"hasTicket":false,"ticketSpentIn":null,"reason":"sin_canal","weight":0},"openingBonus":null,"serverNow"}` → ticket cuesta 200 $MLP, máx. 5; `reason:"sin_canal"` = requiere vincular canal de YouTube; `weight` = peso en el sorteo. `serverNow` se usa para sincronizar relojes.

## 8. Otros patrones de engagement observados
- Directos: `GET /directos` → `{"live":[{userId,name,username,avatarUrl,rank,startedAt,youtubeUrl,platform}],"upcoming":[{...,startsAt,channelUrl}]}`.
- Notificaciones: `/notifications`, `/notifications/unread-count` (badge "16 sin leer").
- Banners: `/promo-banners/active`; transición de exchange: `/bitget-transition/mine`.
- Onboarding con checklist: vincular Telegram (alertas/bot), YouTube (sorteos), Bitunix/Bitget UID, TradingView.
- Perfil compartible: botón "Compartir rango" (tarjeta para redes).
- Noticias y Eventos (`/panel/noticias`): `/noticias/feed?cat=crypto|economia` (`items[{title,link,pubDate,source}]`), `/noticias/market/fear-greed` (`{value:26,classification:"Miedo",history[],previous{yesterday,week,month}}`), `/noticias/market/long-short?symbol=BTC` (fuente OKX: `longPct, shortPct, ratio, history[]`), `/noticias/market/dominance` (`btc, eth, stables, others, totalMarketCapUsd, totalVolumeUsd, marketCapChange24h, altseason{index,window:"30d",outperformers,sample,btcChange}`; VERIFICADO: `altseason.index = outperformers / sample × 100` → 18/50 = 36), `/noticias/market/trending`, `/noticias/market/btc-monthly`, `/noticias/trump-agenda` (agenda de eventos), `/noticias/conferencias-live?channel=<YouTubeChannelId>`.

## 9. Lo que NO se pudo confirmar (no inventar)
- Cálculo de `tendencial_price`, `pts` y umbrales de `sentiment` del Mapa Tendencial.
- Algoritmo de generación de señales (entrada, SL, DCA, winrate) — solo patrones medidos.
- Qué es `starterActive` en el estado de herramientas.
- Dónde se decide la ventana libre de días 1–3 (cliente vs servidor).
- Endpoint/forma de entrega de Sniper, Tendencial y Tactical (inferido: señales 1m y entrega de indicadores TradingView).
- Fórmula exacta del payout de BTC 5 Minutos y del boost por depósito.
- Cuerpos de `/telegram/users/monthly`, `/users/me/exchanges`, `/sorteo/race/check-in`, `/bitget-transition/mine`, `/promo-banners/active`, `/notifications` (cargaron antes de poder capturarlos).

---
---

# COMPLEMENTO v2: huecos resueltos (Tendencial/Tactical, Radar, Mapa Tendencial, La Cubierta)

> Segunda pasada (3 nov 2026), atacando puntualmente lo que quedó "NO CONFIRMADO" en la v1 de
> arriba, más las 2 herramientas bloqueadas. Fuentes nuevas: más señales reales en vivo, pruebas
> de ajuste de curvas contra velas reales (ATR14, SuperTrend), y una guía pública de la propia
> plataforma (`melapela.ai/guias/tactical.html`, enlazada desde su FAQ) que resultó ser la fuente
> más rica de todas — ahí es donde describen su propio indicador en texto plano.

Este documento COMPLEMENTA el prompt anterior ("Sistema de Arsenal, Rangos y Gamificación"). Úsalo junto con él. Incluye correcciones a la v1 (sección 0) y los hallazgos nuevos organizados A–E. Lo marcado **NO CONFIRMADO** no se pudo verificar; no lo trates como hecho. Usa esto como referencia para diseñar MI propia versión en SkillCash (mis nombres, mi marca, mis parámetros), sin copiar textos ni imágenes de ellos.

Fuentes de esta pasada: respuestas JSON de mi propia sesión (solo lectura), bundles JS ya descargados por el navegador, y una guía pública estática de la propia plataforma: `https://www.melapela.ai/guias/tactical.html` (tutorial interactivo "Cómo usar el indicador Tactical", enlazado desde `/panel/faq`). Esa guía resultó ser la fuente más rica.

---

## 0. CORRECCIONES a la v1 (importante)

1. **`dir` del Mapa Tendencial NO es simplemente `precio > tendencial_price`.** Se observó BTC 1m con `dir: "BEAR"` y precio 77.667,8 por ENCIMA de la línea (77.616,27); 13 min después pasó a BULL. Conclusión: `dir` se fija al CIERRE de vela (estado de tendencia del indicador), mientras `tendencial_price` se actualiza dentro de la vela. Regla correcta: la tendencia cambia cuando una vela CIERRA del otro lado de la línea (ver C).
2. **`closedReason: "time"` NO significa que expiró por tiempo.** La guía dice que la "señal de tiempo" (⏳ SALIR) no mide tiempo: salta cuando el impulso se apaga y el oscilador cruza en contra (salida por debilidad).
3. **Sincronización de volumen (antes NO CONFIRMADO):** FAQ oficial → Bitunix se sincroniza 1 vez por hora; Bitget cada 10 minutos.
4. **`sentiment` del Mapa:** vocabulario observado `NEUTRAL` (4/8 = 50 %), `BEAR` (3/8 = 37,5 %), `BULLISH` (6/8 = 75 %). La guía confirma: "por encima del 70 % pone BULLISH". NO CONFIRMADO el resto de cortes (por simetría probablemente <30 % → BEARISH; entre 30–70 % → BULL/BEAR según el lado; 50 % → NEUTRAL).
5. **Ventana libre días 1–3 (antes NO CONFIRMADO si era cliente o servidor):** es lógica de CLIENTE, legible:
```js
const isFreeWindow = (d = new Date()) => d.getUTCDate() <= 3;   // módulo 36349
// hook: re-evalúa cada 5 min → setInterval(() => set(isFreeWindow()), 300000)
```
6. **`starterActive` (antes NO CONFIRMADO)** — función legible del bundle:
```js
function starterActive(u) {
  return isPrivilegedRole(u.role)            // admin/streamer/etc.
      || u.almiranteVitalicio === true
      || (u.role && u.role !== "guest" && isFreeWindow(new Date(u.now ?? Date.now())))
      || lastTradeWithin30Days(u)            // now - lastTradeAt < 2592e6 ms (30 días); si no hay lastTradeAt, usa el lastTradeTime más reciente de monthlyItems
      || (typeof u.volumeReal === "number" && u.volumeReal > 0);
}
```
   Y el estado de cada tarjeta del Arsenal:
```js
tools.map(t => isPrivileged ? { ...t, hideDescription: true, status: "active" }
  : (t.id === "radar" || t.id === "cubierta")
      ? { ...t, status: starterActive ? "active" : vol >= t.unlockAt ? "paused" : "disabled" }
      : { ...t, status: (isFreeWindow && FREE_WINDOW_TOOLS.has(t.id)) || vol >= t.unlockAt ? "active" : "disabled" });
```
   → Por eso Radar y La Cubierta salían "Activo" con $0: estamos en la ventana libre (3 de nov). No hay badge visual de "trial" en las tarjetas; solo el banner superior.

---

## A) Tendencial (150.000) y Tactical (300.000)

1. **Clic en tarjeta bloqueada:** no abre modal, tooltip ni dispara API. La tarjeta solo dice "Requiere 150.000 / 300.000 de volumen · Bloqueado".
2. **Hover:** sin `title`/tooltip.
3. **Bundles JS:** solo aparecen como ids/íconos/colores (`tendencial: rgb(249,115,22)`, `tactical: rgb(139,92,246)`) y estado `status: vol >= 15e4 / 3e5 ? "active" : "disabled"`; los textos van por i18n (`arsenal.tendencial`, `arsenal.tactical`) que no estaban en los chunks cargados. No hay componente de contenido descargado.
4. **Páginas públicas (FAQ + guía) — SÍ dan la respuesta:**
   - FAQ: "Las señales son generadas por el **indicador Tactical** y aparecen automáticamente en el Radar". → **Tactical = el indicador privado de TradingView que genera TODAS las señales del Radar** (entrada, SL, DCA, TPs, winrate). Desbloquearlo (300k) = recibir acceso al indicador en tu propia cuenta de TradingView ("indicador de acceso restringido: solo lo ve quien lo tiene concedido", se agrega desde ƒ Indicadores → invitaciones). Encaja con los endpoints `POST /telegram/users/indicators/deliver`, `GET .../indicators/delivery-status`, `/auth/tradingview/check` y el campo `tradingViewUser`.
   - **Tendencial:** la guía llama "tendencial" a la línea base del Tactical ("la columna vertebral de todo… suelo o techo que se mueve").
5. **CONFIRMADO (6 nov 2026, homepage pública melapela.ai, sin login — fichas de producto):**
   - **Indicador Tendencial ($150K/mes):** "Soportes y resistencias dinámicas directamente en TradingView. Tu **primer** indicador propietario MLP. Visualiza niveles clave para identificar entradas de alta probabilidad." → confirma la inferencia de arriba: es la versión de entrada, solo la línea tendencial (soporte/resistencia dinámico), SIN el motor de señales/DCA/triple confirmación.
   - **MLP Tactical Bridge ($300K/mes), subtítulo "El Arma Definitiva":** "Más de 4.500 líneas de código Pine Script. Sistema de triple confirmación (1/3, 2/3, 3/3), winrate en tiempo real, multi-temporalidad, TP/SL dinámico, DCA integrado, y alertas JSON. Creado por Capitán Aurolo — no existe otro indicador igual." Chips de features: Triple confirmación · Winrate tracking · Multi-TF (1m a 1M) · TP/SL dinámico · DCA integrado · Alertas JSON. Barra de progreso de desbloqueo con los 3 pasos marcados 1/3 (gris) → 2/3 (ámbar) → 3/3 (verde).
   - Ambas fichas viven en la landing pública (scroll normal, no hace falta cuenta) — mismo patrón que el resto del marketing de la página.

### Especificación del indicador Tactical (de la guía pública)
- Hace 4 cosas: cuándo hay entrada, dónde poner el stop, cuánto abrir según tu capital, hasta dónde puede llegar.
- **Línea tendencial**: blanca = alcista (va debajo, hace de suelo); azul = bajista (va encima, techo). Entre tramos hay un **salto vertical** = cambio de tendencia → aviso "❌ CERRAR AHORA" si tienes operación abierta.
- **Zona de entrada**: banda alrededor de la tendencial; su ancho NO es configurable, se calcula con la volatilidad del activo y la temporalidad (ancha en monedas nerviosas). Opción "Tipo de entrada": *Toque* (basta la mecha) o *Cierre* (la vela debe cerrar dentro).
- **Puntuación 3/3 o 2/3** (=`points` de la API y `pts` del Mapa):
  - **T** Tendencial: precio en la zona — **obligatoria**.
  - **W** WaveTrend: el oscilador cruzó en zona extrema.
  - **D** Direccionalidad + ADX: el movimiento empuja a tu favor (DI) Y el ADX dice que tiene fuerza; si falla uno, no hay punto.
  - Etiqueta grande = 3/3, pequeña = 2/3 (el panel dice cuál falta). Long verde bajo la vela, Short rojo encima.
  - "Cambio mínimo nueva señal (%)" = 0,01 por defecto: cuánto debe moverse la tendencial para permitir otra señal en el mismo sitio (evita repetir la misma entrada).
- **Línea de vulneración**: cuánto traspasa el precio la tendencial con mechas, de media, en ese activo. Es donde cae la última entrada del DCA.
- **Stop "SL Inteligente"**: unidad = distancia tendencial→vulneración. `SL = tendencial ∓ multiplicador × (tendencial − vulneración)`. Mínimo 1,5 (default; = media distancia más allá de la vulneración), máximo 4,0 (solo se abre en alta volatilidad; si min = max no se mueve).
- **DCA**: 2 entradas (señal + vulneración) o 3 (señal + punto medio + vulneración). Pesos default 20/30/50. Tamaño calculado suponiendo que se llenan todas y midiendo el stop desde el precio medio.
- **TPs**: NO son múltiplos: cada TP es la tendencial de una temporalidad MAYOR que está por delante del precio (etiqueta `TP1 [1w]`). Máx. a mostrar: 6.
- **Break even**: ratio R:R para BE = 1,0 por default (BE al ganar lo mismo que arriesgas); verificación intravela "Normal (1m)" o "Rápido (10s)" (Premium TV).
- **Apalancamiento**: el indicador propone el que hace que tocar el stop = perder el margen entero, con techo configurable (default 50).
- **Gestión de riesgo (inputs)**: Capital total (default 10.000), Riesgo máximo % (default 1), Apalancamiento máximo (50), SL mín 1,5 / máx 4,0, comisiones taker 0,06 % / maker 0,06 % (entradas por límite, salida a mercado), opción "incluir comisiones en el riesgo".
- **Panel** (filas): SEÑAL (dirección, nº entradas, puntos T/D/W, apalancamiento), WIN 2/3, WIN 3/3, TACTICAL (esperando / listo / en operación con % / avisos de salida), GESTIÓN DCA, AVG (precio medio con entradas llenas, "2 de 3"), E1/E2/E3 (margen y precio, ✓/○), Margen, Gan TP1, Riesgo actual, Riesgo total + precio stop, Comisiones.
- **Tabla Multi-Temporalidad** (= Mapa Tendencial): ordena las TF por el precio de su tendencial e inserta el precio actual entre ellas (fila amarilla = tú; arriba techos/objetivos, abajo suelos). Columnas: TF, dirección, puntos, señal, precio de la tendencial. Barra Bull/Bear = % de TF alcistas; >70 % → BULLISH. Máx. 8 TF (de 1m a 1w).
- **Alertas**: 2/3, 3/3, DCA, TP, ⏳ salida por debilidad, cierre, SL, con apalancamiento. Formato de mensaje: `BTCUSDT → LONG 3/3 [1h] | WR: 67% | Racha: +5 | SL: 76326 | 37x`.
- **Estadísticas (cómo se cuenta un WIN)** — por default cuentan como ganada: tocar cualquier TP, cerrar en verde por ⏳ SALIR, y **llegar al BE**. (Ojo: inflan el winrate; desactivar "BE cuenta como WIN" lo baja.)
- 13 grupos de configuración, 49 opciones; 7 temas de color.

---

## B) Radar: cómo se arma la señal

### B1. Fórmulas legibles (bundle `20-9m…`, módulo de suscripción a señales)
```js
const DEFAULT_SL_MULT = 1.5;            // "q"
const SL_MULT_OPTIONS = [1.5, 2, 2.5, 3]; // botones "SL INTELIGENTE MIN." en el modal de señal (title="Multiplicador SL")
const lastDca = dca => dca?.enabled ? (dca.num_entries === 3 ? dca.e3_price : dca.num_entries === 2 ? dca.e2_price : null) : null;
function adjustSL({ action, slPrice, dca, multiplier }) {
  if (!Number.isFinite(multiplier) || multiplier < 1 || multiplier === 1.5 || !validDca(action, slPrice, dca)) return { slPrice, adjusted: false };
  const vul = lastDca(dca);                                  // E3 = línea de vulneración
  const off = Math.abs(vul - slPrice) * (multiplier - 1) / 0.5;
  const sl  = isShort(action) ? vul + off : vul - off;
  return sl > 0 ? { slPrice: sl, adjusted: true } : { slPrice, adjusted: false };
}
// si se ajustó el SL: leverage = min( clamp(1, 50, round(entry / |entry − sl|)), leverage_señal ?? 50 )
// bePrice = 2 * (currentEntryPrice ?? entryPrice) − sl     // BE a 1R
```
**Verificado con datos reales (TAO 3m LONG):** E1 226,70 · E2 226,1211 · E3 225,5422 · SL 225,3737; tendencial 3m del Mapa = 225,87941. → d = 225,87941 − 225,5422 = 0,33721; `tendencial − 1,5·d = 225,3736` ✔ (SL real 225,3737); `E2 = (E1+E3)/2 = 226,1211` ✔.
**Regla completa:** `E1 = precio señal`, `E3 = vulneración = tendencial ∓ d`, `E2 = punto medio(E1,E3)`, `SL = tendencial ∓ 1,5·d` (equiv. SL a 0,5·d más allá de E3). Lo que NO es visible es cómo se calcula `d` (media de las penetraciones de mecha sobre la tendencial en ese activo, según la guía) — **NO CONFIRMADA la ventana/fórmula exacta**.

Calculadora del panel (legible, mismo bundle del Home) — útil para mi propia calculadora:
```js
// DCA "auto": precio_i = entry − (entry − stop)/n · i   (i = 0..n−1)  ← distinto del Tactical (que usa punto medio y vulneración)
// distribuciones: "50/50","40/60","33/33/34","20/30/50","25/25/50"
weightedEntry = 1 / Σ(alloc_i/100 / price_i)               // media armónica ponderada
stopDist     = |weightedEntry − stop| / weightedEntry
riskUSD      = risk% / 100 · capital
margin       = riskUSD / (stopDist · leverage);  position = margin · leverage
fees         = position · commission% · 2
targetValue  = position · targetPct − fees;  stopValue = −(riskUSD + fees);  rewardRisk = targetValue / |stopValue|
// warnings: long con stop ≥ entry o target ≤ entry (y viceversa en short)
```

### B2. Más señales reales (activas, 03-nov-2026 ~20:05 UTC; 34 activas en total)
| Par | TF | Lado | Entrada | SL (dist.) | E2 / E3 | Paso DCA | Winrate | ATR14 % del TF | SL/ATR |
|---|---|---|---|---|---|---|---|---|---|
| GRAM | 3m | L | 1,17 | 1,165271 (0,404 %) | 1,168081 / 1,166162 | 0,164 % | 56 | 0,162 % | 2,49 |
| DOGE | 1m | S | 0,07512 | 0,07527413 (0,205 %) | 0,07517157 / 0,07522315 | 0,069 % | 60 | 0,055 % | 3,73 |
| SUI | 1m | S | 0,8959 | 0,8977830 (0,21 %) | 0,8965571 / 0,8972142 | 0,073 % | 69 | 0,084 % | 2,50 |
| TAO | 3m | L | 226,70 | 225,3737 (0,585 %) | 226,1211 / 225,5422 | 0,255 % | 58 | 0,172 % | 3,40 |
| ONDO | 3m | L | 0,389 | 0,3868230 (0,56 %) | 0,3880796 / 0,3871593 | 0,237 % | 58 | 0,192 % | 2,92 |
| ZEC | 5m | L | 1208,9 | 1192,978 (1,317 %) | 1201,915 / 1194,930 | 0,578 % | 61 | 0,425 % | 3,10 |
| PONS | 3m | L | 0,2014 | 0,1990154 (1,184 %) | 0,2003681 / 0,1993362 | 0,512 % | 44 | 0,354 % | 3,34 |
| SUI | 5m | L | 0,8959 | 0,8879711 (0,885 %) | 0,8924073 / 0,8889145 | 0,39 % | 60 | 0,202 % | 4,38 |
| AMZN | 1m | L | 251,73 | 251,3143 (0,165 %) | 251,6319 / 251,5338 | 0,039 % | 57 | 0,061 % | 2,70 |
| HYPE | 1h | S | 85,135 | 88,48678 (3,937 %) | 86,41189 / 87,68879 | 1,5 % | 71 | 1,291 % | 3,05 |
| DOGE | 3m | L | 0,07507 | 0,07486285 (0,276 %) | 0,07499112 / 0,07491224 | 0,105 % | 60 | 0,097 % | 2,85 |
| XRP | 5m | L | 1,2782 | 1,272941 (0,411 %) | 1,276079 / 1,273957 | 0,166 % | 62 | 0,151 % | 2,72 |
(Primera pasada, otras: PONS 1m L SL 0,530 %; 5m SHORT SL 1,847 %; etc.) ATR14 calculado por mí (Wilder) con las velas de `/telegram/mtf-map/{sym}/klines` del mismo TF.

**Conclusión sobre volatilidad:** SÍ escala. El SL queda en 2,5–4,4× ATR14 (mediana ≈ 3×) y el paso DCA ≈ 0,6–1,9× ATR14 (≈ 1,1×) en todos los pares y TF; en % el SL va de 0,165 % (AMZN 1m) a 3,9 % (HYPE 1h). Coherente con la guía (zona y vulneración dependen de la volatilidad del activo y TF). Que el ratio no sea constante es coherente con que `d` es la penetración media de mechas, no un múltiplo fijo de ATR.
Siempre: `leverage` 50 (techo), DCA 20/30/50 con 3 entradas, `points` 3/3 en todas las activas vistas, expiración 1m→30 min, 5m→60 min.

### B3. ¿Qué es `winrate`?
El modal de la señal lo rotula **"WINRATE HIST."** y el apalancamiento "Recomendado por el indicador". Según la guía, el Tactical calcula en el propio gráfico (es decir, por **activo + temporalidad**) el acierto histórico de sus señales, separado en 2/3 y 3/3: `⭐67% (12) │ 70% 7/10◐2 │ 🔥5` = acierto histórico y nº de operaciones, últimas 10, y racha. Varía por par/TF en los datos (DOGE 1m 60, SUI 1m 69, SUI 5m 60, PONS 3m 44, HYPE 1h 71). Cuenta como WIN: tocar cualquier TP, salida por debilidad en verde, y BE (defaults). NO CONFIRMADO si el `winrate` de la API corresponde a la fila 2/3 o 3/3 (todas las vistas eran 3/3, así que probablemente la de 3/3).

### B4. Sniper
**No existe endpoint propio.** Endpoints de señales en el bundle: solo `/telegram/signals/active`, `/telegram/signals/locked`, `/telegram/signals/recent-count`, `/telegram/operations/closures`. Sniper = señales `timeframe:"1m"` dentro del mismo feed (la UI y el banner lo llaman "Sniper (señales de 1m)"). En las suscripciones de alertas los presets excluyen 1m: `{ scalping: ["3m","5m","15m"], intraday: ["15m","1h","2h","4h"], swing: ["8h","1d","1w"] }`, TFs posibles `["1m","3m","5m","15m","1h","2h","4h","8h","1d","1w"]`, clases de activo `["cripto","accion","commodity"]`. `/telegram/signals/locked` devolvió `[]`, así que NO CONFIRMADO cómo se le muestran las señales 1m bloqueadas a quien no tiene 100k fuera de la ventana libre.

Modal de señal (UI): par, TF, lado, `x/3`, antigüedad, selector SL ×1,5/×2/×2,5/×3, TP2 y TP1 con % y precio, E1 / E2 (DCA, −%) / E3 (DCA, −%), STOP LOSS (−%), RIESGO:RECOMPENSA (ej. 2,31x = TP1 +1,4 % / SL −0,6 %), APALANCAM. 50x, WINRATE HIST., "ESTRATEGIA DCA 3 entradas · cubre hasta −0,5 %", "Señal activa desde…", botón "Sí, Marino" (suscribirse → aparece en Operaciones Activas). Radar en Vivo agrupa en columnas por TF (1m … 1w), filtros Long/Short/Ambos, contador "Activos 24/24", "Bolas asimétricas" y toggle de sonido.

---

## C) Mapa Tendencial: origen de `tendencial_price`

1. **JS:** no hay cálculo en el cliente (no aparecen `ema`/`vwap`/`supertrend` ligados al mapa; el número viene del servidor). La guía describe la línea pero usa datos precalculados ("valores fijos de la demostración").
2. **Comportamiento (evidencia):**
   - Serie de la guía (170 velas): **0 movimientos contra-tendencia** (en alcista nunca baja, en bajista nunca sube), 66 de 159 velas con la línea **plana** (escalones), y **salto vertical** al cambiar de tendencia (89.509 → 95.275 cuando una vela cerró en 88.940, por debajo). La zona = banda simétrica ±≈2.007 alrededor de la línea.
   - En vivo, entre 20:04 y 20:17 UTC: la mayoría de TF quedaron **idénticos** (BTC 3m, 5m, 1h, 8h, 1d; ETH 1m, 5m, 15m, 1h, 4h, 8h, 1d), algunos con micro-ajustes (BTC 15m +0,035 %, 4h +0,020 %; TAO 4h +0,125 %, 15m −0,057 %), incluso contra-tendencia → probablemente recalculado con la vela en formación. → **Se mueve a saltos/escalones, no suave como una media móvil.**
   - Mis pruebas de ajuste con 800 velas (BTC/ETH/SOL en 15m/1h/4h): EMA/SMA 20–200 fallan (error medio 0,6–2,1 %); la familia **SuperTrend / ATR trailing-stop** acierta la dirección 8/8 con error medio ≈ 0,23 % (mejor: ATR14 RMA × 3,5 sobre hl2). En la serie de la guía, mejor ajuste ST(20, ×4, ATR SMA) con 148/150 direcciones correctas y ~0,9 % de error.
   - **Conclusión: es un trailing-stop de volatilidad tipo SuperTrend (ratchet + flip al cierre). La fórmula y parámetros exactos NO están confirmados.**
3. **Datos reales (03-nov-2026 20:04 UTC), formato `tf: dir / pts / signal / tendencial_price`:**
   - **BTCUSDT.P** px 77.667,8 · 4/4 NEUTRAL — 1m: BEAR/1/SHORT/77.616,272 · 3m: BULL/0/ESPERANDO/77.490,783 · 5m: BULL/0/ESPERANDO/77.350,260 · 15m: BULL/0/ESPERANDO/77.017,804 · 1h: BEAR/0/ESPERANDO/78.204,711 · 4h: BEAR/0/ESPERANDO/79.757,300 · 8h: BEAR/0/ESPERANDO/81.293,305 · 1d: BULL/1/LONG/77.451,049
   - **ETHUSDT.P** px 2.287,27 · 3/5 BEAR — 1m: BEAR/0/ESPERANDO/2.290,2236 · 3m: BEAR/0/ESPERANDO/2.294,9022 · 5m: BULL/1/LONG/2.284,5177 · 15m: BULL/0/ESPERANDO/2.269,7172 · 1h: BULL/0/ESPERANDO/2.244,3189 · 4h: BEAR/0/ESPERANDO/2.343,9782 · 8h: BEAR/0/ESPERANDO/2.411,2330 · 1d: BEAR/0/ESPERANDO/2.575,9076
   - **SOLUSDT.P** px 93,30 · 3/5 BEAR — 1m: BEAR/1/SHORT/93,378185 · 3m: BULL/0/ESPERANDO/93,149568 · 5m: BULL/0/ESPERANDO/92,881071 · 15m: BULL/0/ESPERANDO/92,317707 · 1h: BEAR/0/ESPERANDO/94,693589 · 4h: BEAR/0/ESPERANDO/97,794966 · 8h: BEAR/0/ESPERANDO/101,67423 · 1d: BEAR/0/ESPERANDO/111,48879
   - **TAOUSDT.P** px 226,55 · 4/4 NEUTRAL — 1m: BEAR/1/SHORT/226,88472 · 3m: BULL/3/LONG/225,87941 · 5m: BULL/0/ESPERANDO/225,10887 · 15m: BULL/0/ESPERANDO/223,19422 · 1h: BEAR/0/ESPERANDO/229,76735 · 4h: BEAR/0/ESPERANDO/240,37969 · 8h: BEAR/0/ESPERANDO/253,29191 · 1d: BULL/1/LONG/230,10004
   - **DOGEUSDT.P** px 0,07518 · 3/5 BEAR — 1m: BEAR/1/SHORT/0,075157545 · 3m: BULL/2/LONG/0,075011027 · 5m: BULL/0/ESPERANDO/0,074839800 · 15m: BULL/0/ESPERANDO/0,074427093 · 1h: BEAR/0/ESPERANDO/0,075855439 · 4h: BEAR/0/ESPERANDO/0,078171850 · 8h: BEAR/0/ESPERANDO/0,080695418 · 1d: BEAR/0/ESPERANDO/0,087901903
   - **1000PEPEUSDT.P** px 0,0048671 · 6/2 BULLISH — 1m: BEAR/0/ESPERANDO/0,0048856564 · 3m: BULL/0/ESPERANDO/0,0048334326 · 5m: BULL/0/ESPERANDO/0,0048094048 · 15m: BULL/0/ESPERANDO/0,0047369170 · 1h: BEAR/1/SHORT/0,0049244728 · 4h: BULL/0/ESPERANDO/0,0042788477 · 8h: BULL/0/ESPERANDO/0,0038758019 (1d truncado)
   - Símbolos con sufijo exacto del exchange: `1000PEPE.P` devuelve 404 "Symbol not found"; el correcto es `1000PEPEUSDT.P`.
4. **Klines:** `GET /telegram/mtf-map/{sym}/klines?interval=1h&limit=200&endTime=<ms>` → máx. `limit` 200 (400 si se pide más), paginar con `endTime` en milisegundos; campos `time (unix s), open, high, low, close` (sin volumen); el gráfico de la guía dice "Binance", NO CONFIRMADO qué fuente usa la API.
5. **Patrón `pts`/`signal`:** `pts` = puntos T/D/W de la última señal en esa TF (0–3). `pts 0` → siempre `signal: "ESPERANDO"`; `pts ≥ 1` → `signal` = `LONG`/`SHORT` según `dir` (vistos 1/3, 2/3 y 3/3: TAO 3m 3 LONG, DOGE 3m 2 LONG, varios 1). La señal que aparece en el Radar es la de 3/3 (la de TAO 3m coincide). NO CONFIRMADO si con `pts 1` ya es una señal operable o solo "en formación" (según la guía la T es obligatoria, así que pts≥1 implica precio en zona).

---

## D) La Cubierta a fondo

1. **Feed:** con rango Polizonte (sin trades) **los 20 posts del feed llegan bloqueados desde el servidor**: `locked: true`, `exclusiveRank: {name:"Grumete",min:1}`, `body` vacío, sin `call` ni `poll` (el servidor no envía el contenido, no es un blur de cliente). Sí se ven los metadatos: rango del autor (vistos Comandante, Mayor, Capitán, Oficial, Streamer, Cabo), `hitRate` del autor (ej. 58,14 %, 88,89 %, 56,6 %, 68,42 %, o null), seguidores (1 a 1.076), likes (0–29), comentarios (0–12), donaciones (0), reposts, impresiones (3–261) y alcance (3–89). **No se pudo describir el contenido real de ningún post**: requiere 1 trade en el mes.
2. **Qué es una "call":** una operación publicada como post. Pestaña "Operación" del composer:
   - Activo (buscador, ej. BTC), Dirección LONG/SHORT, Duración (15 min, 1 h, 4 h, 8 h, 1 día, 3 días, 7 días, 15 días, 1 mes, 3 meses), Apalancamiento opcional (10x/20x/50x/100x/otro), Tipo "Libre" (entrada a precio de mercado, cierre automático al vencer la duración) o "Con niveles" (TAKE PROFIT, STOP LOSS, "BE AL TOCAR"; al menos un TP o SL; "los niveles no se cambian después de publicar"), texto "Explica la tesis de tu operación…", audiencia por rango y aviso "Al publicar, participas por el VIP diario de Bitunix".
   - Datos de una call cerrada (`/cubierta/calls/best`): `symbol, direction, entryPrice, horizon (7d, 15d, 3d, 1M…), openedAt, closedAt, pnlPct, exclusive`.
3. **Publicar:** `canPost: true` (por la ventana libre). Pestaña "Publicación": texto libre ("¿Qué estás viendo en el mercado?"), imagen (hasta 3: `hasImage/2/3`), encuesta, Intercom (🔒 por rango), y selector de audiencia **Grumete+ / Marinero+ / Cabo+ / Sargento+ / Suboficial+ / Teniente+** (= `maxReservableRankMin: 300000`). No se publicó nada.
4. **Itercom (salas de audio):** 0 en vivo, 8 programadas. Ejemplo: título de reto de trading, `mode: "abierto"`, `minRank 1 (Grumete)`, host con rango Mayor/Oficial, `participantCount 0`, `scheduledFor` y `expiresAt` = +1 h (salas de 1 hora), `canJoin: false` para Polizonte. Tarjeta UI: "PROGRAMADO · INTERCOM", título, "Sala de audio en vivo de la tripulación", host "Al mando · Canal abierto", fecha/hora y botón "🔒 Ver acceso". Crear sala: bloqueado (`itercomLock.reason: "rank"`).
5. **Ranking de mejores calls:** panel lateral "OPERACIONES ABIERTAS" con pestañas Abiertas / Mejores y check "Apalancamiento". `/cubierta/calls/best` devolvió 5 calls, todas de septiembre 2026 (pnl 52,5 %, 40,01 %, 28,13 %, 26,77 %, 25,89 %; horizontes 7d/15d/7d/3d/1M; varias cerradas antes del horizonte → cierre por TP/SL).
   - **Transparencia:** buena en diseño — la entrada es a precio de mercado al publicar (precio tomado por el servidor: existen `/cubierta/calls/prices` y `/cubierta/calls/price/{sym}`), cierre automático por duración, niveles inmutables y timestamps `openedAt/closedAt`; el usuario no escribe el precio de entrada. NO CONFIRMADO si `pnlPct` incluye apalancamiento (el check "Apalancamiento" sugiere que se puede ver con y sin) ni si el ranking es mensual (mostraba solo calls de septiembre).
   - Otros endpoints: `/cubierta/calls/best-traders`, `/cubierta/calls/stats/{user}`, `/cubierta/calls/mine`, `/cubierta/me/earnings` (donaciones), `/cubierta/impressions`.

---

## E) Pendientes sueltos

- **Ventana libre:** HOY (3-nov) estamos dentro. Banner fijo en todas las páginas: "Primeros 3 días del mes — accesos liberados… abiertos 72 h sin volumen mínimo (cierra 00:00 UTC del día 4)". No hay aviso de la próxima ventana; por el código (`getUTCDate() <= 3`) la próxima es el 1-dic 00:00 UTC.
- **Trial (nuevo):** FAQ → "acceso trial de 7 días a todas las herramientas para usuarios nuevos". `GET /telegram/users/trial-status` → `{"hasTrial":true,"bitunixUid","trialStartedAt":"2026-07-30T04:00:52Z","trialEndsAt":"2026-08-06T04:00:52Z","daysRemaining":0,"isActive":false,"notified24h":false,"lastTradeTime":null,"hasRecentTrade":false,"shouldShowBanner":false}` (trial = registro + 7 días; aviso a las 24 h del fin).
- **`starterActive`**: sin badge visual; ver corrección 0.6.
- **`/referrals/boosts/me/history`** (forma exacta, vacía): `{"userId":"<uuid>","summary":{"realVolume":0,"boostVolume":0,"effectiveVolume":0,"period":"2026-07"},"active":[],"history":[]}`. NO CONFIRMADA la forma de los elementos de `active[]`/`history[]` (vacíos en mi cuenta). Nota: `period` sigue en "2026-07" (mi último mes con registro), no en el mes actual.
- **Cuerpos que faltaban en v1:**
  - `GET /telegram/users/monthly` → `{"items":[{"id","bitunixUid","exchange":"bitunix","year":2026,"month":10,"totalVolume":"0.xxx" (string),"boostVolume":0,"registerTime","lastTradeTime":null,"tradingviewUsername":null,"roleId":1,"telegramLinked":false,"effectiveVolume":0,"youtubeHandle":null,"exchanges":[]}, …]}` (una fila por mes y exchange).
  - `GET /users/me/exchanges` → `[{"exchange":"bitunix","exchangeUid","verified":"true","thisMonthVolume":0,"rawVolume":0,"allVolume":0}]`.
  - FAQ: si el UID queda "Fallido" casi siempre es porque la cuenta del exchange no se creó con el link de referido de la comunidad (el modelo depende de ser afiliado); verificación de UID hasta 2 h.
