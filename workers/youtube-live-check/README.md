# Worker: ¿está este canal de YouTube en vivo? + temas recientes

Revisa si un canal de YouTube está transmitiendo en vivo ahora mismo, y de paso trae sus últimos
videos subidos ("temas recientes") - ver la explicación completa en los comentarios de `worker.js`.

> **Juan: vuelve a pegar el código actualizado (20-nov-2026, 3er cambio del día - "Plan B",
> 2ª vuelta) Y crea el namespace de KV de abajo** - la 1ª versión del "Plan B" (atajo con la API
> oficial) guardaba el "ID de video conocido" en el caché normal de Cloudflare, que es **por
> borde** (cada centro de datos de Cloudflare tiene el suyo, no se comparten entre sí). Probaste y
> seguía sin funcionar - tiene sentido: el borde que te atiende A TI sigue bloqueado por YouTube,
> así que NUNCA iba a tener la oportunidad de "aprender" el ID por sí solo, sin importar cuántas
> veces el resto de visitantes (en otros bordes, sin bloqueo) sí lo descubrieran.
>
> Arreglo real: el ID conocido ahora se guarda en un **namespace de KV** de Cloudflare - a
> diferencia del caché normal, esto SÍ es compartido de verdad entre TODOS los bordes. En cuanto
> CUALQUIER visitante (en cualquier parte del mundo, en un borde sin bloqueo) descubre el video en
> vivo de un canal, tu borde ya puede leer ese mismo dato y confirmarlo con la API oficial sin
> tener que raspar (ni bloquearse) él mismo.
>
> **Paso nuevo que falta (una sola vez)**: crear el namespace de KV y conectarlo al Worker:
> 1. En Cloudflare, menú izquierdo → **Almacenamiento y bases de datos** → **KV** → **Crear
>    namespace** → nómbralo `skillcash-youtube-known-ids` → Crear.
> 2. Entra de nuevo al Worker **`skillcash-youtube-live`** → **Settings** → baja hasta
>    **"Bindings"** (o "Vinculaciones") → **"Add"** → elige **"KV Namespace"**.
> 3. En **"Variable name"** escribe exactamente: `YT_KNOWN_IDS`
> 4. En **"KV namespace"** elige el que acabas de crear (`skillcash-youtube-known-ids`).
> 5. Guarda/Deploy.
>
> Sin ese namespace conectado (o si algo falla), el Worker sigue funcionando igual que la 1ª
> versión del Plan B (caché por borde, el atajo solo sirve si tu PROPIO borde logró aprender el
> ID) - no se rompe nada, solo no resuelve el caso de un borde bloqueado todo el tiempo como el
> tuyo.
>
> Cómo queda funcionando (resto del Plan B, igual que antes): la primera vez que el raspado de
> siempre encuentra un canal en vivo, se guarda ese ID de video 6 horas en el KV compartido. En la
> SIGUIENTE revisión de ese mismo canal (en CUALQUIER borde), en vez de raspar, se le pregunta a
> la API oficial "¿este video específico sigue en vivo?" (`videos.list`, 1 de las 10.000 unidades
> gratis al día, nunca tratada como "tráfico inusual"). Si el video ya terminó (o la API falla),
> se cae de vuelta al raspado normal - puede que haya un directo NUEVO con otro ID.
>
> Lo que esto sigue sin resolver: el PRIMER descubrimiento de un canal que arranca un directo
> nuevo con un ID todavía desconocido (Casa Blanca, ruedas de prensa sueltas) necesita que ALGÚN
> borde (no necesariamente el tuyo) logre raspar sin ser bloqueado - una vez que CUALQUIERA lo
> logra, todos los demás bordes (incluido el tuyo) se benefician al instante via KV.
>
> Cambio anterior (mismo día) - reportaste "varios canales en
> vivo a esta hora y no me está mostrando que está en vivo", con TODOS los canales en rojo a la
> vez (no solo uno). Lo confirmamos pidiéndote que abrieras el link directo del Worker
> (`?channel=...`) desde tu propio navegador: YouTube te estaba respondiendo con HTTP 429 y una
> redirección a `google.com/sorry/...` (la pantalla de "verificar que no eres un robot") - el
> borde de Cloudflare que te atiende a ti se quedó sin cupo de peticiones sin clave ante YouTube,
> algo por IP/región, no por canal (por eso afectaba a TODOS los canales de tu visita a la vez,
> mientras a mí, desde otra IP, me seguía respondiendo bien).
>
> Esa página de bloqueo es muy cortita y casi nunca trae ninguna de las frases que ya buscaba
> `esPaginaDeBotCheck()` ("unusual traffic", "no eres un robot"...), así que se colaba como
> `live:false` normal - el sitio no tenía forma de distinguir "de verdad no está en vivo" de "no
> se pudo revisar, YouTube bloqueó la petición". Dos arreglos:
>
> 1. **Backend**: nueva función `esBloqueoDeGoogle()` que detecta este caso específico (HTTP 429 o
>    redirección a `google.com/sorry/`) y lo marca igual que un `botCheck` (acorta el caché a 15s
>    para reintentar pronto) + un campo nuevo en la respuesta, `"bloqueado":true`.
> 2. **Frontend** (`index.html`): cuando `bloqueado` sale `true`, el sitio YA NO pinta el punto en
>    rojo (eso afirmaría "confirmado que no está en vivo", que es falso) - deja el canal tal cual
>    estaba (el último dato confiable que sí se tenía, o gris si nunca se supo) y, si fue un
>    "Buscar directo" manual, avisa en texto que YouTube bloqueó la verificación momentáneamente.
>
> Esto no evita que YouTube bloquee esa IP de Cloudflare de nuevo - solo evita que el sitio lo
> MUESTRE como una mentira ("sin directo ahora" cuando en realidad no se pudo ni preguntar). Si
> esto te sigue pasando SEGUIDO (no solo una vez cada tanto), ya toca el "Plan B" de la API
> oficial de YouTube (ver más abajo).
>
> Cambio anterior (19-nov-2026, 2º cambio del día, confirmado por Juan) - reportaste
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
 "scheduledStartTime":null,"bloqueado":false,
 "recientes":[{"videoId":"zWfV3LJDnno","titulo":"La FAA levanta la suspensión de vuelos...","hace":"hace 4 h"},
              {"videoId":"9xNy2G3dSxQ","titulo":"FAA ordena la suspensión de todos los vuelos...","hace":"hace 8 h"}],
 "debug":{"httpStatus":200,"finalUrl":"https://www.youtube.com/watch?v=Qr61waJ6AZg","htmlLength":612345,
          "hasPlayerResponse":true,"consentPage":false,"botCheck":false}}
```

- `bloqueado`: `true` cuando YouTube bloqueó/rate-limitó la petición (HTTP 429 o redirección a
  `google.com/sorry/`) - el sitio NO debe leer esto como "confirmado que no está en vivo", sino
  como "no se pudo revisar ahora mismo" (ver el cambio del 20-nov-2026 arriba).

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

- `"debug":{"fuente":"api-oficial",...}` → esta respuesta NO vino de raspar la página, vino del
  atajo de la API oficial (ver "Plan B" abajo) - los demás campos de `debug` (httpStatus,
  finalUrl, etc.) quedan vacíos a propósito, no aplican a este camino.
- `"consentPage":true` → YouTube sigue mandando la pantalla de "antes de continuar", pese a la
  cabecera `Cookie` que ya intenta evitarla. Avísame.
- `"botCheck":true` → YouTube detectó la IP de Cloudflare como tráfico de robot (incluye el
  bloqueo con HTTP 429 / redirección a `google.com/sorry/` - ver "bloqueado" más abajo). El
  "Plan B" ya implementado reduce cuánto pasa esto para los canales 24/7, pero sigue pudiendo
  pasar en canales que arrancan un directo con un ID nuevo que todavía no se conoce.
- `"hasPlayerResponse":false` con `"httpStatus":200` y sin `consentPage`/`botCheck` → YouTube
  cambió otra vez el formato de la página. Mándame el `"htmlLength"` que salió y lo reviso.

## Plan B - IMPLEMENTADO (20-nov-2026)

Ya no es un plan pendiente - ver el cambio de arriba. Resumen de cómo quedó, para referencia:

1. `videos.list` con `part=snippet,liveStreamingDetails` (cuesta solo **1 unidad** por llamada, de
   las 10.000 unidades/día gratis) - **nunca** `search.list` (100 unidades por llamada, inviable
   revisando varios canales seguido). `snippet.liveBroadcastContent=="live"` y sin
   `liveStreamingDetails.actualEndTime` = sigue en vivo.
2. El problema seguía siendo conseguir el ID del video candidato sin la API oficial (el feed RSS
   que se había pensado para esto, `youtube.com/feeds/videos.xml?channel_id=...`, sigue muerto, da
   404 - no usarlo). Solución real: no se necesita descubrir el ID por adelantado - se usa el ID
   que el raspado de siempre YA encontró la primera vez, guardado 6 horas (ver
   `obtieneIdConocido`/`guardaIdConocido` en `worker.js`), y la API oficial solo CONFIRMA que ese
   mismo video sigue en vivo en revisiones futuras. Cuando ese video termina, se cae de vuelta al
   raspado para descubrir el siguiente - el raspado nunca desaparece del todo, solo se usa mucho
   menos seguido para los canales que mantienen el mismo video por horas/días/semanas.
3. Requiere el secreto `YOUTUBE_API_KEY` en el Worker (Settings → Variables and Secrets). Si no
   está configurado, o la llave falla, el Worker funciona exactamente igual que antes de este
   cambio (sin el atajo) - nunca rompe nada por faltar o fallar la llave.
4. El ID conocido se guarda en un **namespace de KV** (`YT_KNOWN_IDS`, ver instrucciones de
   creación arriba) - compartido de verdad entre TODOS los bordes de Cloudflare, a diferencia del
   caché normal (`caches.default`), que es por borde. Esto importa porque un bloqueo de YouTube
   puede ser por borde/región: si el borde que atiende a un visitante en particular está
   bloqueado de forma sostenida, con el caché por borde ese visitante NUNCA se beneficiaría del
   atajo (su propio borde nunca lograría aprender el ID); con KV, en cuanto CUALQUIER borde
   descubre el ID, todos los demás (bloqueados o no) pueden usarlo de inmediato. Sin ese namespace
   conectado, cae de vuelta al caché por borde (sigue funcionando, solo que sin ese beneficio
   cruzado entre bordes).
