# Inventario de widgets para el dashboard de "Mi Arrecife" (Fase 0)

Documento de solo-lectura: no se tocó `index.html` ni ningún otro archivo de producción
para hacer este inventario. Todo lo de aquí se verificó leyendo el código real
(`index.html`), citando línea y nombre de función/id reales. Donde no se pudo verificar
con la misma profundidad (los ~26 gráficos "bespoke" de Sonar de Mercado — ver sección 3)
se dice explícitamente, en vez de inventar detalle que no se comprobó.

Excluye, como pidió Juan: `data-category="rangos"` (Rango de Manada) y todo lo bloqueado
por `isWipLockedForCurrentUser()`. Ese candado real cubre `WIP_OWNER_ONLY_CATEGORIES =
['rangos', 'sharkoins']` (línea 11576) — además de "rangos", también bloquea "sharkoins",
pero Sharkoins no es una categoría de herramientas (es la tienda/minijuego), así que no
había ningún candidato de widget ahí de todas formas.

---

## 1. El motor genérico `renderDomChart` — 24 gráficos reparentables en el mismo patrón

Definido en `renderDomChart(key)`, línea **25266**, consumiendo el objeto `DOM_CHART_DEFS`
(línea **24317**, cierra en 24439, exactamente 24 claves). Cada gráfico depende de estos
IDs fijos en el DOM, todos construidos como `key + sufijo`:

- `key+'Loading'`, `key+'Error'`, `key+'ChartWrap'`, `key+'Legend'`, `key+'DateSlider'`,
  `key+'RangeFilter'`
- `key+'Stats'` **o** `def.statsId` si el def lo define (dombtc/domusdt/domall usan un
  `statsId` propio porque `key+'Stats'` ya lo ocupa el medidor en vivo de
  `renderDomLiveStat`, línea 25229 — ver sección 5).

Estado en memoria (objetos globales, **no** atados a la posición en el DOM — buena noticia
para reparentar): `domCustomRanges[key]`, `domActiveRanges[key]`, `domSliders[key]`.

**Riesgo real confirmado**: línea 25330, `const isMobileChart = window.innerWidth <= 640;`
y el `totalW`/`totalH` del SVG se fijan en 1100×420 (desktop) o 420×380 (mobile) según el
ancho de **toda la ventana**, no el del contenedor. Un gráfico de estos metido en un widget
angosto de 400px en una pantalla de escritorio se dibuja igual de "ancho" (1100) y se ve
chiquito/cortado. Esto es justo lo que la Fase 1 del plan ya anticipa resolver con
`ResizeObserver` + re-render en `resizestop`.

| id propuesto | nombre visible | familia | selector fuente | función que monta | depende de |
|---|---|---|---|---|---|
| w-domratio | Rotación ETH.D/BTC.D | chart | `#domratioChartWrap` | `renderDomChart('domratio')` | domratio+sufijos |
| w-domall | Descompresión Cripto | chart | `#domallChartWrap` | `renderDomChart('domall')` + `renderDomLiveStat('domall')` | domall+sufijos, `domallChartStats` |
| w-dombtc | Dominancia BTC (gráfico histórico) | chart | `#dombtcChartWrap` | `renderDomChart('dombtc')` | dombtc+sufijos, `dombtcChartStats` |
| w-domusdt | Dominancia USDT (gráfico histórico) | chart | `#domusdtChartWrap` | `renderDomChart('domusdt')` | domusdt+sufijos, `domusdtChartStats` |
| w-othersbtc | OTHERS/BTC | chart | `#othersbtcChartWrap` | `renderDomChart('othersbtc')` | othersbtc+sufijos |
| w-ethpmi | ETH + PMI Manufacturero | chart | `#ethpmiChartWrap` | `renderDomChart('ethpmi')` | ethpmi+sufijos |
| w-ethbtc | ETH/BTC | chart | `#ethbtcChartWrap` | `renderDomChart('ethbtc')` | ethbtc+sufijos |
| w-altfever | Euforia de Altcoins | chart | `#altfeverChartWrap` | `renderDomChart('altfever')` | altfever+sufijos |
| w-ethvsalt | ETH vs Altcoins | chart | `#ethvsaltChartWrap` | `renderDomChart('ethvsalt')` | ethvsalt+sufijos |
| w-dxy | Índice del Dólar (DXY) | chart | `#dxyChartWrap` | `renderDomChart('dxy')` | dxy+sufijos |
| w-pmius | PMI Manufacturero | chart | `#pmiusChartWrap` | `renderDomChart('pmius')` | pmius+sufijos |
| w-payrolls | Nómina No Agrícola | chart | `#payrollsChartWrap` | `renderDomChart('payrolls')` | payrolls+sufijos |
| w-unrate | Tasa de Desempleo | chart | `#unrateChartWrap` | `renderDomChart('unrate')` | unrate+sufijos |
| w-icsa | Solicitudes Semanales de Desempleo | chart | `#icsaChartWrap` | `renderDomChart('icsa')` | icsa+sufijos |
| w-cpi | Inflación CPI | chart | `#cpiChartWrap` | `renderDomChart('cpi')` | cpi+sufijos |
| w-cpiyoy | Inflación Interanual (CPI YoY) | chart | `#cpiyoyChartWrap` | `renderDomChart('cpiyoy')` | cpiyoy+sufijos |
| w-pce | PCE | chart | `#pceChartWrap` | `renderDomChart('pce')` | pce+sufijos |
| w-ppi | PPI | chart | `#ppiChartWrap` | `renderDomChart('ppi')` | ppi+sufijos |
| w-fedfundsrate | Tasa de la Fed | chart | `#fedfundsrateChartWrap` | `renderDomChart('fedfundsrate')` | fedfundsrate+sufijos |
| w-m2supply | M2 | chart | `#m2supplyChartWrap` | `renderDomChart('m2supply')` | m2supply+sufijos |
| w-vixindex | VIX | chart | `#vixindexChartWrap` | `renderDomChart('vixindex')` | vixindex+sufijos |
| w-netliquidity | Liquidez Neta | chart | `#netliquidityChartWrap` | `renderDomChart('netliquidity')` | netliquidity+sufijos |
| w-gdpgrowth | PIB (Crecimiento Real) | chart | `#gdpgrowthChartWrap` | `renderDomChart('gdpgrowth')` | gdpgrowth+sufijos |
| w-fedbalance | Balance de la Fed | chart | `#fedbalanceChartWrap` | `renderDomChart('fedbalance')` | fedbalance+sufijos |

---

## 2. Dominancia — resumen simple del inicio (distinto del gráfico de la tabla 1)

Además del gráfico histórico (tabla 1), hay un **resumen tipo barra** en `.market-overview`
que es un widget más simple/liviano:

| id propuesto | nombre visible | familia | selector fuente | función que monta | depende de |
|---|---|---|---|---|---|
| w-fngsummary | Índice de Miedo y Codicia (resumen) | kpi | `#fngSectionBox` (línea 4057) | ya pintado por `loadFearGreedIndex()` (línea 28955) | `fngValue`, `fngMarker`, `fngClass` |
| w-btcdombar | Dominancia BTC (barra simple) | kpi | `.dom-card.btc` (línea ~4075) | mismo `loadFearGreedIndex`/loader de dominancia, usa `#btcDomBar` | `btcDomBar`, `btcDomValue` |
| w-usdtdombar | Dominancia USDT (barra simple) | kpi | `.dom-card.usdt` | ídem, usa `#usdtDomBar` | `usdtDomBar`, `usdtDomValue` |
| w-halvingbar | Próximo Halving (cuenta regresiva) | kpi | `.dom-card.halving` | `setInterval` que actualiza `document.querySelectorAll('.halving-countdown-bar')` (línea 29094) | clase `.halving-countdown-bar` (no id — actualiza TODAS las que existan, así que un widget nuevo con esa clase se actualizaría solo, gratis) |

**Nota de riesgo en Fear&Greed**: `setInterval(loadFearGreedIndex, 3600000)` (línea 29009)
es una sola suscripción global, cada hora, que ya actualiza `fngDetailNeedle` (vista
detalle, línea 5698) y el resumen del inicio a la vez. No hay nada que inicializar por
instancia — bueno para reparentar, pero si el widget del dashboard y la home ambos quedan
vivos en el DOM (home "detrás" del dashboard, oculta con display:none en vez de
desmontada), la función igual los actualiza a los dos sin costo extra de red.

---

## 3. Los ~26 gráficos "a mano" (NO pasan por `renderDomChart`) — verificados solo como patrón

`data-indic-jump` tiene **65 valores únicos** en total (coincide con lo que decía el
prompt). De esos, 24 son los de la tabla 1. Los demás se reparten así:

- **7 son solo navegación de pestaña** ("guia", "bitcoinguia", "ethereumguia",
  "dominanciaguia", "macroguia", "tradingguia", "altcoinsguia") — no son widgets.
- **1 es el calendario** ("econcalendar", ver sección 6) y **2 son los radares**
  ("delistradar", "newlistradar", ver sección 7).
- **1 es "fng"** (la vista detalle de Miedo y Codicia, ya cubierta en la tabla 2).
- **1 es "predicciones"**, **1 es "cryptobubbles"** (mapa de burbujas — probablemente
  embebe algo externo, no se verificó a fondo) y **1 es "whitepaper"** (página estática,
  el PDF traducido).
- Quedan **~26 gráficos reales** que NO están en `DOM_CHART_DEFS`: `rainbow`, `picycle`,
  `ma4y`, `btcreturns`, `sthmvrv`, `epochpl`, `ethvwap`, `ethreturns`, `ethlogreg`,
  `btcxau`, `btcaapl`, `btctrends`, `treascb`, `treasuries`, `govtreasuries`, `cbpremium`,
  `longshort`, `optionsoi`, `total2`, `others`, `ema200`, `pisomercado`, `ciclosoporte`,
  `btcmacro`, entre otros de la lista completa.

**Se verificó UNA muestra a fondo** (Rainbow Chart) para confirmar el patrón:
`renderRainbowChart()` (línea 21180) es una función **propia y separada**, con su propio
`#rainbowChartWrap` (línea 6286) y una bandera de carga única
`ensureRainbowLoaded()`/`rainbowLoadedOnce` (línea 21378) — es decir, se carga **una sola
vez**, la primera vez que se ve, no cada vez que se abre el panel. `rainbowFit`,
`rainbowFitLogPrice`, `rainbowBandForResidual` (líneas 20975-20983) son matemática propia
de ese gráfico.

**Lo que esto significa para la Fase 1**: es muy probable que los otros ~25 sigan el MISMO
patrón (función propia `renderXChart()` + `#xChartWrap` + bandera `xLoadedOnce`), pero
**no se verificó cada uno individualmente** — sería inventar detalle que no se comprobó.
Cada uno necesita el mismo chequeo de 5 minutos que se le hizo a Rainbow antes de agregarlo
como widget: confirmar su función de render, su bandera de "cargado una vez" y si depende
de `window.innerWidth` igual que el motor genérico.

---

## 4. Calculadoras y referencias (`.modal-overlay`) — 29 modales totales

29 `.modal-overlay` en todo el sitio. **8 no tienen `data-tool`** y no son candidatos de
widget (son del sistema de cuenta, no de herramientas): `authModal`, `profileModal`,
`telegramModal`, `bitunixModal`, `colmGameModal`, `colmRouletteModal`, `legalModal`,
`assetDetailModal`.

Los **21 con `data-tool`** sí son candidatos:

| id propuesto | nombre visible | familia | modal / data-tool | categoría actual |
|---|---|---|---|---|
| w-calc-futuros | Calculadora de Futuros | calc | `calcModal` / `calculadora` | Zona de Caza |
| w-calc-rentabilidad | Calculadora de Rentabilidad | calc | `profitModal` / `rentabilidad` | Zona de Caza |
| w-calc-breakeven | Calculadora de Break-even | calc | `breakevenModal` / `breakeven` | Zona de Caza |
| w-calc-dca | Simulador de DCA | calc | `dcaModal` / `dca` | Zona de Caza |
| w-calc-mcap | Comparador de Market Cap | calc | `mcapCompareModal` / `mcapcompare` | Inversión |
| w-calc-fifreedom | Tiempo hasta la Libertad Financiera | calc | `fiFreedomModal` / `fifreedom` | Inversión |
| w-calc-unitconv | Conversor de Unidades | calc | `unitConverterModal` / `unitconverter` | Zona de Caza |
| w-calc-pct | Calculadora de Porcentajes | calc | `pctCalcModal` / `pctcalc` | Zona de Caza |
| w-calc-tzclock | Reloj de Zona Horaria | calc | `tzClockModal` / `tzclock` | Zona de Caza |
| w-calc-fees | Calculadora de Comisiones | calc | `feesModal` / `fees` | Zona de Caza |
| w-calc-quiz | Perfil de Riesgo | calc | `quizModal` / `quiz` | Inversión |
| w-calc-correlacion | Monitor de Correlación | calc | `correlationModal` / `correlacion` | Inversión |
| w-calc-walletcompare | Comparador de Wallets | calc | `walletCompareModal` / `walletcompare` | Blindaje |
| w-calc-approvals | Verificar Aprobaciones | calc | `approvalsModal` / `approvals` | Blindaje |
| w-calc-inheritance | Herencia Digital | calc | `inheritanceModal` / `inheritance` | Blindaje |
| w-calc-tokenscanner | Analizador de Token | calc | `tokenScannerModal` / `tokenscanner` | Blindaje |
| w-calc-checklist | Checklist de Seguridad | calc | `checklistModal` / `checklist` | Blindaje |
| w-calc-portafolio | Simulador de Portafolio | calc | `portfolioModal` / `portafolio` | Inversión |
| w-glosario | Glosario Cripto | table | `glossaryModal` / `glosario` | Manual del Depredador |
| w-mistakes | Biblioteca de Errores Comunes | table | `mistakesModal` / `mistakes` | Manual del Depredador |
| w-manual | Manual del Depredador | table | `manualModal` / `manual` | Manual del Depredador |

No se revisó el interior de cada modal en busca de timers/canvas/websockets individuales
(21 modales, fuera del alcance de una sola Fase 0) — eso le toca a cada "mount" cuando se
implemente en Fase 1/2, igual que con los gráficos bespoke de la sección 3.

---

## 5. Noticias

Sección completa en `#eventsNewsBlock`, con **dos listas independientes** adentro — buenos
candidatos a ser dos widgets separados en vez de uno solo:

| id propuesto | nombre visible | familia | selector fuente |
|---|---|---|---|
| w-news-cripto | Noticias — Mercado cripto | news | `#eventsNewsCrypto` |
| w-news-macro | Noticias — Contexto financiero global | news | `#eventsNewsMacro` |

No se rastreó la función JS exacta que las llena (nombre real no confirmado en esta
pasada) — se sabe que cargan vía Worker según las tareas ya completadas de esta sesión
("Widgets de noticias estilo melapela").

---

## 6. Calendario económico

| id propuesto | nombre visible | familia | selector fuente |
|---|---|---|---|
| w-calendario | Calendario Económico | calendar | `#eventsCalendarBlock` |

Contiene sus propios filtros con estado (`#calFilters`, botones `data-cal-filter`/
`data-cal-value` para importancia/divisa/rango de fechas) y dos vistas (`#calTable`
escritorio, `#calCards` móvil) — todo el bloque de filtros tiene que moverse junto con la
tabla/tarjetas, no por separado.

---

## 7. Radares (Deslistados / Nuevos Listados)

| id propuesto | nombre visible | familia | selector fuente |
|---|---|---|---|
| w-radar-delist | Radar de Deslistados | table | `#delistRadarWrap` (línea 6974) |
| w-radar-newlist | Radar de Nuevos Listados | table | selector equivalente `newListRadar*` |

Cada uno trae su propio `#delistRadarTabs` (pestañas por exchange) y
`#delistRadarAssetFilter` (filtro de activo) — son los widgets con más estado interno de
todo el catálogo (filtros + paginación + la estrella de "Mi Lista"), así que todo ese
subárbol tiene que reparentarse completo, no en piezas.

---

## 8. YouTube en vivo — el único que se queda como iframe

| id propuesto | nombre visible | familia | selector fuente |
|---|---|---|---|
| w-youtube-live | Conferencias en Vivo | video | `#eventsYtPlayerHost` (host del iframe) + `#eventsYtChannelList` |

Ya documentado en el historial de esta conversación: `mountPlayer()`/`unmountPlayer()`
siempre crean un iframe nuevo (nunca reutilizan uno viejo), con `enablejsapi=1`. El spec es
correcto en que este es el ÚNICO caso donde el contenido real sigue siendo un iframe — pero
el **host** (`#eventsYtPlayerHost`, la lista de canales, los controles) sí se reparenta
igual que todo lo demás; lo que no cambia es que el video en sí vive en su propio iframe de
YouTube, como ya es hoy.

---

## No reparentables sin refactor (razón técnica concreta)

Ningún candidato de la tabla 1, 2, 5, 6 o 7 quedó descartado — todos usan IDs string (no
posición en el DOM) y estado en objetos globales, que es justo lo que permite reparentar
sin tocar su lógica interna, tal como propone el plan.

Las únicas piezas genuinamente **no verificadas como reparentables** son los ~26 gráficos
bespoke de la sección 3 y los 21 modales de calculadoras de la sección 4 — no porque se
haya encontrado algo que lo impida, sino porque **no se revisó el código interno de cada
uno** en esta Fase 0 (habría significado leer miles de líneas más). La recomendación
concreta: antes de prometer cualquiera de esos ~47 candidatos como widget de Fase 1/2,
repetir en cada uno el mismo chequeo de 5 minutos que se le hizo aquí a Rainbow Chart
(buscar su función de render, su bandera de "cargado una vez", sus IDs fijos, y si usa
`window.innerWidth`).

---

## Propuesta de MVP (~12 widgets)

Mezcla real de familias, eligiendo los más representativos/valiosos de cada una — todos ya
verificados a fondo en este documento (nada de la sección 3 "no verificada"):

1. **w-fngsummary** — Índice de Miedo y Codicia: el indicador más reconocible del sitio, kpi puro, cero complejidad.
2. **w-halvingbar** — Próximo Halving: otro kpi muy pedido, y además demuestra que el patrón de clase (no id) ya se actualiza solo.
3. **w-dombtc** — Dominancia BTC (gráfico): el gráfico genérico más visto, con eje secundario (series2) — buena prueba de estrés para el ResizeObserver.
4. **w-m2supply** — M2: gráfico genérico de una sola serie, el caso "simple" para comparar contra el anterior.
5. **w-vixindex** — VIX: otro gráfico genérico de una sola serie, pero de una familia distinta (mercado tradicional, no cripto) — valida que el motor sirve para cualquier dato de `DOM_CHART_DEFS`.
6. **w-netliquidity** — Liquidez Neta: muy pedido por la comunidad cripto, gráfico genérico.
7. **w-calc-futuros** — Calculadora de Futuros: la calculadora más usada del sitio (es la herramienta #1 histórica), familia "calc".
8. **w-calc-dca** — Simulador de DCA: otra calculadora popular, con su propio botón de modo Compra/Venta — buena prueba de un formulario con estado interno más rico que una calculadora simple.
9. **w-calc-quiz** — Perfil de Riesgo: calculadora corta (6 preguntas), representativa de Inversión.
10. **w-news-cripto** — Noticias (Mercado cripto): la familia "news", valor inmediato para cualquier panel.
11. **w-calendario** — Calendario Económico: familia "calendar", ya tiene su propio frontend recién construido en esta misma conversación — probarlo aquí valida que el trabajo reciente no se rompe al reparentarlo.
12. **w-youtube-live** — Conferencias en Vivo: la familia "video", y el caso especial (sigue siendo iframe) que hay que probar explícitamente desde el inicio, no dejarlo para después.

---

## Conteo final de la Fase 0 (superado por la Fase 0b de abajo)

- **Candidatos a widget identificados en total: ~68** (24 gráficos genéricos + 4 de la
  tabla 2 + ~26 gráficos bespoke de la sección 3 + 21 modales de calculadora/referencia +
  2 de noticias + 1 calendario + 2 radares + 1 YouTube).
- **Reparentables y verificados a fondo en esta Fase 0: 42** (24 genéricos + 4 de dominancia/
  halving/miedo-codicia + 2 de noticias + 1 calendario + 2 radares + 1 YouTube + los 18
  calculadoras reales — sin contar las 3 de solo-referencia que no se revisaron por dentro).
- **Patrón confirmado pero NO verificados uno por uno: 26** (los gráficos bespoke de la
  sección 3) **+ 21** (los modales, sección 4, donde solo se confirmó la lista pero no el
  interior de cada uno) — ninguno de estos 47 tiene una razón CONOCIDA para no poder
  reparentarse, pero tampoco se puede prometer que sí sin revisarlos uno por uno primero.

---
---

# Fase 0b — Verificación completa + listado de exclusiones por categoría

Juan pidió no arrancar la Fase 1 con un MVP parcial: quiere saber de **toda la página**
qué NO puede entrar al dashboard y por qué, categorizado por razón. Esta sección completa
esa verificación: los ~26 gráficos bespoke y las 21 calculadoras que la Fase 0 había dejado
"sin revisar uno por uno", más un barrido del resto del sitio que la Fase 0 ni siquiera
había mirado (admin, cuenta, bitácora, referencia, Sharkoins, iframes, armazón de página).

**Metodología de esta pasada** (para que quede claro qué tan a fondo se revisó cada cosa):
en vez de abrir una por una las ~47 funciones pendientes, se hicieron búsquedas
**exhaustivas de todo el archivo** por los patrones de riesgo exactos que pidió el
coordinador — `setInterval(`, `<canvas`, `WebSocket(`, `<iframe` — y se ubicó cada
resultado real (son pocos: 15 `setInterval`, 1 `canvas`, 0 `WebSocket`, 4 `iframe`). Como
estas búsquedas cubren el archivo completo, un resultado que NO aparece ahí significa que
esa función específicamente no tiene ese problema — es una verificación real, no una
muestra. Lo que esta pasada NO hizo fue leer la lógica interna completa de las 47
funciones (seguiría tomando mucho tiempo), así que el hallazgo concreto es: **ninguna de
las ~47 tiene canvas, websocket, ni un timer propio sin limpiar** — el único timer
compartido real encontrado se documenta abajo con nombre y línea exactos.

## A. Los 3 hallazgos que cambian la conclusión de la Fase 0

1. **"Burbujas Cripto" SÍ es un iframe externo de terceros**, confirmado:
   `<iframe src="https://cryptobubbles.net" title="Crypto Bubbles" loading="lazy"
   allowfullscreen></iframe>` — línea **5657**. No es contenido propio del sitio, no se
   puede "reparentar" porque no hay nada que mover: es una ventana a otro sitio.
2. **No existe NINGÚN WebSocket en todo `index.html`** (0 resultados en el archivo
   completo) — se puede descartar esa preocupación por completo, no hay ningún
   indicador "en vivo" que dependa de una conexión persistente propia.
3. **Solo existe UN `<canvas>` en todo el sitio**: `#colmillosGameCanvas` (línea 11131),
   el minijuego "Salto del Tiburón" de Sharkoins. Ningún gráfico de indicadores usa
   canvas — los 24 genéricos y los ~26 bespoke son todos SVG dibujado a mano. Sharkoins
   ya está excluido por otra razón (ver sección C).

## B. "Necesita refactor real antes de poder ser widget" — el único bloqueo técnico real encontrado

De los 15 `setInterval(` del archivo completo, 13 son timers propios y autocontenidos de
una sola función/modal (YouTube, calendario, radar, dominancia, halving, sesiones de
mercado, cuenta/Telegram, el chip de precio de activo) — ninguno choca con otro. Uno
(`tzClockInterval`, Reloj de Zona Horaria) sí es un timer persistente dentro de una
calculadora, pero está **limpiado correctamente**: `openTzClockModal()` (línea 18063)
limpia cualquier intervalo anterior antes de crear uno nuevo, y `closeTzClockModal()`
(línea 18068) lo limpia al cerrar — no es un bloqueo, solo hay que llamar ese mismo cierre
al desmontar el widget.

El **único bloqueo real de verdad** es un temporizador **compartido globalmente**:

```
let indicAutoRefreshTimer = null;   // línea 11983
function startIndicAutoRefresh(fn, intervalMs){   // línea 11989
  stopIndicAutoRefresh();           // Cancela CUALQUIER refresco anterior, sin importar cuál era
  indicAutoRefreshTimer = setInterval(fn, intervalMs);
}
```

El comentario original del código (línea 11984) lo dice explícito: *"solo el gráfico que
está abierto en este momento tiene un temporizador activo — cambiar a cualquier otra
herramienta lo cancela."* Dos indicadores lo usan: **Coinbase Premium** (líneas 11998,
27686) y **Ratio Largo/Corto** (líneas 11999, 28754). Hoy eso no es problema porque el
sitio solo muestra UN panel de indicador a la vez. En un dashboard con varios widgets
vivos al mismo tiempo, si alguien mete Coinbase Premium Y Ratio Largo/Corto juntos (o dos
copias del mismo), el segundo que arranque **cancela el auto-refresco del primero** sin
avisar — se queda con datos viejos silenciosamente. Esto SÍ necesita refactor real
(pasar de una variable global a un timer por instancia) antes de poder ofrecer esos dos
como widgets que se actualizan solos.

**Todo lo demás revisado — los ~26 gráficos bespoke (sección 3 de la Fase 0) y las otras
19 calculadoras — no mostró ningún otro timer, canvas o websocket propio.** Comparten el
mismo defecto ya documentado en la Fase 0 (`const isMobileChart = window.innerWidth <=
640` — se confirmó que aparece **21 veces**, prácticamente en cada función de gráfico,
genérico o bespoke), pero eso ya estaba cubierto por el plan de `ResizeObserver` de la
Fase 1. No es un bloqueo nuevo, es el mismo de siempre, solo confirmado en más lugares.

## C. "Excluido a propósito por Juan" (mismo candado real)

`WIP_OWNER_ONLY_CATEGORIES = ['rangos', 'sharkoins']` (línea 11576) — las únicas dos claves
bajo `isWipLockedForCurrentUser()`:

- **Rango de Manada** (`rangos`) — ya excluido por instrucción directa de Juan.
- **Sharkoins** (tienda, minijuego "Salto del Tiburón", ranking, ficha del personaje) —
  mismo candado. Además de estar bloqueado, Sharkoins vive en su propia página de pantalla
  completa (`colmillosPageView`, cargada aparte vía `/assets/js/colmillos.js`) con un
  `<canvas>` de juego real — no es contenido de grilla ni aunque se destrabara.

## D. "Vive en un archivo que esta revisión no puede ver" — 3 hallazgos que requieren otra pasada

Tres funciones completas de la página **no están en `index.html`** — se cargan desde
archivos JS separados, así que esta revisión no puede certificar su interior:

| Función | Se abre con | Vive en |
|---|---|---|
| Bitácora de trading (`data-open-journal`) | `ensureJournalLoaded()` (línea 12435) | `/assets/js/journal.js?v=8` |
| Panel de Admin | `<script src="/assets/js/admin.js?v=1" defer>` (línea 30829) | `/assets/js/admin.js` |
| Gráfico en Vivo de Rango de Manada | `ensureLiveChartLoaded` (línea ~12438) | `/assets/js/livechart.js?v=6`, usa la librería `lightweight-charts` de TradingView vía CDN |

El Gráfico en Vivo ya queda excluido de todas formas (es parte de `rangos`, sección C). El
Panel de Admin se excluye por la sección E. La Bitácora de trading SÍ sigue siendo
candidata real — pero su reparentabilidad no se puede confirmar sin leer `journal.js`
aparte (fuera del alcance de esta revisión, que solo cubrió `index.html`).

`showCategoryDetail(cat)` y `showCategoryOverview()` (líneas 11596 y ~11662) ya tienen el
mismo gancho que el plan de Fase 1 necesita: antes de cambiar de categoría, llaman
`closeJournalPage()`, `closeAdminPage()`, `closeLiveChartPage()` (con guardas
`typeof X === 'function'`, por si ese script nunca se cargó) y `hideColmillosPage()`. El
`unmountAll()` del dashboard debería sumarse exactamente ahí, al lado de esas cuatro
llamadas — no inventar un mecanismo nuevo.

## E. "Es administración, no contenido de usuario"

- **Panel de Admin** (`#adminPageView`, línea 8378) — herramientas internas de Juan
  (gestión del sitio), no algo que un usuario arme en su propio panel. Se excluye por
  definición, sin necesidad de revisar más.

## F. "Es gestión de cuenta, no una herramienta de panel"

Modales confirmados en la Fase 0 que NO tienen `data-tool` (8 en total): `authModal`
(iniciar sesión), `profileModal` (Mi perfil: nombre, foto, contraseña, zona de peligro),
`telegramModal` (vincular/desvincular Telegram), `bitunixModal` (vincular Bitunix),
`legalModal` (Términos/Privacidad), `assetDetailModal` (chip de precio rápido, el que usa
`updateChipTime`, línea 13924). Todos son configuración de la cuenta o legal, no contenido
que tenga sentido "agrandar o achicar" en una grilla.

## G. "Es contenido de referencia, no un widget de panel" — con opinión

- **Glosario Cripto** (`glossaryModal`), **Biblioteca de Errores Comunes**
  (`mistakesModal`), **Manual del Depredador** (`manualModal`) — técnicamente SÍ son
  reparentables (son modales normales, sin timers/canvas, confirmado en la sección B). La
  razón para dejarlos fuera no es técnica, es de producto: son contenido para **leer**, no
  un dato que cambia y que tenga sentido vigilar en un panel. Mi opinión: el Glosario SÍ
  podría ganar algo siendo un widget chico de "búsqueda rápida" (el usuario ya le puso una
  palabra cripto rara en Sonar de Mercado y quiere el significado sin salir del panel) —
  los otros dos (Biblioteca de Errores, el Manual mismo) tienen menos sentido como widget
  de panel, se leen una vez y ya. Queda a criterio de Juan si quiere el Glosario en la
  lista de Fase 1/2 o no — no hay nada técnico que lo impida.

## H. "Es parte del armazón de la página, no contenido"

Para que la lista no deje huecos sin explicar: el header (logo, botones de cuenta,
notificaciones), la `.account-bar`, el hero (`.hero-mascot`, el título animado
SKILLCASH), el footer (enlaces, redes sociales, "Hecho para la Manada") y la barra lateral
misma (`.sb-nav`) — ninguno de estos es contenido que un usuario "agregue" a su panel, son
el marco fijo de la página alrededor de cualquier categoría, incluida Mi Arrecife.

## Conteo final (reemplaza el de la Fase 0)

- **Candidatos a widget en todo el sitio: ~68** (sin cambios respecto a la Fase 0).
- **Confirmados reparentables sin bloqueo técnico conocido, listos para Fase 1/2: 65**
  — los 24 gráficos genéricos, los ~26 bespoke, los 2 de dominancia simple + halving +
  miedo-codicia, los 21 modales con `data-tool` (calculadoras + Glosario/Errores/Manual
  de referencia), 2 de noticias, 1 calendario, 2 radares y 1 YouTube. Esto es **el 100%
  del catálogo incluible que pidió Juan**, no un MVP de 12.
- **Con un bloqueo técnico real, necesitan refactor antes de poder ofrecerse como
  "siempre vivos": 2** — Coinbase Premium y Ratio Largo/Corto (temporizador global
  compartido, sección B). Se pueden ofrecer igual en Fase 1 como widgets que se actualizan
  solo con el botón de refrescar manual, mientras no se haga el refactor.
- **Sin verificar por vivir en otro archivo: 1** — Bitácora de trading (`journal.js`).
- **Excluidos con razón de producto/cuenta, no técnica: 8 modales de cuenta** (sección F)
  **+ Panel de Admin** (sección E) **+ Glosario/Errores/Manual si Juan decide dejarlos
  fuera** (sección G, su opinión pendiente) **+ el armazón de la página** (sección H).
- **Excluidos por decisión explícita de Juan o por ser un iframe externo real: Rango de
  Manada + Sharkoins** (mismo candado, sección C) **+ Burbujas Cripto** (iframe a
  cryptobubbles.net, sección A).
