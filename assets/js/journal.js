/* Bitacora de trading - herramienta de Rango de Manada (se abre desde su tarjeta dentro de esa
   seccion o desde el menu; mientras Rango de Manada este en WIP_OWNER_ONLY_CATEGORIES, solo el
   dueño la puede abrir).

   Datos (scripts/sql/create_trade_journal.sql): trade_journal_trades (cada operacion, manual o
   sincronizada desde Bitunix), trade_journal_settings / trade_journal_capital (capital inicial)
   y trade_journal_sync (estado de la conexion). La conexion automatica la hace la Edge Function
   supabase/functions/trade-journal-sync - el navegador nunca ve ni guarda la API key.

   Todo en dolares. "Neto" de una operacion = pnl - fees + funding. Las estadisticas solo usan
   operaciones CERRADAS dentro del rango de fechas (por fecha de cierre); las abiertas se
   muestran aparte. Las graficas son SVG dibujado a mano, igual que el resto del sitio. */
(function(){
if(typeof sbClient === 'undefined') return;

const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
const usd = (v, d = 2) => (v < 0 ? '-' : '') + '$' + Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const sUsd = v => (v > 0 ? '+' : '') + usd(v);
const pct = (v, d = 1) => (Number.isFinite(v) ? v.toFixed(d) : '—') + '%';
const sPct = v => (v > 0 ? '+' : '') + pct(v);
const signCls = v => v > 0.004 ? 'jr-pos' : (v < -0.004 ? 'jr-neg' : 'jr-be');
const DAY = 86400000;
const MONTHS = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
const MONTHS_S = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
const WEEKDAYS = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'];
const EMOTIONS = ['Tranquilo','Confiado','Paciente','Ansioso','FOMO','Miedo','Revancha','Aburrido','Eufórico'];
const pad = n => String(n).padStart(2, '0');
const monthKey = d => d.getFullYear() + '-' + pad(d.getMonth() + 1);
const dayKey = d => d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
const startOfDay = d => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const fmtDate = d => d ? d.getDate() + ' ' + MONTHS_S[d.getMonth()] + ' ' + String(d.getFullYear()).slice(2) : '—';
const fmtDateTime = d => d ? fmtDate(d) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) : '—';
function fmtDur(ms){
  if(!Number.isFinite(ms) || ms < 0) return '—';
  const m = Math.round(ms / 60000);
  if(m < 60) return m + 'm';
  const h = Math.floor(m / 60);
  if(h < 48) return h + 'h ' + (m % 60) + 'm';
  return Math.floor(h / 24) + 'd ' + (h % 24) + 'h';
}
const toLocalInput = d => d ? d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes()) : '';
const toDateInput = d => d ? dayKey(d) : '';

/* ======================= estado ======================= */
const S = {
  loaded: false, error: null,
  trades: [], settings: { default_capital: 1000 }, capitalByMonth: {}, cashbackByMonth: {}, sync: null, exchangeConnected: false,
  tab: 'resumen',
  f: { preset: 'month', from: null, to: null, symbols: [], side: 'all', result: 'all', source: 'all', tag: 'all', setup: 'all', q: '' },
  sort: { key: 'closed', dir: -1 }, page: 0,
  calMonth: null, year: new Date().getFullYear(),
  syncing: false,
};

function normalize(r){
  const opened = r.opened_at ? new Date(r.opened_at) : null;
  const closed = r.closed_at ? new Date(r.closed_at) : null;
  const pnl = Number(r.pnl) || 0, fees = Number(r.fees) || 0, funding = Number(r.funding) || 0;
  const net = pnl - fees + funding;
  const margin = r.margin != null ? Number(r.margin) : null;
  const lev = r.leverage != null ? Number(r.leverage) : null;
  const entry = r.entry_price != null ? Number(r.entry_price) : null;
  const qty = r.qty != null ? Number(r.qty) : null;
  const notional = entry && qty ? entry * qty : (margin && lev ? margin * lev : null);
  return {
    raw: r, id: r.id, source: r.source, symbol: (r.symbol || '').toUpperCase(), side: r.side, status: r.status,
    leverage: lev, margin, qty, entry, exit: r.exit_price != null ? Number(r.exit_price) : null,
    sl: r.stop_loss != null ? Number(r.stop_loss) : null, tp: r.take_profit != null ? Number(r.take_profit) : null,
    pnl, fees, funding, net, notional,
    roe: margin ? net / margin * 100 : null,
    opened, closed, dur: opened && closed ? closed - opened : null,
    setup: r.setup || '', tags: Array.isArray(r.tags) ? r.tags : [], emotion: r.emotion || '', rating: r.rating || null, notes: r.notes || '',
  };
}

/* ======================= datos ======================= */
async function fetchAllTrades(){
  const PAGE = 1000; let all = [];
  for(let from = 0; ; ){
    const { data, error } = await sbClient.from('trade_journal_trades').select('*')
      .eq('user_id', currentUser.id).order('opened_at', { ascending: true }).range(from, from + PAGE - 1);
    if(error) throw error;
    if(!data || !data.length) return all;
    all = all.concat(data); from += data.length;
  }
}
async function loadAll(){
  if(!currentUser) return;
  try{
    const [trades, settings, capital, sync, cashback, connection] = await Promise.all([
      fetchAllTrades(),
      sbClient.from('trade_journal_settings').select('default_capital,journal_start_date').eq('user_id', currentUser.id).maybeSingle(),
      sbClient.from('trade_journal_capital').select('month,starting_capital').eq('user_id', currentUser.id),
      sbClient.from('trade_journal_sync').select('*').eq('user_id', currentUser.id).eq('exchange', 'bitunix').maybeSingle(),
      sbClient.from('user_bitunix_cashback').select('month,cashback_usdt').eq('user_id', currentUser.id),
      sbClient.from('user_exchange_connections').select('status').eq('user_id', currentUser.id).eq('exchange', 'bitunix').maybeSingle(),
    ]);
    S.trades = trades.map(normalize);
    S.settings = (settings && settings.data) || { default_capital: 1000 };
    // "empezar de cero" desde una fecha - oculta (no borra) todo lo anterior, pedido puntual de
    // Juan para su propia cuenta pero disponible para cualquiera via trade_journal_settings.
    if(S.settings.journal_start_date){
      const startD = new Date(S.settings.journal_start_date + 'T00:00:00');
      S.trades = S.trades.filter(t => t.opened && t.opened >= startD);
    }
    S.capitalByMonth = {};
    ((capital && capital.data) || []).forEach(c => { S.capitalByMonth[c.month] = Number(c.starting_capital); });
    S.sync = (sync && sync.data) || null;
    // conectado a Bitunix (con clave personal via trade-journal-sync, o solo por UID via Partner
    // API) = no se le debe pedir el saldo a mano - aunque hoy solo scripts/sync_journal_partner.py
    // lo llena solo (a quien conecto por UID); a quien tiene SOLO su clave personal (hoy, en la
    // practica, solo el dueño) hay que fijarselo una vez a mano por SQL, pero la caja de "poner
    // saldo" igual se le oculta porque no es algo que tenga sentido que el toque el mismo.
    S.exchangeConnected = !!(connection && connection.data && connection.data.status === 'connected')
      || !!(S.sync && S.sync.status === 'connected');
    // cashback del 20% de descuento de Juan, devuelto a la cuenta spot - lo llena
    // scripts/sync_journal_partner.py (Partner API), no es algo que el usuario registre
    S.cashbackByMonth = {};
    ((cashback && cashback.data) || []).forEach(c => { S.cashbackByMonth[c.month] = Number(c.cashback_usdt); });
    S.error = null;
  }catch(err){
    S.error = err;
  }
  S.loaded = true;
}
const capitalFor = mk => S.capitalByMonth[mk] || Number(S.settings.default_capital) || 1000;

/* ======================= filtros ======================= */
function presetRange(p){
  const now = new Date(), today = startOfDay(now);
  switch(p){
    case 'today': return [today, now];
    case '7d': return [new Date(today - 6 * DAY), now];
    case '30d': return [new Date(today - 29 * DAY), now];
    case 'month': return [new Date(now.getFullYear(), now.getMonth(), 1), now];
    case 'lastmonth': return [new Date(now.getFullYear(), now.getMonth() - 1, 1), new Date(now.getFullYear(), now.getMonth(), 1) - 1];
    case '90d': return [new Date(today - 89 * DAY), now];
    case 'year': return [new Date(now.getFullYear(), 0, 1), now];
    case 'all': return [null, null];
    default: return [S.f.from, S.f.to];
  }
}
function range(){
  const [a, b] = presetRange(S.f.preset);
  return [a ? new Date(a) : null, b ? new Date(b) : null];
}
function matchesNonDate(t){
  const f = S.f;
  if(f.symbols.length && !f.symbols.includes(t.symbol)) return false;
  if(f.side !== 'all' && t.side !== f.side) return false;
  if(f.source !== 'all' && t.source !== f.source) return false;
  if(f.tag !== 'all' && !t.tags.includes(f.tag)) return false;
  if(f.setup !== 'all' && t.setup !== f.setup) return false;
  if(t.status === 'closed' && f.result !== 'all'){
    const cls = t.net > 0.004 ? 'win' : (t.net < -0.004 ? 'loss' : 'be');
    if(cls !== f.result) return false;
  }
  if(f.q){
    const q = f.q.toLowerCase();
    if(!(t.symbol.toLowerCase().includes(q) || t.notes.toLowerCase().includes(q) || t.setup.toLowerCase().includes(q) || t.tags.join(' ').toLowerCase().includes(q))) return false;
  }
  return true;
}
function filteredClosed(){
  const [a, b] = range();
  return S.trades.filter(t => t.status === 'closed' && t.closed && (!a || t.closed >= a) && (!b || t.closed <= b) && matchesNonDate(t))
    .sort((x, y) => x.closed - y.closed);
}
const openTrades = () => S.trades.filter(t => t.status === 'open' && matchesNonDate(t));
const uniq = arr => [...new Set(arr.filter(Boolean))].sort();

/* ======================= estadisticas ======================= */
function stats(list, startCap){
  const n = list.length;
  const wins = list.filter(t => t.net > 0.004), losses = list.filter(t => t.net < -0.004);
  const be = n - wins.length - losses.length;
  const gp = wins.reduce((s, t) => s + t.net, 0), gl = losses.reduce((s, t) => s + t.net, 0);
  const net = gp + gl + list.filter(t => Math.abs(t.net) <= 0.004).reduce((s, t) => s + t.net, 0);
  let eq = startCap, peak = startCap, maxDD = 0, maxDDpct = 0;
  let curW = 0, curL = 0, maxW = 0, maxL = 0;
  const curve = [];
  list.forEach(t => {
    eq += t.net; peak = Math.max(peak, eq);
    const dd = peak - eq; if(dd > maxDD){ maxDD = dd; maxDDpct = peak ? dd / peak * 100 : 0; }
    curve.push({ d: t.closed, eq, dd: -dd });
    if(t.net > 0.004){ curW++; curL = 0; } else if(t.net < -0.004){ curL++; curW = 0; }
    maxW = Math.max(maxW, curW); maxL = Math.max(maxL, curL);
  });
  const levs = list.filter(t => t.leverage), durs = list.filter(t => t.dur != null);
  const days = {};
  list.forEach(t => { const k = dayKey(t.closed); days[k] = (days[k] || 0) + t.net; });
  const dayVals = Object.values(days);
  const mean = dayVals.length ? dayVals.reduce((s, v) => s + v, 0) / dayVals.length : 0;
  const sd = dayVals.length > 1 ? Math.sqrt(dayVals.reduce((s, v) => s + (v - mean) ** 2, 0) / (dayVals.length - 1)) : 0;
  const avgWin = wins.length ? gp / wins.length : 0, avgLoss = losses.length ? gl / losses.length : 0;
  return {
    n, wins: wins.length, losses: losses.length, be, net, gp, gl,
    winrate: (wins.length + losses.length) ? wins.length / (wins.length + losses.length) * 100 : NaN,
    pf: gl ? gp / Math.abs(gl) : (gp > 0 ? Infinity : NaN),
    avgWin, avgLoss, payoff: avgLoss ? avgWin / Math.abs(avgLoss) : NaN,
    expectancy: n ? net / n : 0,
    best: n ? list.reduce((m, t) => t.net > m.net ? t : m) : null,
    worst: n ? list.reduce((m, t) => t.net < m.net ? t : m) : null,
    fees: list.reduce((s, t) => s + t.fees, 0), funding: list.reduce((s, t) => s + t.funding, 0),
    volume: list.reduce((s, t) => s + (t.notional || 0), 0),
    avgLev: levs.length ? levs.reduce((s, t) => s + t.leverage, 0) / levs.length : NaN,
    avgDur: durs.length ? durs.reduce((s, t) => s + t.dur, 0) / durs.length : NaN,
    maxDD, maxDDpct, maxW, maxL, curW, curL, curve,
    ret: startCap ? net / startCap * 100 : NaN,
    recovery: maxDD ? net / maxDD : NaN,
    greenDays: dayVals.filter(v => v > 0).length, tradingDays: dayVals.length,
    sharpe: sd ? mean / sd * Math.sqrt(365) : NaN,
    days,
  };
}
function groupBy(list, keyFn){
  const m = new Map();
  list.forEach(t => { const k = keyFn(t); if(k == null) return; if(!m.has(k)) m.set(k, []); m.get(k).push(t); });
  return m;
}
function groupRows(list, keyFn){
  return [...groupBy(list, keyFn)].map(([k, arr]) => {
    const w = arr.filter(t => t.net > 0.004).length, l = arr.filter(t => t.net < -0.004).length;
    return { k, n: arr.length, net: arr.reduce((s, t) => s + t.net, 0), wr: (w + l) ? w / (w + l) * 100 : NaN, avg: arr.reduce((s, t) => s + t.net, 0) / arr.length };
  });
}

/* ======================= graficas SVG ======================= */
const C = { pos: '#4ade80', neg: '#f87171', line: '#5b8def', grid: 'rgba(255,255,255,.07)', txt: '#8b8f9a' };
function niceTicks(min, max, count = 4){
  if(min === max){ min -= 1; max += 1; }
  const span = max - min, step0 = span / count, mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= step0) || step0;
  const lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step;
  const out = []; for(let v = lo; v <= hi + step / 2; v += step) out.push(+v.toFixed(10));
  return out;
}
const shortUsd = v => { const a = Math.abs(v); const s = a >= 1e6 ? (a / 1e6).toFixed(1) + 'M' : a >= 1e3 ? (a / 1e3).toFixed(a >= 1e4 ? 0 : 1) + 'K' : a.toFixed(a < 10 ? 1 : 0); return (v < 0 ? '-$' : '$') + s; };
function lineChartSvg(points, opt = {}){
  // points: [{x: Date|number, y, label}] ; opt: {h, color, area, zero, fmt}
  const W = opt.W || 900, H = opt.h || 240, L = 62, R = 14, T = 14, B = 28;
  if(points.length < 2) return '<div class="jr-empty">Necesitas al menos 2 operaciones en el rango para ver esta gráfica.</div>';
  const ys = points.map(p => p.y);
  const ticks = niceTicks(Math.min(...ys, opt.zero ? 0 : Infinity), Math.max(...ys, opt.zero ? 0 : -Infinity));
  const yMin = ticks[0], yMax = ticks[ticks.length - 1];
  const xs = points.map((p, i) => i);
  const X = i => L + (W - L - R) * (i / (xs.length - 1));
  const Y = v => T + (H - T - B) * (1 - (v - yMin) / ((yMax - yMin) || 1));
  const fmt = opt.fmt || shortUsd;
  let g = ticks.map(v => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="${C.grid}"/><text x="${L - 8}" y="${Y(v) + 4}" text-anchor="end" fill="${C.txt}" font-size="11">${fmt(v)}</text>`).join('');
  const path = points.map((p, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(p.y).toFixed(1)).join(' ');
  const color = opt.color || C.line;
  if(opt.area){
    const base = Y(opt.areaBase != null ? opt.areaBase : yMin);
    g += `<path d="${path} L${X(points.length - 1)} ${base} L${X(0)} ${base} Z" fill="${color}" opacity=".12"/>`;
  }
  g += `<path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>`;
  const step = Math.max(1, Math.ceil(points.length / Math.max(2, Math.floor(W / 120))));
  points.forEach((p, i) => { if(i % step === 0 || i === points.length - 1) g += `<text x="${X(i)}" y="${H - 8}" text-anchor="middle" fill="${C.txt}" font-size="11">${esc(p.label)}</text>`; });
  const bw = (W - L - R) / points.length;
  points.forEach((p, i) => { g += `<rect x="${X(i) - bw / 2}" y="${T}" width="${bw}" height="${H - T - B}" fill="transparent"><title>${esc(p.label)} · ${esc(opt.tip ? opt.tip(p) : fmt(p.y))}</title></rect>`; });
  return `<svg class="jr-svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${g}</svg>`;
}
function barChartSvg(items, opt = {}){
  // items: [{label, value, tip}] ; barras verdes/rojas segun signo
  const W = opt.W || 900, H = opt.h || 220, L = 62, R = 10, T = 12, B = 30;
  if(!items.length) return '<div class="jr-empty">Sin datos en este rango.</div>';
  const vals = items.map(i => i.value);
  const ticks = niceTicks(Math.min(0, ...vals), Math.max(0, ...vals));
  const yMin = ticks[0], yMax = ticks[ticks.length - 1];
  const Y = v => T + (H - T - B) * (1 - (v - yMin) / ((yMax - yMin) || 1));
  const fmt = opt.fmt || shortUsd;
  const slot = (W - L - R) / items.length, bw = Math.max(2, Math.min(46, slot * .7));
  let g = ticks.map(v => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="${v === 0 ? 'rgba(255,255,255,.18)' : C.grid}"/><text x="${L - 8}" y="${Y(v) + 4}" text-anchor="end" fill="${C.txt}" font-size="11">${fmt(v)}</text>`).join('');
  const step = Math.max(1, Math.ceil(items.length / Math.min(opt.maxLabels || 12, Math.max(2, Math.floor(W / 55)))));
  items.forEach((it, i) => {
    const x = L + slot * i + (slot - bw) / 2, y0 = Y(0), y1 = Y(it.value);
    const color = opt.color || (it.value >= 0 ? C.pos : C.neg);
    g += `<rect x="${x}" y="${Math.min(y0, y1)}" width="${bw}" height="${Math.max(1, Math.abs(y1 - y0))}" rx="3" fill="${color}" opacity=".85"><title>${esc(it.label)} · ${esc(it.tip || fmt(it.value))}</title></rect>`;
    if(i % step === 0) g += `<text x="${x + bw / 2}" y="${H - 10}" text-anchor="middle" fill="${C.txt}" font-size="11">${esc(it.label)}</text>`;
  });
  return `<svg class="jr-svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${g}</svg>`;
}
/* las graficas se arman como un hueco vacio y se dibujan DESPUES de insertarlas, con el ancho
   real de su caja: asi el texto de los ejes nunca queda estirado ni aplastado (en celular la
   caja mide un tercio que en escritorio). Se vuelven a dibujar al cambiar el tamaño. */
let CHART_SPECS = [];
function chartSlot(kind, data, opt){
  CHART_SPECS.push({ kind, data, opt });
  return `<div class="jr-chart" data-chart="${CHART_SPECS.length - 1}" style="height:${(opt && opt.h) || 220}px"></div>`;
}
const lineChart = (points, opt = {}) => points.length < 2 ? lineChartSvg(points, opt) : chartSlot('line', points, opt);
const barChart = (items, opt = {}) => !items.length ? barChartSvg(items, opt) : chartSlot('bar', items, opt);
function drawCharts(){
  document.querySelectorAll('#jrPane .jr-chart').forEach(el => {
    const spec = CHART_SPECS[Number(el.dataset.chart)];
    if(!spec) return;
    const W = Math.max(260, Math.round(el.clientWidth));
    el.innerHTML = (spec.kind === 'line' ? lineChartSvg : barChartSvg)(spec.data, { ...spec.opt, W });
  });
}
let chartResizeTimer;
window.addEventListener('resize', () => { clearTimeout(chartResizeTimer); chartResizeTimer = setTimeout(drawCharts, 150); });
function hBars(items, opt = {}){
  if(!items.length) return '<div class="jr-empty">Sin datos en este rango.</div>';
  const max = Math.max(...items.map(i => Math.abs(i.value))) || 1;
  return '<div class="jr-hbars">' + items.map(it => `
    <div class="jr-hbar" title="${esc(it.tip || '')}">
      <span class="jr-hbar-label">${esc(it.label)}</span>
      <span class="jr-hbar-track"><span class="jr-hbar-fill" style="width:${Math.abs(it.value) / max * 100}%;background:${it.value >= 0 ? C.pos : C.neg}"></span></span>
      <span class="jr-hbar-val ${signCls(it.value)}">${opt.fmt ? opt.fmt(it.value) : sUsd(it.value)}</span>
    </div>`).join('') + '</div>';
}
function donut(parts){
  const total = parts.reduce((s, p) => s + p.value, 0);
  if(!total) return '<div class="jr-empty">Sin operaciones.</div>';
  let a = -Math.PI / 2, g = '';
  parts.forEach(p => {
    if(!p.value) return;
    const da = p.value / total * Math.PI * 2, a2 = a + da, large = da > Math.PI ? 1 : 0;
    const r = 60, x1 = 80 + r * Math.cos(a), y1 = 80 + r * Math.sin(a), x2 = 80 + r * Math.cos(a2), y2 = 80 + r * Math.sin(a2);
    g += p.value === total
      ? `<circle cx="80" cy="80" r="${r}" fill="none" stroke="${p.color}" stroke-width="22"><title>${esc(p.label)}: ${p.value}</title></circle>`
      : `<path d="M${x1} ${y1} A${r} ${r} 0 ${large} 1 ${x2} ${y2}" fill="none" stroke="${p.color}" stroke-width="22"><title>${esc(p.label)}: ${p.value}</title></path>`;
    a = a2;
  });
  return `<div class="jr-donut"><svg viewBox="0 0 160 160" width="150" height="150">${g}</svg><div class="jr-donut-legend">${parts.map(p => `<div><i style="background:${p.color}"></i>${esc(p.label)} <b>${p.value}</b> <span>${total ? (p.value / total * 100).toFixed(0) : 0}%</span></div>`).join('')}</div></div>`;
}

/* ======================= UI base ======================= */
const root = () => $('journalRoot');
function kpi(label, value, sub, cls){
  return `<div class="jr-kpi"><div class="jr-kpi-label">${label}${helpBtn(label)}</div><div class="jr-kpi-val ${cls || ''}">${value}</div>${sub ? `<div class="jr-kpi-sub">${sub}</div>` : ''}</div>`;
}
function card(title, body, extra){
  return `<div class="jr-card ${extra || ''}"><div class="jr-card-title">${title}${helpBtn(title)}</div>${body}</div>`;
}
/* ======================= ayuda (bolitas "?") ======================= */
// Pedido explicito de Juan: no todo el mundo (ni el mismo) entiende todos los terminos de
// trading que aparecen aca - una bolita con "?" al lado de cada titulo/filtro/pestana, que al
// tocarla explica en espanol sencillo que es ese dato. helpBtn() busca el texto por la MISMA
// etiqueta visible (asi no hay que tocar cada sitio donde se usa kpi()/un <th>/una pestana).
const HELP = {
  // pestanas
  'Resumen': 'La vista general: cuánto ganaste o perdiste en el rango de fechas elegido arriba, el cashback de Bitunix del mes, y las métricas clave de tus operaciones cerradas.',
  'Operaciones': 'La lista completa de tus operaciones, abiertas y cerradas, para revisarlas o editarlas una por una.',
  'Calendario': 'Tu resultado día por día en un calendario, para ver de un vistazo en qué días ganaste o perdiste.',
  'Análisis': 'Comparaciones más a fondo: qué par te va mejor, de día o de noche, long contra short, por setup, etc.',
  'Mensual / Anual': 'El resumen de cada mes y de cada año: cuánto operaste, cuánto ganaste y tu capital inicial de ese período.',
  'Conexión y ajustes': 'Aquí conectas o desconectas tu cuenta de Bitunix, y ves el capital con el que se calculan tus porcentajes.',
  // filtros
  'filter_pares': 'Muestra solo las operaciones de uno o varios pares que elijas (ej. BTCUSDT), ocultando el resto.',
  'filter_lado': '"Long" = apostaste a que el precio sube. "Short" = apostaste a que baja. Filtra para ver solo uno de los dos.',
  'filter_resultado': 'Filtra por cómo cerró la operación: con ganancia, con pérdida, o "break-even" (cerró prácticamente sin ganar ni perder).',
  'filter_origen': '"Manual" = la registraste tú a mano. "Bitunix" = llegó sola porque conectaste tu cuenta. Filtra para ver solo un tipo.',
  'filter_setup': 'Filtra por la estrategia o "setup" que le escribiste a la operación al registrarla (ej. "ruptura de rango").',
  'filter_etiqueta': 'Filtra por las etiquetas que le pusiste a tus operaciones (ej. "scalp", "noticia", "tendencia").',
  // hero
  'P&L neto del rango': 'Ganancia o pérdida total, ya con comisiones y funding descontados, de las operaciones CERRADAS dentro del rango de fechas que elegiste arriba (las abiertas no cuentan hasta que cierren).',
  'Ganado': 'La suma de todo lo que ganaste en las operaciones que cerraste con ganancia, dentro del rango de fechas elegido.',
  'Perdido': 'La suma de todo lo que perdiste en las operaciones que cerraste con pérdida, dentro del rango de fechas elegido.',
  'Comisiones': 'Lo que Bitunix te cobró en comisiones por todas tus operaciones del rango elegido (ya descontado del P&L neto).',
  'Funding': 'El pago que se cobra o se paga cada tanto por mantener una posición de futuros abierta - puede ser a tu favor (+) o en contra (-).',
  'Cashback Bitunix (mes)': 'El 20% de descuento que te doy en comisiones no se aplica al momento - Bitunix te lo devuelve como dinero real a tu cuenta spot. Esto es lo que llevas recibido ESTE MES (no depende del rango de fechas de arriba).',
  // kpis resumen
  'Winrate': 'El porcentaje de tus operaciones cerradas que terminaron en ganancia.',
  'Profit factor': 'Todo lo ganado dividido entre todo lo perdido. Más de 1 = ganas más de lo que pierdes. Menos de 1 = al revés.',
  'Expectativa': 'La ganancia o pérdida promedio que puedes esperar por cada operación nueva, según cómo te ha ido hasta ahora.',
  'Ratio G/P': 'Tu ganancia promedio dividida entre tu pérdida promedio - qué tan grandes son tus ganancias comparadas con tus pérdidas.',
  'Ganancia promedio': 'El promedio de dinero que ganas en las operaciones que te salen bien.',
  'Pérdida promedio': 'El promedio de dinero que pierdes en las operaciones que te salen mal.',
  'Max drawdown': 'La caída más grande que tuvo tu capital desde un punto alto hasta un punto bajo, dentro del rango elegido.',
  'Factor de recuperación': 'Tu ganancia neta dividida entre tu peor caída (drawdown) - qué tan bien compensas lo que llegaste a perder.',
  'Mejor operación': 'La operación que más dinero te dejó, dentro del rango de fechas elegido.',
  'Peor operación': 'La operación que más dinero te costó, dentro del rango de fechas elegido.',
  'Rachas': 'La racha más larga de operaciones ganadoras seguidas, y la más larga de operaciones perdedoras seguidas.',
  'Días en verde': 'De los días en que hiciste al menos una operación, cuántos terminaron el día con ganancia neta.',
  'Apalancamiento prom.': 'El apalancamiento (x) promedio que usaste en tus operaciones - cuánto "multiplicaste" tu margen.',
  'Duración promedio': 'Cuánto tiempo, en promedio, mantienes abierta una operación antes de cerrarla.',
  'Volumen operado': 'La suma del tamaño de todas tus posiciones (precio de entrada × cantidad) en el rango elegido.',
  'Sharpe (diario, anual.)': 'Qué tan buena es tu rentabilidad comparada con qué tan pareja o irregular es. Más alto es mejor; 0 o negativo es mala señal.',
  // tabla mensual/anual
  'Mes': 'El mes al que corresponde esa fila.',
  'Op.': 'Cuántas operaciones cerraste ese mes.',
  'Capital inicial': 'El capital con el que arrancó ese mes - se usa para calcular tu % de rentabilidad y de drawdown de ese mes.',
  'P&L neto': 'Ganancia o pérdida total de ese mes, ya con comisiones y funding descontados.',
  'Rentab.': 'El P&L neto de ese mes como porcentaje de tu capital inicial de ese mes.',
  'Mejor día': 'El día con más ganancia neta dentro de ese mes.',
  'Peor día': 'El día con más pérdida neta dentro de ese mes.',
  'Max DD': 'La caída más grande que tuvo tu capital ese mes, desde un punto alto hasta un punto bajo.',
  // titulos de graficos y tarjetas
  'Curva de capital': 'Cómo fue creciendo o bajando tu capital, operación tras operación, dentro del rango de fechas elegido.',
  'Drawdown': 'En cada punto de tu curva de capital, cuánto habías caído desde el pico más alto que llevabas hasta ese momento.',
  'P&L por día': 'Cuánto ganaste o perdiste en total cada día, dentro del rango de fechas elegido.',
  'Long vs Short': 'Compara tus resultados cuando apostaste a que el precio sube (long) contra cuando apostaste a que baja (short).',
  'Resultados': 'De tus operaciones cerradas, cuántas fueron ganadoras, perdedoras, o break-even (sin ganar ni perder).',
  'Mejores y peores pares': 'Los pares (ej. BTCUSDT) que más te dejaron en ganancia, y los que más te costaron, dentro del rango elegido.',
  'Posiciones abiertas': 'Las operaciones que todavía no has cerrado - no cuentan en tus estadísticas hasta que las cierres.',
  'P&L por par': 'Cuánto ganaste o perdiste en total con cada par que operaste (ej. BTCUSDT, ETHUSDT).',
  'P&L por día de la semana': 'Si te va mejor operando lunes, martes, etc. - suma el resultado de cada día de la semana en todo tu historial filtrado.',
  'P&L por hora de apertura': 'Si te va mejor abriendo operaciones a ciertas horas del día - agrupa tus resultados por la hora en que abriste cada operación.',
  'Distribución de resultados': 'Cuántas de tus operaciones cerraron con cada tamaño de ganancia o pérdida, agrupadas en rangos.',
  'ROE por operación (sobre margen)': 'El "Return On Equity": la ganancia o pérdida de cada operación como porcentaje del margen que usaste en ella (no del capital total).',
  'Por apalancamiento': 'Cómo te va según el apalancamiento (x) que usaste en cada operación.',
  'Por duración': 'Cómo te va según cuánto tiempo mantienes abierta una operación antes de cerrarla.',
  'Por setup': 'Cómo te va según la estrategia o "setup" que le escribiste a cada operación al registrarla.',
  'Por emoción': 'Cómo te va según el estado de ánimo que marcaste al registrar cada operación (tranquilo, ansioso, FOMO, etc.).',
  'Por etiqueta': 'Cómo te va según las etiquetas que le pusiste a tus operaciones.',
  'Por calidad de ejecución': 'Cómo te va según la calificación con estrellas que le diste a tu propia ejecución de cada operación.',
  'Detalle por par': 'La tabla completa, par por par, con cuántas operaciones hiciste, tu winrate y tu resultado neto de cada uno.',
  'P&L por mes': 'Cuánto ganaste o perdiste en total cada mes del año que estás viendo.',
  'P&L acumulado del año': 'Tu ganancia o pérdida sumada mes tras mes, para ver cómo va el año completo de corrido.',
  'Detalle mes a mes': 'Un resumen fila por fila de cada mes del año: operaciones, winrate, capital inicial y rentabilidad.',
  'Conexión automática con Bitunix': 'Aquí conectas tu cuenta de Bitunix (con una API key de solo lectura) para que tus operaciones se carguen solas, sin escribirlas a mano.',
  'Capital': 'El capital con el que se calculan tus porcentajes de rentabilidad y de drawdown en cada mes.',
};
function helpBtn(label){
  const t = HELP[label];
  return t ? ` <button type="button" class="jr-help" data-help="${esc(t)}" aria-label="¿Qué es esto?">?</button>` : '';
}
const PRESETS = [['today','Hoy'],['7d','7 días'],['30d','30 días'],['month','Este mes'],['lastmonth','Mes pasado'],['90d','90 días'],['year','Este año'],['all','Todo'],['custom','Personalizado']];
const TABS = [['resumen','Resumen'],['operaciones','Operaciones'],['calendario','Calendario'],['analisis','Análisis'],['anual','Mensual / Anual'],['ajustes','Conexión y ajustes']];

function renderShell(){
  const r = root();
  if(!r) return;
  if(!S.loaded){ r.innerHTML = '<div class="jr-loading">Cargando tu bitácora…</div>'; return; }
  if(S.error){
    r.innerHTML = `<div class="jr-head"><div><div class="section-eyebrow" style="margin-top:0">Rango de Manada</div><h2 class="jr-title">Bitácora de trading</h2></div></div>
      <div class="jr-empty jr-big">No se pudo cargar la bitácora (${esc(S.error.message || S.error)}). Si es la primera vez, falta correr <b>scripts/sql/create_trade_journal.sql</b> en Supabase.</div>`;
    return;
  }
  const symbols = uniq(S.trades.map(t => t.symbol)), tags = uniq(S.trades.flatMap(t => t.tags)), setups = uniq(S.trades.map(t => t.setup));
  const f = S.f;
  const syncTxt = S.sync && S.sync.status === 'connected'
    ? `<span class="jr-sync-dot on"></span>Bitunix conectado · ${S.sync.last_sync_at ? 'sincronizado ' + fmtDateTime(new Date(S.sync.last_sync_at)) : 'sin sincronizar'}`
    : (S.sync && S.sync.status === 'error' ? `<span class="jr-sync-dot err"></span>Error de sincronización` : `<span class="jr-sync-dot"></span>Solo registro manual`);
  r.innerHTML = `
    <div class="jr-head">
      <div>
        <div class="section-eyebrow" style="margin-top:0">Rango de Manada · Bitácora</div>
        <h2 class="jr-title">Bitácora de trading</h2>
        <div class="jr-sync-line">${syncTxt}</div>
      </div>
      <div class="jr-head-actions">
        ${S.sync && S.sync.status !== 'disconnected' ? `<button type="button" class="jr-btn" data-act="sync" ${S.syncing ? 'disabled' : ''}>${S.syncing ? 'Sincronizando…' : '↻ Sincronizar'}</button>` : ''}
        <button type="button" class="jr-btn" data-act="csv">Exportar CSV</button>
        <button type="button" class="jr-btn jr-btn-primary" data-act="new">+ Nueva operación</button>
      </div>
    </div>
    <div class="jr-filters">
      <div class="jr-presets">${PRESETS.map(([k, l]) => `<button type="button" class="jr-chip ${f.preset === k ? 'on' : ''}" data-preset="${k}">${l}</button>`).join('')}</div>
      <div class="jr-custom" style="display:${f.preset === 'custom' ? 'flex' : 'none'}">
        <label>Desde <input type="date" id="jrFrom" value="${toDateInput(f.from)}"></label>
        <label>Hasta <input type="date" id="jrTo" value="${toDateInput(f.to ? new Date(f.to - 1) : null)}"></label>
      </div>
      <div class="jr-filter-row">
        <span class="jr-fitem">
          <div class="jr-ms" id="jrSymbolMs">
            <button type="button" class="jr-select" data-act="ms">${f.symbols.length ? f.symbols.length + ' par' + (f.symbols.length > 1 ? 'es' : '') : 'Todos los pares'} ▾</button>
            <div class="jr-ms-pop" style="display:none">${symbols.length ? symbols.map(s => `<label><input type="checkbox" value="${esc(s)}" ${f.symbols.includes(s) ? 'checked' : ''}> ${esc(s)}</label>`).join('') : '<span class="jr-muted">Aún no hay pares</span>'}</div>
          </div>${helpBtn('filter_pares')}
        </span>
        <span class="jr-fitem"><select class="jr-select" data-f="side"><option value="all">Long y short</option><option value="long" ${f.side === 'long' ? 'selected' : ''}>Solo long</option><option value="short" ${f.side === 'short' ? 'selected' : ''}>Solo short</option></select>${helpBtn('filter_lado')}</span>
        <span class="jr-fitem"><select class="jr-select" data-f="result"><option value="all">Todos los resultados</option><option value="win" ${f.result === 'win' ? 'selected' : ''}>Ganadoras</option><option value="loss" ${f.result === 'loss' ? 'selected' : ''}>Perdedoras</option><option value="be" ${f.result === 'be' ? 'selected' : ''}>Break-even</option></select>${helpBtn('filter_resultado')}</span>
        <span class="jr-fitem"><select class="jr-select" data-f="source"><option value="all">Manual y automático</option><option value="manual" ${f.source === 'manual' ? 'selected' : ''}>Solo manual</option><option value="bitunix" ${f.source === 'bitunix' ? 'selected' : ''}>Solo Bitunix</option></select>${helpBtn('filter_origen')}</span>
        <span class="jr-fitem"><select class="jr-select" data-f="setup"><option value="all">Todos los setups</option>${setups.map(s => `<option ${f.setup === s ? 'selected' : ''}>${esc(s)}</option>`).join('')}</select>${helpBtn('filter_setup')}</span>
        <span class="jr-fitem"><select class="jr-select" data-f="tag"><option value="all">Todas las etiquetas</option>${tags.map(s => `<option ${f.tag === s ? 'selected' : ''}>${esc(s)}</option>`).join('')}</select>${helpBtn('filter_etiqueta')}</span>
        <input type="search" class="jr-search" id="jrSearch" placeholder="Buscar par, nota, setup…" value="${esc(f.q)}">
        <button type="button" class="jr-link" data-act="clear">Limpiar filtros</button>
      </div>
    </div>
    <div class="jr-tabs">${TABS.map(([k, l]) => `<span class="jr-tab-wrap"><button type="button" class="jr-tab ${S.tab === k ? 'on' : ''}" data-tab="${k}">${l}</button>${helpBtn(l)}</span>`).join('')}</div>
    <div id="jrPane"></div>`;
  renderPane();
}

function renderPane(){
  const pane = $('jrPane');
  if(!pane) return;
  const fn = { resumen: paneResumen, operaciones: paneOperaciones, calendario: paneCalendario, analisis: paneAnalisis, anual: paneAnual, ajustes: paneAjustes }[S.tab];
  CHART_SPECS = [];
  pane.innerHTML = fn();
  drawCharts();
}

/* ======================= Resumen ======================= */
function rangeStartCapital(list){
  const [a] = range();
  const first = a || (list[0] && list[0].closed) || new Date();
  return capitalFor(monthKey(first));
}
function paneResumen(){
  const list = filteredClosed();
  const cap = rangeStartCapital(list);
  const st = stats(list, cap);
  if(!S.trades.length) return emptyState();
  // cashback del 20% de descuento de Juan (se devuelve a tu cuenta SPOT, no es un descuento en
  // la comision misma) - siempre del MES EN CURSO, independiente del filtro de fechas de arriba,
  // porque es plata real que ya te devolvieron, no algo que dependa de que rango estes mirando
  const cashbackMonth = S.cashbackByMonth[monthKey(new Date())] || 0;
  const curve = [{ y: cap, label: 'Inicio' }].concat(st.curve.map(p => ({ y: p.eq, label: fmtDate(p.d) })));
  const ddCurve = [{ y: 0, label: 'Inicio' }].concat(st.curve.map(p => ({ y: p.dd, label: fmtDate(p.d) })));
  const dayItems = Object.keys(st.days).sort().map(k => { const [y, m, d] = k.split('-'); return { label: Number(d) + ' ' + MONTHS_S[Number(m) - 1], value: st.days[k] }; });
  const longs = list.filter(t => t.side === 'long'), shorts = list.filter(t => t.side === 'short');
  const sl = stats(longs, cap), ss = stats(shorts, cap);
  const bySym = groupRows(list, t => t.symbol).sort((a, b) => b.net - a.net);
  const top = bySym.slice(0, 5).concat(bySym.length > 5 ? bySym.slice(-3).filter(r => r.net < 0 && !bySym.slice(0, 5).includes(r)) : []);
  const opens = openTrades();
  return `
    <div class="jr-hero ${signCls(st.net)}">
      <div><div class="jr-kpi-label">P&L neto del rango${helpBtn('P&L neto del rango')}</div><div class="jr-hero-val">${sUsd(st.net)}</div>
      <div class="jr-hero-sub"><span class="${signCls(st.ret)}">${sPct(st.ret)}</span> sobre capital de ${usd(cap, 0)} · ${st.n} operaciones cerradas · capital actual ${usd(cap + st.net)}</div></div>
      <div class="jr-hero-mini">
        <div><span>Ganado${helpBtn('Ganado')}</span><b class="jr-pos">${usd(st.gp)}</b></div>
        <div><span>Perdido${helpBtn('Perdido')}</span><b class="jr-neg">${usd(st.gl)}</b></div>
        <div><span>Comisiones${helpBtn('Comisiones')}</span><b>${usd(st.fees)}</b></div>
        <div><span>Funding${helpBtn('Funding')}</span><b class="${signCls(st.funding)}">${sUsd(st.funding)}</b></div>
        <div><span>💰 Cashback Bitunix (mes)${helpBtn('Cashback Bitunix (mes)')}</span><b class="jr-pos">${usd(cashbackMonth)}</b></div>
      </div>
      <div class="jr-hero-sub" style="margin-top:6px">El 20% de descuento que te doy en comisiones no es un descuento en el momento — Bitunix te lo devuelve como cashback real a tu cuenta spot. Esto es lo que llevas recibido este mes.</div>
    </div>
    <div class="jr-kpis">
      ${kpi('Winrate', pct(st.winrate), st.wins + ' G · ' + st.losses + ' P · ' + st.be + ' BE')}
      ${kpi('Profit factor', Number.isFinite(st.pf) ? st.pf.toFixed(2) : (st.pf === Infinity ? '∞' : '—'), 'Ganado ÷ perdido')}
      ${kpi('Expectativa', sUsd(st.expectancy), 'Promedio por operación', signCls(st.expectancy))}
      ${kpi('Ratio G/P', Number.isFinite(st.payoff) ? st.payoff.toFixed(2) : '—', 'Ganancia prom. ÷ pérdida prom.')}
      ${kpi('Ganancia promedio', usd(st.avgWin), '', 'jr-pos')}
      ${kpi('Pérdida promedio', usd(st.avgLoss), '', 'jr-neg')}
      ${kpi('Max drawdown', usd(-st.maxDD), pct(-st.maxDDpct) + ' desde el pico', 'jr-neg')}
      ${kpi('Factor de recuperación', Number.isFinite(st.recovery) ? st.recovery.toFixed(2) : '—', 'Neto ÷ max drawdown')}
      ${kpi('Mejor operación', st.best ? sUsd(st.best.net) : '—', st.best ? esc(st.best.symbol) + ' · ' + fmtDate(st.best.closed) : '', 'jr-pos')}
      ${kpi('Peor operación', st.worst ? sUsd(st.worst.net) : '—', st.worst ? esc(st.worst.symbol) + ' · ' + fmtDate(st.worst.closed) : '', 'jr-neg')}
      ${kpi('Rachas', st.maxW + ' / ' + st.maxL, 'Máx. ganadoras / perdedoras · actual ' + (st.curW ? st.curW + ' G' : st.curL ? st.curL + ' P' : '—'))}
      ${kpi('Días en verde', st.tradingDays ? st.greenDays + '/' + st.tradingDays : '—', st.tradingDays ? pct(st.greenDays / st.tradingDays * 100, 0) + ' de los días operados' : '')}
      ${kpi('Apalancamiento prom.', Number.isFinite(st.avgLev) ? st.avgLev.toFixed(1) + 'x' : '—', '')}
      ${kpi('Duración promedio', fmtDur(st.avgDur), '')}
      ${kpi('Volumen operado', usd(st.volume, 0), 'Tamaño de posición total')}
      ${kpi('Sharpe (diario, anual.)', Number.isFinite(st.sharpe) ? st.sharpe.toFixed(2) : '—', 'Rentabilidad ÷ variabilidad')}
    </div>
    <div class="jr-grid2">
      ${card('Curva de capital', lineChart(curve, { area: true, color: C.line, h: 260, areaBase: Math.min(...curve.map(p => p.y)) }), 'jr-span2')}
      ${card('Drawdown', lineChart(ddCurve, { area: true, color: C.neg, h: 160, areaBase: 0 }), 'jr-span2')}
      ${card('P&L por día', barChart(dayItems, { h: 220 }), 'jr-span2')}
      ${card('Long vs Short', `<table class="jr-table jr-compact"><thead><tr><th></th><th>Long</th><th>Short</th></tr></thead><tbody>
        <tr><td>Operaciones</td><td>${sl.n}</td><td>${ss.n}</td></tr>
        <tr><td>Winrate</td><td>${pct(sl.winrate)}</td><td>${pct(ss.winrate)}</td></tr>
        <tr><td>P&L neto</td><td class="${signCls(sl.net)}">${sUsd(sl.net)}</td><td class="${signCls(ss.net)}">${sUsd(ss.net)}</td></tr>
        <tr><td>Profit factor</td><td>${Number.isFinite(sl.pf) ? sl.pf.toFixed(2) : '—'}</td><td>${Number.isFinite(ss.pf) ? ss.pf.toFixed(2) : '—'}</td></tr>
        <tr><td>Expectativa</td><td class="${signCls(sl.expectancy)}">${sUsd(sl.expectancy)}</td><td class="${signCls(ss.expectancy)}">${sUsd(ss.expectancy)}</td></tr>
      </tbody></table>`)}
      ${card('Resultados', donut([{ label: 'Ganadoras', value: st.wins, color: C.pos }, { label: 'Perdedoras', value: st.losses, color: C.neg }, { label: 'Break-even', value: st.be, color: '#8b8f9a' }]))}
      ${card('Mejores y peores pares', hBars(top.map(r => ({ label: r.k, value: r.net, tip: r.n + ' operaciones · winrate ' + pct(r.wr) }))))}
      ${card('Posiciones abiertas', opens.length ? `<table class="jr-table jr-compact"><thead><tr><th>Par</th><th>Lado</th><th>Entrada</th><th>Margen</th><th>Desde</th></tr></thead><tbody>${opens.map(t => `<tr class="jr-row" data-edit="${t.id}"><td>${esc(t.symbol)}</td><td><span class="jr-side ${t.side}">${t.side === 'long' ? 'LONG' : 'SHORT'}</span> ${t.leverage ? t.leverage + 'x' : ''}</td><td>${t.entry ?? '—'}</td><td>${t.margin != null ? usd(t.margin) : '—'}</td><td>${fmtDateTime(t.opened)}</td></tr>`).join('')}</tbody></table>` : '<div class="jr-empty">No tienes posiciones abiertas.</div>')}
    </div>`;
}
function emptyState(){
  return `<div class="jr-empty jr-big">
    <b>Tu bitácora está vacía.</b><br>Registra tu primera operación a mano, o conecta tu cuenta de Bitunix para que se llene sola.
    <div style="margin-top:14px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap">
      <button type="button" class="jr-btn jr-btn-primary" data-act="new">+ Nueva operación</button>
      <button type="button" class="jr-btn" data-tab="ajustes">Conectar Bitunix</button>
    </div></div>`;
}

/* ======================= Operaciones ======================= */
const COLS = [
  ['closed', 'Cierre'], ['symbol', 'Par'], ['side', 'Lado'], ['leverage', 'Apal.'], ['margin', 'Margen'],
  ['entry', 'Entrada'], ['exit', 'Salida'], ['net', 'P&L neto'], ['roe', 'ROE'], ['dur', 'Duración'], ['setup', 'Setup'], ['source', 'Origen'],
];
const PER_PAGE = 25;
function paneOperaciones(){
  const list = filteredClosed();
  const { key, dir } = S.sort;
  const sorted = list.slice().sort((a, b) => {
    const va = a[key], vb = b[key];
    if(va == null && vb == null) return 0; if(va == null) return 1; if(vb == null) return -1;
    return (va > vb ? 1 : va < vb ? -1 : 0) * dir;
  });
  const pages = Math.max(1, Math.ceil(sorted.length / PER_PAGE));
  S.page = Math.min(S.page, pages - 1);
  const rows = sorted.slice(S.page * PER_PAGE, S.page * PER_PAGE + PER_PAGE);
  const opens = openTrades();
  const tot = stats(list, 0);
  return `
    ${opens.length ? card('Posiciones abiertas (' + opens.length + ')' + helpBtn('Posiciones abiertas'), `<div class="jr-table-wrap"><table class="jr-table"><thead><tr><th>Apertura</th><th>Par</th><th>Lado</th><th>Apal.</th><th>Margen</th><th>Entrada</th><th>SL</th><th>TP</th><th>Origen</th><th></th></tr></thead><tbody>
      ${opens.map(t => `<tr class="jr-row" data-edit="${t.id}"><td>${fmtDateTime(t.opened)}</td><td><b>${esc(t.symbol)}</b></td><td><span class="jr-side ${t.side}">${t.side.toUpperCase()}</span></td><td>${t.leverage ? t.leverage + 'x' : '—'}</td><td>${t.margin != null ? usd(t.margin) : '—'}</td><td>${t.entry ?? '—'}</td><td>${t.sl ?? '—'}</td><td>${t.tp ?? '—'}</td><td>${t.source === 'bitunix' ? 'Bitunix' : 'Manual'}</td><td>${t.source === 'manual' ? '<button type="button" class="jr-link" data-close="' + t.id + '">Cerrar</button>' : ''}</td></tr>`).join('')}
    </tbody></table></div>`) : ''}
    <div class="jr-card">
      <div class="jr-card-title">Operaciones cerradas <span class="jr-muted">· ${list.length} en el rango · neto <b class="${signCls(tot.net)}">${sUsd(tot.net)}</b></span></div>
      ${list.length ? `<div class="jr-table-wrap"><table class="jr-table jr-sortable"><thead><tr>${COLS.map(([k, l]) => `<th data-sort="${k}" class="${key === k ? 'on' : ''}">${l}${key === k ? (dir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}<th></th></tr></thead><tbody>
        ${rows.map(t => `<tr class="jr-row" data-edit="${t.id}">
          <td>${fmtDateTime(t.closed)}</td><td><b>${esc(t.symbol)}</b>${t.tags.length ? '<div class="jr-tags">' + t.tags.map(x => '<span>' + esc(x) + '</span>').join('') + '</div>' : ''}</td>
          <td><span class="jr-side ${t.side}">${t.side.toUpperCase()}</span></td><td>${t.leverage ? t.leverage + 'x' : '—'}</td>
          <td>${t.margin != null ? usd(t.margin) : '—'}</td><td>${t.entry ?? '—'}</td><td>${t.exit ?? '—'}</td>
          <td class="${signCls(t.net)}"><b>${sUsd(t.net)}</b>${t.fees ? '<div class="jr-muted jr-xs">com. ' + usd(t.fees) + '</div>' : ''}</td>
          <td class="${signCls(t.roe || 0)}">${t.roe != null ? sPct(t.roe) : '—'}</td><td>${fmtDur(t.dur)}</td><td>${esc(t.setup) || '—'}</td>
          <td>${t.source === 'bitunix' ? '<span class="jr-src">Bitunix</span>' : '<span class="jr-src man">Manual</span>'}</td>
          <td><button type="button" class="jr-link" data-edit="${t.id}">Editar</button></td></tr>`).join('')}
      </tbody></table></div>
      <div class="jr-pager"><button type="button" class="jr-btn" data-page="-1" ${S.page === 0 ? 'disabled' : ''}>← Anterior</button><span>Página ${S.page + 1} de ${pages}</span><button type="button" class="jr-btn" data-page="1" ${S.page >= pages - 1 ? 'disabled' : ''}>Siguiente →</button></div>`
      : (S.trades.length ? '<div class="jr-empty">Ninguna operación cerrada coincide con los filtros.</div>' : emptyState())}
    </div>`;
}

/* ======================= Calendario ======================= */
function paneCalendario(){
  const base = S.calMonth || new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  const y = base.getFullYear(), m = base.getMonth();
  const monthList = S.trades.filter(t => t.status === 'closed' && t.closed && t.closed.getFullYear() === y && t.closed.getMonth() === m && matchesNonDate(t));
  const byDay = groupBy(monthList, t => t.closed.getDate());
  const first = new Date(y, m, 1), days = new Date(y, m + 1, 0).getDate();
  const lead = (first.getDay() + 6) % 7;
  const st = stats(monthList.sort((a, b) => a.closed - b.closed), capitalFor(monthKey(first)));
  let cells = '', week = [], weekNet = 0, weekN = 0;
  const flush = () => {
    while(week.length < 7) week.push('<div class="jr-cal-cell jr-cal-blank"></div>');
    cells += week.join('') + `<div class="jr-cal-cell jr-cal-week"><span>Semana</span><b class="${signCls(weekNet)}">${weekN ? sUsd(weekNet) : '—'}</b><small>${weekN} op.</small></div>`;
    week = []; weekNet = 0; weekN = 0;
  };
  for(let i = 0; i < lead; i++) week.push('<div class="jr-cal-cell jr-cal-blank"></div>');
  const maxAbs = Math.max(1, ...[...byDay.values()].map(a => Math.abs(a.reduce((s, t) => s + t.net, 0))));
  for(let d = 1; d <= days; d++){
    const arr = byDay.get(d) || [];
    const net = arr.reduce((s, t) => s + t.net, 0);
    const alpha = arr.length ? .12 + .38 * Math.min(1, Math.abs(net) / maxAbs) : 0;
    const bg = !arr.length ? '' : (net > 0.004 ? `background:rgba(74,222,128,${alpha})` : net < -0.004 ? `background:rgba(248,113,113,${alpha})` : 'background:rgba(240,178,61,.15)');
    const isToday = dayKey(new Date()) === dayKey(new Date(y, m, d));
    week.push(`<div class="jr-cal-cell ${arr.length ? 'has' : ''} ${isToday ? 'today' : ''}" style="${bg}" ${arr.length ? `data-day="${y}-${pad(m + 1)}-${pad(d)}" title="Ver las operaciones de este día"` : ''}>
      <span class="jr-cal-d">${d}</span>${arr.length ? `<b class="${signCls(net)}">${Math.abs(net) < .005 ? 'BE' : sUsd(net)}</b><small>${arr.length} op. · ${pct(arr.filter(t => t.net > .004).length / arr.length * 100, 0)}</small>` : ''}</div>`);
    weekNet += net; weekN += arr.length;
    if(week.length === 7) flush();
  }
  if(week.length) flush();
  return `
    <div class="jr-cal-head">
      <button type="button" class="jr-btn" data-cal="-1">←</button>
      <h3>${MONTHS[m][0].toUpperCase() + MONTHS[m].slice(1)} ${y}</h3>
      <button type="button" class="jr-btn" data-cal="1">→</button>
      <div class="jr-cal-sum">Neto <b class="${signCls(st.net)}">${sUsd(st.net)}</b> · ${st.n} op. · winrate ${pct(st.winrate)} · <span class="${signCls(st.ret)}">${sPct(st.ret)}</span> sobre ${usd(capitalFor(monthKey(first)), 0)}</div>
    </div>
    <div class="jr-cal">${WEEKDAYS.map(w => `<div class="jr-cal-wd">${w}</div>`).join('')}<div class="jr-cal-wd">Total</div>${cells}</div>
    <p class="jr-muted jr-xs">Toca un día para ver sus operaciones. El calendario respeta los filtros de par, lado, origen, setup y etiqueta (no el de fechas).</p>`;
}

/* ======================= Analisis ======================= */
function paneAnalisis(){
  const list = filteredClosed();
  if(!list.length) return S.trades.length ? '<div class="jr-empty jr-big">No hay operaciones cerradas con estos filtros.</div>' : emptyState();
  const tableRows = rows => `<div class="jr-table-wrap"><table class="jr-table jr-compact"><thead><tr><th></th><th>Op.</th><th>Winrate</th><th>Promedio</th><th>Neto</th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(r.k)}</td><td>${r.n}</td><td>${pct(r.wr)}</td><td class="${signCls(r.avg)}">${sUsd(r.avg)}</td><td class="${signCls(r.net)}"><b>${sUsd(r.net)}</b></td></tr>`).join('')}</tbody></table></div>`;
  const bySym = groupRows(list, t => t.symbol).sort((a, b) => b.net - a.net);
  const wd = groupRows(list, t => (t.closed.getDay() + 6) % 7);
  const wdItems = WEEKDAYS.map((w, i) => { const r = wd.find(x => x.k === i); return { label: w, value: r ? r.net : 0, tip: r ? r.n + ' op. · winrate ' + pct(r.wr) + ' · ' + sUsd(r.net) : 'sin operaciones' }; });
  const hr = groupRows(list, t => (t.opened || t.closed).getHours());
  const hrItems = Array.from({ length: 24 }, (_, h) => { const r = hr.find(x => x.k === h); return { label: pad(h), value: r ? r.net : 0, tip: r ? r.n + ' op. · ' + sUsd(r.net) : 'sin operaciones' }; });
  const levB = [[0, 5, '1-5x'], [5, 10, '6-10x'], [10, 20, '11-20x'], [20, 50, '21-50x'], [50, 1e9, '51x+']];
  const levRows = groupRows(list.filter(t => t.leverage), t => (levB.find(([a, b]) => t.leverage > a && t.leverage <= b) || [0, 0, '?'])[2]);
  const durB = [[0, 15 * 60e3, '< 15m'], [15 * 60e3, 3600e3, '15m-1h'], [3600e3, 4 * 3600e3, '1-4h'], [4 * 3600e3, DAY, '4-24h'], [DAY, 7 * DAY, '1-7d'], [7 * DAY, 1e15, '> 7d']];
  const durRows = groupRows(list.filter(t => t.dur != null), t => (durB.find(([a, b]) => t.dur >= a && t.dur < b) || [0, 0, '?'])[2]);
  const order = (rows, labels) => labels.map(l => rows.find(r => r.k === l)).filter(Boolean);
  // histograma de resultados
  const nets = list.map(t => t.net), lo = Math.min(...nets), hi = Math.max(...nets), bins = 12, w = (hi - lo) / bins || 1;
  const hist = Array.from({ length: bins }, (_, i) => ({ a: lo + w * i, b: lo + w * (i + 1), c: 0 }));
  nets.forEach(v => { hist[Math.min(bins - 1, Math.floor((v - lo) / w))].c++; });
  const histItems = hist.map(h => ({ label: shortUsd((h.a + h.b) / 2), value: h.c, tip: h.c + ' operaciones entre ' + usd(h.a) + ' y ' + usd(h.b) }));
  const roeList = list.filter(t => t.roe != null);
  return `<div class="jr-grid2">
    ${card('P&L por par', hBars(bySym.map(r => ({ label: r.k, value: r.net, tip: r.n + ' op. · winrate ' + pct(r.wr) }))), 'jr-span2')}
    ${card('P&L por día de la semana', barChart(wdItems, { h: 200 }))}
    ${card('P&L por hora de apertura', barChart(hrItems, { h: 200, maxLabels: 12 }))}
    ${card('Distribución de resultados', barChart(histItems, { h: 200, color: C.line, fmt: v => String(Math.round(v)) }))}
    ${card('ROE por operación (sobre margen)', roeList.length > 1 ? lineChart(roeList.map(t => ({ y: t.roe, label: fmtDate(t.closed) })), { h: 200, zero: true, fmt: v => v.toFixed(0) + '%', tip: p => p.y.toFixed(1) + '%' }) : '<div class="jr-empty">Faltan operaciones con margen.</div>')}
    ${card('Por apalancamiento', tableRows(order(levRows, levB.map(b => b[2]))))}
    ${card('Por duración', tableRows(order(durRows, durB.map(b => b[2]))))}
    ${card('Por setup', tableRows(groupRows(list, t => t.setup || 'Sin setup').sort((a, b) => b.net - a.net)))}
    ${card('Por emoción', tableRows(groupRows(list, t => t.emotion || 'Sin registrar').sort((a, b) => b.net - a.net)))}
    ${card('Por etiqueta', tableRows(groupRows(list.flatMap(t => t.tags.length ? t.tags.map(tag => ({ ...t, _tag: tag })) : [{ ...t, _tag: 'Sin etiqueta' }]), t => t._tag).sort((a, b) => b.net - a.net)))}
    ${card('Por calidad de ejecución', tableRows(groupRows(list, t => t.rating ? '★'.repeat(t.rating) : 'Sin calificar').sort((a, b) => b.k.length - a.k.length)))}
    ${card('Detalle por par', tableRows(bySym), 'jr-span2')}
  </div>`;
}

/* ======================= Mensual / Anual ======================= */
function paneAnual(){
  const y = S.year;
  const yearList = S.trades.filter(t => t.status === 'closed' && t.closed && t.closed.getFullYear() === y && matchesNonDate(t)).sort((a, b) => a.closed - b.closed);
  const years = uniq(S.trades.filter(t => t.closed).map(t => String(t.closed.getFullYear()))).map(Number);
  if(!years.includes(y)) years.push(y);
  years.sort();
  const rows = MONTHS.map((name, m) => {
    const arr = yearList.filter(t => t.closed.getMonth() === m);
    const mk = y + '-' + pad(m + 1), cap = capitalFor(mk), st = stats(arr, cap);
    const dayNets = Object.values(st.days);
    return { name, m, st, cap, bestDay: dayNets.length ? Math.max(...dayNets) : null, worstDay: dayNets.length ? Math.min(...dayNets) : null };
  });
  const ys = stats(yearList, capitalFor(y + '-01'));
  let cum = 0;
  const cumItems = rows.map(r => { cum += r.st.net; return { y: cum, label: MONTHS_S[r.m] }; });
  return `
    <div class="jr-cal-head"><button type="button" class="jr-btn" data-year="-1">←</button><h3>${y}</h3><button type="button" class="jr-btn" data-year="1">→</button>
      <div class="jr-cal-sum">Neto del año <b class="${signCls(ys.net)}">${sUsd(ys.net)}</b> · ${ys.n} op. · winrate ${pct(ys.winrate)} · PF ${Number.isFinite(ys.pf) ? ys.pf.toFixed(2) : '—'}</div></div>
    <div class="jr-grid2">
      ${card('P&L por mes', barChart(rows.map(r => ({ label: MONTHS_S[r.m], value: r.st.net, tip: r.st.n + ' op. · ' + sUsd(r.st.net) }))))}
      ${card('P&L acumulado del año', lineChart([{ y: 0, label: '' }].concat(cumItems), { h: 220, area: true, areaBase: 0, zero: true }))}
      ${card('Detalle mes a mes', `<div class="jr-table-wrap"><table class="jr-table"><thead><tr><th>Mes${helpBtn('Mes')}</th><th>Op.${helpBtn('Op.')}</th><th>Winrate${helpBtn('Winrate')}</th><th>Profit factor${helpBtn('Profit factor')}</th><th>Capital inicial${helpBtn('Capital inicial')}</th><th>P&L neto${helpBtn('P&L neto')}</th><th>Rentab.${helpBtn('Rentab.')}</th><th>Mejor día${helpBtn('Mejor día')}</th><th>Peor día${helpBtn('Peor día')}</th><th>Max DD${helpBtn('Max DD')}</th></tr></thead><tbody>
        ${rows.map(r => `<tr class="${r.st.n ? 'jr-row' : 'jr-dim'}" ${r.st.n ? `data-month="${r.m}"` : ''}><td>${r.name[0].toUpperCase() + r.name.slice(1)}</td><td>${r.st.n}</td><td>${pct(r.st.winrate)}</td><td>${Number.isFinite(r.st.pf) ? r.st.pf.toFixed(2) : '—'}</td><td>${usd(r.cap, 0)}</td>
          <td class="${signCls(r.st.net)}"><b>${r.st.n ? sUsd(r.st.net) : '—'}</b></td><td class="${signCls(r.st.ret)}">${r.st.n ? sPct(r.st.ret) : '—'}</td>
          <td class="jr-pos">${r.bestDay != null ? sUsd(r.bestDay) : '—'}</td><td class="jr-neg">${r.worstDay != null ? sUsd(r.worstDay) : '—'}</td><td class="jr-neg">${r.st.n ? usd(-r.st.maxDD) : '—'}</td></tr>`).join('')}
      </tbody></table></div><p class="jr-muted jr-xs">Toca un mes para abrirlo en el calendario.</p>`, 'jr-span2')}
    </div>`;
}

/* ======================= Conexion y ajustes ======================= */
function paneAjustes(){
  const sy = S.sync;
  const connected = sy && sy.status !== 'disconnected';
  const months = Object.keys(S.capitalByMonth).sort().reverse();
  return `<div class="jr-grid2">
    ${card('Conexión automática con Bitunix', `
      ${connected ? `
        <div class="jr-conn ${sy.status}">
          <div><span class="jr-sync-dot ${sy.status === 'connected' ? 'on' : 'err'}"></span><b>${sy.status === 'connected' ? 'Conectada' : 'Con error'}</b> · clave ${esc(sy.api_key_hint || '')}</div>
          <div class="jr-muted">Última sincronización: ${sy.last_sync_at ? fmtDateTime(new Date(sy.last_sync_at)) : 'nunca'} · ${sy.trades_synced || 0} operaciones de Bitunix</div>
          ${sy.last_error ? `<div class="jr-neg jr-xs">${esc(sy.last_error)}</div>` : ''}
        </div>
        <div class="jr-row-btns"><button type="button" class="jr-btn jr-btn-primary" data-act="sync" ${S.syncing ? 'disabled' : ''}>${S.syncing ? 'Sincronizando…' : '↻ Sincronizar ahora'}</button><button type="button" class="jr-btn" data-act="disconnect">Desconectar</button></div>
        <p class="jr-muted jr-xs">Se sincroniza sola cada vez que abres la bitácora (si pasaron más de 15 minutos).</p>`
      : `
        <p class="jr-muted">Conecta una <b>API key de solo lectura</b> de tu cuenta de futuros de Bitunix y tus operaciones se cargan solas: entrada, salida, apalancamiento, P&L, comisiones y funding.</p>
        <ol class="jr-steps">
          <li>En Bitunix: <b>Perfil → API Management → Create API</b>.</li>
          <li>Dale <b>solo permiso de lectura</b> (Read). <b>Nunca</b> actives trading ni retiros.</li>
          <li>Copia la API key y el Secret y pégalos aquí.</li>
        </ol>
        <form id="jrConnectForm" class="jr-form-grid">
          <label class="jr-span2">API key<input type="text" id="jrApiKey" autocomplete="off" spellcheck="false" required></label>
          <label class="jr-span2">Secret<input type="password" id="jrApiSecret" autocomplete="off" required></label>
          <div class="jr-span2 jr-row-btns"><button type="submit" class="jr-btn jr-btn-primary" ${S.syncing ? 'disabled' : ''}>${S.syncing ? 'Conectando…' : 'Conectar y sincronizar'}</button><span class="jr-msg" id="jrConnectMsg"></span></div>
        </form>
        <p class="jr-muted jr-xs">La clave se guarda cifrada en el servidor: ni esta página ni nadie más la puede volver a leer. Puedes desconectarla cuando quieras.</p>`}
      <div class="jr-msg" id="jrSyncMsg"></div>`)}
    ${card('Capital', S.exchangeConnected ? `
      <p class="jr-muted">Tu saldo inicial de cada mes se detecta solo desde tu cuenta de Bitunix conectada - no hay que escribirlo a mano.</p>
      ${months.length ? `<table class="jr-table jr-compact" style="margin-top:12px"><tbody>${months.map(mk => `<tr><td>${MONTHS[Number(mk.slice(5)) - 1]} ${mk.slice(0, 4)}</td><td>${usd(S.capitalByMonth[mk])}</td></tr>`).join('')}</tbody></table>` : `<p class="jr-muted jr-xs">Todavía no se ha registrado - se guarda solo en la próxima sincronización.</p>`}`
    : `
      <p class="jr-muted">Se usa para calcular la rentabilidad % y el drawdown %. Puedes poner un capital distinto para cada mes (por ejemplo si depositas o retiras).</p>
      <form id="jrCapForm" class="jr-form-grid">
        <label class="jr-span2">Capital inicial por defecto (USD)<input type="number" id="jrDefCap" min="1" step="0.01" value="${S.settings.default_capital}"></label>
        <div class="jr-span2 jr-row-btns"><button type="submit" class="jr-btn jr-btn-primary">Guardar</button><span class="jr-msg" id="jrCapMsg"></span></div>
      </form>
      <form id="jrMonthCapForm" class="jr-form-grid" style="margin-top:14px">
        <label>Mes<input type="month" id="jrCapMonth" value="${monthKey(new Date())}" required></label>
        <label>Capital inicial (USD)<input type="number" id="jrCapMonthVal" min="1" step="0.01" required></label>
        <div class="jr-span2 jr-row-btns"><button type="submit" class="jr-btn">Guardar capital del mes</button></div>
      </form>
      ${months.length ? `<table class="jr-table jr-compact" style="margin-top:12px"><tbody>${months.map(mk => `<tr><td>${MONTHS[Number(mk.slice(5)) - 1]} ${mk.slice(0, 4)}</td><td>${usd(S.capitalByMonth[mk])}</td><td><button type="button" class="jr-link" data-delcap="${mk}">Quitar</button></td></tr>`).join('')}</tbody></table>` : ''}`)}
  </div>`;
}

/* ======================= formulario de operacion ======================= */
function openTradeForm(trade, opts = {}){
  const t = trade || null, raw = t ? t.raw : {};
  const auto = t && t.source === 'bitunix';
  const symbols = uniq(S.trades.map(x => x.symbol)), setups = uniq(S.trades.map(x => x.setup));
  const ov = document.createElement('div');
  ov.className = 'jr-modal';
  ov.innerHTML = `<form class="jr-modal-panel" id="jrTradeForm">
    <div class="jr-modal-head"><h3>${t ? (auto ? 'Operación de Bitunix' : 'Editar operación') : 'Nueva operación'}</h3><button type="button" class="jr-x" data-close>✕</button></div>
    ${auto ? '<p class="jr-muted jr-xs">Los datos de precio y resultado vienen de Bitunix y no se editan. Puedes agregar setup, etiquetas, emoción, calificación y notas.</p>' : ''}
    <div class="jr-form-grid">
      <label>Par<input name="symbol" list="jrSymList" required value="${esc(raw.symbol || '')}" placeholder="BTCUSDT" ${auto ? 'disabled' : ''}></label>
      <label>Lado<select name="side" ${auto ? 'disabled' : ''}><option value="long" ${raw.side !== 'short' ? 'selected' : ''}>Long</option><option value="short" ${raw.side === 'short' ? 'selected' : ''}>Short</option></select></label>
      <label>Estado<select name="status" ${auto ? 'disabled' : ''}><option value="closed" ${raw.status !== 'open' && !opts.open ? 'selected' : ''}>Cerrada</option><option value="open" ${raw.status === 'open' || opts.open ? 'selected' : ''}>Abierta</option></select></label>
      <label>Apalancamiento (x)<input name="leverage" type="number" step="any" min="1" max="500" value="${raw.leverage ?? ''}" ${auto ? 'disabled' : ''}></label>
      <label>Margen (USD)<input name="margin" type="number" step="any" min="0" value="${raw.margin ?? ''}" ${auto ? 'disabled' : ''}></label>
      <label>Cantidad (opcional)<input name="qty" type="number" step="any" min="0" value="${raw.qty ?? ''}" ${auto ? 'disabled' : ''}></label>
      <label>Precio de entrada<input name="entry_price" type="number" step="any" min="0" value="${raw.entry_price ?? ''}" ${auto ? 'disabled' : ''}></label>
      <label>Precio de salida<input name="exit_price" type="number" step="any" min="0" value="${raw.exit_price ?? ''}" ${auto ? 'disabled' : ''}></label>
      <label>Stop loss<input name="stop_loss" type="number" step="any" value="${raw.stop_loss ?? ''}" ${auto ? 'disabled' : ''}></label>
      <label>Take profit<input name="take_profit" type="number" step="any" value="${raw.take_profit ?? ''}" ${auto ? 'disabled' : ''}></label>
      <label>P&L bruto (USD) ${auto ? '' : '<button type="button" class="jr-link" data-calc>Calcular</button>'}<input name="pnl" type="number" step="any" value="${raw.pnl ?? ''}" ${auto ? 'disabled' : ''}></label>
      <label>Comisiones (USD)<input name="fees" type="number" step="any" min="0" value="${raw.fees ?? 0}" ${auto ? 'disabled' : ''}></label>
      <label>Funding (USD, + cobrado / - pagado)<input name="funding" type="number" step="any" value="${raw.funding ?? 0}" ${auto ? 'disabled' : ''}></label>
      <label>Apertura<input name="opened_at" type="datetime-local" required value="${toLocalInput(t ? t.opened : new Date())}" ${auto ? 'disabled' : ''}></label>
      <label>Cierre<input name="closed_at" type="datetime-local" value="${toLocalInput(t ? t.closed : (opts.open ? null : new Date()))}" ${auto ? 'disabled' : ''}></label>
      <label>Setup / estrategia<input name="setup" list="jrSetupList" maxlength="60" value="${esc(raw.setup || '')}" placeholder="Ej. Ruptura de rango"></label>
      <label>Etiquetas (separadas por coma)<input name="tags" value="${esc((raw.tags || []).join(', '))}" placeholder="scalp, noticia, tendencia"></label>
      <label>Emoción<select name="emotion"><option value="">—</option>${EMOTIONS.map(e => `<option ${raw.emotion === e ? 'selected' : ''}>${e}</option>`).join('')}</select></label>
      <label>Calificación de la ejecución<span class="jr-rate">${[1,2,3,4,5].map(n => `<button type="button" data-rate="${n}" class="${raw.rating >= n ? 'on' : ''}">★</button>`).join('')}</span><input type="hidden" name="rating" value="${raw.rating || ''}"></label>
      <label class="jr-span3">Notas<textarea name="notes" rows="3" maxlength="2000" placeholder="¿Por qué entraste? ¿Qué salió bien o mal?">${esc(raw.notes || '')}</textarea></label>
    </div>
    <div class="jr-net-preview" id="jrNetPreview"></div>
    <div class="jr-modal-foot">
      ${t ? '<button type="button" class="jr-btn jr-danger" data-del>Borrar</button>' : ''}
      <span class="jr-msg" id="jrFormMsg"></span>
      <button type="button" class="jr-btn" data-close>Cancelar</button>
      <button type="submit" class="jr-btn jr-btn-primary">Guardar</button>
    </div>
    <datalist id="jrSymList">${symbols.map(s => `<option value="${esc(s)}">`).join('')}</datalist>
    <datalist id="jrSetupList">${setups.map(s => `<option value="${esc(s)}">`).join('')}</datalist>
  </form>`;
  document.body.appendChild(ov);
  const form = ov.querySelector('form');
  const val = n => form.elements[n].value;
  const numOrNull = n => val(n) === '' ? null : Number(val(n));
  const preview = () => {
    const net = (numOrNull('pnl') || 0) - (numOrNull('fees') || 0) + (numOrNull('funding') || 0);
    const m = numOrNull('margin');
    ov.querySelector('#jrNetPreview').innerHTML = val('status') === 'open' ? 'Posición abierta: el resultado se cuenta cuando la cierres.'
      : `Resultado neto: <b class="${signCls(net)}">${sUsd(net)}</b>${m ? ` · ROE <b class="${signCls(net)}">${sPct(net / m * 100)}</b>` : ''}`;
  };
  form.addEventListener('input', preview); preview();
  const close = () => ov.remove();
  ov.addEventListener('click', async e => {
    if(e.target === ov || e.target.closest('[data-close]')) return close();
    const rate = e.target.closest('[data-rate]');
    if(rate){
      const n = Number(rate.dataset.rate);
      form.elements.rating.value = form.elements.rating.value == n ? '' : n;
      ov.querySelectorAll('[data-rate]').forEach(b => b.classList.toggle('on', Number(b.dataset.rate) <= Number(form.elements.rating.value || 0)));
      return;
    }
    if(e.target.closest('[data-calc]')){
      const en = numOrNull('entry_price'), ex = numOrNull('exit_price'), m = numOrNull('margin'), lev = numOrNull('leverage') || 1, q = numOrNull('qty');
      if(!en || !ex || (!m && !q)){ ov.querySelector('#jrFormMsg').textContent = 'Para calcular: entrada, salida y margen (o cantidad).'; return; }
      const dirN = val('side') === 'short' ? -1 : 1;
      const p = q ? (ex - en) * q * dirN : m * lev * (ex - en) / en * dirN;
      form.elements.pnl.value = Math.round(p * 100) / 100; preview();
      return;
    }
    if(e.target.closest('[data-del]')){
      if(!confirm('¿Borrar esta operación de la bitácora?' + (auto ? ' (Si sigue en tu historial de Bitunix, volverá en la próxima sincronización.)' : ''))) return;
      const { error } = await sbClient.from('trade_journal_trades').delete().eq('id', t.id);
      if(error){ ov.querySelector('#jrFormMsg').textContent = error.message; return; }
      close(); await reload();
    }
  });
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const msg = ov.querySelector('#jrFormMsg');
    const journalFields = {
      setup: val('setup').trim() || null,
      tags: val('tags').split(',').map(s => s.trim()).filter(Boolean).slice(0, 12),
      emotion: val('emotion') || null,
      rating: form.elements.rating.value ? Number(form.elements.rating.value) : null,
      notes: val('notes').trim() || null,
    };
    let payload = journalFields;
    if(!auto){
      const status = val('status');
      const opened = val('opened_at') ? new Date(val('opened_at')) : null;
      const closed = status === 'closed' ? (val('closed_at') ? new Date(val('closed_at')) : new Date()) : null;
      if(!val('symbol').trim()){ msg.textContent = 'Falta el par.'; return; }
      if(closed && opened && closed < opened){ msg.textContent = 'El cierre no puede ser antes de la apertura.'; return; }
      payload = {
        ...journalFields,
        symbol: val('symbol').trim().toUpperCase().replace(/[^A-Z0-9/._-]/g, ''), side: val('side'), status,
        leverage: numOrNull('leverage'), margin: numOrNull('margin'), qty: numOrNull('qty'),
        entry_price: numOrNull('entry_price'), exit_price: status === 'closed' ? numOrNull('exit_price') : null,
        stop_loss: numOrNull('stop_loss'), take_profit: numOrNull('take_profit'),
        pnl: status === 'closed' ? (numOrNull('pnl') || 0) : null, fees: numOrNull('fees') || 0, funding: numOrNull('funding') || 0,
        opened_at: (opened || new Date()).toISOString(), closed_at: closed ? closed.toISOString() : null,
      };
    }
    msg.textContent = 'Guardando…';
    const { error } = t
      ? await sbClient.from('trade_journal_trades').update(payload).eq('id', t.id)
      : await sbClient.from('trade_journal_trades').insert({ ...payload, user_id: currentUser.id, source: 'manual' });
    if(error){ msg.textContent = typeof friendlyErrMsg === 'function' ? friendlyErrMsg(error) : error.message; return; }
    close(); await reload();
  });
  setTimeout(() => { const first = form.querySelector('input:not([disabled])'); if(first) first.focus(); }, 30);
}

/* ======================= acciones ======================= */
async function reload(){ await loadAll(); renderShell(); }
function setSyncMsg(text, cls){ const el = $('jrSyncMsg') || $('jrConnectMsg'); if(el){ el.textContent = text; el.className = 'jr-msg ' + (cls || ''); } }
async function callSync(action, extra){
  S.syncing = true; renderShell();
  const { data, error } = await sbClient.functions.invoke('trade-journal-sync', { body: { action, ...(extra || {}) } });
  S.syncing = false;
  let errMsg = error ? (error.message || 'Error') : (data && data.error);
  if(error && error.context && typeof error.context.json === 'function'){
    try{ const b = await error.context.json(); if(b && b.error) errMsg = b.error; }catch(e){}
  }
  await reload();
  if(errMsg) setSyncMsg(/Failed to send|not found|FunctionsFetchError|FunctionsRelayError/i.test(errMsg) ? 'La función de sincronización todavía no está desplegada en Supabase (trade-journal-sync).' : errMsg, 'jr-neg');
  else if(action !== 'disconnect') setSyncMsg('Listo: ' + (data.imported || 0) + ' posiciones leídas de Bitunix.', 'jr-pos');
  return !errMsg;
}
function exportCsv(){
  const list = filteredClosed().concat(openTrades());
  const head = ['estado','apertura','cierre','par','lado','apalancamiento','margen','cantidad','entrada','salida','stop_loss','take_profit','pnl_bruto','comisiones','funding','pnl_neto','roe_pct','duracion_min','setup','etiquetas','emocion','calificacion','origen','notas'];
  const q = v => { const s = v == null ? '' : String(v); return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
  const lines = [head.join(',')].concat(list.map(t => [t.status, t.opened && t.opened.toISOString(), t.closed && t.closed.toISOString(), t.symbol, t.side, t.leverage, t.margin, t.qty, t.entry, t.exit, t.sl, t.tp, t.pnl, t.fees, t.funding, t.status === 'closed' ? t.net.toFixed(2) : '', t.roe != null ? t.roe.toFixed(2) : '', t.dur != null ? Math.round(t.dur / 60000) : '', t.setup, t.tags.join('|'), t.emotion, t.rating, t.source, t.notes].map(q).join(',')));
  const a = document.createElement('a');
  a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent('﻿' + lines.join('\n'));
  a.download = 'bitacora-skillcash-' + dayKey(new Date()) + '.csv';
  a.click();
}

function bindEvents(){
  const r = root();
  if(!r || r.dataset.bound) return;
  r.dataset.bound = '1';
  r.addEventListener('click', async e => {
    const el = e.target.closest('button, [data-edit], [data-day], [data-month], th[data-sort]');
    if(!el) return;
    if(el.classList.contains('jr-help')){ toggleHelp(el); return; }
    if(el.dataset.preset){ S.f.preset = el.dataset.preset; if(el.dataset.preset === 'custom' && !S.f.from){ S.f.from = new Date(new Date().getFullYear(), new Date().getMonth(), 1); S.f.to = null; } S.page = 0; return renderShell(); }
    if(el.dataset.tab){ S.tab = el.dataset.tab; return renderShell(); }
    if(el.dataset.sort){ S.sort = { key: el.dataset.sort, dir: S.sort.key === el.dataset.sort ? -S.sort.dir : -1 }; return renderPane(); }
    if(el.dataset.page){ S.page += Number(el.dataset.page); return renderPane(); }
    if(el.dataset.cal){ const b = S.calMonth || new Date(new Date().getFullYear(), new Date().getMonth(), 1); S.calMonth = new Date(b.getFullYear(), b.getMonth() + Number(el.dataset.cal), 1); return renderPane(); }
    if(el.dataset.year){ S.year += Number(el.dataset.year); return renderPane(); }
    if(el.dataset.month != null && el.dataset.month !== undefined && el.tagName === 'TR'){ S.calMonth = new Date(S.year, Number(el.dataset.month), 1); S.tab = 'calendario'; return renderShell(); }
    if(el.dataset.day){ const [y, m, d] = el.dataset.day.split('-').map(Number); S.f.preset = 'custom'; S.f.from = new Date(y, m - 1, d); S.f.to = new Date(y, m - 1, d + 1); S.tab = 'operaciones'; S.page = 0; return renderShell(); }
    if(el.dataset.close){ const t = S.trades.find(x => x.id === el.dataset.close); if(t){ openTradeForm(t); setTimeout(() => { const f = $('jrTradeForm'); if(f){ f.elements.status.value = 'closed'; f.elements.closed_at.value = toLocalInput(new Date()); f.elements.exit_price.focus(); f.dispatchEvent(new Event('input')); } }, 40); } return; }
    if(el.dataset.edit){ const t = S.trades.find(x => x.id === el.dataset.edit); if(t) openTradeForm(t); return; }
    if(el.dataset.delcap){ await sbClient.from('trade_journal_capital').delete().eq('user_id', currentUser.id).eq('month', el.dataset.delcap); return reload(); }
    const act = el.dataset.act;
    if(act === 'new') return openTradeForm(null);
    if(act === 'csv') return exportCsv();
    if(act === 'clear'){ S.f = { preset: S.f.preset, from: S.f.from, to: S.f.to, symbols: [], side: 'all', result: 'all', source: 'all', tag: 'all', setup: 'all', q: '' }; return renderShell(); }
    if(act === 'ms'){ const pop = el.parentElement.querySelector('.jr-ms-pop'); pop.style.display = pop.style.display === 'none' ? 'block' : 'none'; return; }
    if(act === 'sync') return callSync('sync');
    if(act === 'disconnect'){ if(confirm('¿Desconectar Bitunix? Las operaciones ya importadas se quedan en tu bitácora.')) return callSync('disconnect'); }
  });
  r.addEventListener('change', e => {
    const el = e.target;
    if(el.dataset.f){ S.f[el.dataset.f] = el.value; S.page = 0; return renderShell(); }
    if(el.closest('#jrSymbolMs')){ S.f.symbols = [...r.querySelectorAll('#jrSymbolMs input:checked')].map(i => i.value); S.page = 0; renderPane(); r.querySelector('#jrSymbolMs .jr-select').textContent = (S.f.symbols.length ? S.f.symbols.length + ' par' + (S.f.symbols.length > 1 ? 'es' : '') : 'Todos los pares') + ' ▾'; return; }
    if(el.id === 'jrFrom' && el.value){ const [y, m, d] = el.value.split('-').map(Number); S.f.from = new Date(y, m - 1, d); return renderPane(); }
    if(el.id === 'jrTo' && el.value){ const [y, m, d] = el.value.split('-').map(Number); S.f.to = new Date(y, m - 1, d + 1); return renderPane(); }
  });
  let qTimer;
  r.addEventListener('input', e => {
    if(e.target.id !== 'jrSearch') return;
    clearTimeout(qTimer);
    qTimer = setTimeout(() => { S.f.q = e.target.value.trim(); S.page = 0; renderPane(); }, 250);
  });
  r.addEventListener('submit', async e => {
    e.preventDefault();
    if(e.target.id === 'jrConnectForm'){
      const ok = await callSync('connect', { apiKey: $('jrApiKey').value, apiSecret: $('jrApiSecret').value });
      if(ok){ S.tab = 'resumen'; renderShell(); }
    }
    if(e.target.id === 'jrCapForm'){
      const v = Number($('jrDefCap').value);
      if(!(v > 0)) return;
      const { error } = await sbClient.from('trade_journal_settings').upsert({ user_id: currentUser.id, default_capital: v, updated_at: new Date().toISOString() });
      if(error){ $('jrCapMsg').textContent = error.message; return; }
      await reload();
    }
    if(e.target.id === 'jrMonthCapForm'){
      const mk = $('jrCapMonth').value, v = Number($('jrCapMonthVal').value);
      if(!mk || !(v > 0)) return;
      const { error } = await sbClient.from('trade_journal_capital').upsert({ user_id: currentUser.id, month: mk, starting_capital: v });
      if(error){ alert(error.message); return; }
      await reload();
    }
  });
  document.addEventListener('click', e => {
    const ms = $('jrSymbolMs');
    if(ms && !ms.contains(e.target)){ const pop = ms.querySelector('.jr-ms-pop'); if(pop) pop.style.display = 'none'; }
    const hp = document.getElementById('jrHelpPop');
    if(hp && !hp.contains(e.target) && !e.target.closest('.jr-help')) hp.remove();
  });
}
// bolita "?": popover flotante con el texto de ayuda, se abre/cierra al tocarla, se cierra al
// tocar afuera (mismo patron que el popover de pares de arriba) - funciona igual en touch y mouse.
function toggleHelp(btn){
  const existing = document.getElementById('jrHelpPop');
  if(existing){
    const wasFor = existing.dataset.for;
    existing.remove();
    if(wasFor === btn.dataset.help) return;
  }
  const pop = document.createElement('div');
  pop.id = 'jrHelpPop';
  pop.className = 'jr-help-pop';
  pop.dataset.for = btn.dataset.help;
  pop.textContent = btn.dataset.help;
  document.body.appendChild(pop);
  const r = btn.getBoundingClientRect();
  const pw = Math.min(240, window.innerWidth - 20);
  pop.style.width = pw + 'px';
  let left = r.left + r.width / 2 - pw / 2;
  left = Math.max(10, Math.min(left, window.innerWidth - pw - 10));
  pop.style.left = left + 'px';
  const ph = pop.offsetHeight;
  const spaceBelow = window.innerHeight - r.bottom;
  pop.style.top = (spaceBelow > ph + 16 ? r.bottom + 8 : r.top - ph - 8) + 'px';
}

/* ======================= abrir / cerrar la vista ======================= */
const view = () => $('journalPageView');
window.openJournalPage = async function(){
  if(!currentUser){ if(typeof openAuthModal === 'function') openAuthModal(); return; }
  if(typeof closeAnyOpenToolInline === 'function') closeAnyOpenToolInline();
  if(typeof closeAdminPage === 'function') closeAdminPage();
  if(typeof hideColmillosPage === 'function' && typeof colmillosPageView !== 'undefined' && colmillosPageView.style.display === 'block') hideColmillosPage();
  ['categoryOverviewGrid', 'categoryDetailView', 'marketDashboardBlock', 'favoritesSection'].forEach(id => { const el = $(id); if(el) el.style.display = 'none'; });
  document.querySelectorAll('.hero-mascot, .crypto-ticker').forEach(el => { el.style.display = 'none'; });
  view().style.display = 'block';
  if(typeof setPageTitle === 'function') setPageTitle('Bitácora de trading');
  if(typeof pushRoute === 'function' && typeof closingFromPopstate !== 'undefined' && !closingFromPopstate && location.pathname !== '/bitacora'){
    pushRoute({ skillcashDepth: 'category' }, '/bitacora');
  }
  window.scrollTo({ top: 0 });
  bindEvents();
  S.loaded = false; renderShell();
  await loadAll(); renderShell();
  // sincronizacion automatica si hay cuenta conectada y pasaron mas de 15 minutos
  if(S.sync && S.sync.status === 'connected' && (!S.sync.last_sync_at || Date.now() - new Date(S.sync.last_sync_at) > 15 * 60000)) callSync('sync');
};
// la cierra sin tocar lo demas: quien la llama (Volver, showCategoryOverview, abrir otra
// categoria, Sharkoins...) se encarga de mostrar lo que corresponda
window.closeJournalPage = function(){
  const v = view();
  if(!v || v.style.display === 'none') return false;
  v.style.display = 'none';
  document.querySelectorAll('.jr-modal').forEach(m => m.remove());
  return true;
};
/* la Bitacora es una herramienta de Rango de Manada: se abre desde su tarjeta dentro de esa
   seccion y desde el menu lateral. Mientras Rango de Manada este en construccion
   (WIP_OWNER_ONLY_CATEGORIES), solo el dueño la puede abrir */
document.querySelectorAll('[data-open-journal]').forEach(btn => btn.addEventListener('click', () => {
  if(typeof isWipLockedForCurrentUser === 'function' && isWipLockedForCurrentUser('rangos')){
    if(typeof showWipToast === 'function') showWipToast('🔒 Todavía estamos construyendo esto — vuelve pronto.');
    return;
  }
  document.getElementById('sidebar').classList.remove('mobile-open');
  const bd = document.getElementById('sbBackdrop'); if(bd) bd.classList.remove('show');
  window.openJournalPage();
}));
// igual que adminBackBtn (assets/js/admin.js): si openJournalPage() de verdad empujo /bitacora
// al historial (se entro desde adentro del sitio), "Volver" hace history.back() - un solo paso
// atras, a donde sea que la persona estuviera antes (no siempre "Rango de Manada"). Si no hay
// esa entrada (ej. se abrio /bitacora por URL directa), se cae al comportamiento de siempre.
const backBtn = $('journalBackBtn');
if(backBtn) backBtn.addEventListener('click', () => {
  if(history.state && history.state.skillcashDepth === 'category' && location.pathname === '/bitacora'){
    history.back();
  } else {
    window.closeJournalPage();
    if(typeof showCategoryDetail === 'function') showCategoryDetail('rangos');
    else if(typeof showCategoryOverview === 'function') showCategoryOverview();
  }
});
// si se cierra sesion con la bitacora abierta, se vuelve al inicio
sbClient.auth.onAuthStateChange((event, session) => {
  if(!session && view() && view().style.display === 'block'){ window.closeJournalPage(); if(typeof showCategoryOverview === 'function') showCategoryOverview(); }
});
})();
