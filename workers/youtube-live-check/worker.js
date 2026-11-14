/* Cloudflare Worker: revisa si un canal de YouTube está transmitiendo EN VIVO justo ahora,
 * sin usar la API oficial de YouTube como primera opción (esa tiene cuota gratis de 10.000
 * "unidades" al día; una búsqueda con search.list cuesta 100 unidades - con eso alcanzaría para
 * unas 100 consultas en todo el día repartidas entre los 9+ canales, muy poco si se quiere
 * revisar seguido. videos.list cuesta solo 1 unidad por llamada y acepta hasta 50 IDs de video a
 * la vez, pero necesita ya saber el ID del video, que es justo lo que no se sabe de entrada).
 *
 * Truco: la propia página pública de YouTube "youtube.com/channel/<ID>/live" trae, dentro del
 * HTML, el bloque `var ytInitialPlayerResponse = {...};` con el video que YouTube eligió mostrar
 * para esa ruta - si el canal está en vivo, es el directo; si no, cae a un video subido normal.
 * Es la misma técnica que usan proyectos de código abierto conocidos (yt-dlp, Invidious, etc.)
 * para esto mismo. No es una API oficial de YouTube, así que si en el futuro cambian el formato
 * de esa página, este Worker puede dejar de detectar bien el directo - se arregla actualizando
 * la extracción de abajo, no es nada grave si pasa (por eso el campo "debug" de la respuesta:
 * para poder ver rápido qué cambió sin tener que adivinar).
 *
 * NOTA (verificado 13-nov-2026): YouTube ya NO pone "isLiveNow":true ni "isLiveBroadcast":true
 * en el HTML (la versión anterior de este Worker buscaba eso y por eso dejó de funcionar). La
 * señal correcta hoy es videoDetails.isLive dentro de ytInitialPlayerResponse.
 *
 * Uso desde el sitio: GET https://<tu-worker>.workers.dev/?channel=UCxxxxxxxx
 * Responde (siempre con el bloque "debug" para poder diagnosticar sin adivinar):
 *   {"live":true,"videoId":"abc123","title":"De qué trata el directo","channelId":"UCxxxxxxxx",
 *    "checkedAt":169...,"upcoming":false,"playability":"OK","embeddable":true,
 *    "debug":{"httpStatus":200,"finalUrl":"https://www.youtube.com/watch?v=abc123","htmlLength":123456,
 *             "hasPlayerResponse":true,"consentPage":false,"botCheck":false}}
 *
 * Cacheado en el borde de Cloudflare (compartido entre TODAS las visitas, no por visitante) -
 * así, aunque el sitio tenga miles de visitas, YouTube solo recibe como máximo una consulta por
 * canal cada 60 segundos (normal) o 15 segundos (si hubo un error o una página rara, para no
 * quedarse 60 segundos mostrando un dato malo).
 */

const CACHE_SECONDS_OK = 60;
const CACHE_SECONDS_ERROR = 15;
const CHANNEL_ID_RE = /^UC[\w-]{10,}$/;

// Extrae y parsea `var ytInitialPlayerResponse = {...};` contando llaves a mano (no con regex),
// porque el objeto puede tener comillas escapadas y llaves anidadas que una regex simple rompe.
function extraeYtInitialPlayerResponse(html) {
  const clave = 'var ytInitialPlayerResponse = ';
  let inicio = html.indexOf(clave);
  if (inicio < 0) return null;
  inicio += clave.length;
  let profundidad = 0;
  let enString = false;
  let escapando = false;
  for (let j = inicio; j < html.length; j++) {
    const c = html[j];
    if (enString) {
      if (escapando) escapando = false;
      else if (c === '\\') escapando = true;
      else if (c === '"') enString = false;
      continue;
    }
    if (c === '"') enString = true;
    else if (c === '{') profundidad++;
    else if (c === '}') {
      profundidad--;
      if (profundidad === 0) {
        try {
          return JSON.parse(html.slice(inicio, j + 1));
        } catch (err) {
          return null;
        }
      }
    }
  }
  return null;
}

function esPaginaDeConsentimiento(html, finalUrl) {
  if (finalUrl && finalUrl.includes('consent.youtube.com')) return true;
  return /action="https:\/\/consent\.youtube\.com/.test(html);
}

function esPaginaDeBotCheck(html) {
  return /unusual traffic|detectamos tr[aá]fico inusual|not a robot|no eres un robot/i.test(html);
}

async function revisaCanal(channelId) {
  const resultado = {
    live: false,
    videoId: null,
    title: null,
    channelId,
    checkedAt: Date.now(),
    upcoming: false,
    playability: null,
    embeddable: null,
  };
  const debug = {
    httpStatus: null,
    finalUrl: null,
    htmlLength: 0,
    hasPlayerResponse: false,
    consentPage: false,
    botCheck: false,
  };

  try {
    const ytResp = await fetch(`https://www.youtube.com/channel/${channelId}/live`, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'es-ES,es;q=0.9',
        // sin esto, YouTube a veces responde con la pantalla de "antes de continuar a YouTube"
        // en vez de la página real del canal - ese truco (documentado y usado por yt-dlp/
        // Invidious para esto mismo) le dice a YouTube que el consentimiento ya se dio. El campo
        // debug.consentPage de abajo sirve para comprobar si de verdad sigue haciendo falta.
        'Cookie': 'CONSENT=YES+1; SOCS=CAI',
      },
      redirect: 'follow',
    });

    debug.httpStatus = ytResp.status;
    debug.finalUrl = ytResp.url;

    const html = await ytResp.text();
    debug.htmlLength = html.length;
    debug.consentPage = esPaginaDeConsentimiento(html, ytResp.url);
    debug.botCheck = esPaginaDeBotCheck(html);

    const player = extraeYtInitialPlayerResponse(html);
    debug.hasPlayerResponse = !!player;

    if (player && player.videoDetails) {
      const vd = player.videoDetails;
      const ps = player.playabilityStatus || {};
      // solo se confía en el resultado si el video que YouTube devolvió es realmente del canal
      // que se pidió (evita reportar en vivo el video equivocado si algo viene raro)
      if (vd.channelId === channelId) {
        resultado.live = vd.isLive === true;
        resultado.upcoming = vd.isUpcoming === true;
        resultado.videoId = vd.videoId || null;
        resultado.title = vd.title || null;
        resultado.playability = ps.status || null;
        resultado.embeddable = ps.playableInEmbed !== false;
      }
    }
  } catch (err) {
    debug.error = String(err && err.message ? err.message : err);
  }

  resultado.debug = debug;
  return resultado;
}

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

    const resultado = await revisaCanal(channelId);

    const huboProblema =
      !!resultado.debug.error ||
      resultado.debug.consentPage ||
      resultado.debug.botCheck ||
      (resultado.debug.httpStatus === 200 && !resultado.debug.hasPlayerResponse);
    const ttl = huboProblema ? CACHE_SECONDS_ERROR : CACHE_SECONDS_OK;

    const response = new Response(JSON.stringify(resultado), {
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': `public, max-age=${ttl}`,
        ...corsHeaders,
      },
    });
    await cache.put(cacheKey, response.clone());
    return response;
  },
};
