/* Panel de administrador (solo Juan) - pagina propia (/administrador), no modal. Reemplaza al
   viejo modal basico: filtros, tabla completa (UID del exchange, estado de conexion, fechas) y
   graficos de tendencia, mismo lenguaje visual que la Bitacora (clases .jr-*, ya definidas en
   el <style> de index.html). La proteccion real vive en el servidor (scripts/sql/
   create_admin_dashboard.sql + admin_dashboard_v2.sql, SECURITY DEFINER que revisa
   auth.uid() = OWNER_USER_ID) - lo de aca es solo para no mostrarle la pagina a nadie mas. */
(function(){
if(typeof sbClient === 'undefined') return;

const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
const usd = (v, d = 0) => '$' + Number(v || 0).toLocaleString('es-CO', { maximumFractionDigits: d });
const DAY = 86400000;
const MONTHS_S = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
const pad = n => String(n).padStart(2, '0');
const fmtDate = d => d ? d.getDate() + ' ' + MONTHS_S[d.getMonth()] + ' ' + String(d.getFullYear()).slice(2) : '—';
const fmtDateTime = d => d ? fmtDate(d) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) : '—';

const RANK_LABELS = { sin_rango: 'Sin rango', cria: 'Cría', explorador: 'Explorador', cazador: 'Cazador', depredador: 'Depredador', alfa: 'Alfa' };
const STATUS_LABELS = { connected: '✅ Conectado', pending: '⏳ Pendiente', rejected: '🔴 Rechazado', none: '— Sin conectar' };
const OWNER_ID = 'e4309251-6078-4233-aab3-6ab8d6c624e1';

/* ======================= graficos (copia compacta de los de journal.js, su propio namespace) */
const C = { pos: '#4ade80', neg: '#f87171', line: '#5b8def', grid: 'rgba(255,255,255,.07)', txt: '#8b8f9a' };
function niceTicks(min, max, count = 4){
  if(min === max){ min -= 1; max += 1; }
  const span = max - min, step0 = span / count, mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= step0) || step0;
  const lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step;
  const out = []; for(let v = lo; v <= hi + step / 2; v += step) out.push(+v.toFixed(10));
  return out;
}
function barChartSvg(items, opt = {}){
  const W = opt.W || 900, H = opt.h || 200, L = 40, R = 10, T = 12, B = 28;
  if(!items.length) return '<div class="jr-empty">Sin datos.</div>';
  const vals = items.map(i => i.value);
  const ticks = niceTicks(Math.min(0, ...vals), Math.max(0, ...vals));
  const yMin = ticks[0], yMax = ticks[ticks.length - 1];
  const Y = v => T + (H - T - B) * (1 - (v - yMin) / ((yMax - yMin) || 1));
  const fmt = opt.fmt || (v => String(Math.round(v)));
  const slot = (W - L - R) / items.length, bw = Math.max(2, Math.min(28, slot * .7));
  let g = ticks.map(v => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="${v === 0 ? 'rgba(255,255,255,.18)' : C.grid}"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" fill="${C.txt}" font-size="10">${fmt(v)}</text>`).join('');
  const step = Math.max(1, Math.ceil(items.length / Math.min(opt.maxLabels || 10, Math.max(2, Math.floor(W / 55)))));
  items.forEach((it, i) => {
    const x = L + slot * i + (slot - bw) / 2, y0 = Y(0), y1 = Y(it.value);
    const color = opt.color || C.line;
    g += `<rect x="${x}" y="${Math.min(y0, y1)}" width="${bw}" height="${Math.max(1, Math.abs(y1 - y0))}" rx="3" fill="${color}" opacity=".85"><title>${esc(it.label)} · ${esc(it.tip || fmt(it.value))}</title></rect>`;
    if(i % step === 0) g += `<text x="${x + bw / 2}" y="${H - 10}" text-anchor="middle" fill="${C.txt}" font-size="10">${esc(it.label)}</text>`;
  });
  return `<svg class="jr-svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${g}</svg>`;
}
let ADMIN_CHART_SPECS = [];
function chartSlot(data, opt){
  ADMIN_CHART_SPECS.push({ data, opt });
  return `<div class="jr-chart admin-chart" data-achart="${ADMIN_CHART_SPECS.length - 1}" style="height:${(opt && opt.h) || 200}px"></div>`;
}
const barChart = (items, opt = {}) => chartSlot(items, opt);
function drawAdminCharts(){
  document.querySelectorAll('#adminRoot .admin-chart').forEach(el => {
    const spec = ADMIN_CHART_SPECS[Number(el.dataset.achart)];
    if(!spec) return;
    const W = Math.max(240, Math.round(el.clientWidth));
    el.innerHTML = barChartSvg(spec.data, { ...spec.opt, W });
  });
}
let adminChartResizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(adminChartResizeTimer);
  adminChartResizeTimer = setTimeout(() => { if(root() && root().style.display !== 'none') drawAdminCharts(); }, 150);
});
function donut(parts){
  const total = parts.reduce((s, p) => s + p.value, 0);
  if(!total) return '<div class="jr-empty">Sin datos.</div>';
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

/* ======================= estado ======================= */
const S = {
  loaded: false, error: null,
  users: [], summary: null, timeseries: [],
  tab: 'resumen',
  f: { preset: '30d', from: null, to: null, status: 'all', telegram: 'all', q: '' },
  sort: { key: 'signup', dir: -1 }, page: 0,
};
const PRESETS = [['7d', '7 días'], ['30d', '30 días'], ['90d', '90 días'], ['year', 'Este año'], ['all', 'Todo']];
function presetRange(p){
  const now = new Date(), today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  switch(p){
    case '7d': return [new Date(today - 6 * DAY), null];
    case '30d': return [new Date(today - 29 * DAY), null];
    case '90d': return [new Date(today - 89 * DAY), null];
    case 'year': return [new Date(now.getFullYear(), 0, 1), null];
    case 'all': return [null, null];
    default: return [null, null];
  }
}

function normalize(r){
  return {
    ...r,
    signup: r.signup_at ? new Date(r.signup_at) : null,
    connReviewed: r.connection_reviewed_at ? new Date(r.connection_reviewed_at) : null,
    connRequested: r.connection_requested_at ? new Date(r.connection_requested_at) : null,
    telegramLinked: r.telegram_linked_at ? new Date(r.telegram_linked_at) : null,
  };
}

async function loadAll(){
  try{
    const [usersRes, summaryRes, tsRes] = await Promise.all([
      sbClient.rpc('get_admin_dashboard_users'),
      sbClient.rpc('get_admin_summary_stats'),
      sbClient.rpc('get_admin_dashboard_timeseries', { p_days: 30 }),
    ]);
    if(usersRes.error || summaryRes.error) throw (usersRes.error || summaryRes.error);
    S.users = (usersRes.data || []).map(normalize);
    S.summary = summaryRes.data;
    S.timeseries = tsRes.error ? [] : (tsRes.data || []);
    S.error = null;
  }catch(err){
    S.error = err;
  }
  S.loaded = true;
}

function filtered(){
  const [from] = presetRange(S.f.preset);
  return S.users.filter(u => {
    if(from && u.signup && u.signup < from) return false;
    const st = u.connection_status || 'none';
    if(S.f.status !== 'all' && S.f.status !== st) return false;
    if(S.f.telegram === 'yes' && !u.telegram_connected) return false;
    if(S.f.telegram === 'no' && u.telegram_connected) return false;
    if(S.f.q){
      const q = S.f.q.toLowerCase();
      if(!(u.username || '').toLowerCase().includes(q) && !(u.exchange_uid || '').toLowerCase().includes(q)) return false;
    }
    return true;
  });
}

/* ======================= UI base ======================= */
const root = () => $('adminRoot');
function kpi(label, value, sub){
  return `<div class="jr-kpi"><div class="jr-kpi-label">${esc(label)}</div><div class="jr-kpi-val">${value}</div>${sub ? `<div class="jr-kpi-sub">${esc(sub)}</div>` : ''}</div>`;
}
function card(title, body, extra){
  return `<div class="jr-card ${extra || ''}"><div class="jr-card-title">${esc(title)}</div>${body}</div>`;
}
const TABS = [['resumen', 'Resumen'], ['usuarios', 'Usuarios']];

function renderShell(){
  const r = root();
  if(!r) return;
  if(!S.loaded){ r.innerHTML = '<div class="jr-loading">Cargando el panel…</div>'; return; }
  if(S.error){
    r.innerHTML = `<div class="jr-head"><div><div class="section-eyebrow" style="margin-top:0">Solo tú puedes ver esto</div><h2 class="jr-title">Panel de admin</h2></div></div>
      <div class="jr-empty jr-big">No se pudo cargar el panel (${esc(S.error.message || S.error)}). Si es la primera vez, falta correr <b>scripts/sql/admin_dashboard_v2.sql</b> en Supabase.</div>`;
    return;
  }
  const f = S.f;
  r.innerHTML = `
    <div class="jr-head">
      <div>
        <div class="section-eyebrow" style="margin-top:0">Solo tú puedes ver esto</div>
        <h2 class="jr-title">📊 Panel de admin</h2>
      </div>
      <div class="jr-head-actions"><button type="button" class="jr-btn" data-act="refresh">↻ Actualizar</button></div>
    </div>
    <div class="jr-filters">
      <div class="jr-presets">${PRESETS.map(([k, l]) => `<button type="button" class="jr-chip ${f.preset === k ? 'on' : ''}" data-preset="${k}">${l}</button>`).join('')}</div>
      <div class="jr-filter-row">
        <select class="jr-select" data-f="status">
          <option value="all">Todos los estados</option>
          <option value="connected" ${f.status === 'connected' ? 'selected' : ''}>Conectados</option>
          <option value="pending" ${f.status === 'pending' ? 'selected' : ''}>Pendientes</option>
          <option value="rejected" ${f.status === 'rejected' ? 'selected' : ''}>Rechazados</option>
          <option value="none" ${f.status === 'none' ? 'selected' : ''}>Sin conectar ningún exchange</option>
        </select>
        <select class="jr-select" data-f="telegram">
          <option value="all">Telegram: todos</option>
          <option value="yes" ${f.telegram === 'yes' ? 'selected' : ''}>Con Telegram</option>
          <option value="no" ${f.telegram === 'no' ? 'selected' : ''}>Sin Telegram</option>
        </select>
        <input type="search" class="jr-search" id="adminSearch" placeholder="Buscar usuario o UID…" value="${esc(f.q)}">
      </div>
    </div>
    <div class="jr-tabs">${TABS.map(([k, l]) => `<button type="button" class="jr-tab ${S.tab === k ? 'on' : ''}" data-tab="${k}">${l}</button>`).join('')}</div>
    <div id="adminPane"></div>`;
  renderPane();
}

function renderPane(){
  const pane = $('adminPane');
  if(!pane) return;
  ADMIN_CHART_SPECS = [];
  pane.innerHTML = S.tab === 'usuarios' ? paneUsuarios() : paneResumen();
  drawAdminCharts();
  if(typeof window.refreshAdminLiveBtn === 'function') window.refreshAdminLiveBtn();
}

/* ======================= Resumen ======================= */
function paneResumen(){
  const s = S.summary || {};
  const rankRows = Object.entries(s.rank_distribution || {}).map(([rank, count]) => ({ label: RANK_LABELS[rank] || rank, value: count, color: C.line }));
  const ts = S.timeseries || [];
  const tsItems = (key) => ts.map(d => ({ label: String(d.day).slice(8, 10), value: d[key], tip: d.day + ': ' + d[key] }));
  return `
    <div class="admin-live-row"><span>Indicador <b>EN VIVO</b> en la barra de arriba:</span><button type="button" class="admin-live-btn" id="adminLiveToggle">Cargando…</button></div>
    <div class="jr-kpis">
      ${kpi('Usuarios totales', s.total_users ?? '—')}
      ${kpi('Nuevos esta semana', s.new_signups_week ?? '—')}
      ${kpi('Bitunix conectado', (s.bitunix_connected_count ?? '—') + ' / ' + (s.total_users ?? '—'))}
      ${kpi('Telegram conectado', (s.telegram_connected_count ?? '—') + ' / ' + (s.total_users ?? '—'))}
      ${kpi('Activos hoy', s.dau ?? '—')}
      ${kpi('Activos esta semana', s.wau ?? '—')}
      ${kpi('Sharkoins repartidos hoy', Number(s.sharkoins_today || 0).toLocaleString('es-CO'))}
      ${kpi('Sharkoins repartidos esta semana', Number(s.sharkoins_week || 0).toLocaleString('es-CO'))}
    </div>
    <div class="jr-grid2">
      ${card('Registros nuevos (30 días)', barChart(tsItems('new_signups'), { h: 190, color: C.line }), 'jr-span2')}
      ${card('Conexiones de Bitunix aprobadas (30 días)', barChart(tsItems('new_bitunix_connections'), { h: 190, color: C.pos }))}
      ${card('Telegram vinculado (30 días)', barChart(tsItems('new_telegram_links'), { h: 190, color: '#5b8def' }))}
      ${card('Distribución de rangos', donut(rankRows))}
      ${card('Categorías más usadas (7 días)', (s.top_categories || []).length
        ? '<div class="jr-hbars">' + s.top_categories.map(c => `<div class="jr-hbar"><span class="jr-hbar-label">${esc(c.category)}</span><span class="jr-hbar-track"><span class="jr-hbar-fill" style="width:${Math.min(100, c.count / Math.max(...s.top_categories.map(x => x.count)) * 100)}%;background:${C.line}"></span></span><span class="jr-hbar-val">${c.count}</span></div>`).join('') + '</div>'
        : '<div class="jr-empty">Sin datos.</div>')}
    </div>`;
}

/* ======================= Usuarios ======================= */
const COLS = [
  ['signup', 'Registro'], ['username', 'Usuario'], ['exchange_uid', 'UID exchange'], ['exchange', 'Exchange'],
  ['connection_status', 'Estado'], ['connReviewed', 'Conectado el'], ['month_volume_usd', 'Volumen (mes)'],
  ['current_rank', 'Rango'], ['telegram_connected', 'Telegram'], ['sharkoins_balance', 'Sharkoins'],
];
const PER_PAGE = 30;
function paneUsuarios(){
  const list = filtered();
  const { key, dir } = S.sort;
  const sorted = list.slice().sort((a, b) => {
    const va = a[key], vb = b[key];
    if(va == null && vb == null) return 0; if(va == null) return 1; if(vb == null) return -1;
    return (va > vb ? 1 : va < vb ? -1 : 0) * dir;
  });
  const pages = Math.max(1, Math.ceil(sorted.length / PER_PAGE));
  S.page = Math.min(S.page, pages - 1);
  const rows = sorted.slice(S.page * PER_PAGE, S.page * PER_PAGE + PER_PAGE);
  return `
    <p class="jr-muted jr-xs" style="margin-bottom:10px">${list.length} usuario(s) en este filtro de ${S.users.length} en total.</p>
    <div class="jr-table-wrap"><table class="jr-table jr-sortable"><thead><tr>${COLS.map(([k, l]) => `<th data-sort="${k}" class="${key === k ? 'on' : ''}">${esc(l)}${key === k ? (dir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead><tbody>
      ${rows.map(u => `<tr>
        <td>${fmtDate(u.signup)}</td>
        <td><b>${esc(u.username)}</b>${u.user_id === OWNER_ID ? ' 👑' : ''}</td>
        <td>${esc(u.exchange_uid || '—')}</td>
        <td>${esc(u.exchange || '—')}</td>
        <td>${esc(STATUS_LABELS[u.connection_status || 'none'] || u.connection_status)}</td>
        <td>${fmtDateTime(u.connReviewed)}</td>
        <td>${usd(u.month_volume_usd)}</td>
        <td>${esc(RANK_LABELS[u.current_rank] || u.current_rank)}</td>
        <td class="${u.telegram_connected ? 'jr-pos' : 'jr-neg'}">${u.telegram_connected ? '✓ ' + fmtDate(u.telegramLinked) : '✗'}</td>
        <td>${Number(u.sharkoins_balance || 0).toLocaleString('es-CO')}</td>
      </tr>`).join('')}
    </tbody></table></div>
    ${pages > 1 ? `<div class="jr-row-btns" style="margin-top:10px"><button type="button" class="jr-btn" data-page="-1" ${S.page === 0 ? 'disabled' : ''}>← Anterior</button><span class="jr-muted jr-xs">Página ${S.page + 1} de ${pages}</span><button type="button" class="jr-btn" data-page="1" ${S.page >= pages - 1 ? 'disabled' : ''}>Siguiente →</button></div>` : ''}`;
}

/* ======================= eventos ======================= */
function bindEvents(){
  const r = root();
  if(!r || r.dataset.bound) return;
  r.dataset.bound = '1';
  r.addEventListener('click', e => {
    const el = e.target.closest('button, th[data-sort]');
    if(!el) return;
    if(el.dataset.preset){ S.f.preset = el.dataset.preset; S.page = 0; return renderShell(); }
    if(el.dataset.tab){ S.tab = el.dataset.tab; S.page = 0; return renderShell(); }
    if(el.dataset.sort){ S.sort = { key: el.dataset.sort, dir: S.sort.key === el.dataset.sort ? -S.sort.dir : -1 }; return renderPane(); }
    if(el.dataset.page){ S.page += Number(el.dataset.page); return renderPane(); }
    if(el.dataset.act === 'refresh'){ S.loaded = false; renderShell(); loadAll().then(renderShell); }
  });
  r.addEventListener('change', e => {
    const el = e.target;
    if(el.dataset.f){ S.f[el.dataset.f] = el.value; S.page = 0; return renderPane(); }
  });
  let qTimer;
  r.addEventListener('input', e => {
    if(e.target.id !== 'adminSearch') return;
    clearTimeout(qTimer);
    qTimer = setTimeout(() => { S.f.q = e.target.value.trim(); S.page = 0; renderPane(); }, 250);
  });
}

/* ======================= abrir / cerrar la vista ======================= */
const view = () => $('adminPageView');
window.openAdminPage = async function(){
  if(!currentUser || currentUser.id !== OWNER_ID){ if(typeof showCategoryOverview === 'function') showCategoryOverview(); return; }
  if(typeof closeAnyOpenToolInline === 'function') closeAnyOpenToolInline();
  if(typeof closeJournalPage === 'function') closeJournalPage();
  if(typeof hideColmillosPage === 'function' && typeof colmillosPageView !== 'undefined' && colmillosPageView.style.display === 'block') hideColmillosPage();
  ['categoryOverviewGrid', 'categoryDetailView', 'marketDashboardBlock', 'favoritesSection'].forEach(id => { const el = $(id); if(el) el.style.display = 'none'; });
  document.querySelectorAll('.hero-mascot, .crypto-ticker').forEach(el => { el.style.display = 'none'; });
  view().style.display = 'block';
  if(typeof setPageTitle === 'function') setPageTitle('Panel de admin');
  if(typeof pushRoute === 'function' && typeof closingFromPopstate !== 'undefined' && !closingFromPopstate && location.pathname !== '/administrador'){
    pushRoute({ skillcashDepth: 'category' }, '/administrador');
  }
  window.scrollTo({ top: 0 });
  bindEvents();
  S.loaded = false; renderShell();
  await loadAll(); renderShell();
};
window.closeAdminPage = function(){
  const v = view();
  if(!v || v.style.display === 'none') return false;
  v.style.display = 'none';
  return true;
};
// si openAdminPage() de verdad empujo /administrador al historial (entro desde adentro del
// sitio), "Volver" hace history.back() - el popstate normal se encarga de cerrar la pagina y
// mostrar lo que corresponda. Si no hay esa entrada (ej. alguien abrio /administrador por URL
// directa, sin nada nuestro antes en el historial), history.back() podria sacarlo del sitio -
// en ese caso simplemente se cierra y se va al inicio, igual que closeModalGeneric.
const adminBackBtn = $('adminBackBtn');
if(adminBackBtn) adminBackBtn.addEventListener('click', () => {
  if(history.state && history.state.skillcashDepth === 'category' && location.pathname === '/administrador'){
    history.back();
  } else {
    window.closeAdminPage();
    if(typeof showCategoryOverview === 'function') showCategoryOverview();
    if(typeof replaceRoute === 'function') replaceRoute(null, '/');
  }
});
})();
