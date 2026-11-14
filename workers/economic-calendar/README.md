# Worker: calendario económico propio (reemplaza Investing.com/TradingView widget)

Trae los eventos económicos (CPI, nóminas, tasas de interés, etc.) desde TradingView (con
respaldo en Forex Factory si falla) y los devuelve ya traducidos, formateados y coloreados en
JSON, para la tabla propia de "Calendario Económico" (ver la explicación completa en los
comentarios de `worker.js`).

## Cómo desplegarlo (mismo patrón que los otros Workers de este sitio)

1. Entra a [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers y Pages** → **Crear**
   → **"Crear Worker"**. Dale el nombre **`skillcash-calendario`** (exacto, sin el nombre al azar
   que propone Cloudflare).
2. **"Editar código"** → borra todo el código de ejemplo → pega **todo** el contenido del archivo
   `worker.js` de esta misma carpeta → **"Desplegar"**.
3. **Crear y conectar el KV (una sola vez)** - esto es lo que guarda una copia de respaldo por si
   algún día las dos fuentes (TradingView y Forex Factory) fallan al mismo tiempo:
   - En el menú de la izquierda, **Almacenamiento y Bases de Datos** → **KV** → **Crear
     namespace**. Nómbralo, por ejemplo, `skillcash-calendario-kv`.
   - Vuelve al Worker `skillcash-calendario` → **"Settings"** → **"Bindings"** (o "Variables y
     bindings") → **"Add"** → elige **"KV Namespace"** → en **"Variable name"** escribe
     exactamente **`CALENDARIO_KV`** (así, en mayúsculas - el código lo busca con ese nombre
     exacto) → selecciona el namespace que acabas de crear → Guardar/Deploy.
   - Sin este paso el calendario sigue funcionando igual (TradingView/Forex Factory en vivo),
     solo que no tendría ningún respaldo si las dos fuentes fallan a la vez al mismo tiempo.
4. Cloudflare te va a dar una URL parecida a `https://skillcash-calendario.<tu-usuario>.workers.dev`
   — **mándame esa URL exacta** para conectarla al sitio.

## Cómo probarlo tú mismo (opcional, muy recomendado la primera vez)

Abre en el navegador (cambia la URL por la tuya real):

```
https://<tu-worker>.workers.dev/?debug=1
```

Con `?debug=1` la respuesta trae un bloque `"debug"` extra que dice exactamente qué pasó: si
TradingView respondió bien (`tvStatus`, `tvItems`) o si falló y por qué (`tvError`), y lo mismo
para Forex Factory. Sin `?debug=1`, la respuesta normal se ve así:

```json
{"fuente":"TradingView","actualizado":"2026-11-14T...","desactualizado":false,
 "eventos":[{"id":"tv-123","fechaUTC":"2026-11-14T13:30:00.000Z","divisa":"USD","pais":"US",
 "importancia":3,"evento":"Core CPI m/m","eventoES":"IPC subyacente m/m","actual":"0,3%",
 "prevision":"0,2%","anterior":"0,3%","tendencia":"bueno","direccion":"arriba", ...}]}
```

**Cosa muy importante que avisarme apenas lo pruebes**: si ves `"fuente":"Forex Factory"` en
vez de `"TradingView"` en una prueba normal (sin tumbar nada a propósito), o si `debug.tvError`
dice algo como "403" o "Forbidden", probablemente TradingView empezó a exigir que la petición
venga con cabeceras que digan que viene de su propia página (`Origin`/`Referer`) - en ese caso
**no agregues esas cabeceras tú mismo ni me pidas que lo haga sin que lo hablemos primero**
(podría no estar permitido por sus términos de uso). Avísame y lo revisamos con calma; mientras
tanto el calendario sigue funcionando con Forex Factory, solo que sin el dato "Actual".

## Límites a tener en cuenta (plan gratis de Cloudflare)

- **KV**: el límite documentado por Cloudflare al momento de escribir esto es **1000 escrituras
  por día** en el plan gratis (puede cambiar - conviene revisar la cifra vigente en
  `developers.cloudflare.com/kv/platform/limits` de vez en cuando). El código ya está hecho para
  escribir ahí como máximo una vez cada 10 minutos y solo si los datos cambiaron, así que en uso
  normal no debería acercarse a ese límite ni de lejos.
- **Cron Triggers** (la idea de "precalentar" la caché unos minutos antes de cada evento
  importante): se dejó FUERA de esta primera versión - el plan gratis de Workers limita cuántos
  Cron Triggers se pueden tener en la cuenta, y antes de sumar uno más conviene revisar cuántos
  ya estás usando en el resto de Workers de este sitio. Si quieres que lo agreguemos después,
  dímelo y lo revisamos con el panel de Cloudflare a la vista.

## No se pudo probar en vivo

Este Worker se escribió y se probó con datos SINTÉTICOS que imitan la forma real de las dos
fuentes (documentada en la investigación previa), porque el entorno donde se escribió esto no
tiene salida a internet hacia tradingview.com ni hacia faireconomy.media. La lógica (traducción,
colores, formato de números, respaldo entre fuentes) está probada; lo que falta confirmar
contigo es que las dos fuentes de verdad respondan como se espera una vez desplegado - por eso
el paso de `?debug=1` de arriba es tan importante la primera vez.
