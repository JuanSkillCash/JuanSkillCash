# Worker: calendario económico propio (Forex Factory + Nasdaq + FRED)

Trae los eventos económicos (CPI, nóminas, tasas de interés, etc.), ya traducidos, formateados y
coloreados en JSON, para la tabla propia de "Calendario Económico" del sitio (ver la explicación
completa en los comentarios de `worker.js`).

## Rediseño de fuentes (14-nov-2026)

**TradingView se descartó por completo.** Causa confirmada del error 403: su endpoint
`economic-calendar.tradingview.com/events` solo acepta peticiones con la cabecera `Origin` de su
propia página - no es bloqueo de IP ni límite de peticiones. Arreglarlo exigiría fingir esa
cabecera, y la decisión de Juan fue **no hacerlo**.

Arquitectura nueva, 3 fuentes:

1. **Forex Factory** (horario, importancia, previsión, anterior) - un **Cron Trigger la refresca
   cada 30 minutos y la guarda en KV**; el sitio nunca le pega directo a Forex Factory en cada
   visita (eso era lo que causaba los 429 con la versión anterior).
2. **Nasdaq** (`api.nasdaq.com/api/calendar/economicevents`) - el dato "Actual" + consenso, sin
   llave, verificado que no exige cabecera Origin.
3. **FRED** (oficial, solo EE.UU., opcional) - respaldo si Nasdaq no trajo el dato. Necesita el
   secreto `FRED_API_KEY` configurado en el Worker (ver abajo); si no está, simplemente no se usa.

## Cómo desplegarlo

1. Entra al Worker **`skillcash-calendario`** en Cloudflare → **"Edit code"** → borra todo → pega
   el contenido de `worker.js` de esta carpeta → **"Deploy"**.
2. **KV** (si no lo tenías ya de la versión anterior): **Storage & Databases → KV → Create** →
   nómbralo como quieras → en el Worker, **Settings → Bindings → Add → KV Namespace** → nombre de
   variable exacto **`CALENDARIO_KV`** → selecciona el namespace.
3. **Cron Trigger** (nuevo, necesario para que Forex Factory no de 429): en el Worker →
   **Settings → Triggers → Cron Triggers → Add** → **`*/30 * * * *`** (cada 30 minutos).
4. **FRED_API_KEY (opcional, recomendado)**: si quieres que el dato "Actual" de indicadores de
   EE.UU. tenga un respaldo oficial cuando Nasdaq no lo traiga, agrega el secreto: Worker →
   **Settings → Variables and Secrets → Add** → nombre **`FRED_API_KEY`** → tipo **Secret** →
   pega la llave de FRED que ya tienes (la misma que usan los scripts de Python del repo, o saca
   una nueva gratis en `fred.stlouisfed.org/docs/api/api_key.html`). Sin esto, el calendario
   sigue funcionando normal con Nasdaq solamente - solo se pierde el respaldo para los casos que
   Nasdaq no cubra.

## Cómo probarlo

```
https://<tu-worker>.workers.dev/?debug=1
```

Con `?debug=1` la respuesta trae `debug.ff` (si la copia de Forex Factory en KV está fresca o
desactualizada), `debug.nasdaq` (qué días se consultaron y cuántas filas trajo cada uno) y
`debug.fred` (si se intentó FRED para algún evento). Revisa semana del 9 al 13 de noviembre: debe
salir CPI 0,4% / Core CPI 0,3% / PPI 0,3% / Unemployment Claims 200K / Existing Home Sales 3,75M.

**Si `?debug=1` da un error 503 con `"Forex Factory respondió 429"`**: no es un error del código,
es que Forex Factory está rechazando temporalmente por el límite de peticiones compartido entre
todos los Workers de Cloudflare (no solo el tuyo) - reintenta en unos minutos. Con el Cron Trigger
puesto, esto se va a arreglar solo apenas el cron corra una vez con éxito (máximo 30 min).

## Verificado en producción (14-nov-2026)

Desplegado y probado contra las fuentes reales (con un token de Cloudflare que Juan autorizó para
esta tarea). La lógica de emparejamiento Forex Factory ↔ Nasdaq (con el desfase de 1 día en el
parámetro `date` de Nasdaq, y la desambiguación de filas duplicadas por magnitud) está probada con
un harness de Node contra los ejemplos reales documentados (CPI/Core CPI/PPI/Core PPI de la semana
del 9-13 de noviembre) - todos los casos pasaron. Falta confirmar en vivo (apenas el cron tenga
tiempo de correr sin toparse con el 429 de Forex Factory) que la respuesta real coincide con estos
mismos números - avísenme si ven algo distinto a lo documentado arriba.

### Pendiente: medir la velocidad real de Nasdaq/FRED

El 17-nov-2026 a las 8:30 ET (hora de publicación de Retail Sales) hay que medir cuántos minutos
tardan Nasdaq y FRED (`RSAFS`) en mostrar el dato real después de publicado, para confirmar o
ajustar el `latenciaMin` de `FRED_MAP` en el código. Programado un chequeo automático para ese
momento (ver scheduled task en Claude Code) - si no se hizo, probar a mano con
`?debug=1&desde=2026-11-17&hasta=2026-11-17&paises=US` varias veces esa mañana.

## Nota sobre `tendencia` (color verde/rojo) en CPI/PPI - no se tocó, queda para decidir aparte

La lógica de "bueno/malo" (`INDICADORES_INVERTIDOS`) solo invierte el color para desempleo/
solicitudes de subsidio/inventarios - CPI y PPI usan la regla por defecto ("actual > previsión =
bueno"), que es la misma convención que ya traía este Worker desde antes de este rediseño. Hay un
argumento para que CPI/PPI/Core-CPI/Core-PPI también estén invertidos (una inflación más alta de
lo esperado se suele leer como mala noticia) - no se cambió porque no fue parte de lo pedido en
este rediseño de fuentes. Si Juan quiere ese ajuste, es un cambio chiquito y aparte.
