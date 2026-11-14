# Fuentes de datos de cada indicador/herramienta del sitio

Referencia de con qué fuente externa y con qué mecanismo se actualiza cada indicador o gráfico
de datos reales del sitio (`index.html`). Generado para responder la duda de Juan: "esto se
actualiza con esto, esto otro con esto otro" — para no tener que adivinar la próxima vez que algo
se vea desactualizado.

Dos mecanismos posibles:
- **En vivo (navegador)**: el navegador le pega directo a la API externa cada vez que el usuario
  abre esa herramienta. Siempre está fresco, no depende de ningún robot ni de Supabase.
- **Robot (GitHub Actions → Supabase)**: un workflow corre un script de Python en un horario fijo,
  guarda el dato en una tabla de Supabase, y el frontend lee esa tabla. Puede atrasarse si el
  robot falla o si la fuente original (ej. FRED) publica tarde.

## Macro (FRED / TradingView) — tabla `fred_series_history` y `macro_tv_history`

Todas estas se recalculan varias veces al día vía `update-macro-realtime.yml` (ventanas horarias
alrededor de cada publicación oficial EEUU) + un respaldo diario a las 00:30 UTC dentro de
`update-cryptocap-daily.yml`.

| Indicador (UI) | Fuente | Mecanismo | Script |
|---|---|---|---|
| Inflación CPI / CPI YoY | FRED (`CPIAUCSL`, `CPILFESL`) | Robot | `update_fred_series_daily.py` |
| PCE | FRED (`PCEPI`) | Robot | `update_fred_series_daily.py` |
| PPI | FRED (`PPIACO`) | Robot | `update_fred_series_daily.py` |
| Nómina no agrícola / desempleo | FRED (`PAYEMS`, `UNRATE`) | Robot | `update_fred_series_daily.py` |
| Solicitudes de desempleo | FRED (`ICSA`) | Robot | `update_fred_series_daily.py` |
| Tasa de interés de la Fed | FRED (`DFF`) | Robot | `update_fred_series_daily.py` |
| M2 (oferta monetaria) | FRED (`M2SL`) | Robot | `update_fred_series_daily.py` |
| PIB (crecimiento real) | FRED (`A191RL1Q225SBEA`) | Robot | `update_fred_series_daily.py` |
| Liquidez Neta (Fed − TGA − RRP) | FRED (`WALCL`, `WTREGEN`, `RRPONTSYD`) | Robot | `update_fred_series_daily.py` |
| **VIX** | **TradingView** (`TVC:VIX`, vía `tvDatafeed`) — escribe en `fred_series_history` con `series_id=VIXCLS` para no tocar el frontend | Robot | `update_macro_tv_daily.py` *(cambiado hoy; antes era FRED, con 1-2 días de rezago)* |
| DXY | TradingView (`TVC:DXY`) | Robot | `update_macro_tv_daily.py` |
| PMI manufacturero | TradingView (`ECONOMICS:USBCOI`) | Robot | `update_macro_tv_daily.py` |
| ~~Rendimientos del Tesoro (DGS2/5/10/20/30, T10Y2Y)~~ | ~~FRED~~ | **Eliminado hoy** — no se mostraba en ninguna página del sitio | — |

## Cripto — gráficos en vivo (sin robot, tabla ninguna)

| Indicador (UI) | Fuente | Mecanismo |
|---|---|---|
| **Bandas Log de ETH** (la "cosa logarítmica" de ETH) | **Coin Metrics Community API** (`community-api.coinmetrics.io`, gratis/sin llave) — histórico diario completo de ETH. Si falla, respaldo a CoinGecko (`coins/ethereum/market_chart`, solo últimos 364 días) | En vivo, recalculado cada vez que se abre la herramienta |
| **Rainbow Chart (BTC, regresión logarítmica)** | Mismo historial diario que usa "Ciclos de Halving" (Coin Metrics) — la curva central es una regresión fija calculada una vez sobre 2009-2021, no se recalcula con cada carga | En vivo |
| ETH/BTC, Ciclos de Halving | Coin Metrics Community API | En vivo |
| Simulador de portafolio, buscador de monedas, DCA, Comparador de correlación, precios "simple price" | CoinGecko (`api.coingecko.com`, proxiado vía `cgUrl()`) | En vivo, bajo demanda |
| Gráficos de velas BTC/ETH (ej. calculadora de futuros) | **Binance** (`api.binance.com/api/v3/klines`, `fapi.binance.com` para futuros) | En vivo |
| Capitalización total / dominancia (dashboard, boletín) | CoinGecko (`global`) en vivo para el dashboard; además hay un snapshot diario guardado en `cryptocap_history` | En vivo (dashboard) + Robot diario (histórico) — `update_cryptocap_daily.py`, 00:30 UTC |

## Cripto — robots (Supabase)

| Indicador (UI) | Fuente | Tabla | Script | Frecuencia |
|---|---|---|---|---|
| Fear & Greed (valor actual) | CoinMarketCap | `cmc_fng_latest` | `update_cmc_fng_latest.py` | Cada hora (`0 * * * *`) |
| Fear & Greed (histórico) | CoinMarketCap | `cmc_fng_history` | `update_cmc_fng_daily.py` | Diario, dentro de `update-cryptocap-daily.yml` |
| Market cap histórico (snapshot) | CoinGecko | `cryptocap_history` | `update_cryptocap_daily.py` | Diario (00:30 UTC) |
| Tendencias de Google | Google Trends | `google_trends_history` | `update_google_trends_daily.py` | Diario |
| STH-MVRV | (on-chain) | `sth_mvrv_history` | `update_sth_mvrv_daily.py` | Diario |
| Ganancia/pérdida por época | (on-chain) | `epoch_profit_loss_daily` | `update_epoch_profit_loss_daily.py` | Diario |
| Costo de producción BTC | (minería) | `cost_of_production_history` | `update_cost_of_production_daily.py` | Diario |
| Costo base del Tesoro (empresas con BTC) | CoinGecko | — | `update_treasury_cost_basis_daily.py` | Diario |

## Exchanges — delistados / nuevos listados

| Indicador (UI) | Fuente | Tabla | Script | Frecuencia |
|---|---|---|---|---|
| Deslistados (14 exchanges con API oficial) | APIs oficiales de cada exchange | `exchange_delistings` | `update_exchange_delistings.py` | Cada hora |
| Nuevos listados (14 exchanges) | APIs oficiales de cada exchange | `exchange_new_listings` | `update_new_listings.py` | Cada hora (`:15`) |
| Deslistados/listados de **Gate** | WebSocket público de Gate (`wss://api.gateio.ws/ws/v4/ann`) — su API REST completa está bloqueada por Akamai para la IP de GitHub Actions, así que esto es el respaldo | `exchange_delistings` / `exchange_new_listings` | `update_gate_frequent.py` | Cada 15 min (más frecuente que el resto porque el WebSocket solo entrega el último anuncio, no historial) |

## Afiliados / Bitunix

| Indicador (UI) | Fuente | Tabla | Script | Frecuencia |
|---|---|---|---|---|
| Rango de Manada / volumen de trading | API de Bitunix (solo lectura) | `user_exchange_volume`, `user_exchange_volume_history` | `update_bitunix_volume.py` | Cada hora (`:20`) |
| Estado de conexión Bitunix | API de Bitunix | `user_exchange_connections` | `update_bitunix_connections.py` | Cada hora (`:20`) |
| Bitácora (sincronización de operaciones) | API de Bitunix | `trade_journal_sync`, `trade_journal_trades` | `sync_journal_partner.py` | Diario (4:59 UTC) |

## Eventos y Noticias (Workers de Cloudflare, no pasan por Supabase)

En vivo desde el navegador, pero el navegador no le pega directo a la fuente externa (casi
ninguna trae cabeceras CORS) - le pega a un Worker propio de Cloudflare que hace de intermediario,
agrega/traduce/colorea, y cachea unos minutos en el borde. Ver `workers/<carpeta>/README.md` de
cada uno para cómo redesplegarlo si hay que actualizar el código.

| Indicador (UI) | Fuente real | Worker | Caché |
|---|---|---|---|
| Noticias Cripto / Macro y Economía | RSS de CoinDesk/Cointelegraph (cripto) y MarketWatch/Investing.com (macro), traducidos y resumidos con Workers AI (Llama 3.1) | `workers/rss-news/` (`skillcash-noticias`) | 30 min |
| Conferencias en Vivo (¿está este canal en vivo ahora?) | Scraping de la página pública `youtube.com/channel/<ID>/live` (no hay API oficial gratis que alcance para revisar 9 canales seguido) | `workers/youtube-live-check/` (`skillcash-youtube-live`) | 60 s |
| **Calendario Económico** | 3 fuentes combinadas (rediseñado 14-nov-2026, TradingView descartado - exigía fingir la cabecera Origin de su propia página): **Forex Factory** (`ff_calendar_thisweek.json`, horario/previsión/anterior, refrescada por un Cron Trigger cada 30 min y guardada en KV - nunca se le pide directo por visita, eso causaba 429) + **Nasdaq** (`api.nasdaq.com/api/calendar/economicevents`, dato "Actual"/consenso, sin llave) + **FRED** (respaldo oficial solo EE.UU., opcional, necesita el secreto `FRED_API_KEY` en el Worker) | `workers/economic-calendar/` (`skillcash-calendario`) | 15 min (1 min si hay un evento de alta importancia publicado hace menos de 30 min y todavía sin dato "Actual") |

## Telegram (no son indicadores del sitio, solo envíos)

Los 3 workflows de Telegram (`post-crypto-bulletin-telegram-daily.yml`, `post-fng-telegram-daily.yml`,
`post-dominance-telegram-daily.yml`) dependen de un disparo manual (`workflow_dispatch`) porque el
`schedule` nativo de GitHub Actions en este repo llega atrasado 3-6 horas — se disparan a mano cada
mañana a la hora correcta. No afectan ningún dato del sitio, solo el mensaje que se envía al canal.
