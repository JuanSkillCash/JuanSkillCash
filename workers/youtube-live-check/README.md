# Worker: ¿está este canal de YouTube en vivo? + temas recientes

Revisa si un canal de YouTube está transmitiendo en vivo ahora mismo, y de paso trae sus últimos
videos subidos ("temas recientes"), sin necesitar una API key de YouTube (ver la explicación
completa en los comentarios de `worker.js`).

> **Juan: vuelve a pegar el código actualizado (19-nov-2026, 2º cambio del día)** - reportaste
> que un canal que SÍ está en vivo (confirmado por ti mismo en YouTube) a veces el sitio lo
> marcaba en vivo y a veces no, sin patrón claro, incluso entre celular y computador al mismo
> tiempo. Dos causas posibles, ambas reales en este tipo de Worker:
>
> 1. **Lectura rara de YouTube** (la que sí se puede arreglar en código): la página de YouTube a
>    veces responde bien pero con datos incompletos - un `ytInitialPlayerResponse` sin
>    `videoDetails`, o con el video de OTRO contenido (no el directo). Antes esto se leía
>    exactamente igual que "de verdad no está en vivo" y se guardaba así 60 segundos. Ahora se
>    detecta ese caso (`debug.hasVideoDetails`/`debug.channelIdMatch` en `?channel=...&debug=1`
>    más abajo) y se reintenta en 15s en vez de quedarse 60s con una lectura posiblemente mala.
> 2. **El caché de Cloudflare es "por sede"** (no se puede arreglar sin rediseñar esto, por ahora
>    no lo toqué): este Worker corre en decenas de centros de datos de Cloudflare alrededor del
>    mundo, y cada uno guarda SU PROPIA copia en caché por 60 segundos - no hay un solo caché
>    compartido. Si tu celular y tu computador salen a internet por rutas distintas (muy común),
>    pueden terminar pegándole a sedes distintas de Cloudflare, cada una con su propia copia
>    guardada en un momento ligeramente distinto - eso solo, sin que nada esté roto, ya explica
>    ver resultados distintos por unos segundos entre dispositivos. Si después de este cambio
>    sigue pasando seguido (no solo por unos segundos), avísame y lo rediseñamos con un caché
>    compartido de verdad (como el que ya usa el calendario económico con Supabase).
>
> Cambio anterior (mismo día): el campo `scheduledStartTime`
> (cuándo arranca un directo programado, para la cuenta regresiva "faltan Xh Ymin") ya está en
> producción. Sigue el mismo truco de raspar la página de YouTube, así que si en algún momento
> deja de verse la cuenta regresiva (pero el punto amarillo "programado" sigue apareciendo bien),
> probablemente YouTube cambió el formato interno de ese campo - no es grave, el sitio sigue
> funcionando igual, solo sin la cuenta regresiva.
>
> Cambio anterior (14-nov-2026): se agregó el campo `recientes` (últimos videos subidos del
> canal, máximo 3, de las últimas 24h) usando el mismo truco de siempre pero sobre la página
> `/videos` del canal en vez de `/live`. La detección de "en vivo" en sí no cambió en ese paso.

## Cómo desplegarlo

1. Entra al Worker **`skillcash-youtube-live`** en Cloudflare → **"Edit code"** → borra todo →
   pega **todo** el contenido del archivo `worker.js` de esta misma carpeta → **"Deploy"**.

## Forma de la respuesta

```json
{"live":true,"videoId":"Qr61waJ6AZg","title":"CNN en Español en vivo","channelId":"UC_lEiu6917IJz03TnntWUaQ",
 "checkedAt":1762500000000,"upcoming":false,"playability":"OK","embeddable":true,
 "scheduledStartTime":null,
 "recientes":[{"videoId":"zWfV3LJDnno","titulo":"La FAA levanta la suspensión de vuelos...","hace":"hace 4 h"},
              {"videoId":"9xNy2G3dSxQ","titulo":"FAA ordena la suspensión de todos los vuelos...","hace":"hace 8 h"}],
 "debug":{"httpStatus":200,"finalUrl":"https://www.youtube.com/watch?v=Qr61waJ6AZg","htmlLength":612345,
          "hasPlayerResponse":true,"consentPage":false,"botCheck":false}}
```

- `upcoming`: hay un directo anunciado pero todavía no arrancó (no intentar reproducir).
- `scheduledStartTime`: timestamp en milisegundos de cuándo arranca el directo programado (solo
  cuando `upcoming` es `true` y YouTube publicó esa fecha) - `null` si no aplica o no se pudo leer.
  El sitio lo usa para mostrar "Empieza en X h Y min" junto al punto amarillo.
- `playability`/`embeddable`: si `playability` no es `"OK"` o `embeddable` es `false`, el video
  no se debe intentar embeber aunque `live` sea `true` - el sitio ya maneja esto mostrando un
  link directo a YouTube.
- `recientes`: hasta 3 de los últimos videos subidos del canal, solo si son de las últimas 24
  horas (si no hay ninguno tan reciente, llega como arreglo vacío `[]`). Se usa en el sitio para
  mostrar "de qué está hablando" cada canal, tanto en la lista de canales (2ª línea, "Último: …")
  como debajo del reproductor ("Temas recientes en este canal").
- Cacheado 60 segundos en el borde de Cloudflare la parte de "en vivo" (15 segundos si hubo algún
  error o página rara). `recientes` se cachea aparte, 10 minutos (cambia mucho menos seguido), así
  que no se escanea la página de videos del canal en cada chequeo de "en vivo".

## Si `live` sale mal, revisa el `debug`

- `"consentPage":true` → YouTube sigue mandando la pantalla de "antes de continuar", pese a la
  cabecera `Cookie` que ya intenta evitarla. Avísame.
- `"botCheck":true` → YouTube detectó la IP de Cloudflare como tráfico de robot. Avísame (este
  es el caso donde haría falta el "Plan B" de abajo).
- `"hasPlayerResponse":false` con `"httpStatus":200` y sin `consentPage`/`botCheck` → YouTube
  cambió otra vez el formato de la página. Mándame el `"htmlLength"` que salió y lo reviso.

## Plan B (solo si `botCheck` sale en `true` seguido, es decir YouTube bloquea Cloudflare)

No implementado todavía - documentado aquí como lo que seguiría si hace falta:

1. Una sola llamada a la API oficial de YouTube: `videos.list` con `part=snippet,liveStreamingDetails`
   y hasta 50 IDs de video a la vez (cuesta solo **1 unidad** por llamada, de las 10.000
   unidades/día gratis) - **nunca** `search.list` (cuesta 100 unidades por llamada, se acabaría
   la cuota del día enseguida entre varios canales). `snippet.liveBroadcastContent=="live"` = en
   vivo.
2. El problema es conseguir el ID del video candidato sin la API oficial (que es lo que este
   Worker hace hoy raspando la página) - el feed RSS que se había pensado para esto
   (`youtube.com/feeds/videos.xml?channel_id=...`) **quedó confirmado muerto, da 404** (probado
   el 14-nov-2026 con 3 canales distintos) - **no usarlo**. Si se llega a necesitar el Plan B,
   hay que investigar de cero una forma de conseguir el ID del video candidato.

Si llegas a necesitarlo, dímelo con el `debug` completo de un caso con `botCheck:true` y lo
armamos con calma (necesita una API key de YouTube Data API v3 nueva, como secreto del Worker).
