/* Cloudflare Worker: calendario económico PROPIO de SkillCash (reemplaza el iframe de
 * sslecal2.investing.com y el componente <tv-economic-calendar> de TradingView).
 *
 * Por qué se construyó esto en vez de seguir con un widget de terceros (investigado a fondo
 * antes de escribir una sola línea de este archivo):
 * - El widget de Investing.com solo expone 5 parámetros de color (ecoDayBackground/
 *   ecoDayFontColor/defaultFont/innerBorderColor/borderColor) que pintan la barra separadora de
 *   cada día - el fondo de las FILAS de datos, que es la mayoría de lo que se ve, queda fijo en
 *   blanco sin importar qué se le mande (probado con ?theme/?darkMode/?bgColor/?background/
 *   ?backgroundColor/?width=100%/?responsive, ninguno tuvo efecto). Su ancho también es fijo
 *   (~618px), no se estira. Al ser un iframe cross-origin, tampoco se le puede meter CSS propio.
 * - El Web Component <tv-economic-calendar> de TradingView sí acepta tema oscuro y ancho 100%,
 *   pero no muestra encabezados de columna, así que no se entiende cuál número es la previsión y
 *   cuál el dato anterior - inservible para lo que pidió Juan.
 *
 * Fuente principal: el mismo endpoint JSON (no documentado oficialmente, pero público y sin
 * llave) que usa la propia página de TradingView para pintar su calendario:
 *   GET https://economic-calendar.tradingview.com/events?from=<ISO UTC>&to=<ISO UTC>&countries=US,EU
 * Confirmado en vivo el 13-nov-2026 (ver comentarios de abajo para la forma exacta de la
 * respuesta). Como es un endpoint interno no documentado, NO se le manda ninguna cabecera
 * Origin/Referer fingiendo venir de tradingview.com - solo un fetch normal de servidor a
 * servidor con un User-Agent descriptivo, igual que los demás Workers de este sitio. Si
 * TradingView lo empieza a rechazar por eso, el código ya cae solo al respaldo de abajo; NO se
 * debe agregar spoofing de esas cabeceras sin confirmar primero que no viola sus términos de uso.
 *
 * Fuente de respaldo (si la de arriba falla): Forex Factory, también JSON público sin llave:
 *   GET https://nfs.faireconomy.media/ff_calendar_thisweek.json
 * Solo trae la semana en curso (no se le puede pedir un rango custom) y no trae el dato "actual"
 * (solo previsión y anterior) - por eso es respaldo y no la fuente principal.
 *
 * Caché en 2 capas:
 * 1. Cache API de Cloudflare (caches.default) - 10 min normalmente, baja a 1 min si hay algún
 *    evento de importancia alta dentro de la ventana [5 min antes, 30 min después] de su hora
 *    real, para que el dato "actual" aparezca rápido apenas se publica.
 * 2. KV (binding CALENDARIO_KV, hay que crearlo y conectarlo a mano una vez - ver README.md de
 *    esta carpeta) guarda la última respuesta buena conocida, para seguir sirviendo algo si
 *    fallan AMBAS fuentes a la vez. Se escribe como máximo cada 10 minutos y solo si los datos
 *    de verdad cambiaron (no en cada visita) - el plan gratis de Workers KV tiene un límite bajo
 *    de escrituras al día (revisar la cifra vigente en developers.cloudflare.com/kv/platform/limits,
 *    puede cambiar; al momento de escribir esto el límite documentado era 1000 escrituras/día).
 */

const CACHE_SECONDS_DEFAULT = 600;
const CACHE_SECONDS_NEAR_EVENT = 60;
const NEAR_EVENT_BEFORE_MS = 5 * 60 * 1000;
const NEAR_EVENT_AFTER_MS = 30 * 60 * 1000;
const KV_MIN_WRITE_GAP_MS = 10 * 60 * 1000;
const MAX_RANGE_DAYS = 31;
const BOGOTA_OFFSET_MS = 5 * 60 * 60 * 1000; // America/Bogota = UTC-5, sin horario de verano
const FETCH_TIMEOUT_MS = 8000;

const COUNTRY_WHITELIST = ['US', 'EU'];
// Forex Factory no distingue "país" de "divisa" - su campo `country` YA es el código de divisa
const PAIS_A_DIVISA_FF = { US: 'USD', EU: 'EUR' };

const TV_URL = 'https://economic-calendar.tradingview.com/events';
const FF_URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json';
const KV_KEY_PREFIX = 'calendario:';

// Traduce los títulos de indicadores de alta importancia más comunes (vienen en inglés de las 2
// fuentes) - lista pedida explícitamente por Juan. Si un título no está acá, se deja en inglés
// (mejor eso que una traducción inventada/incorrecta). Match por substring en minúsculas, para
// que sufijos como "(Oct)" o "YoY" no rompan la coincidencia.
const TRADUCCIONES = [
  ['core inflation rate mom', 'IPC subyacente m/m'],
  ['core cpi', 'IPC subyacente m/m'],
  ['inflation rate mom', 'IPC m/m'],
  ['cpi', 'IPC m/m'],
  ['ppi mom', 'IPP m/m'],
  ['retail sales mom', 'Ventas minoristas m/m'],
  ['initial jobless claims', 'Peticiones de subsidio por desempleo'],
  ['unemployment claims', 'Peticiones de subsidio por desempleo'],
  ['non farm payrolls', 'Nóminas no agrícolas'],
  ['nonfarm payrolls', 'Nóminas no agrícolas'],
  ['unemployment rate', 'Tasa de desempleo'],
  ['fed interest rate decision', 'Decisión de tipos de la Fed'],
  ['existing home sales', 'Ventas de viviendas de segunda mano'],
  ['housing starts', 'Inicios de viviendas'],
  ['building permits', 'Permisos de construcción'],
  ['gdp growth rate', 'PIB'],
  ['ecb interest rate decision', 'Decisión de tipos del BCE'],
];

// indicadores donde SUBIR es una mala señal (desempleo, solicitudes de subsidio, inventarios) -
// para estos se invierte el color verde/rojo respecto al resto. Match por substring en inglés.
const INDICADORES_INVERTIDOS = ['unemployment', 'jobless claims', 'crude oil inventories', 'inventories'];

function traduceEvento(tituloIngles) {
  const clave = String(tituloIngles || '').trim().toLowerCase();
  for (const [ing, es] of TRADUCCIONES) {
    if (clave.includes(ing)) return es;
  }
  return tituloIngles;
}

function esIndicadorInvertido(tituloIngles) {
  const t = String(tituloIngles || '').toLowerCase();
  return INDICADORES_INVERTIDOS.some((k) => t.includes(k));
}

function toNum(v) {
  if (v == null || v === '') return null;
  const n = typeof v === 'number' ? v : parseFloat(String(v).replace(/,/g, ''));
  return Number.isNaN(n) ? null : n;
}

// "0.3" + "%" -> "0,3%"; "1.268" + "M" -> "1,268M" - coma decimal (pedido explícito de Juan,
// igual que el resto del sitio), escala pegada antes que la unidad (así vienen los ejemplos
// reales que se confirmaron viendo la respuesta real de TradingView)
function formatValorTV(valor, unidad, escala) {
  const num = toNum(valor);
  if (num == null) return null;
  let texto = String(valor).replace('.', ',');
  if (escala) texto += escala;
  if (unidad) texto += unidad;
  return texto;
}

// Forex Factory ya manda el texto formateado ("194K", "-0.6M", "0.3%") - solo se le cambia el
// punto decimal por coma para que se vea igual de consistente que el resto del sitio
function formatValorFF(texto) {
  if (texto == null || texto === '') return null;
  return String(texto).replace('.', ',');
}

function calculaTendencia(actualNum, previsionNum, invertido) {
  if (actualNum == null || previsionNum == null || actualNum === previsionNum) return 'neutral';
  const subio = actualNum > previsionNum;
  const esBueno = invertido ? !subio : subio;
  return esBueno ? 'bueno' : 'malo';
}

function calculaDireccion(actualNum, previsionNum) {
  if (actualNum == null || previsionNum == null) return null;
  if (actualNum > previsionNum) return 'arriba';
  if (actualNum < previsionNum) return 'abajo';
  return null;
}

// hash corto y determinista (no criptográfico, no hace falta) - solo para darle un id estable a
// las filas de Forex Factory, que no traen uno propio
function hashCorto(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) | 0; }
  return (h >>> 0).toString(36);
}

// lunes 00:00 a domingo 23:59:59 en hora de Bogotá (UTC-5 fijo, sin horario de verano),
// devuelto ya convertido a instantes UTC reales
function semanaActualBogotaUtc(ahora) {
  const bogotaAhora = new Date(ahora.getTime() - BOGOTA_OFFSET_MS);
  const diaSemana = bogotaAhora.getUTCDay(); // 0=domingo .. 6=sabado
  const diasDesdeLunes = (diaSemana + 6) % 7;
  const lunesBogota = Date.UTC(
    bogotaAhora.getUTCFullYear(), bogotaAhora.getUTCMonth(), bogotaAhora.getUTCDate() - diasDesdeLunes, 0, 0, 0
  );
  const domingoBogota = lunesBogota + 7 * 24 * 60 * 60 * 1000 - 1;
  return {
    desdeUtc: new Date(lunesBogota + BOGOTA_OFFSET_MS),
    hastaUtc: new Date(domingoBogota + BOGOTA_OFFSET_MS),
  };
}

function fetchConTimeout(url, opts, ms) {
  const signal = AbortSignal.timeout ? AbortSignal.timeout(ms) : undefined;
  return fetch(url, { ...opts, signal });
}

// Fuente principal - endpoint interno (no documentado oficialmente) de TradingView, confirmado
// en vivo el 13-nov-2026. Forma de un item real (ejemplo visto de verdad, no inventado):
//   { id, title:"Core Inflation Rate MoM", country:"US", indicator, comment, category, period,
//     referenceDate, referencePeriod, source, source_url, actual:0.3, previous:0.3, forecast:0.2,
//     actualRaw:0.3, previousRaw:0.3, forecastRaw:0.2, currency:"USD", importance:1,
//     date:"2026-11-10T13:30:00.000Z", unit:"%", scale:null }
// importance: -1 baja, 0 media, 1 alta. actual=null hasta que se publique el dato real.
async function obtenerDeTradingView(desdeUtc, hastaUtc, paises, debug) {
  const url = `${TV_URL}?from=${encodeURIComponent(desdeUtc.toISOString())}&to=${encodeURIComponent(hastaUtc.toISOString())}&countries=${paises.join(',')}`;
  const resp = await fetchConTimeout(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'application/json',
    },
  }, FETCH_TIMEOUT_MS);
  if (debug) debug.tvStatus = resp.status;
  if (!resp.ok) throw new Error('TradingView respondió ' + resp.status);
  const data = await resp.json();
  const items = (data && data.result) || [];
  if (debug) debug.tvItems = items.length;
  return items.map((it) => {
    const importancia = it.importance === 1 ? 3 : it.importance === 0 ? 2 : 1;
    const actualNum = toNum(it.actualRaw != null ? it.actualRaw : it.actual);
    const previsionNum = toNum(it.forecastRaw != null ? it.forecastRaw : it.forecast);
    const anteriorNum = toNum(it.previousRaw != null ? it.previousRaw : it.previous);
    const invertido = esIndicadorInvertido(it.title);
    return {
      id: 'tv-' + it.id,
      fechaUTC: it.date,
      divisa: it.currency || '',
      pais: it.country || '',
      importancia,
      evento: it.title,
      eventoES: traduceEvento(it.title),
      actual: formatValorTV(it.actual != null ? it.actual : it.actualRaw, it.unit, it.scale),
      prevision: formatValorTV(it.forecast != null ? it.forecast : it.forecastRaw, it.unit, it.scale),
      anterior: formatValorTV(it.previous != null ? it.previous : it.previousRaw, it.unit, it.scale),
      actualNum,
      previsionNum,
      anteriorNum,
      tendencia: calculaTendencia(actualNum, previsionNum, invertido),
      direccion: calculaDireccion(actualNum, previsionNum),
      unidad: it.unit || '',
      escala: it.scale || '',
      fuente: 'TradingView',
    };
  });
}

// Respaldo - Forex Factory, solo trae la semana en curso (no admite rango custom) y nunca trae
// "actual" (ver comentario arriba de la constante FF_URL). Forma real de un item:
//   { title, country:"USD", date:"2026-11-10T08:30:00-05:00", impact:"High",
//     forecast:"0.2%", previous:"0.3%" }
async function obtenerDeForexFactory(desdeUtc, hastaUtc, paises, debug) {
  const resp = await fetchConTimeout(FF_URL, {
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' },
  }, FETCH_TIMEOUT_MS);
  if (debug) debug.ffStatus = resp.status;
  if (!resp.ok) throw new Error('Forex Factory respondió ' + resp.status);
  const items = await resp.json();
  if (debug) debug.ffItems = Array.isArray(items) ? items.length : 0;
  const divisasPermitidas = new Set(paises.map((p) => PAIS_A_DIVISA_FF[p]).filter(Boolean));
  const impactMap = { Low: 1, Medium: 2, High: 3 };
  return (Array.isArray(items) ? items : [])
    .filter((it) => {
      const t = new Date(it.date).getTime();
      if (Number.isNaN(t) || t < desdeUtc.getTime() || t > hastaUtc.getTime()) return false;
      if (!divisasPermitidas.has(it.country)) return false;
      return true;
    })
    .map((it) => {
      const esFeriado = it.impact === 'Holiday';
      const previsionNum = toNum(String(it.forecast || '').replace(/[%KMB]/gi, ''));
      return {
        id: 'ff-' + hashCorto(it.title + '|' + it.date),
        fechaUTC: new Date(it.date).toISOString(),
        divisa: it.country || '',
        pais: it.country || '',
        importancia: esFeriado ? 1 : (impactMap[it.impact] || 1),
        evento: it.title,
        eventoES: traduceEvento(it.title),
        actual: null, // Forex Factory nunca trae el dato real publicado
        prevision: formatValorFF(it.forecast),
        anterior: formatValorFF(it.previous),
        actualNum: null,
        previsionNum,
        anteriorNum: null,
        tendencia: 'neutral', // sin "actual" no hay nada que comparar
        direccion: null,
        unidad: '',
        escala: '',
        fuente: 'Forex Factory',
        esFeriado,
      };
    });
}

function calculaTtlSegundos(eventos, ahoraMs) {
  const cercaDeUnoImportante = eventos.some((e) => {
    if (e.importancia !== 3) return false;
    const t = Date.parse(e.fechaUTC);
    if (Number.isNaN(t)) return false;
    return ahoraMs >= t - NEAR_EVENT_BEFORE_MS && ahoraMs <= t + NEAR_EVENT_AFTER_MS;
  });
  return cercaDeUnoImportante ? CACHE_SECONDS_NEAR_EVENT : CACHE_SECONDS_DEFAULT;
}

export default {
  async fetch(request, env) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': 'https://juanskillcash.com',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Vary': 'Origin',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);
    const cache = caches.default;
    const cacheKey = new Request(url.toString(), request);
    const cached = await cache.match(cacheKey);
    if (cached) return cached;

    const ahora = new Date();
    let desdeUtc, hastaUtc;
    const desdeParam = url.searchParams.get('desde');
    const hastaParam = url.searchParams.get('hasta');
    if (desdeParam && hastaParam) {
      desdeUtc = new Date(desdeParam + 'T00:00:00Z');
      hastaUtc = new Date(hastaParam + 'T23:59:59Z');
      if (Number.isNaN(desdeUtc.getTime()) || Number.isNaN(hastaUtc.getTime()) || hastaUtc < desdeUtc) {
        return new Response(JSON.stringify({ error: '"desde"/"hasta" inválidos (formato YYYY-MM-DD)' }), {
          status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders },
        });
      }
      const rangoDias = (hastaUtc.getTime() - desdeUtc.getTime()) / 86400000;
      if (rangoDias > MAX_RANGE_DAYS) {
        return new Response(JSON.stringify({ error: 'el rango máximo entre "desde" y "hasta" es de ' + MAX_RANGE_DAYS + ' días' }), {
          status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders },
        });
      }
    } else {
      const semana = semanaActualBogotaUtc(ahora);
      desdeUtc = semana.desdeUtc;
      hastaUtc = semana.hastaUtc;
    }

    const paisesParam = url.searchParams.get('paises');
    const paises = paisesParam
      ? paisesParam.split(',').map((p) => p.trim().toUpperCase()).filter((p) => COUNTRY_WHITELIST.includes(p))
      : COUNTRY_WHITELIST.slice();
    if (paises.length === 0) {
      return new Response(JSON.stringify({ error: '"paises" inválido - usa alguno de: ' + COUNTRY_WHITELIST.join(', ') }), {
        status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }

    const debugWanted = url.searchParams.get('debug') === '1';
    const debugInfo = debugWanted ? {} : null;
    const kvKey = KV_KEY_PREFIX + desdeUtc.toISOString() + '_' + hastaUtc.toISOString() + '_' + paises.join(',');

    let eventos = null;
    let fuenteUsada = null;
    let desactualizado = false;

    try {
      eventos = await obtenerDeTradingView(desdeUtc, hastaUtc, paises, debugInfo);
      fuenteUsada = 'TradingView';
    } catch (err) {
      if (debugInfo) debugInfo.tvError = String(err);
      try {
        eventos = await obtenerDeForexFactory(desdeUtc, hastaUtc, paises, debugInfo);
        fuenteUsada = 'Forex Factory';
      } catch (err2) {
        if (debugInfo) debugInfo.ffError = String(err2);
      }
    }

    // ambas fuentes fallaron - se intenta servir la última copia buena guardada en KV
    if (!eventos && env.CALENDARIO_KV) {
      try {
        const respaldo = await env.CALENDARIO_KV.get(kvKey, 'json');
        if (respaldo && Array.isArray(respaldo.eventos)) {
          eventos = respaldo.eventos;
          fuenteUsada = respaldo.fuente + ' (copia de respaldo)';
          desactualizado = true;
        }
      } catch (err3) {
        if (debugInfo) debugInfo.kvReadError = String(err3);
      }
    }

    if (!eventos) {
      return new Response(JSON.stringify({
        error: 'No se pudo obtener el calendario (TradingView y Forex Factory fallaron, y no hay copia de respaldo en KV todavía)',
        ...(debugWanted ? { debug: debugInfo } : {}),
      }), { status: 503, headers: { 'Content-Type': 'application/json', ...corsHeaders } });
    }

    eventos.sort((a, b) => Date.parse(a.fechaUTC) - Date.parse(b.fechaUTC));

    // guardar copia de respaldo en KV - como mucho cada 10 minutos, y solo si los datos
    // realmente cambiaron (comparado contra lo último que ya había guardado ahí)
    if (!desactualizado && env.CALENDARIO_KV) {
      try {
        const existente = await env.CALENDARIO_KV.get(kvKey, 'json');
        const haPasadoElMinimo = !existente || (ahora.getTime() - Date.parse(existente.actualizado)) >= KV_MIN_WRITE_GAP_MS;
        const cambio = !existente || JSON.stringify(existente.eventos) !== JSON.stringify(eventos);
        if (haPasadoElMinimo && cambio) {
          await env.CALENDARIO_KV.put(kvKey, JSON.stringify({ eventos, fuente: fuenteUsada, actualizado: ahora.toISOString() }), {
            expirationTtl: 7 * 24 * 60 * 60, // 7 días - de sobra para ser solo un respaldo de corto plazo
          });
        }
      } catch (err4) {
        if (debugInfo) debugInfo.kvWriteError = String(err4);
      }
    }

    const ttlSegundos = calculaTtlSegundos(eventos, ahora.getTime());
    const body = JSON.stringify({
      fuente: fuenteUsada,
      actualizado: ahora.toISOString(),
      desactualizado,
      eventos,
      ...(debugWanted ? { debug: debugInfo } : {}),
    });
    const response = new Response(body, {
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': `public, max-age=${ttlSegundos}`,
        ...corsHeaders,
      },
    });
    if (!debugWanted) await cache.put(cacheKey, response.clone());
    return response;
  },
};
