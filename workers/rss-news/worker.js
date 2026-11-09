/* Cloudflare Worker: junta titulares de varios RSS públicos (cripto y macro/economía) y los
 * devuelve ya ordenados en JSON, para las tarjetas "Noticias Cripto" / "Macro y Economía" de
 * Eventos y Noticias (replicando lo que hace melapela.ai).
 *
 * Por qué hace falta este Worker: casi ningún RSS público trae cabeceras CORS, así que el
 * navegador no puede pedirlos directo desde juanskillcash.com (el propio sitio del medio los
 * bloquea por seguridad). Este Worker sí puede pedirlos (corre en el servidor de Cloudflare,
 * no en el navegador de la visita) y se los pasa al sitio ya limpios. Mismo patrón que el
 * Worker de YouTube en vivo (ver workers/youtube-live-check/).
 *
 * Uso desde el sitio: GET https://<tu-worker>.workers.dev/?category=crypto
 *                      GET https://<tu-worker>.workers.dev/?category=macro
 * Responde: {"items":[{"title":"...","link":"...","source":"CoinDesk","publishedAt":169...}, ...],"checkedAt":169...}
 *
 * Cacheado 30 minutos en el borde de Cloudflare (compartido entre TODAS las visitas, no por
 * visitante) - las noticias no cambian segundo a segundo, no tiene sentido pedirle a cada
 * feed (ni traducir de nuevo) en cada visita al sitio. El caché más largo que el del Worker
 * de YouTube (60s) es a propósito: aquí cada refresco también dispara varias llamadas a la
 * API de traducción gratuita (ver traduceTitulo más abajo), que tiene un límite diario - entre
 * más seguido se refresque, antes se acaba ese límite para todo el sitio.
 *
 * Los titulares llegan en inglés (así los publican los medios) y se traducen al español antes
 * de responder - pedido explícito de Juan, que por defecto los vea en español sin tener que
 * traducir él mismo. Se usa la API gratuita de MyMemory (sin necesitar cuenta ni llave) - si
 * por lo que sea falla o no traduce bien, se deja el titular en inglés en vez de romper nada.
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

// MyMemory (api.mymemory.translated.net) es gratuita, sin llave/cuenta, pensada justo para
// volúmenes chicos como este. Si no responde bien (medio caído, límite diario alcanzado,
// texto raro que no logra traducir) se devuelve el título original en inglés - mejor eso que
// tumbar toda la tarjeta de noticias.
async function traduceTitulo(texto) {
  try {
    const url = 'https://api.mymemory.translated.net/get?q=' + encodeURIComponent(texto) + '&langpair=en|es';
    const resp = await fetch(url);
    if (!resp.ok) return texto;
    const data = await resp.json();
    const traducido = data && data.responseData && data.responseData.translatedText;
    return (traducido && traducido.trim()) ? decodeEntities(traducido.trim()) : texto;
  } catch (err) {
    return texto;
  }
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

    // traducir solo los que de verdad se van a mostrar (ya recortado a MAX_ITEMS) - traducir
    // antes del slice() desperdiciaría llamadas en titulares que ni siquiera se usan
    items = await Promise.all(items.map(async (it) => ({ ...it, title: await traduceTitulo(it.title) })));

    const body = JSON.stringify({ items, checkedAt: Date.now() });
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
