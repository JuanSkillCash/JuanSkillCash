# Worker: titulares de noticias (Cripto / Macro) via RSS

Junta titulares de varios medios (RSS público) y los devuelve ya ordenados en JSON, para las
tarjetas "Noticias Cripto" y "Macro y Economía" de Eventos y Noticias (ver la explicación
completa en los comentarios de `worker.js`).

## Cómo desplegarlo (igual que hiciste con el de YouTube en vivo)

1. Entra a [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers y Pages** → **Crear**.
2. Elige **"Crear Worker"** (no "Pages"). Dale el nombre `skillcash-news-feed` — **importante
   que sea ese nombre exacto**, porque ya quedó conectado así en el sitio.
3. Una vez creado, dale a **"Editar código"**.
4. Borra todo el código de ejemplo que trae por defecto, y pega **todo** el contenido del
   archivo `worker.js` de esta misma carpeta.
5. Dale a **"Desplegar"** (Deploy).
6. Si Cloudflare te da una URL distinta a `https://skillcash-news-feed.juanchodigital86.workers.dev`
   (por ejemplo si tu usuario de Cloudflare cambió), avísame para ajustarla en el sitio.

## Cómo probarlo tú mismo (opcional)

Una vez desplegado, abre en el navegador:

```
https://skillcash-news-feed.juanchodigital86.workers.dev/?category=crypto
```

Debería responder algo como:

```json
{"items":[{"title":"...","link":"https://...","source":"CoinDesk","publishedAt":1762500000000}, ...],"checkedAt":1762500000000}
```

Y con `?category=macro` lo mismo pero con titulares de MarketWatch/Investing.com.

Si alguno de los dos sale con `"items":[]` (vacío) no es necesariamente un error — puede ser
que ese medio esté lento o haya cambiado algo en su RSS. Avísame si pasa seguido con el mismo.
