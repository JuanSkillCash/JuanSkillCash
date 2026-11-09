# Worker: titulares de noticias (Cripto / Macro) via RSS

Junta titulares de varios medios (RSS público) y los devuelve ya ordenados en JSON, para las
tarjetas "Noticias Cripto" y "Macro y Economía" de Eventos y Noticias (ver la explicación
completa en los comentarios de `worker.js`).

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
{"items":[{"title":"...","link":"https://...","source":"CoinDesk","publishedAt":1762500000000}, ...],"checkedAt":1762500000000}
```

Y con `?category=macro` lo mismo pero con titulares de MarketWatch/Investing.com.

Si alguno de los dos sale con `"items":[]` (vacío) no es necesariamente un error — puede ser
que ese medio esté lento o haya cambiado algo en su RSS. Avísame si pasa seguido con el mismo.
