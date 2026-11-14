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

## Ya desplegado y probado en producción (14-nov-2026)

Desplegado directamente desde Claude Code (con un token de Cloudflare que Juan autorizó para
esta tarea) y confirmado en vivo:

- **TradingView (fuente principal) respondió 403 (Forbidden)** apenas se desplegó - exactamente
  el escenario que este mismo README avisaba que podía pasar. O sea: TradingView SÍ empezó a
  exigir algo (probablemente las cabeceras `Origin`/`Referer` de su propia página) que este
  Worker deliberadamente no manda. **No se agregó ese spoofing** - sigue pendiente de que Juan
  decida si quiere intentarlo o no (ver "Decisión pendiente" abajo).
- **Forex Factory (respaldo) respondió 429 (Too Many Requests)** en varias pruebas seguidas -
  probablemente por el límite de peticiones que le pone a las IPs compartidas de Cloudflare
  (parecido a lo que ya pasaba con MyMemory/Google Translate en el Worker de noticias), no algo
  específico de este Worker. Con tráfico normal del sitio (una consulta real cada ~10 minutos,
  no las pruebas seguidas que se le hicieron para verificar esto) debería fallar mucho menos.
- **La copia de respaldo en KV sí funcionó como estaba pensada**: con las dos fuentes fallando,
  el calendario siguió sirviendo la última copia buena guardada, marcada `"desactualizado":true`,
  en vez de romperse con un error. El sitio NO se cayó en ningún momento de la prueba.

### Decisión pendiente para Juan: ¿qué hacer con el 403 de TradingView?

Mientras esto no se resuelva, el calendario funciona SOLO con Forex Factory (sin el dato
"Actual", solo Previsión/Anterior) o con la copia de respaldo en KV si Forex Factory también
falla en el momento. Opciones, sin tomar ninguna todavía:

1. **Dejarlo así** - Forex Factory + respaldo en KV ya cubre el calendario, solo sin el dato
   "Actual" publicado. Es lo más simple y lo que ya está funcionando ahora mismo.
2. **Agregar las cabeceras `Origin`/`Referer` de tradingview.com** a la petición - probablemente
   arreglaría el 403, pero es fingir que la petición viene de su propia página, algo que este
   Worker evitó a propósito hasta no confirmar que no viola los términos de uso de TradingView.
3. **Buscar otra fuente** para el dato "Actual" (alguna API de calendario económico de pago, o
   revisar si hay otro endpoint público de TradingView que sí acepte la petición tal cual).

No se hizo nada de esto sin que Juan lo decida primero.
