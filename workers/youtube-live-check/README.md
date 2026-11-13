# Worker: ¿está este canal de YouTube en vivo?

Revisa si un canal de YouTube está transmitiendo en vivo ahora mismo, sin necesitar una
API key de YouTube (ver la explicación completa en los comentarios de `worker.js`).

> **Juan: si ya tenías este Worker desplegado, vuelve a pegar el código actualizado** (pasos
> abajo, sección "Cómo desplegarlo") - se le agregó una cabecera que le dice a YouTube que ya
> se dio el consentimiento, porque sin eso es muy probable que el Worker SIEMPRE diga "no está
> en vivo" (que es justo lo que reportaste - nunca lograste pillar un directo), así YouTube
> esté transmitiendo. No lo pude probar en vivo porque este entorno no tiene salida a internet
> hacia youtube.com ni hacia el Worker; después de volver a pegar el código, prueba con
> "Buscar directo" en un canal que normalmente transmite seguido (NTN24, CNN en Español,
> Noticias Telemundo) para confirmar que ahora sí detecta un directo real.

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
