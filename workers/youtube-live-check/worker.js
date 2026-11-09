/* Cloudflare Worker: revisa si un canal de YouTube está transmitiendo EN VIVO justo ahora,
 * sin usar la API oficial de YouTube (esa solo da ~100 consultas gratis al día en total,
 * imposible de estirar entre 9 canales si se quiere revisar seguido).
 *
 * Truco: la propia página pública de YouTube "youtube.com/channel/<ID>/live" muestra el
 * directo si existe (con "isLiveNow":true adentro del HTML) o cae al canal normal si no hay
 * nada en vivo. Es la misma técnica que usan proyectos de código abierto conocidos (yt-dlp,
 * Invidious, etc.) para esto mismo. No es una API oficial de YouTube, así que si en el
 * futuro cambian el formato de esa página, este Worker puede dejar de detectar bien el
 * directo (seguiría funcionando normal, solo volvería a decir "no está en vivo" siempre) -
 * se arregla actualizando el patrón de abajo, no es nada grave si pasa.
 *
 * Uso desde el sitio: GET https://<tu-worker>.workers.dev/?channel=UCxxxxxxxx
 * Responde: {"live":true,"videoId":"abc123","title":"De qué trata el directo","channelId":"UCxxxxxxxx","checkedAt":169...}
 *           {"live":false,"videoId":null,"title":null,"channelId":"UCxxxxxxxx","checkedAt":169...}
 *
 * Cacheado 60 segundos en el borde de Cloudflare (compartido entre TODAS las visitas, no por
 * visitante) - así, aunque el sitio tenga miles de visitas, YouTube solo recibe como máximo
 * una consulta por canal cada 60 segundos.
 */

const CACHE_SECONDS = 60;
const CHANNEL_ID_RE = /^UC[\w-]{10,}$/;

export default {
  async fetch(request) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);
    const channelId = url.searchParams.get('channel') || '';

    if (!CHANNEL_ID_RE.test(channelId)) {
      return new Response(JSON.stringify({ error: 'parámetro "channel" faltante o inválido (debe empezar con "UC")' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }

    const cache = caches.default;
    const cacheKey = new Request(url.toString(), request);
    const cached = await cache.match(cacheKey);
    if (cached) return cached;

    let live = false;
    let videoId = null;
    let title = null;

    try {
      const ytResp = await fetch(`https://www.youtube.com/channel/${channelId}/live`, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
          'Accept-Language': 'es-ES,es;q=0.9',
        },
        redirect: 'follow',
      });
      const html = await ytResp.text();
      if (/"isLiveNow":\s*true/.test(html) || /"isLiveBroadcast":\s*true/.test(html)) {
        live = true;
        const m = html.match(/"videoId":"([\w-]{11})"/);
        if (m) videoId = m[1];
        // el título real del directo (para el "Buscar directo" mejorado: mostrar de qué trata
        // cada canal en vivo, no solo que está en vivo) - og:title es más confiable que el
        // <title> de la pestaña, que YouTube a veces le pega " - YouTube" al final
        const t = html.match(/<meta property="og:title" content="([^"]*)"/);
        if (t) title = t[1].replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
      }
    } catch (err) {
      // si falla la consulta a YouTube (red, timeout, etc.), se responde "no en vivo" en vez
      // de tronar - más vale mostrar la lista de videos subidos que una página de error
      live = false;
    }

    const body = JSON.stringify({ live, videoId, title, channelId, checkedAt: Date.now() });
    const response = new Response(body, {
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': `public, max-age=${CACHE_SECONDS}`,
        ...corsHeaders,
      },
    });
    await cache.put(cacheKey, response.clone());
    return response;
  },
};
