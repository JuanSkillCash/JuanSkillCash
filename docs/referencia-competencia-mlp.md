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
