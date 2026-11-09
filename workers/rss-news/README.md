# Worker: titulares de noticias (Cripto / Macro) via RSS

Junta titulares de varios medios (RSS público) y los devuelve ya ordenados en JSON, para las
tarjetas "Noticias Cripto" y "Macro y Economía" de Eventos y Noticias (ver la explicación
completa en los comentarios de `worker.js`).

## Cómo desplegarlo (igual que hiciste con el de YouTube en vivo)

1. Entra a [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers y Pages** → **Crear**.
2. Elige **"Crear Worker"** (no "Pages"). Dale el nombre `skillcash-news-feed` — **importante
   que sea ese nombre exacto, sin mezclarlo con el nombre al azar que propone Cloudflare**
   (borra por completo lo que venga puesto por defecto antes de escribir el tuyo).
3. Una vez creado, dale a **"Editar código"**.
4. Borra todo el código de ejemplo que trae por defecto, y pega **todo** el contenido del
   archivo `worker.js` de esta misma carpeta.
5. Dale a **"Desplegar"** (Deploy) — guardar el código no es suficiente, tiene que quedar
   publicado.
6. Cualquier URL que te dé Cloudflare (sea `skillcash-news-feed...` o, si quedó mezclada con
   el nombre al azar, algo como `jolly-waterfall-723askillcash-news-feed...`), mándamela y
   ajusto el sitio para que apunte ahí exacto — no hace falta que coincida con un nombre fijo,
   solo que me la pases tal cual.

## Cómo probarlo tú mismo (opcional)

Una vez desplegado, abre en el navegador (cambia la URL por la tuya real):

```
https://<tu-worker>.workers.dev/?category=crypto
```

Debería responder algo como:

```json
{"items":[{"title":"...","link":"https://...","source":"CoinDesk","publishedAt":1762500000000}, ...],"checkedAt":1762500000000}
```

Y con `?category=macro` lo mismo pero con titulares de MarketWatch/Investing.com.

Si alguno de los dos sale con `"items":[]` (vacío) no es necesariamente un error — puede ser
que ese medio esté lento o haya cambiado algo en su RSS. Avísame si pasa seguido con el mismo.
