/* Gráfico en Vivo (Rango de Manada): velas en vivo (WebSocket de Binance, 1 minuto) para
   cualquier moneda del top ~300 por capitalización que SÍ tenga un par real en Binance (si una
   moneda no cotiza ahí, no se muestra - mejor eso que mostrar datos que no son en vivo de
   verdad, pedido explícito de Juan). CoinGecko solo se usa para el ranking/nombres/íconos del
   top 300, nunca para los precios ni las velas. */
(function(){
if(typeof showCategoryOverview === 'undefined') return;

const CG_BASE = 'https://api.coingecko.com/api/v3';
const BINANCE_REST = 'https://api.binance.com';
const BINANCE_WS = 'wss://stream.binance.com:9443/ws';
const INTERVAL = '1m';

let coinList = null; // [{id,symbol,name,image,current_price,price_change_percentage_24h,high_24h,low_24h,total_volume}, ...] - solo las que sí tienen par en Binance
let binanceSymbols = null; // Set de pares "BTCUSDT" etc.
let loadingPromise = null;
let chart = null, candleSeries = null, volumeSeries = null;
let ws = null, wsReconnectTimer = null, wsSymbol = null;
let currentCoin = null;

/* ---- datos: universo de monedas (CoinGecko para el ranking, Binance para saber cuáles son en vivo) ---- */
async function fetchBinanceSymbols(){
  if(binanceSymbols) return binanceSymbols;
  const res = await fetch(BINANCE_REST + '/api/v3/exchangeInfo');
  const data = await res.json();
  binanceSymbols = new Set(
    (data.symbols || [])
      .filter(s => s.status === 'TRADING' && s.quoteAsset === 'USDT')
      .map(s => s.symbol)
  );
  return binanceSymbols;
}
async function fetchCoinGeckoPage(page){
  const url = CG_BASE + '/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=' + page + '&price_change_percentage=24h';
  const res = await fetch(url);
  if(!res.ok) throw new Error('CoinGecko ' + res.status);
  return res.json();
}
async function ensureCoinList(){
  if(coinList) return coinList;
  if(loadingPromise) return loadingPromise;
  loadingPromise = (async () => {
    const [symbols, page1, page2] = await Promise.all([
      fetchBinanceSymbols(),
      fetchCoinGeckoPage(1),
      fetchCoinGeckoPage(2),
    ]);
    const all = [...page1, ...page2];
    coinList = all
      .map(c => {
        const binanceSymbol = symbols.has((c.symbol || '').toUpperCase() + 'USDT') ? (c.symbol || '').toUpperCase() + 'USDT' : null;
        return { ...c, binanceSymbol };
      })
      .filter(c => c.binanceSymbol);
    return coinList;
  })();
  return loadingPromise;
}

/* ---- velas iniciales (REST) + velas en vivo (WebSocket), ambas 100% de Binance ---- */
async function loadInitialCandles(symbol){
  const url = BINANCE_REST + '/api/v3/klines?symbol=' + symbol + '&interval=' + INTERVAL + '&limit=300';
  const res = await fetch(url);
  const rows = await res.json();
  return rows.map(r => ({
    time: Math.floor(r[0] / 1000),
    open: Number(r[1]), high: Number(r[2]), low: Number(r[3]), close: Number(r[4]),
    volume: Number(r[5]),
  }));
}
function closeSocket(){
  clearTimeout(wsReconnectTimer);
  if(ws){ ws.onclose = null; ws.onerror = null; try{ ws.close(); }catch(e){} ws = null; }
  wsSymbol = null;
}
function openLiveSocket(symbol){
  closeSocket();
  wsSymbol = symbol;
  const streamUrl = BINANCE_WS + '/' + symbol.toLowerCase() + '@kline_' + INTERVAL;
  ws = new WebSocket(streamUrl);
  ws.onmessage = (ev) => {
    if(wsSymbol !== symbol) return; // mensaje tardío de un socket ya reemplazado
    let msg;
    try{ msg = JSON.parse(ev.data); }catch(e){ return; }
    const k = msg.k;
    if(!k) return;
    const candle = {
      time: Math.floor(k.t / 1000),
      open: Number(k.o), high: Number(k.h), low: Number(k.l), close: Number(k.c),
      volume: Number(k.v),
    };
    if(candleSeries) candleSeries.update(candle);
    if(volumeSeries) volumeSeries.update({ time: candle.time, value: candle.volume, color: candle.close >= candle.open ? 'rgba(46,204,113,.5)' : 'rgba(255,47,79,.5)' });
    updateLivePrice(candle.close, k.x);
  };
  ws.onclose = () => {
    if(wsSymbol !== symbol) return; // ya se cambió de moneda, no reconectar este
    wsReconnectTimer = setTimeout(() => { if(wsSymbol === symbol) openLiveSocket(symbol); }, 2000);
  };
  ws.onerror = () => { try{ ws.close(); }catch(e){} };
}

/* ---- UI ---- */
const $ = id => document.getElementById(id);
const fmtUsd = (n, decimals) => {
  if(n == null || isNaN(n)) return '—';
  const d = decimals != null ? decimals : (n >= 1 ? 2 : 6);
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
};
const fmtVol = (n) => {
  if(n == null || isNaN(n)) return '—';
  if(n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if(n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if(n >= 1e3) return (n / 1e3).toFixed(2) + 'K';
  return String(Math.round(n));
};

function renderShell(){
  const root = $('liveChartRoot');
  root.innerHTML = `
    <div class="lc-head">
      <h2 class="lc-title">📈 Gráfico en Vivo</h2>
      <p class="lc-sub">Velas en tiempo real (1 minuto) de cualquier cripto con par en Binance — mismo dato, al mismo tiempo.</p>
    </div>
    <div class="lc-layout">
      <div class="lc-sidebar">
        <div class="lc-search-wrap">
          <input type="text" id="lcSearchInput" placeholder="Buscar moneda (BTC, Solana...)" autocomplete="off">
        </div>
        <div class="lc-coin-list" id="lcCoinList"><div class="lc-loading">Cargando monedas…</div></div>
      </div>
      <div class="lc-main">
        <div class="lc-stats-bar" id="lcStatsBar"></div>
        <div class="lc-chart-box">
          <div id="lcChartContainer" class="lc-chart-container"></div>
        </div>
      </div>
    </div>
  `;
  $('lcSearchInput').addEventListener('input', (e) => renderCoinList(e.target.value.trim().toLowerCase()));
}

function renderCoinList(filter){
  const list = $('lcCoinList');
  if(!list) return;
  if(!coinList){ list.innerHTML = '<div class="lc-loading">Cargando monedas…</div>'; return; }
  const q = filter || '';
  const items = q
    ? coinList.filter(c => c.symbol.toLowerCase().includes(q) || c.name.toLowerCase().includes(q))
    : coinList;
  if(!items.length){ list.innerHTML = '<div class="lc-loading">Sin resultados.</div>'; return; }
  list.innerHTML = items.slice(0, 200).map(c => {
    const up = (c.price_change_percentage_24h || 0) >= 0;
    const active = currentCoin && currentCoin.id === c.id;
    return `
      <button type="button" class="lc-coin-item${active ? ' active' : ''}" data-coin="${c.id}">
        <img src="${c.image}" alt="" loading="lazy">
        <span class="lc-coin-info">
          <span class="lc-coin-symbol">${c.symbol.toUpperCase()}</span>
          <span class="lc-coin-name">${c.name}</span>
        </span>
        <span class="lc-coin-change ${up ? 'lc-pos' : 'lc-neg'}">${up ? '+' : ''}${(c.price_change_percentage_24h || 0).toFixed(2)}%</span>
      </button>
    `;
  }).join('');
  list.querySelectorAll('[data-coin]').forEach(btn => {
    btn.addEventListener('click', () => selectCoin(btn.dataset.coin, true));
  });
}

function renderStatsBar(coin){
  const bar = $('lcStatsBar');
  if(!bar) return;
  const up = (coin.price_change_percentage_24h || 0) >= 0;
  bar.innerHTML = `
    <div class="lc-stats-coin">
      <img src="${coin.image}" alt="">
      <div>
        <div class="lc-stats-symbol">${coin.symbol.toUpperCase()}<span class="lc-stats-pair">/USDT</span></div>
        <div class="lc-stats-name">${coin.name}</div>
      </div>
    </div>
    <div class="lc-stats-price">
      <div class="lc-stats-price-val ${up ? 'lc-pos' : 'lc-neg'}" id="lcLivePrice">${fmtUsd(coin.current_price)}</div>
      <div class="lc-stats-price-chg ${up ? 'lc-pos' : 'lc-neg'}">${up ? '▲' : '▼'} ${Math.abs(coin.price_change_percentage_24h || 0).toFixed(2)}%</div>
    </div>
    <div class="lc-stats-mini"><span>Máximo 24h</span><b>${fmtUsd(coin.high_24h)}</b></div>
    <div class="lc-stats-mini"><span>Mínimo 24h</span><b>${fmtUsd(coin.low_24h)}</b></div>
    <div class="lc-stats-mini"><span>Volumen 24h</span><b>${fmtVol(coin.total_volume)}</b></div>
  `;
}
function updateLivePrice(price, isFinalCandle){
  const el = $('lcLivePrice');
  if(el) el.textContent = fmtUsd(price);
}

function ensureChart(){
  if(chart) return;
  if(typeof LightweightCharts === 'undefined') return;
  const container = $('lcChartContainer');
  chart = LightweightCharts.createChart(container, {
    layout: { background: { color: 'transparent' }, textColor: '#b3b6bf' },
    grid: { vertLines: { color: 'rgba(255,255,255,.06)' }, horzLines: { color: 'rgba(255,255,255,.06)' } },
    rightPriceScale: { borderColor: 'rgba(91,141,239,.3)' },
    timeScale: { borderColor: 'rgba(91,141,239,.3)', timeVisible: true, secondsVisible: false },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    autoSize: true,
  });
  candleSeries = chart.addCandlestickSeries({
    upColor: '#2ecc71', downColor: '#ff2f4f', borderVisible: false,
    wickUpColor: '#2ecc71', wickDownColor: '#ff2f4f',
  });
  volumeSeries = chart.addHistogramSeries({
    color: 'rgba(91,141,239,.4)', priceFormat: { type: 'volume' },
    priceScaleId: '', scaleMargins: { top: 0.82, bottom: 0 },
  });
}

async function selectCoin(coinId, fromClick){
  if(!coinList) return;
  const coin = coinList.find(c => c.id === coinId);
  if(!coin) return;
  currentCoin = coin;
  renderStatsBar(coin);
  renderCoinList($('lcSearchInput') ? $('lcSearchInput').value.trim().toLowerCase() : '');
  if(fromClick && typeof replaceRoute === 'function' && !closingFromPopstate){
    replaceRoute({ skillcashDepth: 'category' }, '/grafico-en-vivo/' + coinId);
  }
  ensureChart();
  if(!chart) return; // la librería todavía no cargó (CDN lento) - selectCoin se reintenta al abrir
  closeSocket();
  try{
    const candles = await loadInitialCandles(coin.binanceSymbol);
    candleSeries.setData(candles.map(c => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close })));
    volumeSeries.setData(candles.map(c => ({ time: c.time, value: c.volume, color: c.close >= c.open ? 'rgba(46,204,113,.5)' : 'rgba(255,47,79,.5)' })));
    chart.timeScale().fitContent();
  }catch(err){
    console.error('Gráfico en vivo: error cargando velas', err);
  }
  openLiveSocket(coin.binanceSymbol);
}

/* ======================= abrir / cerrar la vista ======================= */
const view = () => $('liveChartPageView');
window.openLiveChartPage = async function(initialCoinId){
  if(typeof isWipLockedForCurrentUser === 'function' && isWipLockedForCurrentUser('rangos')){
    if(typeof showWipToast === 'function') showWipToast('🔒 Todavía estamos construyendo esto — vuelve pronto.');
    return;
  }
  if(typeof closeAnyOpenToolInline === 'function') closeAnyOpenToolInline();
  if(typeof closeAdminPage === 'function') closeAdminPage();
  if(typeof closeJournalPage === 'function') closeJournalPage();
  if(typeof hideColmillosPage === 'function' && typeof colmillosPageView !== 'undefined' && colmillosPageView.style.display === 'block') hideColmillosPage();
  ['categoryOverviewGrid', 'categoryDetailView', 'marketDashboardBlock', 'favoritesSection'].forEach(id => { const el = document.getElementById(id); if(el) el.style.display = 'none'; });
  document.querySelectorAll('.hero-mascot, .crypto-ticker').forEach(el => { el.style.display = 'none'; });
  if(typeof window.syncHomeMirror === 'function') window.syncHomeMirror();
  view().style.display = 'block';
  if(typeof setPageTitle === 'function') setPageTitle('Gráfico en Vivo');
  const path = '/grafico-en-vivo' + (initialCoinId ? '/' + initialCoinId : '');
  if(typeof pushRoute === 'function' && typeof closingFromPopstate !== 'undefined' && !closingFromPopstate && location.pathname !== path){
    pushRoute({ skillcashDepth: 'category' }, path);
  }
  window.scrollTo({ top: 0 });
  renderShell();
  try{
    await ensureCoinList();
  }catch(err){
    console.error('Gráfico en vivo: error cargando lista de monedas', err);
    const list = $('lcCoinList');
    if(list) list.innerHTML = '<div class="lc-loading">No se pudo cargar la lista de monedas. Intenta de nuevo en un momento.</div>';
    return;
  }
  renderCoinList('');
  await selectCoin(initialCoinId && coinList.some(c => c.id === initialCoinId) ? initialCoinId : 'bitcoin');
};
window.closeLiveChartPage = function(){
  const v = view();
  closeSocket();
  if(!v || v.style.display === 'none') return false;
  v.style.display = 'none';
  if(chart){ chart.remove(); chart = null; candleSeries = null; volumeSeries = null; }
  return true;
};
document.querySelectorAll('[data-open-livechart]').forEach(btn => btn.addEventListener('click', () => {
  if(typeof isWipLockedForCurrentUser === 'function' && isWipLockedForCurrentUser('rangos')){
    if(typeof showWipToast === 'function') showWipToast('🔒 Todavía estamos construyendo esto — vuelve pronto.');
    return;
  }
  document.getElementById('sidebar').classList.remove('mobile-open');
  const bd = document.getElementById('sbBackdrop'); if(bd) bd.classList.remove('show');
  window.openLiveChartPage();
}));
const backBtn = $('liveChartBackBtn');
if(backBtn) backBtn.addEventListener('click', () => {
  if(history.state && history.state.skillcashDepth === 'category' && location.pathname.startsWith('/grafico-en-vivo')){
    history.back();
  } else {
    window.closeLiveChartPage();
    if(typeof showCategoryDetail === 'function') showCategoryDetail('rangos');
    else if(typeof showCategoryOverview === 'function') showCategoryOverview();
  }
});
})();
