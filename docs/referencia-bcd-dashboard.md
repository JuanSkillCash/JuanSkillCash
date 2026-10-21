# REFERENCIA TÉCNICA COMPLETA: ingeniería inversa de app.buscandocryptodinero.com/dashboard ("BCD A-Strategy")

## Instrucciones para Claude Code

Este documento es la investigación COMPLETA que hice (Juan, SkillCash) sobre un dashboard de trading cripto de la competencia, usando solo el navegador (DevTools: Console, Network, Headers, Preview, Elements) y una página pública del sitio. Es mi especificación de referencia. No necesito que me expliques el producto.

1. Guarda este documento en el repo como `docs/referencia-bcd-dashboard.md` y agrega una línea en `CLAUDE.md` que diga: "Antes de trabajar en el screener/dashboard, lee docs/referencia-bcd-dashboard.md". Así no se pierde entre sesiones.
2. Revisa mi código actual y dime cómo encaja esto con lo que ya tengo: qué tengo, qué me falta y qué hago mejor o peor.
3. NO escribas código todavía. Primero dame el diagnóstico de mi repo y un plan (ver sección 12).

Convenciones:
- [CONFIRMADO] = lo vi directamente en DevTools o en el sitio.
- [INFERIDO] = deducción con evidencia, no verificada.
- [PENDIENTE] = no se pudo confirmar.
- [CORRECCIÓN] = algo que se dijo antes en la investigación y resultó incorrecto. Vale la versión corregida.

---

## 0. Cómo se hizo la investigación (contexto)

- El acceso automatizado está bloqueado: `robots.txt` prohíbe bots y Cloudflare devuelve 403 (protección anti-bot con la cookie `cf_clearance`). Todo se sacó manualmente desde el navegador Edge del usuario, con sesión iniciada (usuario de prueba, Tier 0, Niv.1, cuenta de Bitunix sin conectar, saldo 0).
- La página pública `https://app.buscandocryptodinero.com/guia-puntos` ("Cómo ganar BCD Sats") sí se pudo leer directamente.
- Los warnings de consola de `contentscript.js` (ObjectMultiplex "orphaned data for stream app-init-liveness / background-liveness", MaxListenersExceededWarning) vienen de una extensión del navegador del usuario (MetaMask), NO del sitio. Ignorarlos.
- Los avisos "Tracking Prevention blocked access to storage for cdn.jsdelivr.net/npm/chart.js" y el bloqueo de `static.cloudflareinsights.com/beacon.min.js` (ERR_BLOCKED_BY_CLIENT) los produce la prevención de rastreo de Edge.

---

## 1. Resumen ejecutivo de la arquitectura

```
[Bitunix API (y probablemente Binance para velas)] ──► velas/precios de 498 pares USDT
                │
[Backend Python (pandas) — hora México (CST, UTC-6)]
  - Calcula indicadores en lote para las 498 monedas
  - DataFrame: 1 fila por moneda, columnas = indicadores
  - Genera columnas "crudas" (números) + columnas "de presentación" (HTML con clases Tailwind)
  - Snapshot general (/api/dashboard, TF 1H) ~cada minuto
  - Endpoint por timeframe (/api/timeframe/{tf}), aparentemente calculado bajo demanda (3–5 s)
  - Bot de trading que opera cuentas de usuarios en Bitunix (y Hyperliquid) vía API keys
  - Motor de gamificación (XP, Sats, niveles, rachas, tiers) + bot de Telegram @BCDAlertBOT
                │
[Cloudflare] proxy completo, anti-bot, zstd, HTTP/3, SIN caché (DYNAMIC, no-store)
                │
[Navegador] UNA página HTML monolítica (+7.000 líneas) con JS vanilla inline
  - Tailwind por CDN (necesario porque el servidor manda HTML con clases Tailwind)
  - Chart.js por CDN (sin versión fijada)
  - Polling con fetch cada 10 s exactos (setInterval), sin WebSockets
  - Inserta con innerHTML los fragmentos que llegan del servidor; no calcula nada
```

Conclusión: proyecto de una o pocas personas, probablemente en México. Es funcional pero rudimentario y tiene bastante deuda técnica. Es el panel de un bot de trading propio, abierto a usuarios, cuyo modelo de negocio es la afiliación de Bitunix (comisión por volumen) potenciada con gamificación.

---

## 2. Frontend

- [CONFIRMADO] Sin framework (no React, Vue, Svelte ni Next). Es UNA sola página HTML monolítica con JavaScript vanilla inline. Todos los "Initiator" de las peticiones son líneas del mismo documento `dashboard`: 1304, 1406, 2598, 2624, 2665, 2852, 2997, 3030, 3152, 3758, 4131, 4635, 4730, 4758, 4759, 6084, 6217, 6236, 6622, 6630, 7073. El HTML tiene más de 7.000 líneas.
- [CONFIRMADO] Sin build step: no hay bundle, ni sourcemaps, ni carpeta `webpack://`.
- [CONFIRMADO] Tailwind cargado por CDN (`cdn.tailwindcss.com`). La consola avisa "cdn.tailwindcss.com should not be used in production".
- [INFERIDO, importante] Usan Tailwind CDN por necesidad: el servidor envía fragmentos HTML con clases Tailwind dinámicas (`text-green-400`, `text-[8px]`, `font-black`, `opacity-70`, `font-semibold`…). El JIT del CDN genera ese CSS en el navegador al vuelo. Con Tailwind compilado, esas clases no existirían.
- [CONFIRMADO] Chart.js desde `https://cdn.jsdelivr.net/npm/chart.js` SIN versión fijada (siempre carga la última).
- [CONFIRMADO] Cloudflare Web Analytics: `static.cloudflareinsights.com/beacon.min.js` (dashboard:7073).
- [CONFIRMADO] Widgets en scripts separados:
  - `bcd-ratings-widget.js`: calificación "★ 4.9 (32) Calificar"; llama a `stats`.
  - `bcd-gamif-widget.js`: gamificación; llama a `history?limit=10` (línea 325 del widget).
- [CONFIRMADO] Logs de debug en producción:
  - `🔍 DEBUG: data.crypto tiene 498 elementos` (dashboard:2624)
  - `✅ MARKET_DATA creado con 498 símbolos` (dashboard:2665)
  - Aparecen 2 veces al cargar: el fetch inicial se dispara duplicado. Los datos se guardan en una variable global `MARKET_DATA`.
- [CONFIRMADO] Actualización por POLLING, sin WebSockets: `GET /api/dashboard?t=<epoch_ms>` cada 10 s exactos. El parámetro `t` es cache-busting. Timestamps observados (suben de a ~10.000 ms): 1792470483834 y 1792470484061 (duplicado inicial), 493837, 503836, 514361, 524363, 534359, 544354, 554354, 563842, 573835, 584359, 594363, 604352, 614353, 623835, 634350, 644360, 653836…; más tarde 1792472006358 → 1792472016352.
- [INFERIDO] El front no calcula indicadores: solo inserta con innerHTML lo que manda el servidor.

---

## 3. Backend / API

- [CONFIRMADO] TODO va a su propio dominio `app.buscandocryptodinero.com/api/…`. El navegador NUNCA llama directo a Binance, Bybit ni Bitunix.
- [CONFIRMADO] Respuestas JSON (`Content-Type: application/json; charset=utf-8`).
- [CONFIRMADO] Endpoints observados (Fetch/XHR), con tamaño y tiempo aproximados:

| Endpoint | Tamaño | Tiempo | Frecuencia / notas |
|---|---|---|---|
| `/api/dashboard?t=…` | 73–76 KB | 1.85–3.32 s | cada 10 s; snapshot principal (TF 1H) |
| `/api/timeframe/{tf}?t=…` (4h, 1w vistos) | 66–69 KB | 3.3–5.1 s | al elegir TF y luego en cada ciclo; los más lentos |
| `news` | ~78–79 KB | ~740–900 ms | ¡cada 10 s! |
| `google-trends` | ~9 KB | ~370–500 ms | cada ciclo |
| `bias` | 5.7 KB | 487 ms | al cargar |
| `top-movers` | 3.3 KB | 647 ms | al cargar |
| `me` | 1.3 KB | 224–513 ms | solo al cargar (sesión del usuario) |
| `indices` | 1.2 KB | 288 ms | S&P, NQ, Gold, WTI |
| `cycle_index` | ~900–920 B | ~205–256 ms | cada ciclo ("Ciclo BTC 44") |
| `character` | 719 B | 609 ms | solo al cargar (personaje/avatar) |
| `balance` | 713 B | 624 ms | solo al cargar |
| `max-levels` | ~700 B | ~245–380 ms | cada ciclo |
| `daily_results` | ~620 B | ~257–430 ms | cada ciclo |
| `stats` | 614 B | 256 ms | ratings widget |
| `history?limit=10` | 695 B | 234–250 ms | gamif widget, periódico |
| `page_visit?page=dashboard` | 467 B | 471 ms | analítica propia |
| `orderflow` | 301 → `orderflow/` → 404 | 200 ms – 2.95 s | ROTO; falla en cada ciclo |

  También se vio el nombre `cryptocap_history` (no analizado; probablemente el histórico de market cap).
- [CONFIRMADO] Autenticación por cookie, sin token en headers ni URL:
  - `session_user_id=<id_numérico>.<hash_hex>`: formato casero "ID.firma". No es `sessionid` de Django, ni `connect.sid` de Express, ni `PHPSESSID`.
  - `cf_clearance=…`: pase anti-bot de Cloudflare.
- [INFERIDO] Backend en Python con pandas: columnas duplicadas y mezcladas (`Symbol`/`symbol`, `Precio_Raw`/`Precio_Num`/`Precio_Fmt`/`Precio`/`Feed`) y nombres en español con mayúscula y guion bajo, típico de un DataFrame exportado con `df.to_dict("records")`.
- [CORRECCIÓN] Al principio se dijo "casi seguro Django" por el 301 que añade "/" en `orderflow`. Pero faltan los headers que Django pone por defecto (`X-Frame-Options`, `X-Content-Type-Options`) y la cookie no es `sessionid`. El framework web NO se puede determinar; lo más probable es un backend a medida y sencillo.
- [INFERIDO] `/api/dashboard` tarda 2–3 s aunque pese 74 KB: no sale de una caché rápida, sino que se lee o arma en cada petición.

---

## 4. Estructura exacta de `/api/dashboard`

Claves de primer nivel:
```
timestamp: "22:27:00"
regime: { label: "BAJISTA", score: -85, … }
assets: []
balances: { hyperliquid: 0, bitunix: 0 }
candles: []          ← VACÍO: no se envían velas al navegador
crypto: [ …498 objetos… ]     ← tabla del TF 1H (por defecto)
daily_results: { mx_date: null, rows: [], totals: { open: 0, win: 0, loss: 0, winrate: 0 }, … }
ind: {}              ← VACÍO
logs: []
macro: { energy: 0, btc_price: null, fng_value: 55, flush_risk: 0.6087, crowdedness: 1.1384, … }
music: []
pnlday: { hyperliquid_usd: 0, hyperliquid_pct: 0, bitunix_usd: 0, bitunix_pct: 0 }
policies: { leverage: 10, riesgo_trade_pct: 1, riesgo_total_pct: 8, max_posiciones: 8, sizing_por_riesgo: true, … }
```

- [INFERIDO] `macro.fng_value` = Fear & Greed Index; `flush_risk` y `crowdedness` probablemente salen de funding y open interest.
- Orden de `crypto[]`: por capitalización de mercado. BTC, ETH, BNB, XRP, SOL, TRX, DOGE, ADA, BCH, LTC, LINK, XLM, SUI, ZEC, AVAX, XMR, HBAR, SHIB, WLFI, TON, DOT, UNI, TAO, AAVE, PEPE, ICP… Formato de símbolo: par de exchange (`BTCUSDT`).
- [INFERIDO] La lista de 498 monedas sale de cruzar los pares USDT del exchange con un ranking de market cap (CoinGecko/CMC); encaja con `cryptocap_history`.

### Objeto completo `crypto[0]` (BTC, TF 1H), literal
```
ADX: "16.8 <span class='text-[8px] opacity-70'>chop</span>"
ADX_Class: "text-gray-400"
ATR: "367.12 (0.45%)"
ATR_Class: "text-cyan-400"
Alert_Class: ""
Boll_Class: "text-gray-400"
Bollinger: "Lateral"
Change_24h: "-0.49%"
Change_24h_raw: -0.495
Change_Pct: 0
Color_Flecha: "red"
Div_Class: "text-gray-500"
Divergencia: "Sin Divergencia"
Feed: "$82,090.01"
Flecha: "▼"
Gaussian: "<span class='text-green-400'>Alcista</span>"
Liquidez: "—"
MarketEngine_Html: "<span class='text-red-400'>BAJISTA</span><br><span class='text-gray-500'>— sin señal</span>"
Nube: "<span class='text-green-400'>Alcista</span>"
Precio: "$82,090.01"
Precio_Fmt: "$82,090.01"
Precio_Num: 82090.01
Precio_Raw: 82090.01
RSI: 52
SMC: "Estructura OK"
SMC_Class: "text-gray-400"
Signal_Html: ""
Symbol: "BTCUSDT"
Tendencia: "<span class='text-green-400'>Alcista</span>"
UT_Alert: "SIN SEÑAL"
Velas: "<span class='text-green-400 font-black'>Bullish Engulfing</span>"
Vol: "B:53% S:47%"
Vol2_Html: "<span class='text-red-500'>Zombie</span><span class='text-gray-500'> · </span><span class='text-orange-400'>Ascendente</span>"
Vol_Class: "text-cyan-400"
Vol_Dir: "🟢"
Vol_Fmt: "B:53% S:47%"
Zonas: "<span class='text-gray-500'>Sin Zonas</span>"
adx: 16.80101423807101
adx_state: "chop"
asset_category: "crypto"
atr_pct: 0.004469074560215918
bb_pos: 0.5471765479739392
bb_regime: ""
bb_side: "MID"
close_val: 82090.01
rsi_txt: "52 (Alcista 🟢)"
rsi_val: 52
symbol: "BTC"
tendencia_text: "<span class='text-green-400'>Alcista</span>"
```

### Cómo leer esta estructura
- [CONFIRMADO] Cada activo trae dos capas de datos:
  - **Valores crudos** (minúscula): `rsi_val`, `adx`, `adx_state`, `atr_pct`, `bb_pos` (0–1), `bb_side` (LOW/MID/HIGH), `bb_regime`, `close_val`, `Change_24h_raw`.
  - **Presentación ya renderizada**: HTML con clases Tailwind, textos, emojis, flechas y colores (`Velas`, `Nube`, `Tendencia`, `Gaussian`, `Zonas`, `MarketEngine_Html`, `Vol2_Html`, `*_Class`…).
- [CONFIRMADO] TODOS los indicadores se calculan en el SERVIDOR. El navegador no recibe velas (`candles: []`) y no calcula RSI, Bollinger, zonas ni patrones.
- [CONFIRMADO] "Zombie · Ascendente/Descendente" es un régimen de VOLUMEN (`Vol2_Html`), no del RSI. "Lateral" es el estado de Bollinger.
- [INFERIDO] Indicadores portados de scripts populares de TradingView a Python:
  - `UT_Alert` = UT Bot Alerts
  - `Gaussian` = Gaussian Channel
  - `SMC` = Smart Money Concepts (estructura)
  - además ADX (con estado chop/trend/trend_strong), ATR, Bollinger, RSI, divergencias, patrones de velas (Bullish Engulfing, Hammer, Inverted Hammer, Doji, Bearish Engulfing), zonas S/R y liquidez.
- [CORRECCIÓN] Primero se dijo "Nube = probablemente Ichimoku". Pero `Nube`, `Gaussian` y `Tendencia` traen exactamente el mismo texto en 1H y en 4H, así que probablemente son el MISMO cálculo duplicado en tres campos (alias heredados). Que sea Ichimoku queda en duda. "(Dentro)" indica precio dentro de un canal o nube.
- [INFERIDO] Split de volumen B%/S%: volumen comprador taker contra el total (los klines de Binance traen "taker buy base asset volume"). No cambia entre timeframes (ver sección 6), así que probablemente es de 24h.

---

## 5. Generación de datos y frecuencia de actualización

- [CONFIRMADO] `/api/dashboard` trajo `timestamp: "22:27:00"`: segundos en :00 y ~3 min de atraso respecto a la petición (04:30 UTC). Corresponde a UTC-6 (hora de México); el campo `daily_results.mx_date` y el reloj "CST" del widget lo confirman.
- [INFERIDO] Un worker o cron en Python recalcula el snapshot general en lote cada ~1 minuto (o pocos minutos) y `/api/dashboard` lo sirve. El front pregunta cada 10 s por datos que cambian como mucho cada minuto.
- [CONFIRMADO] Los valores del panel de régimen se actualizan solos: "Reversión/Rebote" pasó de 67.8% a 55.2% y luego a 51.0% en pocos minutos.

---

## 6. Timeframe global (cómo funciona el selector 15M/1H/4H/1D/1W)

- [CONFIRMADO] Cada timeframe tiene su propio endpoint:
  - `GET /api/timeframe/4h?t=<epoch_ms>` (URL completa vista: `https://app.buscandocryptodinero.com/api/timeframe/4h?t=1792473298394`)
  - `GET /api/timeframe/1w?t=<epoch_ms>` (visto)
  - [INFERIDO] también `/api/timeframe/15m`, `/1h` y `/1d`.
- [CONFIRMADO] Respuesta:
  ```
  { timeframe: "4h", timestamp: "23:15:05", count: 498, crypto: [ …498 objetos… ] }
  ```
  Solo trae la tabla. Régimen, balances, macro y policies siguen viniendo de `/api/dashboard`, que se sigue pidiendo en paralelo cada 10 s.
- [CONFIRMADO] Pesa 66–69 KB y tarda 3.3–5.1 s; son las peticiones más lentas del sitio.
- [CONFIRMADO] El `timestamp` de `/api/timeframe` coincide con la hora exacta de la petición (23:14:14 y 23:15:05 CST, con segundos), a diferencia de `/api/dashboard`, que venía redondeado y atrasado.
- [INFERIDO] `/api/timeframe/{tf}` se calcula bajo demanda o con caché corta (de ahí los 3–5 s). No se puede descartar que el timestamp sea la hora de entrega y no la del cálculo.
- [CONFIRMADO] Al cambiar de TF, la petición sale desde dos lugares del código (`dashboard:1406` y `dashboard:4131`) con ~3 s de diferencia: llamada duplicada (clic + ciclo de polling).
- [CONFIRMADO] El `crypto[]` de `/api/dashboard` corresponde a 1H (TF por defecto). Evidencia: ATR de BTC 367.12 (0.45%) en dashboard contra 721.28 (0.88%) en 4h.
- [CONFIRMADO] Los 49 campos son idénticos en todos los timeframes; solo cambian los valores.
- [CONFIRMADO] El recálculo NO ocurre en el navegador.
- [CONFIRMADO] El panel de régimen muestra 1H/4H/1D/1W a la vez ("MTF"), así que al menos el régimen se calcula para todos los timeframes simultáneamente.

### Objeto BTC en 4H, literal
```
ADX: "31.0 <span class='text-[8px] opacity-70'>trend</span>"
ADX_Class: "text-red-400 font-semibold"
ATR: "721.28 (0.88%)"
ATR_Class: "text-yellow-300"
Alert_Class: ""
Boll_Class: "text-gray-400"
Bollinger: "Lateral"
Change_24h: "-0.71%"
Change_24h_raw: -0.714
Change_Pct: 0
Color_Flecha: "red"
Div_Class: "text-green-400"
Divergencia: "Alcista"
Feed: "$82,019.79"
Flecha: "▼"
Gaussian: "<span class='text-red-400'>Bajista</span> <span class='text-gray-300'>(Dentro)</span>"
Liquidez: "—"
MarketEngine_Html: "<span class='text-green-400'>ALCISTA</span><br><span class='text-gray-500'>— sin señal</span> <span class='text-orange-400'>⚡</span>"
Nube: "<span class='text-red-400'>Bajista</span> <span class='text-gray-300'>(Dentro)</span>"
Precio: "$82,019.79"
Precio_Fmt: "$82,019.79"
Precio_Num: 82019.79
Precio_Raw: 82019.79
RSI: 51
SMC: "Estructura OK"
SMC_Class: "text-gray-400"
Signal_Html: ""
Symbol: "BTCUSDT"
Tendencia: "<span class='text-red-400'>Bajista</span> <span class='text-gray-300'>(Dentro)</span>"
UT_Alert: "SIN SEÑAL"
Velas: "<span class='text-yellow-300 font-black'>Hammer</span>"
Vol: "B:53% S:47%"
Vol2_Html: "<span class='text-red-500'>Zombie</span><span class='text-gray-500'> · </span><span class='text-yellow-300'>Descendente</span>"
Vol_Class: "text-cyan-400"
Vol_Dir: "🟢"
Vol_Fmt: "B:53% S:47%"
Zonas: "<span class='text-gray-500'>Sin Zonas</span>"
adx: 30.98812003772427
adx_state: "trend_strong"
asset_category: "crypto"
atr_pct: 0.008780422563926155
bb_pos: 0.6737397415661034
bb_regime: ""
bb_side: "MID"
close_val: 82019.79
rsi_txt: "51 (Alcista 🟢)"
rsi_val: 51
symbol: "BTC"
tendencia_text: "<span class='text-red-400'>Bajista</span> <span class='text-gray-300'>(Dentro)</span>"
```

### Comparación BTC 1H → 4H
- ADX 16.8 "chop" → 31.0 "trend". Ojo: el texto visible dice "trend" y el valor crudo `adx_state` dice "trend_strong".
- ADX_Class `text-gray-400` → `text-red-400 font-semibold`.
- ATR 367.12 (0.45%) → 721.28 (0.88%).
- Divergencia "Sin Divergencia" → "Alcista".
- Velas "Bullish Engulfing" → "Hammer".
- MarketEngine "BAJISTA — sin señal" → "ALCISTA — sin señal ⚡".
- Vol2 "Zombie · Ascendente" → "Zombie · Descendente".
- Nube / Gaussian / Tendencia "Alcista" → "Bajista (Dentro)".
- RSI 52 → 51; bb_pos 0.547 → 0.674; Bollinger "Lateral" en ambos.
- Vol "B:53% S:47%" IDÉNTICO en ambos: el split de volumen no sale de las velas del TF.
- Otros valores vistos en la tabla para otras monedas: "Bajista (Dentro)", "Bajista → Alcista" (transición), Zonas "Dentro"/"Soporte", Velas "Inverted Hammer".

---

## 7. Ciclo de polling completo

- [CONFIRMADO] Cada ~10 s se dispara siempre este bloque, en este orden:
  `cycle_index` → `max-levels` → `news` → `google-trends` → `orderflow` (301 → `orderflow/` 404) → `daily_results` → `dashboard?t=…` (+ `/api/timeframe/{tf}?t=…` si hay un TF elegido)
- [CONFIRMADO] `news` (~79 KB) se pide cada 10 s: el mayor desperdicio de ancho de banda.
- [CONFIRMADO] `orderflow` falla en CADA ciclo; el 301 a veces tarda hasta ~3 s antes del 404.
- [CONFIRMADO] `me`, `character` y `balance` NO se repiten: solo se cargan al abrir la página.
- [CONFIRMADO] `history?limit=10` (bcd-gamif-widget.js:325) también aparece periódicamente.

---

## 8. Infraestructura

- [CONFIRMADO] Cloudflare como proxy completo:
  - IP `2606:4700:3033::6815:4615` (rango de Cloudflare)
  - `Server: cloudflare`
  - `Cf-Ray: a4d549ba8da8a546-MIA` (nodo Miami)
  - NEL/Report-To hacia `a.nel.cloudflare.com`
  - `Server-Timing: cfExtPri`
  - `Alt-Svc: h3=":443"; ma=86400` (HTTP/3 activo)
- [CONFIRMADO] `Content-Encoding: zstd` (compresión de Cloudflare).
- [CONFIRMADO] Sin caché: `Cf-Cache-Status: DYNAMIC`; `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`; `Pragma: no-cache`. Cada usuario golpea el servidor de origen cada 10 s.
- [CONFIRMADO] Request headers: `Accept: */*`, `Accept-Encoding: gzip, deflate, br, zstd`, `Cache-Control: no-cache`, `Sec-Fetch-Site: same-origin`, `Sec-Fetch-Mode: cors`, `Sec-Fetch-Dest: empty`, `Referrer-Policy: strict-origin-when-cross-origin`.
- [CONFIRMADO] Protección anti-bot de Cloudflare (`cf_clearance`); `robots.txt` prohíbe el acceso automatizado.
- [CONFIRMADO] Carga inicial: ~8.7 MB transferidos, ~13–14 MB de recursos, DOMContentLoaded ~1.5 s, Load ~1.7 s. Las llamadas Fetch/XHR suman solo ~0.5–0.6 MB: el peso viene del HTML monolítico y de los recursos estáticos.
- [NO VISIBLE] Hosting de origen detrás de Cloudflare (AWS, VPS u otro).

---

## 9. UI completa observada

- Cabecera: "GLOBAL INTELLIGENCE · BCD A-STRATEGY".
- Cinta superior animada:
  - PERDEDORES (ej. Q -26.79% / -32.88%, ARIA -21.21%, BTW -18.46%, SIREN -17.26%, ZEREBRO -15.11%)
  - GANADORES (ej. BR +28.88%, CTR +23.29%, XNY +17.54%)
  - VOLUMEN (BTC $1.8B, ETH $1.1B, SOL $243M, SNDK $90M, XRP $77M)
  - ÍNDICES (JP Nikkei 225 -1.08%, HK Hang Seng -0.95%…)
- Píldoras de navegación con desplegable: FREE ▾, SOCIOS ▾, BCD WORLD ▾, TIER 0.
- Badge de usuario: avatar, nombre ("Charly"), "Niv.1", saldo de Sats (3 ₿) y racha (🔥1).
- Reproductor de música con botón play y barra de volumen (campo `music: []`).
- **Widget de timeframe y reloj** (arriba, debajo del reproductor; NO aparece en vista móvil angosta):
  - "TF: 15M 1H 4H 1D 1W"
  - "ACTUAL: 23:12:07 CST", "NEXT: 23:17:22 CST"
  - [INFERIDO] Con 4H seleccionado, NEXT estaba solo ~5 min adelante, así que "NEXT" NO es el cierre de la vela: probablemente es la próxima actualización de datos (ciclo de ~5 min o TTL de caché). [PENDIENTE] confirmar si siempre salta de a 5 min.
- **Tarjeta "BALANCES & PNL"**:
  - "Bitunix: 0.00 (0.00 · 0.00%)"
  - Periodos: HOY, 7D, 30D, 60D, 90D, 180D, 1 AÑO
  - Tabla "RESULTADOS": ESTRATEGIA, TOTALES, ABIERTOS, GANADOS, PERDIDOS, EFECTIVIDAD; fila TOTAL; "Sin datos para este período."
  - "POLÍTICAS ESTÁNDAR": riesgo por operación 1.00% del capital del BOT, Lev x10; TP/SL según ATR, varía según la estrategia; máx. 8 posiciones por BOT; riesgo total abierto máx. 8.00% del capital del BOT; HOLD: 11 pérdidas en 24 h → pausa de 5 h.
- **Tarjeta "RÉGIMEN"**:
  - BAJISTA, "BUSCAR SHORTS", SCORE -85, badge "IN THE HUNT"
  - MTF: 1H SELECTIVO / 4H SELECTIVO / 1D SELECTIVO / 1W NO OPERAR
  - Breadth: 37A / 304B / 0L / 25T (A=alcistas, B=bajistas, L=laterales, T=transición, inferido)
  - Riesgo: BAJO (12.8%)
  - Reversión/Rebote: 67.8% · NO SHORTS (varía)
  - Liquidez: Soporte 0.8% | Resistencia 7.9%
  - Volumen: NONE | ZOMBIE · DESCENDENTE · Modo: SELECTIVO
  - Cada línea tiene "(click)" para ver el detalle.
  - "DECISIÓN OPERATIVA: LIBRE": "Precio comprimido entre muros (↑0.7% ↓0.8%) — evitar entradas · nivel LOW" (a veces solo "nivel LOW").
  - "CICLO BTC 44 · DCA PASIVO" con barra de progreso (endpoint `cycle_index`).
  - Panel macro: S&P 7,691 (+0.41%), NQ 26,431 (+1.11%), GOLD ~4,163 (+0.08%), WTI ~98.6 (-4.8%) (endpoint `indices`).
- **Barra de la tabla**: Buscar moneda…, filtro All (ligado a `asset_category`), EN POSICIÓN, BCD LAB, RWA, BCD BURBUJAS, ALERTAS, ATH, ESTACIONALIDAD, DEFAULT, TODAS.
- **Tabla**, columnas: ASSET, FEED (precio), 24H, SIGNAL ("SIN SEÑAL"), MANUAL (botones BUY/SELL + ícono 📋), NUBE, TREND (MarketEngine), ZONA, liquidez, divergencia, velas, volumen (B%/S% + Zombie…), RSI, Bollinger, etc.
- Ticker inferior fijo con precios (BTC, ETH, BNB, XRP, SOL, TRX, DOGE, ADA, BCH, LTC, LINK…).
- Botón flotante "★ 4.9 (32) Calificar".

### Ficha de detalle por moneda (modal al hacer clic en un activo)
- [CONFIRMADO] Encabezado "BTC · $BTC · Bitunix": el precio de referencia sale de BITUNIX (explica el formato BTCUSDT).
- [CONFIRMADO] Precio grande + variación del periodo (ej. "-25.73% · 1Y"); botones de periodo 1H, 4H, 1D, 1W, 1M, 1Y, cada uno con su %; "CAMBIO PERÍODO", "MÁXIMO PERÍODO" ($110,540.68), "MÍNIMO PERÍODO" ($59,577.01).
- [CONFIRMADO] Gráfico de LÍNEA (no velas) con área sombreada, eje de precio a la derecha, fechas abajo (10/26, 4/26, 10/18), línea punteada del precio actual, marca de agua "BUSCANDO CRYPTODINERO" y botón de expandir. [INFERIDO] Chart.js.
- [CONFIRMADO] Botones: CoinGecko y TradingView (enlaces externos), "📊 Más indicadores", "⚡ Trade On Bitunix" y "🎁 Crear cuenta (bono)". Cada ficha es un embudo de afiliado hacia Bitunix.
- [PENDIENTE] Qué endpoint alimenta el gráfico y si cada periodo hace una petición nueva (CoinGecko, Bitunix o API propia).

---

## 10. Qué es realmente el producto (análisis funcional)

- [INFERIDO, con fuerte evidencia] Es el **panel de control de un BOT de trading automático que opera la cuenta del usuario en Bitunix** (y Hyperliquid) vía API keys, con estrategias automatizadas que se activan. El JSON trae `balances`, `pnlday`, `policies`, `daily_results` y `logs`, y la UI muestra reglas de riesgo del "BOT". Nació como monitor del bot propio del creador y luego se abrió a usuarios.
- El nombre "BCD **A**-Strategy" y la columna "ESTRATEGIA" sugieren que hay varias estrategias para elegir.
- [INFERIDO] Los botones BUY/SELL de la columna MANUAL probablemente lanzan órdenes en el exchange conectado (no se probó).
- El panel de RÉGIMEN funciona como semáforo o filtro: dice cuándo operar y cuándo no ("Decisión operativa", "NO OPERAR" en 1W, "NO SHORTS"). Es su diferenciador frente a un screener puro.
- Hay modelo freemium por tiers (FREE / SOCIOS / TIER 0). [PENDIENTE] contenido y precios de los menús FREE ▾, SOCIOS ▾ y BCD WORLD ▾.
- [INFERIDO] Monetización principal: afiliado de Bitunix (comisión por volumen de sus usuarios), reforzada por la gamificación (sección 11) y los botones de afiliado en cada ficha.
- [INFERIDO] Desarrollo de una o pocas personas, en México.

---

## 11. Gamificación y modelo de negocio (fuente pública: `/guia-puntos`, "Cómo ganar BCD Sats")

- [CONFIRMADO] Dos monedas internas: **XP** (sube de nivel) y **BCD Sats** (se gastan).
- [CONFIRMADO] **Tiers 0–3 según el VOLUMEN de trading del usuario.**
  - Multiplicador de XP/Sats: Tier 0 = 1×, Tier 1 = 2×, Tier 2 = 3×, Tier 3 = 4×.
  - Tope diario de XP pasivo: 100 / 200 / 300 / 400. Los logros reales (trades ganadores, vincular cuenta…) no tienen tope.
  - Nivel máximo por tier: 25 / 50 / 75 / 100.
  - La página no dice qué volumen exacto da cada tier.
- **Eventos de recompensa:**
  - Dashboard web: login diario 10 XP; ver charts 30 s de interacción → 15 XP (cada hora); ver 5/10/20 secciones distintas al día → 20/30/50 XP + 5/10/20 Sats.
  - Trading con el bot: primer trade cerrado del día (auto o manual) 10 XP + 10 Sats; bono por 3+ trades en el día 15/15; cada trade cerrado con ganancia real 5/5 (máx. 5 al día); saldo en Bitunix 5 XP + 5 Sats por cada $500, snapshot diario a las 00:30 CST (ej. $10.000 → 100 XP base). Activo desde abril de 2026.
  - Rachas de días rentables (≥1 trade en verde por día), calculadas al cierre de cada trade: 3 días 20/20; 7 días 50/50; 14 días 100/100; 30 días 300/300.
  - Milestones de volumen en Bitunix (únicos de por vida): $10K 50/50; $50K 100/100; $100K 200/200; $500K 500/500; $1M 1.000/1.000.
  - Logros únicos: elegir avatar 20/20; vincular Telegram 50/50; activar primera estrategia automatizada 50/50; agregar API Keys de Bitunix 100/100; dejar una evaluación 150 XP / 300 Sats (desde el widget de calificaciones).
  - Redes: compartir tu personaje 10 XP + 5 Sats (1 vez al día); compartir una predicción 5/5 (1 vez por predicción al día).
  - Premios semanales (corte domingo 6:00 PM hora México; solo trades automáticos; acumulables): mejor win rate (mín. 5 trades) 500 XP / 400 Sats; mejor PnL neto (> $0) 400/300; mayor volumen operado 300/300; mejor % en un solo trade ganador 300/200; mayor ganancia en $ en un solo trade 300/200.
  - Bot de Telegram **@BCDAlertBOT**: `/sats` +5 XP / +5 Sats cada 4 h; cualquier otro comando +1/+1 por uso (tope 10 al día); sin cuenta vinculada, los puntos quedan "pendientes" hasta transferirlos con `/link` desde "Mi Personaje".
- **Curva de niveles** progresiva: nivel 2 = 200 XP; nivel 6 = 3.500 XP; nivel 10 ≈ 14.500 XP acumulado; nivel 100 ≈ 10 millones de XP acumulado.
- **Usos de los Sats**:
  - Tienda con 20+ ítems para el personaje (cabeza, cuerpo, arma, aura, botas, etc.).
  - `/ranking` con categoría "Sats gastados".
  - Próximamente: rifas con boletos en Sats, avatares generados con IA (Tier 2+), temporadas / Battle Pass, marketplace P2P de ítems, "BCD World temporada 2" con trabajo, sueldo y crédito.
- [INFERIDO] El rating "4.9 (32)" está sesgado: dejar una evaluación da la recompensa única más alta (300 Sats).
- [INFERIDO] Toda la gamificación empuja volumen y saldo en Bitunix, que es lo que paga la comisión de afiliado.
- [INFERIDO] Componentes técnicos necesarios para replicar algo así:
  - motor de eventos de XP con topes diarios por tipo de evento y por tier;
  - sincronización periódica de trades y saldo desde la API de Bitunix;
  - crons: snapshot de mercado (~1 min), refresco de ~5 min (reloj NEXT), saldo diario (00:30 CST) y premios semanales (domingo 18:00 CST);
  - cálculo de rachas al cerrar cada trade;
  - bot de Telegram compartiendo el backend y vinculación de cuentas (`/link`);
  - tienda, inventario y ranking.
- **Nota de diseño para SkillCash:** premiar volumen y número de trades con apalancamiento x10 incentiva sobreoperar. Si replico algo, quiero recompensas ligadas a la disciplina (respetar el riesgo, rachas sin violar reglas, cumplir el plan), no al volumen puro.

---

## 12. Deuda técnica observada (lo que NO debo copiar)

- Logs de debug en producción.
- Fetch inicial duplicado; fetch de timeframe duplicado (dashboard:1406 y 4131).
- Endpoint `orderflow` roto (301 → 404) que se sigue llamando cada 10 s.
- `news` (~79 KB) pedido cada 10 s.
- Tailwind por CDN en producción; Chart.js sin versión fijada.
- Cero caché (no-store) en datos que cambian cada ~1–5 min; cada usuario golpea el origen cada 10 s.
- El servidor manda HTML/clases CSS dentro del JSON, lo que acopla backend y diseño.
- Campos duplicados o redundantes (Precio/Precio_Fmt/Feed; Vol/Vol_Fmt; Nube/Gaussian/Tendencia/tendencia_text; RSI/rsi_val).
- Endpoints de 2–5 s de respuesta.
- HTML monolítico de 7.000+ líneas sin build.

---

## 13. Pendientes de investigar

1. Endpoint del gráfico de la ficha de moneda y si cada periodo (1W/1M/1Y) dispara una petición nueva.
2. Contenido y precios de los menús FREE ▾, SOCIOS ▾ y BCD WORLD ▾.
3. Preview de `me`, `character`, `balance`, `history`, `bias`, `top-movers`, `max-levels`, `cycle_index`.
4. Pantalla de conexión de API keys o estrategias (clic en el nombre de usuario).
5. Qué hacen EN POSICIÓN, BCD LAB, RWA, BURBUJAS, ALERTAS, ATH y ESTACIONALIDAD (y sus endpoints).
6. Confirmar si "NEXT" del reloj salta siempre de a 5 min.
7. Qué hacen los botones BUY/SELL.
8. Otras subpáginas públicas del sitio (indicadores parecidos a los míos), que investigaré después.

---

## 14. Qué quiero de ti, Claude Code

1. Guarda este documento en el repo y referéncialo desde CLAUDE.md (ver instrucciones al inicio).
2. Revisa mi proyecto actual y compáralo con esta arquitectura de referencia: qué ya tengo, qué me falta y qué hago mejor o peor.
3. Propón cómo replicar la funcionalidad útil, con mejoras claras sobre la referencia:
   - Worker que calcule en lote por timeframe (15m/1h/4h/1d/1w) y guarde snapshots precomputados (no cálculo bajo demanda de 3–5 s).
   - API que devuelva DATOS (valores crudos + estados como enums), NO HTML; el front decide los estilos (así puedo usar Tailwind compilado).
   - Caché corta en el borde/CDN (≈60 s o alineada al ciclo real de recálculo) en lugar de no-store; ETag/If-None-Match.
   - WebSocket o stream solo para el precio en vivo; el resto del snapshot por polling alineado al intervalo real de recálculo (no cada 10 s).
   - Noticias y datos lentos (news, google-trends, indices) con su propio intervalo largo.
   - Contador de cierre de vela calculado en el cliente a partir del timeframe, separado del "próxima actualización".
   - Panel de régimen / semáforo de "cuándo operar" como diferenciador.
   - Si hay gamificación: recompensas por disciplina, no por volumen.
4. NO escribas código todavía: primero diagnóstico de mi repo + plan por fases. Después te pasaré más hallazgos de la segunda investigación (subpáginas).
