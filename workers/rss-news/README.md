# Worker: titulares de noticias (Cripto / Macro) via RSS

Junta titulares de varios medios (RSS público) y los devuelve ya ordenados en JSON, para las
tarjetas "Noticias Cripto" y "Macro y Economía" de Eventos y Noticias (ver la explicación
completa en los comentarios de `worker.js`).

> **Juan: vuelve a pegar el código actualizado (20-nov-2026)** - se agregó el campo
> `importancia` (`"alta"` o `"baja"`), para las alertas de Telegram de noticias cripto clave que
> pediste (ver `scripts/post_important_news_telegram.py`). Sale "alta" solo si la noticia entra
> en una de las 12 categorías que elegiste una por una (ETF, SEC/regulación, Fed, hackeo grande,
> quiebra/fraude grande, movimiento de precio fuerte, adopción institucional, país adoptando
> cripto, upgrade de red grande, empresa grande no-cripto con producto cripto, ballena grande,
> figura política) - igual que `resumenLargo`, sale de la MISMA llamada a Workers AI que ya
> armaba `resumen`/`sentimiento`/`resumenLargo`, no es una llamada nueva, no gasta más cupo.
>
> Cambio anterior (confirmado por Juan, 19-nov-2026): se agregaron los campos `resumenLargo` (un
> párrafo más largo, 3-4 frases) e `imagen` (si el feed la trae), para la "vista detallada" de
> Noticias (una noticia grande a la vez, con foto y resumen más largo, con flechas para pasar a
> la siguiente). `imagen` sale del RSS del medio cuando lo trae (`<enclosure>`, `<media:content>`
> o un `<img>` suelto en la bajada) - no todos la traen, por eso el sitio tiene que poder
> mostrarse bien cuando sale `null` (muestra un cartel genérico en vez de romperse).
>
> Cambio anterior (confirmado por Juan): se le agregó la bajada/entradilla de la noticia (cuando
> el feed la trae) como contexto extra para el modelo que arma el "resumen", porque antes solo
> tenía el título y terminaba parafraseándolo casi igual.

## Cómo desplegarlo (igual que hiciste con el de YouTube en vivo)

Ya está desplegado como `skillcash-noticias` (`https://skillcash-noticias.juanchodigital86.workers.dev`),
así quedó conectado en el sitio. Estos pasos son para cuando haya que volver a pegar el código
actualizado ahí (o, si algún día hay que crear uno desde cero):

1. Entra a [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers y Pages** →
   `skillcash-noticias` (o **Crear** → **"Crear Worker"** si es uno nuevo; en ese caso dale el
   nombre `skillcash-noticias` — **importante que sea ese nombre exacto, sin mezclarlo con el
   nombre al azar que propone Cloudflare**, borrando por completo lo que venga puesto por
   defecto antes de escribir el tuyo).
2. Dale a **"Editar código"**.
3. Borra todo el código que haya, y pega **todo** el contenido del archivo `worker.js` de esta
   misma carpeta.
4. Dale a **"Desplegar"** (Deploy) — guardar el código no es suficiente, tiene que quedar
   publicado.
5. **Paso extra, una sola vez** (solo si el Worker es nuevo o todavía no tiene este binding):
   en la pestaña **"Settings"** → **"Bindings"** (o "Variables y bindings") → **"Add"** → elige
   **"Workers AI"** → en el nombre del binding escribe exactamente `AI` (mayúsculas) → guarda.
   Sin este paso, la traducción al español no funciona (el Worker sigue respondiendo todo en
   inglés, sin romperse).
6. Si Cloudflare te da una URL distinta a `https://skillcash-noticias.juanchodigital86.workers.dev`,
   avísame para ajustarla en el sitio.

## Cómo probarlo tú mismo (opcional)

Una vez desplegado, abre en el navegador (cambia la URL por la tuya real):

```
https://<tu-worker>.workers.dev/?category=crypto
```

Debería responder algo como:

```json
{"items":[{"title":"...","link":"https://...","source":"CoinDesk","publishedAt":1762500000000,
           "resumen":"...","resumenLargo":"...","imagen":"https://.../foto.jpg","sentimiento":"alcista"}, ...],
 "checkedAt":1762500000000}
```

Y con `?category=macro` lo mismo pero con titulares de MarketWatch/Investing.com.

Si alguno de los dos sale con `"items":[]` (vacío) no es necesariamente un error — puede ser
que ese medio esté lento o haya cambiado algo en su RSS. Avísame si pasa seguido con el mismo.

`"imagen":null` tampoco es un error - ese medio en particular no trajo ninguna imagen en el RSS
para esa noticia puntual (pasa seguido, sobre todo con MarketWatch/Investing.com). El sitio ya
está preparado para mostrar un cartel genérico ahí en vez de un espacio roto.
