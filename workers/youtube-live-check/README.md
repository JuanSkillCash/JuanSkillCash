# Worker: ¿está este canal de YouTube en vivo?

Revisa si un canal de YouTube está transmitiendo en vivo ahora mismo, sin necesitar una
API key de YouTube (ver la explicación completa en los comentarios de `worker.js`).

> **Juan: vuelve a pegar el código actualizado (14-nov-2026)** - la versión anterior buscaba
> `"isLiveNow":true`/`"isLiveBroadcast":true` en la página de YouTube, pero esa señal ya NO
> existe ahí (confirmado en navegador el 13-nov-2026, 0 coincidencias hasta en un canal que SÍ
> estaba en vivo) - por eso nunca detectaba nada, así los canales sí estuvieran transmitiendo.
> La versión nueva lee `ytInitialPlayerResponse` (el bloque que de verdad trae YouTube hoy) y
> además ahora distingue "en vivo", "programado, todavía no empieza" y "en vivo pero no se
> puede ver embebido aquí" (bloqueado por país o por el propio dueño del canal), y siempre
> trae un bloque `"debug"` en la respuesta para poder revisar qué pasó sin tener que adivinar.
>
> **No lo pude probar contra YouTube de verdad** porque este entorno no tiene salida a
> internet hacia youtube.com ni hacia el propio Worker - solo se probó la lógica con HTML de
> prueba armado a mano, imitando la forma real que confirmaste en el navegador. Por eso el
> primer paso después de desplegar es la prueba de abajo con CNN en Español.

## Cómo desplegarlo (igual que hiciste con los otros Workers de este sitio)

1. Entra a [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers y Pages** → tu Worker
   **`skillcash-youtube-live`** (si no existe todavía, **Crear** → **"Crear Worker"**, con ese
   nombre exacto).
2. **"Editar código"** → borra todo lo que haya → pega **todo** el contenido del archivo
   `worker.js` de esta misma carpeta → **"Desplegar"**.

## Primera prueba después de desplegar (importante, hacerla sí o sí)

Abre en el navegador (cambia la URL por la tuya real) usando el ID de **CNN en Español**, que
transmite 24/7 y por eso sirve para confirmar rápido que la detección básica funciona:

```
https://<tu-url>.workers.dev/?channel=UC_lEiu6917IJz03TnntWUaQ
```

Debería responder con `"live":true` y un `videoId` real. **Si sale `"live":false`**, mira el
bloque `"debug"` de la respuesta antes de asumir que algo quedó mal:

- `"consentPage":true` → YouTube sigue mandando la pantalla de "antes de continuar", pese a la
  cabecera `Cookie` que ya intenta evitarla. Avísame.
- `"botCheck":true` → YouTube detectó la IP de Cloudflare como tráfico de robot. Avísame (este
  es el caso donde haría falta el "Plan B" con la API oficial de YouTube, ver abajo).
- `"hasPlayerResponse":false` con `"httpStatus":200` y sin `consentPage`/`botCheck` → YouTube
  cambió otra vez el formato de la página. Mándame el `"htmlLength"` que salió y lo reviso.
- Cualquier otra cosa rara en `debug` (por ejemplo `httpStatus` distinto de 200) → mándamela tal
  cual salió.

Después de confirmar CNN en Español, prueba también con **DW Español**
(`UCT4Jg8h03dD0iN3Pb5L0PMA`, 24/7) y con **NTN24** (`UCEJs1fTF3KszRJGxJY14VrA` - este puede salir
`"live":true"` pero con `"embeddable":false` o `"playability"` distinto de `"OK"`, porque YouTube
a veces lo restringe; en el sitio eso se ve como "En vivo, pero no se puede ver aquí" con un link
directo a YouTube, en vez de intentar reproducirlo roto).

## Forma de la respuesta

```json
{"live":true,"videoId":"Qr61waJ6AZg","title":"CNN en Español en vivo","channelId":"UC_lEiu6917IJz03TnntWUaQ",
 "checkedAt":1762500000000,"upcoming":false,"playability":"OK","embeddable":true,
 "debug":{"httpStatus":200,"finalUrl":"https://www.youtube.com/watch?v=Qr61waJ6AZg","htmlLength":612345,
          "hasPlayerResponse":true,"consentPage":false,"botCheck":false}}
```

- `upcoming`: hay un directo anunciado pero todavía no arrancó (no intentar reproducir).
- `playability`/`embeddable`: si `playability` no es `"OK"` o `embeddable` es `false`, el video
  no se debe intentar embeber aunque `live` sea `true` - el sitio ya maneja esto mostrando un
  link directo a YouTube.
- Cacheado 60 segundos en el borde de Cloudflare en el caso normal, 15 segundos si hubo algún
  error o página rara (para no quedarse mostrando un dato malo tanto tiempo).

## Plan B (solo si `botCheck` sale en `true` seguido, es decir YouTube bloquea Cloudflare)

No implementado todavía - documentado aquí como lo que seguiría si hace falta, para no tener
que investigarlo de cero:

1. Sacar IDs de video candidatos por canal desde `https://www.youtube.com/feeds/videos.xml?channel_id=<ID>`
   (RSS público, sin llave) + una lista en KV de IDs de directos 24/7 ya conocidos (esos streams
   viejos a veces no aparecen en el RSS).
2. Una sola llamada a la API oficial de YouTube: `videos.list` con `part=snippet,liveStreamingDetails`
   y hasta 50 IDs de video a la vez (cuesta solo **1 unidad** por llamada, de las 10.000
   unidades/día gratis) - **nunca** `search.list` (cuesta 100 unidades por llamada, se acabaría
   la cuota del día enseguida entre varios canales).
3. `snippet.liveBroadcastContent=="live"` = en vivo.

Si llegas a necesitarlo, dímelo con el `debug` completo de un caso con `botCheck:true` y lo
armamos con calma (necesita una API key de YouTube Data API v3 nueva, como secreto del Worker).
