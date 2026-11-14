/* Cloudflare Worker: calendario económico PROPIO de SkillCash (reemplaza el iframe de
 * sslecal2.investing.com y el componente <tv-economic-calendar> de TradingView).
 *
 * REDISEÑO DE FUENTES (14-nov-2026) - verificado en navegador, no re-investigar:
 *
 * TradingView (la fuente principal de la primera versión de este Worker) quedó DESCARTADA.
 * Causa confirmada del error 403: el endpoint `economic-calendar.tradingview.com/events` tiene
 * una lista blanca por la cabecera `Origin` - solo acepta peticiones que digan venir de su
 * propia página (tradingview.com). No es bloqueo por IP de Cloudflare ni límite de peticiones.
 * Usarlo exigiría fingir esa cabecera (simular que la petición viene de su propio sitio cuando
 * no es así) - decisión explícita de Juan: NO hacerlo.
 *
 * Arquitectura nueva, 3 fuentes combinadas:
 *
 * A) Forex Factory (horario/importancia/previsión/anterior) - GET
 *    https://nfs.faireconomy.media/ff_calendar_thisweek.json . Solo trae la semana en curso y
 *    NUNCA trae el dato "actual". Responde 429 seguido si se le pide en cada visita (límite por
 *    las IPs compartidas de Cloudflare) - por eso NO se pide por petición: un Cron Trigger
 *    (`scheduled()` abajo) la refresca cada 30 min y la guarda en KV; el handler normal SOLO lee
 *    de KV. Si el KV está vacío (primera vez, antes de que corra el primer cron), se hace un
 *    fetch directo una sola vez como arranque.
 *
 * B) Nasdaq (dato "actual" + consenso, de TODOS los países) - GET
 *    https://api.nasdaq.com/api/calendar/economicevents?date=YYYY-MM-DD . Sin llave, sin
 *    cabecera Origin (confirmado abriendo la URL directo en el navegador) - por eso NO se le
 *    manda Origin/Referer fingido, solo un User-Agent descriptivo normal.
 *    Rarezas verificadas (OJO si algo no cuadra en el futuro):
 *      - El parámetro `date` viene DESFASADO 1 día: pedir date=D+1 para los eventos del día D.
 *      - El campo `gmt` de cada fila en realidad está en hora de Nueva York, no en GMT de verdad.
 *      - `country` viene en texto largo ("United States", "Euro Zone", "Germany"...), no en código.
 *      - Puede haber 2 filas con el mismo nombre de evento sin distinguir m/m de y/y (ej. 2 filas
 *        "PPI") - se desambigua comparando magnitud contra el forecast/previous de Forex Factory.
 *      - No trae importancia (esa sigue viniendo de Forex Factory).
 *
 * C) FRED (respaldo oficial, solo EE.UU., opcional) - GET
 *    https://api.stlouisfed.org/fred/series/observations?series_id=<ID>&api_key=<KEY>&file_type=json
 *    Necesita el secreto `FRED_API_KEY` configurado en el Worker (Settings → Variables and
 *    Secrets). Si no está configurado, este Worker simplemente no intenta FRED - Nasdaq ya cubre
 *    la mayoría de los casos. Solo se usa cuando Nasdaq no trajo el dato, y solo después de pasado
 *    el tiempo de publicación típico medido para cada serie (ver FRED_MAP) - así nunca se muestra
 *    por error el dato del mes/trimestre ANTERIOR como si fuera el actual recién publicado.
 *
 * Descartadas (verificado, no reinvestigar): Trading Economics (cuenta de invitado discontinuada),
 * BCE/Eurostat para zona euro (las series que se probaron quedaron desactualizadas o dan 404).
 *
 * Caché en 2 capas igual que antes: Cache API (caches.default) por petición completa, con TTL
 * de 60s si hay algún evento de importancia alta dentro de [0, 30min] después de su hora sin
 * dato "actual" todavía (para no tardar en mostrarlo apenas se publique), 15 min el resto del
 * tiempo; y KV (binding CALENDARIO_KV) para la copia semanal de Forex Factory que mantiene el
 * Cron Trigger.
 */

const CACHE_SECONDS_DEFAULT = 900;
const CACHE_SECONDS_NEAR_EVENT = 60;
const NEAR_EVENT_WINDOW_MS = 30 * 60 * 1000; // [hora del evento, hora del evento + 30 min]
const MAX_RANGE_DAYS = 31;
const BOGOTA_OFFSET_MS = 5 * 60 * 60 * 1000; // America/Bogota = UTC-5, sin horario de verano
const FETCH_TIMEOUT_MS = 8000;
const FF_KV_KEY = 'ff_cache_semana';
const FF_STALE_AFTER_MS = 70 * 60 * 1000; // el cron corre cada 30 min - más de 70 min sin refrescar = algo falló
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

const COUNTRY_WHITELIST = ['US', 'EU'];
const PAIS_A_DIVISA_FF = { US: 'USD', EU: 'EUR' };

const FF_URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json';
const NASDAQ_URL = 'https://api.nasdaq.com/api/calendar/economicevents';
const FRED_URL = 'https://api.stlouisfed.org/fred/series/observations';

// Traduce los títulos de indicadores de alta importancia más comunes (vienen en inglés de Forex
// Factory). Si un título no está acá, se deja en inglés (mejor eso que una traducción inventada).
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
  ['non-farm employment change', 'Nóminas no agrícolas'],
  ['nonfarm payrolls', 'Nóminas no agrícolas'],
  ['unemployment rate', 'Tasa de desempleo'],
  ['fed interest rate decision', 'Decisión de tipos de la Fed'],
  ['federal funds rate', 'Tasa de fondos federales'],
  ['existing home sales', 'Ventas de viviendas de segunda mano'],
  ['housing starts', 'Inicios de viviendas'],
  ['building permits', 'Permisos de construcción'],
  ['gdp growth rate', 'PIB'],
  ['ecb interest rate decision', 'Decisión de tipos del BCE'],
  ['crude oil inventories', 'Inventarios de petróleo crudo'],
];

// indicadores donde SUBIR es una mala señal - para estos se invierte el color verde/rojo
const INDICADORES_INVERTIDOS = ['unemployment', 'jobless claims', 'crude oil inventories', 'inventories'];

// --- alias Forex Factory -> nombre de evento en Nasdaq (match exacto, en minúsculas) ---
const ALIAS_FF_A_NASDAQ = {
  'cpi m/m': 'cpi',
  'core cpi m/m': 'core cpi',
  'ppi m/m': 'ppi',
  'core ppi m/m': 'core ppi',
  'unemployment claims': 'initial jobless claims',
  'existing home sales': 'existing home sales',
  'crude oil inventories': 'crude oil inventories',
  'retail sales m/m': 'retail sales',
  'core retail sales m/m': 'core retail sales',
  'non-farm employment change': 'nonfarm payrolls',
  'unemployment rate': 'unemployment rate',
};

// --- respaldo FRED: título FF (minúsculas) -> serie + cómo calcular el "actual" ---
// latenciaMin = minutos medidos (14-nov-2026) entre la hora oficial de publicación y que FRED
// muestre el dato nuevo - no se intenta FRED antes de ese tiempo, para no mostrar por error el
// dato del periodo ANTERIOR como si fuera el recién publicado.
const FRED_MAP = {
  'cpi m/m': { serie: 'CPIAUCSL', calc: 'pctMoM', latenciaMin: 50, decimales: 1 },
  'core cpi m/m': { serie: 'CPILFESL', calc: 'pctMoM', latenciaMin: 50, decimales: 1 },
  'cpi y/y': { serie: 'CPIAUCNS', calc: 'pctYoY', latenciaMin: 50, decimales: 1 },
  'ppi m/m': { serie: 'PPIFIS', calc: 'pctMoM', latenciaMin: 120, decimales: 1 },
  'core ppi m/m': { serie: 'PPIFES', calc: 'pctMoM', latenciaMin: 120, decimales: 1 },
  'unemployment claims': { serie: 'ICSA', calc: 'ultimoEntreMilK', latenciaMin: 15, decimales: 0 },
  'non-farm employment change': { serie: 'PAYEMS', calc: 'diferenciaK', latenciaMin: 140, decimales: 0 },
  'unemployment rate': { serie: 'UNRATE', calc: 'ultimoDirectoPct', latenciaMin: 140, decimales: 1 },
  'average hourly earnings m/m': { serie: 'CES0500000003', calc: 'pctMoM', latenciaMin: 140, decimales: 1 },
  'retail sales m/m': { serie: 'RSAFS', calc: 'pctMoM', latenciaMin: 15, decimales: 1 },
  'core retail sales m/m': { serie: 'RSFSXMV', calc: 'pctMoM', latenciaMin: 15, decimales: 1 },
  'gdp growth rate q/q': { serie: 'A191RL1Q225SBEA', calc: 'ultimoDirectoPct', latenciaMin: 40, decimales: 1 },
  'core pce price index m/m': { serie: 'PCEPILFE', calc: 'pctMoM', latenciaMin: 20, decimales: 1 },
  'building permits': { serie: 'PERMIT', calc: 'ultimoEntreMilM', latenciaMin: 10, decimales: 2 },
  'housing starts': { serie: 'HOUST', calc: 'ultimoEntreMilM', latenciaMin: 10, decimales: 2 },
  'existing home sales': { serie: 'EXHOSLUSM495S', calc: 'ultimoEntreMillonM', latenciaMin: 15, decimales: 2 },
  'jolts job openings': { serie: 'JTSJOL', calc: 'ultimoEntreMilM', latenciaMin: 15, decimales: 2 },
  'industrial production m/m': { serie: 'INDPRO', calc: 'pctMoM', latenciaMin: 10, decimales: 1 },
  'federal funds rate': { serie: 'DFEDTARU', calc: 'ultimoDirectoPct', latenciaMin: 15, decimales: 2 },
};
// Sin equivalente en FRED (confirmado 14-nov-2026): ISM/S&P Global PMIs, CB Consumer Confidence,
// UoM Consumer Sentiment (FRED UMCSENT va atrasado meses), Crude Oil/Natural Gas Inventories (son
// de la EIA, no de FRED), ADP, discursos y subastas del Tesoro.

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

function formatValorFF(texto) {
  if (texto == null || texto === '') return null;
  return String(texto).replace('.', ',');
}

function formatNumero(n, decimales) {
  if (n == null || Number.isNaN(n)) return null;
  return n.toFixed(decimales).replace('.', ',');
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

function hashCorto(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) | 0; }
  return (h >>> 0).toString(36);
}

function semanaActualBogotaUtc(ahora) {
  const bogotaAhora = new Date(ahora.getTime() - BOGOTA_OFFSET_MS);
  const diaSemana = bogotaAhora.getUTCDay();
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

// fecha YYYY-MM-DD de un instante, en una zona horaria dada
function fechaEnZona(fechaUTC, zona) {
  const fmt = new Intl.DateTimeFormat('en-CA', { timeZone: zona, year: 'numeric', month: '2-digit', day: '2-digit' });
  return fmt.format(new Date(fechaUTC));
}

function sumaDias(fechaStr, dias) {
  const [y, m, d] = fechaStr.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + dias);
  return dt.toISOString().slice(0, 10);
}

// ===== Forex Factory (horario/importancia/previsión/anterior - la base de cada evento) =====
// Forma real de un item (verificada): { title, country:"USD", date:"2026-11-10T08:30:00-05:00",
// impact:"High", forecast:"0.2%", previous:"0.3%" }. country YA es el código de divisa, no el país.
async function obtenerDeForexFactory() {
  const resp = await fetchConTimeout(FF_URL, { headers: { 'User-Agent': UA } }, FETCH_TIMEOUT_MS);
  if (!resp.ok) throw new Error('Forex Factory respondió ' + resp.status);
  const items = await resp.json();
  const impactMap = { Low: 1, Medium: 2, High: 3 };
  return (Array.isArray(items) ? items : []).map((it) => {
    const esFeriado = it.impact === 'Holiday';
    const previsionNum = toNum(String(it.forecast || '').replace(/[%KMB]/gi, ''));
    const anteriorNum = toNum(String(it.previous || '').replace(/[%KMB]/gi, ''));
    return {
      id: 'ff-' + hashCorto(it.title + '|' + it.date),
      fechaUTC: new Date(it.date).toISOString(),
      divisa: it.country || '',
      pais: it.country || '',
      importancia: esFeriado ? 1 : (impactMap[it.impact] || 1),
      evento: it.title,
      eventoES: traduceEvento(it.title),
      actual: null,
      prevision: formatValorFF(it.forecast),
      anterior: formatValorFF(it.previous),
      actualNum: null,
      previsionNum,
      anteriorNum,
      tendencia: 'neutral',
      direccion: null,
      unidad: '',
      escala: '',
      fuente: 'Forex Factory',
      fuenteActual: null,
      consenso: null,
      esFeriado,
    };
  });
}

async function refrescaCacheFF(env) {
  const eventos = await obtenerDeForexFactory();
  if (env.CALENDARIO_KV) {
    await env.CALENDARIO_KV.put(FF_KV_KEY, JSON.stringify({ eventos, actualizado: new Date().toISOString() }));
  }
  return eventos;
}

// ===== Nasdaq (dato "actual" + consenso) =====
// OJO: el parámetro `date` viene desfasado 1 día - para los eventos del día D hay que pedir D+1.
async function obtenerDeNasdaq(fechaObjetivoStr, debug) {
  const fechaParam = sumaDias(fechaObjetivoStr, 1);
  const url = `${NASDAQ_URL}?date=${fechaParam}`;
  try {
    const resp = await fetchConTimeout(url, {
      headers: { 'User-Agent': UA, 'Accept': 'application/json' },
    }, FETCH_TIMEOUT_MS);
    if (debug) debug[fechaObjetivoStr] = { status: resp.status };
    if (!resp.ok) return [];
    const data = await resp.json();
    const filas = (data && data.data && Array.isArray(data.data.rows)) ? data.data.rows : [];
    if (debug) debug[fechaObjetivoStr].filas = filas.length;
    return filas;
  } catch (err) {
    if (debug) debug[fechaObjetivoStr] = { error: String(err) };
    return [];
  }
}

function paisNasdaqEsperado(evFF) {
  const t = String(evFF.evento || '').toLowerCase();
  if (evFF.divisa === 'USD') return 'united states';
  if (t.startsWith('german')) return 'germany';
  if (t.startsWith('french')) return 'france';
  if (t.startsWith('italian')) return 'italy';
  if (t.startsWith('spanish')) return 'spain';
  return 'euro zone';
}

function limpiaValorNasdaq(v) {
  if (v == null) return null;
  const s = String(v).replace(/&nbsp;/g, '').trim();
  return s === '' ? null : s;
}

function numeroDesdeTextoNasdaq(v) {
  const limpio = limpiaValorNasdaq(v);
  if (limpio == null) return null;
  return toNum(limpio.replace(/[%KMB]/gi, ''));
}

// busca, entre las filas de Nasdaq de la fecha correcta, la que corresponde a este evento de
// Forex Factory - por alias de nombre + país, desambiguando por magnitud si hay varias filas con
// el mismo nombre (ej. 2 filas "PPI": una mensual y otra anual)
function buscaFilaNasdaq(evFF, filasDelDia) {
  const claveFF = String(evFF.evento || '').trim().toLowerCase();
  const aliasNasdaq = ALIAS_FF_A_NASDAQ[claveFF];
  if (!aliasNasdaq) return null;
  const paisEsperado = paisNasdaqEsperado(evFF);
  const candidatas = filasDelDia.filter((f) => {
    const nombre = String(f.eventName || '').trim().toLowerCase();
    const pais = String(f.country || '').trim().toLowerCase();
    return nombre === aliasNasdaq && pais === paisEsperado;
  });
  if (candidatas.length === 0) return null;
  if (candidatas.length === 1) return candidatas[0];
  // varias filas con el mismo nombre - la que más se parezca en magnitud al forecast/previous de FF
  const refFF = evFF.previsionNum != null ? evFF.previsionNum : evFF.anteriorNum;
  if (refFF == null) return candidatas[0];
  let mejor = candidatas[0], mejorDist = Infinity;
  for (const c of candidatas) {
    const refNasdaq = numeroDesdeTextoNasdaq(c.consensus) != null ? numeroDesdeTextoNasdaq(c.consensus) : numeroDesdeTextoNasdaq(c.previous);
    if (refNasdaq == null) continue;
    const dist = Math.abs(refNasdaq - refFF);
    if (dist < mejorDist) { mejorDist = dist; mejor = c; }
  }
  return mejor;
}

// ===== FRED (respaldo oficial, solo si Nasdaq no trajo el dato) =====
async function obtieneObservacionesFred(serie, apiKey) {
  const url = `${FRED_URL}?series_id=${serie}&api_key=${apiKey}&file_type=json&sort_order=desc&limit=14`;
  const resp = await fetchConTimeout(url, { headers: { 'Accept': 'application/json' } }, FETCH_TIMEOUT_MS);
  if (!resp.ok) throw new Error('FRED respondió ' + resp.status + ' (serie ' + serie + ')');
  const data = await resp.json();
  const obs = (data && data.observations) || [];
  // solo observaciones numéricas válidas, ya en orden del más nuevo al más viejo
  return obs.filter((o) => toNum(o.value) != null).map((o) => ({ fecha: o.date, valor: toNum(o.value) }));
}

function calculaActualFred(calc, obs, decimales) {
  if (!obs.length) return null;
  if (calc === 'ultimoDirectoPct' ) return formatoPct(obs[0].valor, decimales);
  if (calc === 'ultimoEntreMilK') return Math.round(obs[0].valor / 1000) + 'K';
  if (calc === 'ultimoEntreMilM') return formatNumero(obs[0].valor / 1000, decimales) + 'M';
  if (calc === 'ultimoEntreMillonM') return formatNumero(obs[0].valor / 1000000, decimales) + 'M';
  if (calc === 'diferenciaK') {
    if (obs.length < 2) return null;
    return Math.round(obs[0].valor - obs[1].valor) + 'K';
  }
  if (calc === 'pctMoM') {
    if (obs.length < 2) return null;
    const pct = (obs[0].valor - obs[1].valor) / obs[1].valor * 100;
    return formatoPct(pct, decimales);
  }
  if (calc === 'pctYoY') {
    if (obs.length < 13) return null;
    const pct = (obs[0].valor - obs[12].valor) / obs[12].valor * 100;
    return formatoPct(pct, decimales);
  }
  return null;
}
function formatoPct(n, decimales) {
  const f = formatNumero(n, decimales);
  return f == null ? null : f + '%';
}
function numeroDesdeActualFred(texto) {
  if (texto == null) return null;
  return toNum(String(texto).replace(/[%KM]/gi, ''));
}

async function intentaFred(evFF, env, debug) {
  const clave = String(evFF.evento || '').trim().toLowerCase();
  const cfg = FRED_MAP[clave];
  if (!cfg) return null;
  if (!env.FRED_API_KEY) return null;
  const minutosDesdePublicacion = (Date.now() - Date.parse(evFF.fechaUTC)) / 60000;
  if (minutosDesdePublicacion < cfg.latenciaMin) return null; // aún muy pronto, evita mostrar el dato del periodo anterior
  try {
    const obs = await obtieneObservacionesFred(cfg.serie, env.FRED_API_KEY);
    // seguridad extra: la observación más nueva no debería tener más de ~110 días (cubre hasta
    // series trimestrales como el PIB) - si es más vieja que eso, FRED probablemente no se ha
    // actualizado todavía para este periodo, mejor no mostrar nada que mostrar algo viejo
    if (!obs.length || (Date.now() - Date.parse(obs[0].fecha)) / 86400000 > 110) return null;
    const actual = calculaActualFred(cfg.calc, obs, cfg.decimales);
    if (debug) debug[clave] = { serie: cfg.serie, actual, obsMasNueva: obs[0] && obs[0].fecha };
    return actual;
  } catch (err) {
    if (debug) debug[clave] = { error: String(err) };
    return null;
  }
}

// enriquece un evento de Forex Factory con el dato "actual" de Nasdaq (primero) o FRED (si
// Nasdaq no lo trajo) y recalcula tendencia/dirección ya con el actual real
async function enriqueceConActual(evFF, filasNasdaqPorDia, env, debugNasdaq, debugFred) {
  const diaNY = fechaEnZona(evFF.fechaUTC, 'America/New_York');
  const filasDelDia = filasNasdaqPorDia[diaNY] || [];
  const filaNasdaq = buscaFilaNasdaq(evFF, filasDelDia);
  let actualTxt = null, actualNum = null, consensoTxt = null, fuenteActual = null;

  if (filaNasdaq) {
    const valorActual = limpiaValorNasdaq(filaNasdaq.actual);
    if (valorActual != null) {
      actualTxt = formatValorFF(valorActual);
      actualNum = numeroDesdeTextoNasdaq(valorActual);
      fuenteActual = 'Nasdaq';
    }
    const valorConsenso = limpiaValorNasdaq(filaNasdaq.consensus);
    if (valorConsenso != null) consensoTxt = formatValorFF(valorConsenso);
  }

  if (actualTxt == null) {
    const actualFred = await intentaFred(evFF, env, debugFred);
    if (actualFred != null) {
      actualTxt = actualFred;
      actualNum = numeroDesdeActualFred(actualFred);
      fuenteActual = 'FRED (oficial)';
    }
  }

  // evento de importancia alta, ya pasó su hora, y seguimos sin "actual" de ninguna fuente -
  // vale la pena dejarlo en los logs (Cloudflare → pestaña Logs) para ir ampliando el diccionario
  if (actualTxt == null && evFF.importancia === 3 && Date.parse(evFF.fechaUTC) <= Date.now()) {
    console.log('[calendario] sin "actual" para evento de importancia alta:', evFF.evento, '|', evFF.fechaUTC, '| fila Nasdaq esperada:', ALIAS_FF_A_NASDAQ[String(evFF.evento || '').toLowerCase()] || '(sin alias)');
  }

  const invertido = esIndicadorInvertido(evFF.evento);
  return {
    ...evFF,
    actual: actualTxt,
    actualNum,
    consenso: consensoTxt,
    fuenteActual,
    tendencia: calculaTendencia(actualNum, evFF.previsionNum, invertido),
    direccion: calculaDireccion(actualNum, evFF.previsionNum),
  };
}

function calculaTtlSegundos(eventos, ahoraMs) {
  const faltaActualYaPublicable = eventos.some((e) => {
    if (e.importancia !== 3 || e.actual != null) return false;
    const t = Date.parse(e.fechaUTC);
    if (Number.isNaN(t)) return false;
    return ahoraMs >= t && ahoraMs <= t + NEAR_EVENT_WINDOW_MS;
  });
  return faltaActualYaPublicable ? CACHE_SECONDS_NEAR_EVENT : CACHE_SECONDS_DEFAULT;
}

export default {
  // Cron Trigger (configurado en el Worker, cada 30 min) - refresca la copia de Forex Factory en
  // KV. Pedirle esto a Forex Factory en cada visita del sitio es lo que causaba los 429.
  async scheduled(event, env, ctx) {
    ctx.waitUntil(refrescaCacheFF(env).catch((err) => console.log('[calendario] cron: falló refrescar Forex Factory -', String(err))));
  },

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
    const divisasPermitidas = new Set(paises.map((p) => PAIS_A_DIVISA_FF[p]).filter(Boolean));

    const debugWanted = url.searchParams.get('debug') === '1';
    const debugInfo = debugWanted ? { nasdaq: {}, fred: {} } : null;

    // 1) Forex Factory desde KV (actualizado por el cron) - si el KV está vacío (primera vez),
    // se hace un fetch directo de arranque una sola vez.
    let ffCache = env.CALENDARIO_KV ? await env.CALENDARIO_KV.get(FF_KV_KEY, 'json') : null;
    let ffDesactualizado = false;
    if (!ffCache) {
      try {
        const eventos = await refrescaCacheFF(env);
        ffCache = { eventos, actualizado: new Date().toISOString() };
      } catch (err) {
        if (debugInfo) debugInfo.ffError = String(err);
        return new Response(JSON.stringify({
          error: 'No se pudo obtener el calendario (Forex Factory falló y todavía no hay copia guardada en KV)',
          ...(debugWanted ? { debug: debugInfo } : {}),
        }), { status: 503, headers: { 'Content-Type': 'application/json', ...corsHeaders } });
      }
    } else if (Date.now() - Date.parse(ffCache.actualizado) > FF_STALE_AFTER_MS) {
      ffDesactualizado = true;
    }
    if (debugInfo) debugInfo.ff = { actualizado: ffCache.actualizado, eventos: ffCache.eventos.length, desactualizado: ffDesactualizado };

    // 2) filtra por rango de fechas y países pedidos
    const filtrados = ffCache.eventos.filter((e) => {
      const t = Date.parse(e.fechaUTC);
      if (Number.isNaN(t) || t < desdeUtc.getTime() || t > hastaUtc.getTime()) return false;
      return divisasPermitidas.has(e.divisa);
    });

    // 3) trae de Nasdaq SOLO los días (en hora de Nueva York) que de verdad hacen falta
    const diasNecesarios = [...new Set(filtrados.map((e) => fechaEnZona(e.fechaUTC, 'America/New_York')))];
    const filasNasdaqPorDia = {};
    await Promise.all(diasNecesarios.map(async (dia) => {
      filasNasdaqPorDia[dia] = await obtenerDeNasdaq(dia, debugInfo && debugInfo.nasdaq);
    }));

    // 4) enriquece cada evento con el "actual" (Nasdaq primero, FRED de respaldo si aplica)
    const eventos = await Promise.all(filtrados.map((e) => enriqueceConActual(e, filasNasdaqPorDia, env, debugInfo && debugInfo.nasdaq, debugInfo && debugInfo.fred)));
    eventos.sort((a, b) => Date.parse(a.fechaUTC) - Date.parse(b.fechaUTC));

    const ttlSegundos = calculaTtlSegundos(eventos, ahora.getTime());
    const body = JSON.stringify({
      fuente: ffDesactualizado ? 'Forex Factory (copia desactualizada)' : 'Forex Factory',
      actualizado: ahora.toISOString(),
      desactualizado: ffDesactualizado,
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
