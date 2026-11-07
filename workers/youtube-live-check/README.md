# Worker: ¿está este canal de YouTube en vivo?

Revisa si un canal de YouTube está transmitiendo en vivo ahora mismo, sin necesitar una
API key de YouTube (ver la explicación completa en los comentarios de `worker.js`).

## Cómo desplegarlo (igual que hiciste con el de CoinGecko)

1. Entra a [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers y Pages** → **Crear**.
2. Elige **"Crear Worker"** (no "Pages"). Dale un nombre, por ejemplo `skillcash-youtube-live`.
3. Una vez creado, dale a **"Editar código"**.
4. Borra todo el código de ejemplo que trae por defecto, y pega **todo** el contenido del
   archivo `worker.js` de esta misma carpeta.
5. Dale a **"Desplegar"** (Deploy).
6. Cloudflare te va a dar una URL parecida a `https://skillcash-youtube-live.<tu-usuario>.workers.dev`
   — **mándame esa URL exacta** para conectarla al sitio.

## Cómo probarlo tú mismo (opcional)

Una vez desplegado, abre en el navegador:

```
https://<tu-url>.workers.dev/?channel=UCYxRlFDqcWM4y7FfpiAN3KQ
```

(ese ID es el de la Casa Blanca). Debería responder algo como:

```json
{"live":false,"videoId":null,"channelId":"UCYxRlFDqcWM4y7FfpiAN3KQ","checkedAt":1762500000000}
```

Si en ese momento la Casa Blanca está transmitiendo en vivo de verdad, `"live"` debería salir
en `true` y `"videoId"` con el ID del video del directo.
