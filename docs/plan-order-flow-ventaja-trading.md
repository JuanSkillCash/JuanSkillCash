# Plan (futuro): Order Flow orientado a ventaja de trading real

**Estado: pendiente de implementar — fecha: 2026-11-09**

NO está implementado. Esto es el documento completo que Juan preparó (con ayuda
de otra sesión de IA, investigando el repo open source `zadescoxp/order-flow-screener`)
como plan para evaluar e implementar a futuro un sistema de *order flow* que dé
una ventaja estadística real en trading — no otro indicador "bonito" sin
validar. Se guarda tal cual, completo, para no perder el trabajo de
investigación entre sesiones. Las "REGLAS PARA CUANDO SE IMPLEMENTE" (al final)
dejan claro que antes de escribir código hay que presentar un plan de archivos
y esperar la aprobación de Juan.

## Índice

- [Objetivo principal](#objetivo-principal)
- [Fuente: proyecto open source a reutilizar](#fuente-proyecto-open-source-a-reutilizar)
  - [Auditoría de seguridad (2026-11-09)](#auditoría-de-seguridad-hecha-el-2026-11-09)
  - [Arquitectura](#arquitectura)
  - [Funcionalidades](#funcionalidades)
- [Plan a futuro (orientado a ventaja de trading)](#plan-a-futuro-orientado-a-ventaja-de-trading)
  - [Fase 1 — Recolección de datos](#fase-1--recolección-de-datos-sin-datos-no-hay-ventaja)
  - [Fase 2 — Hipótesis a probar](#fase-2--hipótesis-a-probar-todas-son-hipótesis-no-ventajas-demostradas)
  - [Fase 3 — Laboratorio de backtesting](#fase-3--laboratorio-de-backtesting)
  - [Fase 4 — Forward test](#fase-4--forward-test)
  - [Fase 5 — Producto SkillCash](#fase-5--producto-skillcash)
  - [Fase transversal — Adaptador Bitunix](#fase-transversal--adaptador-bitunix)
- [Decisiones de integración pendientes](#decisiones-de-integración-pendientes)
- [Cumplimiento Apache 2.0](#cumplimiento-apache-20)
- [Reglas para cuando se implemente](#reglas-para-cuando-se-implemente)

---

Contexto: Soy Juan, de SkillCash (juanskillcash.com, repo JuanSkillCash/JuanSkillCash). Soy Official Partner de Bitunix. Construyo "SkillCash Tools": un screener RSI/estocástico multi-timeframe, un Radar de Nuevos Listados y un Radar de Deslistados (scrapers Python + GitHub Actions + Supabase), y un sistema de herramientas desbloqueables por volumen de afiliado en Bitunix, con rangos y minijuegos. Ese sistema está inspirado en mi investigación de Marines Live Platform (melapela.ai).

OBJETIVO PRINCIPAL: encontrar y validar herramientas que den una VENTAJA ESTADÍSTICA REAL para hacer trading rentable. No quiero indicadores "bonitos". Quiero señales con expectativa positiva demostrada con datos, después de comisiones, slippage y funding. Si una señal no demuestra ventaja, se descarta o se presenta solo como contexto, nunca como señal de entrada.

=== FUENTE: PROYECTO OPEN SOURCE A REUTILIZAR ===
- Repo: https://github.com/zadescoxp/order-flow-screener (Apache 2.0, v2.2.0, ~51 commits, 13 estrellas, muy reciente)
- Demo: https://order-flow.zadescoxp.com

--- Auditoría de seguridad (hecha el 2026-11-09) ---
- package.json: solo scripts dev/build/start/lint/test. Sin pre/postinstall.
- Dependencias: next 16.4.0, react/react-dom 19.3.0, zustand ^5.0.15, ws ^8.22.0, lucide-react 1.59.0, @types/ws. Dev: tailwind 4, jest 30, ts-jest, eslint 9, typescript 5.
- Sin eval, atob, new Function, binarios, .sh ni acceso a cookies.
- No pide wallets, login ni API keys de exchanges. Sin ejecución de órdenes.
- Endpoints (todos públicos/oficiales):
  wss://fstream.binance.com (public/ws y market/ws), wss://stream.binance.com, https://fapi.binance.com (openInterest, depth?limit=1000, fundingInfo, klines), https://api.binance.com/api/v3/klines, wss://stream.bybit.com/v5/public/linear y /spot, wss://ws.okx.com, https://www.okx.com/api/v5/public/instruments, wss://ws.bitget.com/v2/ws/public, wss://api.hyperliquid.xyz/ws, wss://www.deribit.com/ws/api/v2, wss://advanced-trade-ws.coinbase.com, wss://ws.finnhub.io (forex).
- Rastreo: Google Analytics en app/layout.tsx con ID G-RECLTGYHCC. QUITARLO si reutilizamos código.
- localStorage: solo preferencias de UI (uiStore), alertas (alertStore) y un flag del BugReportDialog.
- Alertas (lib/alerts/delivery.ts): tono generado con Web Audio API + Notification API. Sin envío a servidores.
- .env.example: NEXT_PUBLIC_FINNHUB_API_KEY (queda expuesta en el navegador; usar key restringida) y NEXT_PUBLIC_SITE_URL.
- Último commit auditado: "Merge pull request #20 from zadescoxp/feature/terminal-redesign" (2026-11-09). Re-auditar cualquier cambio posterior antes de usarlo.

--- Arquitectura ---
Exchange WebSockets → Exchange Adapters → Order Flow Engine → Zustand Store → React Components (Canvas API).

Archivos clave:
- lib/adapters/: base.ts (244 líneas), exchanges.ts (888), binanceFutures.ts (200), forex.ts (110), capabilities.ts (48).
- lib/engine/: orderFlowEngine.ts (466), alerts.ts (304), analytics.ts (274), derivatives.ts (258, OI/funding/basis), microstructure.ts (229, absorción/grandes prints), venues.ts (180), depthHistory.ts (141), priorSessions.ts (129), imbalance.ts (33, OBI).
- lib/render/liquidityHeatmap.ts, lib/recording/ (recorder, player, storage), lib/export/csv.ts, lib/session/ (MarketSession, RingBuffer, adapterPool, canvasScheduler), lib/aggregation/marketAggregation.ts, lib/config/ (venues, instruments).
- components/: FootprintChart, OrderBook, OBIPanel, CVDPanel, VolumeZScorePanel, VolatilityPanel, DepthOfMarket, TimeAndSales, LiquidationsPanel, OpenInterestPanel, VenuesPanel, AlertsMenu/AlertCard/AlertToasts, RecordingsMenu, ReplayBar, ExportMenu, IndicatorsMenu, MarketStatsBar, TopBar, StatusBar.
- __tests__/ cubre engine, adapters (fixtures), derivatives, alerts, recording/replay, export CSV, forex, aggregation y microstructure.
- Incluye AGENTS.md y docs/forex_setup.md.

--- Funcionalidades ---
Footprint (bid×ask, delta por nivel, imbalance 3x configurable, stacked imbalances, énfasis por z-score), order book (single/aggregated/compact), OBI de -1 a +1 con EMA, volume/trades profile (POC/VAH/VAL), DOM, z-score de volumen (ventanas 20/50/100/200), volatilidad realizada anualizada, CVD, VWAP, time & sales con filtros ≥2×/5×/10×.
Novedades: feed de liquidaciones, open interest, funding rate, basis perp vs spot, régimen de posicionamiento, burbujas de grandes prints, alertas por eventos, grabación/replay de sesiones, exportación CSV, heatmap de liquidez en reposo, marcadores de absorción, comparación de venues, estadísticas de la sesión anterior. Timeframes 1m a 4H, modos Perp/Spot/FX, 6 temas.

Venues: Perps (Binance, Bybit, OKX, Bitget, Hyperliquid, Deribit). Spot (Binance, Bybit, OKX, Bitget, Coinbase). NO soporta Bitunix.

=== PLAN A FUTURO (orientado a ventaja de trading) ===

FASE 1 — Recolección de datos (sin datos no hay ventaja)
- Reutilizar los adaptadores y el motor del repo en un recolector del lado del servidor (Node), no en el navegador, que guarde de forma continua: trades agregados, snapshots de order book (top N niveles), liquidaciones, OI, funding, basis y velas.
- Empezar con BTC y ETH en Binance y Bybit (la mayor liquidez) y agregar Bitunix cuando exista el adaptador.
- Almacenamiento: Supabase/Postgres para eventos y métricas; parquet o un almacenamiento barato para datos tick-level crudos. Estimar el costo de almacenamiento antes de empezar.
- La grabación de sesiones del repo (lib/recording) sirve para replays manuales, pero no reemplaza al recolector continuo.

FASE 2 — Hipótesis a probar (todas son HIPÓTESIS, no ventajas demostradas)
H1. Absorción en niveles clave: mucho volumen agresivo contra un nivel (POC/VAH/VAL de la sesión anterior, VWAP) sin que el precio avance → reversión.
H2. Cascadas de liquidación: tras un pico de liquidaciones (z-score alto) en una dirección → rebote de corto plazo (agotamiento).
H3. Funding extremo + OI subiendo + precio estancado → posicionamiento saturado → movimiento en contra de la mayoría.
H4. Divergencia CVD vs precio (nuevo máximo de precio sin nuevo máximo de CVD) → debilidad.
H5. Stacked imbalances (≥3 niveles a 3x) a favor de la tendencia → continuación.
H6. Grandes prints (≥5×/10× del tamaño medio) en dirección de la tendencia del timeframe mayor → continuación.
H7. Basis perp vs spot extremo → reversión a la media.
H8. Confluencia con mi screener: sobrecompra/sobreventa RSI/estocástico SOLO cuando el order flow lo confirma (absorción o divergencia CVD) frente a RSI solo. Medir si el filtro mejora la expectativa.
H9. Spikes de z-score de volumen + volatilidad realizada baja previa → ruptura.
Para cada hipótesis, definir reglas exactas y sin ambigüedad: condición de entrada, stop, take profit o salida por tiempo, y timeframe.

FASE 3 — Laboratorio de backtesting
- Motor de backtest sobre los datos de la Fase 1, event-driven, sin look-ahead bias (usar solo datos disponibles en el momento de la señal).
- Costos reales: comisiones taker/maker de Bitunix, slippage estimado según la profundidad del libro y funding pagado o recibido.
- Métricas por hipótesis: número de trades (mínimo ~100 para considerarla), win rate, R:R medio, expectativa por trade en R, profit factor, max drawdown, Sharpe/Sortino y distribución de resultados.
- Contra el sobreajuste: separar in-sample/out-of-sample, hacer walk-forward, limitar parámetros, probar la robustez con variaciones (si un pequeño cambio rompe la estrategia, no es ventaja) y comparar contra un baseline de entradas aleatorias con la misma gestión.
- Separar resultados por régimen de mercado (tendencia/rango, volatilidad alta/baja); una ventaja puede existir solo en un régimen.

FASE 4 — Forward test
- Paper trading en tiempo real con alertas automáticas durante al menos 4–8 semanas antes de arriesgar capital.
- Registrar cada señal en Supabase y compararla con el backtest. Si el resultado en vivo se desvía mucho, revisar la hipótesis.

FASE 5 — Producto SkillCash
- Solo las señales que pasen las fases 3 y 4 se convierten en "herramientas de ventaja". El resto se muestra como contexto de mercado, sin promesas.
- Mostrar en cada herramienta sus estadísticas reales (expectativa, número de trades, drawdown, periodo probado). Eso diferencia a SkillCash de la competencia que vende indicadores sin pruebas.
- Desbloqueo por volumen/rangos (estilo Marines Live / melapela.ai): contexto básico (footprint, CVD, OBI, liquidaciones) para rangos bajos; señales validadas, heatmap de liquidez, comparador de venues y alertas en tiempo real para rangos altos.
- Alertas al bot de noticias de Telegram, del lado del servidor, sin exponer tokens en el frontend.
- Gestión de riesgo integrada: calculadora de tamaño de posición por % de riesgo y stop, conectada a la Calculadora de Trading Skill Cash.
- Incluir avisos de riesgo: resultados pasados no garantizan resultados futuros.

FASE TRANSVERSAL — Adaptador Bitunix
- Crear el adaptador siguiendo base.ts y capabilities.ts.
- Usar SOLO la documentación oficial de la API pública de Bitunix (WebSocket de trades, order book, liquidaciones si existen, funding, OI). No inventar endpoints; lo que no exista en la API pública se marca como no soportado en capabilities.
- Tests con fixtures como en adapterFixtures.test.ts. Bitunix como venue por defecto.

=== DECISIONES DE INTEGRACIÓN PENDIENTES ===
a) Fork con branding SkillCash como subsección/subdominio, o
b) Extraer solo los módulos (adapters, derivatives, microstructure, liquidaciones, alertas, recording) e integrarlos a mi stack.
Cuando se implemente, recomendar una opción justificada.

=== CUMPLIMIENTO APACHE 2.0 ===
Conservar LICENSE, crear NOTICE con atribución a zadescoxp/order-flow-screener, marcar los archivos modificados y eliminar el Google Analytics G-RECLTGYHCC.

=== REGLAS PARA CUANDO SE IMPLEMENTE ===
- Antes de escribir código, presentar un plan con los archivos a crear o modificar y esperar mi aprobación.
- Clonar el repo fuente en una carpeta aparte, correr npm install y npm test, y re-auditar los commits nuevos.
- Prioridad: Fase 1 → 2 → 3 antes que cualquier interfaz. La interfaz va al final.
