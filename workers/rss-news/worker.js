/* Cloudflare Worker: junta titulares de varios RSS públicos (cripto y macro/economía) y los
 * devuelve ya ordenados en JSON, para las tarjetas "Noticias Cripto" / "Macro y Economía" de
 * Eventos y Noticias (replicando lo que hace melapela.ai). También sirve, en el mismo Worker,
 * la moderación automática de las reseñas de la plataforma (ver moderaTexto más abajo) - se
 * reutiliza este Worker en vez de crear uno nuevo porque ambas cosas ya necesitan el mismo
 * binding "AI" de Workers AI, así no hay que configurar nada de Cloudflare dos veces.
 *
 * Por qué hace falta este Worker: casi ningún RSS público trae cabeceras CORS, así que el
 * navegador no puede pedirlos directo desde juanskillcash.com (el propio sitio del medio los
 * bloquea por seguridad). Este Worker sí puede pedirlos (corre en el servidor de Cloudflare,
 * no en el navegador de la visita) y se los pasa al sitio ya limpios. Mismo patrón que el
 * Worker de YouTube en vivo (ver workers/youtube-live-check/).
 *
 * Uso desde el sitio:
 *   GET  https://<tu-worker>.workers.dev/?category=crypto
 *   GET  https://<tu-worker>.workers.dev/?category=macro
 *   POST https://<tu-worker>.workers.dev/?action=moderate   cuerpo JSON: {"text":"..."}
 * Las de noticias responden:
 *   {"items":[{"title":"...","link":"...","source":"CoinDesk","publishedAt":169...,
 *              "resumen":"...","sentimiento":"alcista|bajista|neutral"}, ...],"checkedAt":169...}
 * La de moderación responde: {"flagged":true|false}
 *
 * Cacheado 30 minutos en el borde de Cloudflare (compartido entre TODAS las visitas, no por
 * visitante) - las noticias no cambian segundo a segundo, no tiene sentido pedirle a cada
 * feed (ni traducir de nuevo) en cada visita al sitio.
 *
 * Los titulares llegan en inglés (así los publican los medios) y se traducen al español antes
 * de responder - pedido explícito de Juan, que por defecto los vea en español sin tener que
 * traducir él mismo. La traducción usa Workers AI, la inteligencia artificial propia de
 * Cloudflare (ver traduceTitulo más abajo) - requiere agregarle al Worker un "binding" llamado
 * "AI" desde Settings -> Bindings en el panel de Cloudflare (un clic, no es código).
 *
 * Se probó primero con dos servicios externos gratuitos de traducción (MyMemory y el endpoint
 * no oficial de Google Translate) y AMBOS devolvían HTTP 429 (demasiadas peticiones) al
 * llamarlos desde un Worker, aunque la misma consulta funcionaba bien desde un navegador
 * normal - ambos ven el tráfico compartido de Cloudflare como "robot" y lo bloquean. Workers AI
 * no tiene ese problema porque corre dentro de la propia red de Cloudflare, no le pide nada a
 * ningún tercero. Si por lo que sea esto llegara a fallar, se deja el titular en inglés en vez
 * de romper nada.
 *
 * Mantenimiento: si algún día un medio cambia su URL de RSS o la quita, solo hay que
 * actualizar/quitar esa entrada en FEEDS de abajo - no rompe a los demás (cada feed se pide
 * por separado y uno caído simplemente no aporta noticias, no tumba la respuesta completa).
 */

const CACHE_SECONDS = 1800;
const MAX_ITEMS = 8;

const FEEDS = {
  crypto: [
    { url: 'https://www.coindesk.com/arc/outboundfeeds/rss/', source: 'CoinDesk' },
    { url: 'https://cointelegraph.com/rss', source: 'Cointelegraph' },
  ],
  macro: [
    { url: 'https://feeds.content.dowjones.io/public/rss/mw_topstories', source: 'MarketWatch' },
    // news_14.rss es la categoria "Economy News" de Investing.com (no el feed general
    // news.rss, que en la prueba real de Juan trajo puras transcripciones de resultados de
    // empresas sueltas como Pagaya o KKR - eso no es "macro y economia")
    { url: 'https://www.investing.com/rss/news_14.rss', source: 'Investing.com' },
  ],
};

function stripCdata(s) {
  if (!s) return '';
  const m = s.match(/<!\[CDATA\[([\s\S]*?)\]\]>/);
  return (m ? m[1] : s).trim();
}
function decodeEntities(s) {
  // Ademas de las entidades con nombre de siempre, MarketWatch/Investing.com usan bastante
  // las entidades numericas para comillas tipograficas y acentos (ej. &#x2019; para el
  // apostrofe curvo "'") - sin estas dos ultimas lineas, esos titulos salian con el codigo
  // crudo en vez del caracter real.
  return s
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec) => String.fromCodePoint(parseInt(dec, 10)));
}
function stripTags(s) {
  return s.replace(/<[^>]*>/g, '').trim();
}

// Parser casero a propósito (sin librería de XML): Cloudflare Workers no trae un DOMParser de
// verdad en su runtime, y para solo sacar título/link/fecha de cada <item> de un RSS, unas
// expresiones regulares bastan - es la misma idea que ya se usó en el Worker de YouTube para
// sacar el videoId del HTML de la página.
function parseRssItems(xml, source) {
  const items = [];
  const itemBlocks = xml.match(/<item\b[\s\S]*?<\/item>/gi) || [];
  for (const block of itemBlocks) {
    const titleMatch = block.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i);
    const linkMatch = block.match(/<link\b[^>]*>([\s\S]*?)<\/link>/i);
    const dateMatch = block.match(/<(?:pubDate|published|dc:date)\b[^>]*>([\s\S]*?)<\/(?:pubDate|published|dc:date)>/i);
    if (!titleMatch) continue;
    const title = decodeEntities(stripTags(stripCdata(titleMatch[1])));
    let link = linkMatch ? decodeEntities(stripTags(stripCdata(linkMatch[1]))) : '';
    if (!link) {
      const guidMatch = block.match(/<guid\b[^>]*>([\s\S]*?)<\/guid>/i);
      if (guidMatch) link = decodeEntities(stripTags(stripCdata(guidMatch[1])));
    }
    const dateStr = dateMatch ? stripTags(stripCdata(dateMatch[1])) : '';
    const publishedAt = dateStr ? Date.parse(dateStr) : NaN;
    if (!title || !link) continue;
    items.push({
      title,
      link,
      source,
      publishedAt: isNaN(publishedAt) ? null : publishedAt,
    });
  }
  return items;
}

async function fetchFeed(feed) {
  try {
    const resp = await fetch(feed.url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
      },
    });
    if (!resp.ok) return [];
    const xml = await resp.text();
    return parseRssItems(xml, feed.source);
  } catch (err) {
    return []; // un feed caído o lento no debe tumbar a los demás
  }
}

// Traduce usando la IA propia de Cloudflare (Workers AI, modelo m2m100 - traductor entre 100
// idiomas), NO un servicio externo. Se llegó aquí después de confirmar con ?debug=1 que TANTO
// MyMemory COMO el endpoint gratuito de Google Translate devuelven HTTP 429 (demasiadas
// peticiones) cuando se llaman desde un Worker de Cloudflare - ambos servicios ven que la
// petición viene de una dirección de Cloudflare (compartida entre miles de sitios) y la tratan
// como tráfico automatizado/robot, aunque la misma consulta funcione perfecto desde un
// navegador normal. Como Workers AI corre DENTRO de la propia red de Cloudflare, no depende de
// pedirle nada a un tercero que nos pueda bloquear.
//
// Para que esto funcione hace falta un paso de configuración (una sola vez, no es código):
// en el Worker, en la pestaña "Settings" -> "Bindings" (o "Variables y bindings") -> "Add" ->
// elegir "Workers AI" -> el nombre del binding debe ser exactamente "AI" (en mayúsculas, así
// como está escrito en env.AI aquí abajo) -> Guardar/Deploy. Sin ese binding, env.AI no existe
// y esta función cae directo al "catch" (se ve en el debug como una excepción).
//
// El parámetro `debug` es opcional (solo se usa con ?debug=1 en la URL, ver más abajo) - es
// un objeto donde se anota qué pasó de verdad en la llamada, para diagnosticar sin adivinar.
async function traduceTitulo(texto, env, debug) {
  try {
    const result = await env.AI.run('@cf/meta/m2m100-1.2b', {
      text: texto,
      source_lang: 'english',
      target_lang: 'spanish',
    });
    if (debug) debug.respuestaCruda = result;
    const traducido = result && result.translated_text;
    if (!traducido || !traducido.trim()) {
      if (debug) debug.motivo = 'Workers AI respondió sin texto traducido usable';
      return texto;
    }
    return decodeEntities(traducido.trim());
  } catch (err) {
    if (debug) debug.motivo = 'Excepción al llamar a Workers AI (revisa que el binding "AI" esté agregado en Settings -> Bindings): ' + String(err);
    return texto;
  }
}

// Resumen "por qué importa" + etiqueta de sentimiento (alcista/bajista/neutral), en UNA sola
// llamada a un modelo de texto (Llama 3.1 8b) en vez de dos llamadas separadas - cada llamada
// a Workers AI cuesta "neuronas" del cupo gratis diario de la cuenta de Cloudflare de Juan, así
// que combinar ambas cosas en un solo pedido ahorra la mitad de ese costo para esta función.
// Se le pide al modelo que responda en un formato fijo de dos líneas (no JSON) porque es más
// fácil de leer con una expresión regular sin que un modelo de lenguaje "invente" un JSON mal
// formado y rompa el parseo.
async function analizaTitulo(tituloOriginalIngles, env, debug) {
  const vacio = { resumen: null, sentimiento: null };
  try {
    const prompt = 'Eres un analista que explica noticias de cripto y economía a principiantes, en español.\n' +
      'Para la siguiente noticia (el título viene en inglés), responde EXACTAMENTE en este formato, sin nada antes ni después:\n' +
      'SENTIMIENTO: alcista, bajista o neutral\n' +
      'RESUMEN: una frase corta en español (máximo 20 palabras) explicando por qué le podría importar a alguien que invierte en cripto\n\n' +
      'Noticia: "' + tituloOriginalIngles + '"';
    const result = await env.AI.run('@cf/meta/llama-3.1-8b-instruct-fast', {
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 120,
    });
    if (debug) debug.respuestaCrudaAnalisis = result;
    const texto = (result && result.response) || '';
    const sentMatch = texto.match(/SENTIMIENTO:\s*(alcista|bajista|neutral)/i);
    const resMatch = texto.match(/RESUMEN:\s*(.+)/i);
    return {
      sentimiento: sentMatch ? sentMatch[1].toLowerCase() : null,
      resumen: resMatch ? decodeEntities(resMatch[1].trim()) : null,
    };
  } catch (err) {
    if (debug) debug.motivoAnalisis = 'Excepción al pedir resumen/sentimiento: ' + String(err);
    return vacio;
  }
}

// Modera un comentario de reseña (platform_reviews) con la misma IA - detecta insultos, odio,
// spam o publicidad de otro sitio. Una crítica negativa normal ("este sitio es lento", "no me
// gustó tal herramienta") NO debe marcarse como inapropiada, solo contenido realmente tóxico o
// spam. Se usa para decidir si una reseña nueva se guarda visible de una o queda oculta
// (hidden=true) pendiente de que Juan la revise a mano desde el panel de administración que ya
// existe - nunca para bloquear el envío por completo, así un falso positivo no le quita a nadie
// la reseña que escribió, solo la deja pendiente de revisión.
async function moderaTexto(texto, env, debug) {
  try {
    const prompt = 'Eres un moderador de contenido para reseñas de un sitio de herramientas cripto, en español.\n' +
      'Responde con una sola palabra, "SI" o "NO" (sin comillas, sin nada más):\n' +
      'Responde "SI" solo si el texto tiene insultos, lenguaje de odio, spam o publicidad de otro sitio/servicio.\n' +
      'Responde "NO" si es una reseña normal, aunque sea una crítica negativa (las críticas negativas normales están permitidas).\n\n' +
      'Texto: "' + texto + '"';
    const result = await env.AI.run('@cf/meta/llama-3.1-8b-instruct-fast', {
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 5,
    });
    if (debug) debug.respuestaCrudaModeracion = result;
    const respuesta = ((result && result.response) || '').trim().toUpperCase();
    return { flagged: respuesta.startsWith('SI'), motivo: null };
  } catch (err) {
    // si la IA falla, mejor dejar pasar la reseña (visible) que bloquear a alguien por un
    // problema técnico que no tiene nada que ver con lo que escribió
    return { flagged: false, motivo: 'Excepción al moderar: ' + String(err) };
  }
}

export default {
  async fetch(request, env) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);

    // ?action=moderate (POST, cuerpo {"text":"..."}) - moderación de reseñas de la plataforma
    // (platform_reviews), ver moderaTexto() más arriba. Va antes de lo de noticias porque no
    // usa "category" ni el caché de RSS - cada reseña es única, no tiene sentido cachearla.
    if (request.method === 'POST' && url.searchParams.get('action') === 'moderate') {
      let payload;
      try {
        payload = await request.json();
      } catch (err) {
        return new Response(JSON.stringify({ error: 'cuerpo JSON inválido' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json', ...corsHeaders },
        });
      }
      const texto = (payload && typeof payload.text === 'string') ? payload.text : '';
      if (!texto.trim()) {
        return new Response(JSON.stringify({ error: 'falta "text" (string) en el cuerpo' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json', ...corsHeaders },
        });
      }
      const resultado = await moderaTexto(texto, env);
      return new Response(JSON.stringify(resultado), {
        headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }

    const category = url.searchParams.get('category') || '';
    const feeds = FEEDS[category];

    if (!feeds) {
      return new Response(JSON.stringify({ error: 'parámetro "category" faltante o inválido (usa "crypto" o "macro")' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }

    const cache = caches.default;
    const cacheKey = new Request(url.toString(), request);
    const cached = await cache.match(cacheKey);
    if (cached) return cached;

    const results = await Promise.all(feeds.map(fetchFeed));
    let items = results.flat();
    items.sort((a, b) => (b.publishedAt || 0) - (a.publishedAt || 0));
    items = items.slice(0, MAX_ITEMS);

    // ?debug=1 (temporal, para diagnosticar la traducción si algún día vuelve a fallar) -
    // anota en el primer titular qué pasó de verdad con la llamada a Workers AI, sin tener
    // que adivinar. Quitar esto en algún momento, no debe quedar permanente.
    const debugWanted = url.searchParams.get('debug') === '1';
    const debugInfo = debugWanted ? {} : null;

    // traducir Y analizar (resumen + sentimiento) solo los que de verdad se van a mostrar (ya
    // recortado a MAX_ITEMS) - antes del slice() desperdiciaría llamadas en titulares que ni
    // siquiera se usan. Las dos llamadas de IA por titular corren en paralelo (Promise.all),
    // no una detrás de otra, para no duplicar el tiempo de espera.
    items = await Promise.all(items.map(async (it, idx) => {
      const dbg = (debugWanted && idx === 0) ? debugInfo : null;
      const [titulo, analisis] = await Promise.all([
        traduceTitulo(it.title, env, dbg),
        analizaTitulo(it.title, env, dbg),
      ]);
      return { ...it, title: titulo, resumen: analisis.resumen, sentimiento: analisis.sentimiento };
    }));

    const body = JSON.stringify({ items, checkedAt: Date.now(), ...(debugWanted ? { debug: debugInfo } : {}) });
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
