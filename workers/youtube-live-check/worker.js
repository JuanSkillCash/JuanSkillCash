/* Cloudflare Worker: revisa si un canal de YouTube está transmitiendo EN VIVO justo ahora, y de
 * paso trae sus "temas recientes" (últimos videos subidos), sin usar la API oficial de YouTube
 * como primera opción (esa tiene cuota gratis de 10.000 "unidades" al día; una búsqueda con
 * search.list cuesta 100 unidades - con eso alcanzaría para unas 100 consultas en todo el día
 * repartidas entre los 9+ canales, muy poco si se quiere revisar seguido. videos.list cuesta
 * solo 1 unidad por llamada y acepta hasta 50 IDs de video a la vez, pero necesita ya saber el
 * ID del video, que es justo lo que no se sabe de entrada).
 *
 * Truco para "¿está en vivo?": la propia página pública de YouTube "youtube.com/channel/<ID>/live"
 * trae, dentro del HTML, el bloque `var ytInitialPlayerResponse = {...};` con el video que
 * YouTube eligió mostrar para esa ruta - si el canal está en vivo, es el directo; si no, cae a
 * un video subido normal. Es la misma técnica que usan proyectos de código abierto conocidos
 * (yt-dlp, Invidious, etc.) para esto mismo. No es una API oficial de YouTube, así que si en el
 * futuro cambian el formato de esa página, este Worker puede dejar de detectar bien el directo -
 * se arregla actualizando la extracción de abajo, no es nada grave si pasa (por eso el campo
 * "debug" de la respuesta: para poder ver rápido qué cambió sin tener que adivinar).
 *
 * NOTA (verificado 13-nov-2026): YouTube ya NO pone "isLiveNow":true ni "isLiveBroadcast":true
 * en el HTML (la versión anterior de este Worker buscaba eso y por eso dejó de funcionar). La
 * señal correcta hoy es videoDetails.isLive dentro de ytInitialPlayerResponse.
 *
 * Truco para "temas recientes" (verificado 14-nov-2026): la página "youtube.com/channel/<ID>/videos"
 * trae, igual que arriba, un bloque `var ytInitialData = {...};` con la lista de videos subidos.
 * Dentro hay objetos `lockupViewModel` (formato nuevo: contentId = ID del video,
 * metadata.lockupMetadataViewModel.title.content = título, y en algún punto de
 * metadata.lockupMetadataViewModel.metadata un texto "hace X h/d/min") o, de respaldo,
 * `videoRenderer` (formato viejo: videoId, title.runs[0].text, publishedTimeText.simpleText) -
 * se buscan ambos por si YouTube cambia de uno a otro. IMPORTANTE: el feed RSS
 * (youtube.com/feeds/videos.xml?channel_id=...) que se había pensado como alternativa da 404
 * ahora (probado con 3 canales distintos) - NO usarlo, quedó confirmado muerto.
 *
 * Uso desde el sitio: GET https://<tu-worker>.workers.dev/?channel=UCxxxxxxxx
 * Responde (siempre con el bloque "debug" para poder diagnosticar sin adivinar):
 *   {"live":true,"videoId":"abc123","title":"De qué trata el directo","channelId":"UCxxxxxxxx",
 *    "checkedAt":169...,"upcoming":false,"playability":"OK","embeddable":true,
 *    "recientes":[{"videoId":"xyz","titulo":"...","hace":"hace 4 h"}, ...] (máx 3, últimas 24h),
 *    "debug":{"httpStatus":200,"finalUrl":"https://www.youtube.com/watch?v=abc123","htmlLength":123456,
 *             "hasPlayerResponse":true,"consentPage":false,"botCheck":false}}
 *
 * Caché en 2 capas, cada una con su propio tiempo: la detección de "en vivo" se cachea 60 s
 * (normal) o 15 s (si hubo un error o página rara) - compartido entre TODAS las visitas, así
 * YouTube recibe como máximo una consulta por canal cada 60 s. Los "temas recientes" cambian
 * poco (un canal no sube videos nuevos a cada rato), así que se cachean 10 minutos aparte, en una
 * entrada de caché independiente - para no tener que escanear la página de videos en cada chequeo
 * de "en vivo" cuando ni falta hace.
 */

const CACHE_SECONDS_OK = 60;
const CACHE_SECONDS_ERROR = 15;
const CACHE_SECONDS_RECIENTES = 600;
const RECIENTES_MAX_HORAS = 24;
const RECIENTES_MAX = 3;
const CHANNEL_ID_RE = /^UC[\w-]{10,}$/;
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

// Extrae y parsea `var <clave> = {...};` contando llaves a mano (no con regex), porque el objeto
// puede tener comillas escapadas y llaves anidadas que una regex simple rompe. Sirve tanto para
// ytInitialPlayerResponse como para ytInitialData (misma forma, distinto nombre de variable).
function extraeJsonTrasVar(html, nombreVariable) {
  const clave = 'var ' + nombreVariable + ' = ';
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

function fetchYoutube(url) {
  return fetch(url, {
    headers: {
      'User-Agent': UA,
      'Accept-Language': 'es-ES,es;q=0.9',
      // sin esto, YouTube a veces responde con la pantalla de "antes de continuar a YouTube" en
      // vez de la página real - este truco (documentado y usado por yt-dlp/Invidious para esto
      // mismo) le dice a YouTube que el consentimiento ya se dio.
      'Cookie': 'CONSENT=YES+1; SOCS=CAI',
    },
    redirect: 'follow',
  });
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
    const ytResp = await fetchYoutube(`https://www.youtube.com/channel/${channelId}/live`);

    debug.httpStatus = ytResp.status;
    debug.finalUrl = ytResp.url;

    const html = await ytResp.text();
    debug.htmlLength = html.length;
    debug.consentPage = esPaginaDeConsentimiento(html, ytResp.url);
    debug.botCheck = esPaginaDeBotCheck(html);

    const player = extraeJsonTrasVar(html, 'ytInitialPlayerResponse');
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

// busca, recorriendo el objeto a mano, el primer string que parezca "hace X h/d/min" - no se
// sabe de antemano la ruta exacta dentro de metadata.lockupMetadataViewModel.metadata (YouTube
// cambia esa estructura interna seguido), así que se busca por forma del texto, no por ruta fija
function buscaTextoHace(obj, profundidad) {
  if (profundidad > 8) return null; // tope de seguridad, no bajar infinito
  if (typeof obj === 'string') return /^hace\s+\d+/i.test(obj) ? obj : null;
  if (Array.isArray(obj)) {
    for (const item of obj) {
      const r = buscaTextoHace(item, profundidad + 1);
      if (r) return r;
    }
    return null;
  }
  if (obj && typeof obj === 'object') {
    for (const k in obj) {
      const r = buscaTextoHace(obj[k], profundidad + 1);
      if (r) return r;
    }
  }
  return null;
}

// convierte "hace 4 h" / "hace 2 d" / "hace 30 min" a horas (número), para poder filtrar a
// "últimas 24 h" - si no se entiende el texto, Infinity (se descarta, mejor eso que adivinar)
function horasDesdeTexto(txt) {
  if (!txt) return Infinity;
  const m = /hace\s+(\d+)\s*(min|minuto|h|hora|d[ií]a)/i.exec(txt);
  if (!m) return Infinity;
  const n = Number(m[1]);
  const unidad = m[2].toLowerCase();
  if (unidad.startsWith('min')) return n / 60;
  if (unidad.startsWith('d')) return n * 24;
  return n; // h / hora
}

// recorre ytInitialData buscando lockupViewModel (formato nuevo) y videoRenderer (de respaldo,
// por si YouTube vuelve al formato viejo) - para en cuanto se junten unos cuantos candidatos, no
// hace falta seguir escaneando el árbol entero (puede pesar varios cientos de KB)
function recolectaVideosRecientes(obj, out, vistos, profundidad) {
  if (out.length >= 10 || profundidad > 40 || !obj || typeof obj !== 'object') return;
  if (Array.isArray(obj)) {
    for (const item of obj) {
      recolectaVideosRecientes(item, out, vistos, profundidad + 1);
      if (out.length >= 10) return;
    }
    return;
  }
  if (obj.lockupViewModel) {
    const lv = obj.lockupViewModel;
    const videoId = lv.contentId;
    const meta = lv.metadata && lv.metadata.lockupMetadataViewModel;
    const titulo = meta && meta.title && meta.title.content;
    if (videoId && titulo && !vistos.has(videoId)) {
      vistos.add(videoId);
      out.push({ videoId, titulo, hace: buscaTextoHace(meta.metadata, 0) });
    }
  } else if (obj.videoRenderer) {
    const vr = obj.videoRenderer;
    const videoId = vr.videoId;
    const titulo = vr.title && vr.title.runs && vr.title.runs[0] && vr.title.runs[0].text;
    if (videoId && titulo && !vistos.has(videoId)) {
      vistos.add(videoId);
      out.push({ videoId, titulo, hace: vr.publishedTimeText && vr.publishedTimeText.simpleText });
    }
  }
  for (const k in obj) {
    if (out.length >= 10) return;
    recolectaVideosRecientes(obj[k], out, vistos, profundidad + 1);
  }
}

async function obtieneRecientes(channelId) {
  try {
    const resp = await fetchYoutube(`https://www.youtube.com/channel/${channelId}/videos`);
    if (!resp.ok) return [];
    const html = await resp.text();
    const data = extraeJsonTrasVar(html, 'ytInitialData');
    if (!data) return [];
    const candidatos = [];
    recolectaVideosRecientes(data, candidatos, new Set(), 0);
    return candidatos
      .filter((v) => horasDesdeTexto(v.hace) <= RECIENTES_MAX_HORAS)
      .slice(0, RECIENTES_MAX);
  } catch (err) {
    return [];
  }
}

async function obtieneRecientesCacheado(channelId, cache) {
  const cacheKey = new Request('https://cache-interno.invalid/recientes/' + channelId);
  const cached = await cache.match(cacheKey);
  if (cached) return cached.json();
  const recientes = await obtieneRecientes(channelId);
  await cache.put(cacheKey, new Response(JSON.stringify(recientes), {
    headers: { 'Content-Type': 'application/json', 'Cache-Control': `public, max-age=${CACHE_SECONDS_RECIENTES}` },
  }));
  return recientes;
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

    const [resultado, recientes] = await Promise.all([
      revisaCanal(channelId),
      obtieneRecientesCacheado(channelId, cache),
    ]);
    resultado.recientes = recientes;

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
