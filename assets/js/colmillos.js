/* ---- modal de Colmillos: explica como se ganan (estilo "logros" de videojuego) y para que
   sirven por ahora - se abre al picarle a la pildora de la billetera ---- */
const colmillosPageView = document.getElementById('colmillosPageView');
const colmillosLoading = document.getElementById('colmillosLoading');
const colmillosContent = document.getElementById('colmillosContent');
const colmillosBackBtn = document.getElementById('colmillosBackBtn');
const colmillosBigCoin = document.getElementById('colmillosBigCoin');

/* ---- personaje: sprite real en pixel art (generado con PixelLab, ver assets/mascot/) -
   el mismo PNG se usa como <img> en las vistas previas (Inicio/Tienda) y se dibuja con
   drawImage dentro del canvas del minijuego. Los accesorios (gorra/gafas/cadena) son PNGs
   pixel art dibujados a mano (assets/mascot/accessories/, mismo canvas 96x96 que el
   tiburon) superpuestos encima del sprite ---- */
const SHARK_IMG_PATHS = {
  default: 'assets/mascot/source/base_original.png',
  skin_gold: 'assets/mascot/variants/shark_skin_gold.png',
  skin_red: 'assets/mascot/variants/shark_skin_red.png',
  skin_abyss: 'assets/mascot/variants/shark_skin_abyss.png',
  skin_emerald: 'assets/mascot/variants/shark_skin_emerald.png',
  skin_cyan: 'assets/mascot/variants/shark_skin_cyan.png',
  skin_pink: 'assets/mascot/variants/shark_skin_pink.png',
  skin_orange: 'assets/mascot/variants/shark_skin_orange.png',
  skin_ice: 'assets/mascot/variants/shark_skin_ice.png',
  skin_lime: 'assets/mascot/variants/shark_skin_lime.png',
  skin_violet: 'assets/mascot/variants/shark_skin_violet.png',
  skin_camo: 'assets/mascot/variants/shark_skin_camo.png',
  skin_tiger: 'assets/mascot/variants/shark_skin_tiger.png',
  skin_galaxy: 'assets/mascot/variants/shark_skin_galaxy.png',
  skin_arcoiris: 'assets/mascot/variants/shark_skin_arcoiris.png',
  skin_oroliquido: 'assets/mascot/variants/shark_skin_oroliquido.png',
  skin_neon: 'assets/mascot/variants/shark_skin_neon.png',
  skin_dragon: 'assets/mascot/variants/shark_skin_dragon.png',
  skin_martillo: 'assets/mascot/variants/shark_skin_martillo.png',
  skin_rayosx: 'assets/mascot/variants/shark_skin_rayosx.png',
};
const BG_IMG_PATHS = {
  bg_reef: 'assets/mascot/backgrounds/bg_reef.png',
  bg_abyss: 'assets/mascot/backgrounds/bg_abyss.png',
  bg_surface: 'assets/mascot/backgrounds/bg_surface.png',
  bg_sunken_city: 'assets/mascot/backgrounds/bg_sunken_city.png',
  bg_volcano: 'assets/mascot/backgrounds/bg_volcano.png',
  bg_night: 'assets/mascot/backgrounds/bg_night.png',
  bg_nave: 'assets/mascot/backgrounds/bg_nave.png',
  bg_tormenta: 'assets/mascot/backgrounds/bg_tormenta.png',
  bg_playa: 'assets/mascot/backgrounds/bg_playa.png',
  bg_laboratorio: 'assets/mascot/backgrounds/bg_laboratorio.png',
  bg_atardecer: 'assets/mascot/backgrounds/bg_atardecer.png',
  bg_selva: 'assets/mascot/backgrounds/bg_selva.png',
  bg_cueva: 'assets/mascot/backgrounds/bg_cueva.png',
  bg_neon: 'assets/mascot/backgrounds/bg_neon.png',
  bg_pradera: 'assets/mascot/backgrounds/bg_pradera.png',
  bg_nieve: 'assets/mascot/backgrounds/bg_nieve.png',
  bg_desierto: 'assets/mascot/backgrounds/bg_desierto.png',
  bg_cripto_bitcoin: 'assets/mascot/backgrounds/fondo_cripto_bitcoin.png',
  bg_cripto_ethereum: 'assets/mascot/backgrounds/fondo_cripto_ethereum.png',
  bg_cripto_solana: 'assets/mascot/backgrounds/fondo_cripto_solana.png',
  bg_cripto_monero: 'assets/mascot/backgrounds/fondo_cripto_monero.png',
  bg_cripto_pepe: 'assets/mascot/backgrounds/fondo_cripto_pepe.png',
  bg_cripto_dogecoin: 'assets/mascot/backgrounds/fondo_cripto_dogecoin.png',
};
const sharkImgCache = {};
function getSharkImg(skinId){
  const key = (skinId && SHARK_IMG_PATHS[skinId]) ? skinId : 'default';
  if(!sharkImgCache[key]){
    const img = new Image();
    img.src = SHARK_IMG_PATHS[key];
    sharkImgCache[key] = img;
  }
  return sharkImgCache[key];
}
const bgImgCache = {};
function getBgImg(backgroundId){
  if(!backgroundId || !BG_IMG_PATHS[backgroundId]) return null;
  if(!bgImgCache[backgroundId]){
    const img = new Image();
    img.src = BG_IMG_PATHS[backgroundId];
    bgImgCache[backgroundId] = img;
  }
  return bgImgCache[backgroundId];
}
const ACC_IMG_PATHS = {
  acc_cap: 'assets/mascot/accessories/acc_cap.png',
  acc_shades: 'assets/mascot/accessories/acc_shades.png',
  acc_chain: 'assets/mascot/accessories/acc_chain.png',
  acc_scuba: 'assets/mascot/accessories/acc_scuba.png',
  acc_scarf: 'assets/mascot/accessories/acc_scarf.png',
  acc_headphones: 'assets/mascot/accessories/acc_headphones.png',
  acc_crown: 'assets/mascot/accessories/acc_crown.png',
  acc_cape: 'assets/mascot/accessories/acc_cape.png',
  acc_sombrero: 'assets/mascot/accessories/acc_sombrero.png',
  acc_antifaz: 'assets/mascot/accessories/acc_antifaz.png',
  acc_aletarobot: 'assets/mascot/accessories/acc_aletarobot.png',
  acc_collar: 'assets/mascot/accessories/acc_collar.png',
  acc_paraguas: 'assets/mascot/accessories/acc_paraguas.png',
  acc_guantes: 'assets/mascot/accessories/acc_guantes.png',
  acc_microfono: 'assets/mascot/accessories/acc_microfono.png',
  acc_bate: 'assets/mascot/accessories/acc_bate.png',
  acc_escudo: 'assets/mascot/accessories/acc_escudo.png',
  acc_espada: 'assets/mascot/accessories/acc_espada.png',
  acc_mazo: 'assets/mascot/accessories/acc_mazo.png',
  acc_raqueta: 'assets/mascot/accessories/acc_raqueta.png',
  acc_varita: 'assets/mascot/accessories/acc_varita.png',
  acc_aletasbuceo: 'assets/mascot/accessories/acc_aletasbuceo.png',
  acc_botasnieve: 'assets/mascot/accessories/acc_botasnieve.png',
  acc_botaspirata: 'assets/mascot/accessories/acc_botaspirata.png',
  acc_patines: 'assets/mascot/accessories/acc_patines.png',
  acc_sandalias: 'assets/mascot/accessories/acc_sandalias.png',
  acc_tenis: 'assets/mascot/accessories/acc_tenis.png',
  acc_laser: 'assets/mascot/accessories/acc_ojos_ojos_laser.png',
  acc_corazon: 'assets/mascot/accessories/acc_ojos_gafas_corazon.png',
  acc_monoculo: 'assets/mascot/accessories/acc_ojos_monoculo.png',
  acc_gafas3d: 'assets/mascot/accessories/acc_ojos_gafas_3d.png',
  acc_cyberpunk: 'assets/mascot/accessories/acc_ojos_visor_cyberpunk.png',
  acc_buceo: 'assets/mascot/accessories/acc_ojos_careta_buceo.png',
};
/* accessoryIds: un arreglo (0 a 4 ids, uno por cada "parte del cuerpo" - cabeza/cara/cuerpo/
   manos) para poder llevar puesto un gorro Y gafas Y cadena Y algo en la mano, todo a la vez -
   tambien acepta un solo id suelto (string) o null/undefined por comodidad en los call-sites */
function sharkAccessoryOverlayHtml(accessoryIds){
  const ids = Array.isArray(accessoryIds) ? accessoryIds : (accessoryIds ? [accessoryIds] : []);
  return ids.map(id => {
    const src = id && ACC_IMG_PATHS[id];
    if(!src) return '';
    return '<img loading="lazy" src="' + src + '" alt="" style="position:absolute;left:0;top:0;width:100%;height:100%;image-rendering:pixelated;image-rendering:crisp-edges">';
  }).join('');
}
function sharkImgMarkup(skinId, accessoryIds, width){
  const src = (skinId && SHARK_IMG_PATHS[skinId]) ? SHARK_IMG_PATHS[skinId] : SHARK_IMG_PATHS.default;
  const w = width || 150;
  return '<div style="position:relative;width:' + w + 'px;height:' + w + 'px;margin:0 auto">' +
    '<img loading="lazy" src="' + src + '" alt="" style="width:100%;height:100%;image-rendering:pixelated;image-rendering:crisp-edges">' +
    sharkAccessoryOverlayHtml(accessoryIds) +
    '</div>';
}
/* saldo grande siempre arranca en 0 y sube contando hasta el total real - se ve mas vivo que
   un numero que aparece de golpe */
function animateColmBalance(target){
  const el = document.getElementById('colmillosBigBalance');
  if(!el) return;
  const fighterEl = document.getElementById('colmillosFighterBalance');
  const fighterFill = document.getElementById('colmillosCurrencyFill');
  const coinChipEl = document.getElementById('colmillosHeroCoinChip');
  cancelAnimationFrame(window._colmBalanceRaf);
  const duration = 900;
  const startTime = performance.now();
  function tick(now){
    const progress = Math.min(1, (now - startTime) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    const value = Math.round(target * eased);
    el.textContent = value.toLocaleString('es-CO');
    if(fighterEl) fighterEl.textContent = value.toLocaleString('es-CO');
    if(coinChipEl) coinChipEl.textContent = value.toLocaleString('es-CO');
    // barrita decorativa tipo "XP" - se llena cada 100 y vuelve a empezar, solo para que
    // se vea viva, no representa ningun limite real de saldo
    if(fighterFill) fighterFill.style.width = (value > 0 ? ((value % 100) || 100) : 0) + '%';
    if(progress < 1) window._colmBalanceRaf = requestAnimationFrame(tick);
  }
  window._colmBalanceRaf = requestAnimationFrame(tick);
}
/* "nivel de heroe" ahora lo calcula getHeroProgress() (assets/js/hero-progress.js), una
   funcion PURA y testeada (scripts/tests/hero_progress.test.mjs) que no toca el DOM ni las
   variables globales de este archivo - aqui solo se le arma el catalogo+lo poseido/equipado
   y se usa el resultado para pintar tanto el HUD chiquito del escenario como la Ficha de
   Heroe grande. Ver hero-progress.js para la formula completa (pesos por rareza, umbrales de
   estrellas, mapeo item->stat). */
function buildHeroCatalogForProgress(){
  return colmillosShopItemsCache.map(item => ({
    id: item.id,
    category: item.category,
    slot: item.category === 'skin' ? 'skin' : (item.category === 'accessory' ? (ACC_SLOT_MAP[item.id] || 'body') : null),
  }));
}
function getColmHeroProgress(){
  const catalog = buildHeroCatalogForProgress();
  if(colmHeroDebugOverride) return getHeroProgress({ catalog, ...colmHeroDebugOverride });
  const equippedTiers = Object.keys(COLM_POWER_BY_SLOT).map(field => {
    const itemId = colmillosEquippedState[field];
    return itemId ? (colmillosItemRarity.get(itemId) || 1) : 0;
  }).filter(Boolean);
  return getHeroProgress({
    catalog,
    ownedIds: colmillosOwnedItemIds,
    rarityById: Object.fromEntries(colmillosItemRarity),
    equippedTiers,
  });
}
/* pinta el nivel en la barrita del HUD (antes era "SUERTE", una barra decorativa aleatoria
   sin ningun significado - ahora mide lo mismo que la Ficha de Heroe) y las estrellitas */
function renderColmLevelHud(){
  const info = getColmHeroProgress();
  const numEl = document.getElementById('colmillosLevelNum');
  const fillEl = document.getElementById('colmillosLifeFill');
  const starsEl = document.getElementById('colmillosFighterStars');
  if(numEl) numEl.textContent = info.level;
  if(fillEl) fillEl.style.width = Math.round(info.progress * 100) + '%';
  if(starsEl){
    starsEl.innerHTML = Array.from({ length: 5 }, (_, i) =>
      '<span class="' + (i < info.stars ? 'filled' : '') + '">★</span>'
    ).join('');
  }
  return info;
}
/* "edad del tiburon" = tiempo desde que el usuario se registro en la plataforma */
function formatSharkAge(createdAtIso){
  if(!createdAtIso) return '—';
  const days = Math.floor((Date.now() - new Date(createdAtIso).getTime()) / 86400000);
  if(days < 1) return 'Nuevo';
  if(days < 30) return days + (days === 1 ? ' día' : ' días');
  if(days < 365){ const m = Math.floor(days / 30); return m + (m === 1 ? ' mes' : ' meses'); }
  const y = Math.floor(days / 365); return y + (y === 1 ? ' año' : ' años');
}
let colmSessionStartTs = null;
function updateColmSessionTimer(){
  const el = document.getElementById('colmillosSessionTimer');
  if(!el || !colmSessionStartTs) return;
  const secs = Math.floor((Date.now() - colmSessionStartTs) / 1000);
  const mm = Math.floor(secs / 60);
  const ss = secs % 60;
  el.textContent = mm > 0 ? (mm + ':' + String(ss).padStart(2, '0')) : String(secs).padStart(2, '0');
}
/* 5 "partes del cuerpo" para accesorios - cada una es su propia columna en
   user_colmillos_equipped (accessory_head_id, accessory_face_id, ...) para que se puedan
   llevar puestas al mismo tiempo sin que una se quite a la otra */
const ACC_SLOTS = ['head', 'face', 'body', 'hands', 'feet'];
const COLM_EQUIPPED_DEFAULT = { skin_id: null, accessory_head_id: null, accessory_face_id: null, accessory_body_id: null, accessory_hands_id: null, accessory_feet_id: null, background_id: null };
let colmillosEquippedState = { ...COLM_EQUIPPED_DEFAULT };
let colmillosOwnedItemIds = new Set();
let colmillosShopItemsCache = [];
let colmillosRaffleBoughtThisMonth = false;
/* ---- rareza/evolucion de skins y accesorios (NO aplica a fondos ni al boleto - esos siguen
   con un solo precio): cada skin/accesorio es una "familia" que se compra una vez al precio
   de catalogo (eso es el tier 1, Común) y despues se puede EVOLUCIONAR pagando Sharkoins
   extra - Raro, Épico, Legendario, Mítico - sin comprar nada nuevo, es la MISMA pieza
   mejorando (como las piezas de Axie Infinity). El costo de evolucionar es igual para
   cualquier familia, y la rareza alcanzada queda guardada como una fila mas del ledger de
   siempre (event_type='evolve_<item_id>', period_key='tier2'/'tier3'/...) - ver
   scripts/sql/colm_shop_repricing.sql. Es puramente decorativo/coleccionable: no cambia nada
   del minijuego, la ruleta ni la trivia. */
const COLM_RARITY_TIERS = [
  null, // no existe tier 0
  { tier: 1, name: 'Común', color: '#9d9d9d' },
  { tier: 2, name: 'Raro', color: '#3b82f6' },
  { tier: 3, name: 'Épico', color: '#a335ee' },
  { tier: 4, name: 'Legendario', color: '#f0a020' },
  { tier: 5, name: 'Mítico', color: 'linear-gradient(135deg,#ff5f6d,#a78bfa,#38bdf8)' },
];
const COLM_EVOLVE_COST = { 2: 75, 3: 150, 4: 275, 5: 450 };
const COLM_RARITY_CATEGORIES = new Set(['skin', 'accessory']);
/* las 6 "categorias de poder" del personaje - el color (skin) y cada una de las 5 partes del
   cuerpo le dan su propio poder decorativo, cuyo NIVEL es la rareza de lo que tengas
   equipado ahi (nada equipado = sin poder en esa categoria) */
const COLM_POWER_BY_SLOT = {
  skin_id: { label: 'Instinto', icon: '🧬' },
  accessory_head_id: { label: 'Astucia', icon: '🧠' },
  accessory_face_id: { label: 'Visión', icon: '👁️' },
  accessory_body_id: { label: 'Resistencia', icon: '🛡️' },
  accessory_hands_id: { label: 'Fuerza', icon: '💪' },
  accessory_feet_id: { label: 'Velocidad', icon: '⚡' },
};
let colmillosItemRarity = new Map(); // itemId -> tier (1-5), solo para items que se poseen
/* vista previa "para ver como se veria" dentro de la tienda - NO es lo realmente equipado,
   solo cambia lo que se ve en colmillosCharPreviewBig al tocar una cajita. Se limpia (vuelve
   a mostrar lo que el usuario ya tiene puesto de verdad) cada vez que se entra a la tienda o
   se confirma un equipar/comprar */
let colmillosShopPreview = {};
function colmEquippedAccessoryIds(state){
  return ACC_SLOTS.map(slot => state['accessory_' + slot + '_id']).filter(Boolean);
}
/* el tiburon + pedestal de la Ficha de Heroe se escalan a partir de su lienzo nativo (tiburon
   384x384, pedestal 384x160 - pack de arte v2; ver assets/hero/LEEME.txt), usando el MISMO
   factor "m" para los dos sprites. El tiburon ocupa 75% del alto del ESCENARIO (sin achicarlo
   aparte) - lo que se redujo para que se vea menos pixelado es el escenario completo (ver
   min-height de .colm-hero en el CSS), no el personaje dentro de un escenario igual de alto -
   eso dejaba al tiburon chiquito y descolgado en una esquina, que es justo lo que NO se
   queria. La posicion del tiburon sobre el pedestal usa el offset fijo del pack (x:+24,y:-268
   en pixeles nativos, multiplicados por "m") medido desde el rectangulo YA renderizado del
   pedestal, asi no hay que duplicar su logica de centrado. */
const HERO_PEDESTAL_NATIVE = { w: 384, h: 160 };
const HERO_SHARK_NATIVE = { w: 384, h: 384, offsetX: 24, offsetY: -268 };
const HERO_SHARK_HEIGHT_FRACTION = 0.75;
function sizeAndRenderHeroChar(accessoryIds){
  const stage = document.querySelector('.colm-hero-main');
  const charEl = document.getElementById('colmillosHeroShark');
  const pedGroup = document.getElementById('colmillosPedestalGroup');
  const shadowEl = document.getElementById('colmillosContactShadow');
  const floorEl = document.getElementById('colmillosFloorShadow');
  if(!stage || !charEl || !pedGroup) return;
  const stageRect = stage.getBoundingClientRect();
  const stageH = stageRect.height || 480;
  // el factor de escala NO se redondea a un entero - se usa el valor exacto que da la fraccion
  // de alto pedida; image-rendering:pixelated evita el borroneo igual con escala fraccionaria -
  // el pedestal usa el MISMO factor para que coincida el pixel art
  let m = Math.max(0.5, (stageH * HERO_SHARK_HEIGHT_FRACTION) / HERO_SHARK_NATIVE.h);
  // tope de ancho: en escritorio el pedestal/tiburon estan centrados en el 34% del ancho del
  // escenario (ver .colm-hero-pedestal-group) para dejarle sitio al panel de info flotante -
  // el lado IZQUIERDO es el que limita primero ahi (36% + margen a la derecha). En celular el
  // panel va DEBAJO (no al lado), asi que ahi el tiburon se centra en el 50% del escenario
  // (ver el media query de .colm-hero-pedestal-group) y el tope solo es un margen cosmetico,
  // no una prevencion de recorte como en escritorio.
  const isMobileHero = window.matchMedia('(max-width:900px)').matches;
  const maxPedW = stageRect.width * (isMobileHero ? 0.9 : 0.46);
  const maxM = maxPedW / HERO_PEDESTAL_NATIVE.w;
  if(m > maxM) m = Math.max(0.5, maxM);
  const sharkPx = m * HERO_SHARK_NATIVE.h;
  const pedW = m * HERO_PEDESTAL_NATIVE.w;
  const pedH = m * HERO_PEDESTAL_NATIVE.h;

  charEl.innerHTML = sharkImgMarkup(colmillosEquippedState.skin_id, accessoryIds, sharkPx);
  charEl.style.width = sharkPx + 'px';
  charEl.style.height = sharkPx + 'px';
  pedGroup.style.width = pedW + 'px';
  pedGroup.style.height = pedH + 'px';

  const pedRect = pedGroup.getBoundingClientRect();
  const charLeft = (pedRect.left - stageRect.left) + HERO_SHARK_NATIVE.offsetX * m;
  const charTop = (pedRect.top - stageRect.top) + HERO_SHARK_NATIVE.offsetY * m;
  charEl.style.left = charLeft + 'px';
  charEl.style.top = charTop + 'px';

  if(shadowEl){
    const shW = sharkPx * 0.46, shH = shW * 0.3;
    shadowEl.style.width = shW + 'px';
    shadowEl.style.height = shH + 'px';
    shadowEl.style.left = (charLeft + sharkPx / 2 - shW / 2) + 'px';
    shadowEl.style.top = ((pedRect.top - stageRect.top) + pedH * 0.2 - shH / 2) + 'px';
  }
  if(floorEl){
    floorEl.style.width = (pedW * 1.3) + 'px';
    floorEl.style.height = (pedH * 0.9) + 'px';
  }
}
window.addEventListener('resize', () => {
  clearTimeout(window._colmHeroResizeTimer);
  window._colmHeroResizeTimer = setTimeout(() => {
    sizeAndRenderHeroChar(colmEquippedAccessoryIds(colmillosEquippedState));
  }, 150);
});
/* particulas decorativas flotando alrededor del heroe (moneditas/destellos SkillCash, no
   colores chillones) - puramente ambientacion, se regeneran cada vez que se entra a la
   pagina para que no se vean siempre en la misma posicion */
/* particulas decorativas: 1 de cada 3 es la moneda SkillCash original (assets/mascot/coin_tooth.png,
   la del tiburoncito doradita - NO la moneda roja del pack nuevo, esa nunca se pidio), el
   resto son destellos rojo/blanco */
function renderColmHeroParticles(){
  const farEl = document.getElementById('colmillosHeroParticlesFar');
  const nearEl = document.getElementById('colmillosHeroParticlesNear');
  const sparkGlyphs = ['✦', '·'];
  const build = (count, near) => Array.from({ length: count }, (_, i) => {
    const left = (5 + Math.random() * 55).toFixed(1);
    const top = (10 + Math.random() * 70).toFixed(1);
    const dur = (4 + Math.random() * 5).toFixed(1);
    const delay = (Math.random() * 6).toFixed(1);
    const drift = (Math.random() * 16 - 8).toFixed(1) + 'px';
    const posStyle = 'left:' + left + '%;top:' + top + '%;--drift:' + drift + ';animation-duration:' + dur + 's;animation-delay:' + delay + 's';
    if(i % 3 === 0){
      return '<span class="colm-hero-particle colm-hero-particle-coin' + (near ? ' near' : '') + '" style="' + posStyle + '"></span>';
    }
    const size = near ? (8 + Math.random() * 4) : (6 + Math.random() * 8);
    const color = i % 2 ? 'var(--hero-red)' : '#fff';
    return '<span class="colm-hero-particle' + (near ? ' near' : '') + '" style="' + posStyle + ';font-size:' + size.toFixed(1) + 'px;color:' + color + '">' + sparkGlyphs[i % sparkGlyphs.length] + '</span>';
  }).join('');
  if(farEl) farEl.innerHTML = build(10, false);
  if(nearEl) nearEl.innerHTML = build(3, true);
}
function renderSharkPreviews(){
  const miniEl = document.getElementById('colmillosCharPreviewMini');
  const loadingSharkEl = document.getElementById('colmillosLoadingShark');
  const accessoryIds = colmEquippedAccessoryIds(colmillosEquippedState);
  if(miniEl) miniEl.innerHTML = sharkImgMarkup(colmillosEquippedState.skin_id, accessoryIds, 62);
  sizeAndRenderHeroChar(accessoryIds);
  // en la pantalla de carga tambien se muestra el tiburon que cada quien configuro (en vez
  // del emoji generico de antes), una vez se sepa su skin
  const startSrc = (colmillosEquippedState.skin_id && SHARK_IMG_PATHS[colmillosEquippedState.skin_id]) || SHARK_IMG_PATHS.default;
  const startImgHtml = '<img src="' + startSrc + '" alt="" style="width:100%;height:100%;object-fit:contain;image-rendering:pixelated;image-rendering:crisp-edges">';
  if(loadingSharkEl) loadingSharkEl.innerHTML = startImgHtml;
  renderColmHeroBackground();
  renderColmillosShopPreview();
  renderColmPowerSheet();
  renderAccountMiniAvatar();
  renderColmHeroCard();
  initColmHeroDebugPanel();
}
/* tarjeta de Heroe en Inicio (.colm-hero-card) - muñeco parado sobre un pedestal + nombre,
   nivel, estrellas y las 6 habilidades en barras de progreso (llenas segun la rareza de lo
   que tenes equipado en cada parte) - pedido explicito de Juan, calcada de una carta de
   personaje de RPG, NO es el HUD chiquito del escenario arcade (eso sigue aparte) */
/* colores fijos por stat (ya NO por rareza - cada barra siempre es del mismo color, lo que
   cambia es cuanto esta llena) - pedido explicito para que la ficha se lea de un vistazo */
const COLM_HERO_STAT_COLOR = {
  instinto: '#8B5CF6', astucia: '#EC4899', vision: '#22D3EE',
  resistencia: '#3B82F6', fuerza: '#F97316', velocidad: 'var(--hero-red)',
};
/* campo de colmillosEquippedState -> slot que usa hero-progress.js (HERO_STAT_BY_SLOT) */
const COLM_FIELD_SLOT = { skin_id: 'skin', accessory_head_id: 'head', accessory_face_id: 'face', accessory_body_id: 'body', accessory_hands_id: 'hands', accessory_feet_id: 'feet' };
const HERO_STAT_BLOCKS = 10;
let colmHCPrevLevel = null, colmHCPrevStars = null;
function renderColmHeroCard(){
  const nameEl = document.getElementById('colmillosHCName');
  if(!nameEl) return;
  if(currentUser){
    const meta = currentUser.user_metadata || {};
    nameEl.textContent = (meta.username || currentUser.email || 'JUGADOR').toUpperCase();
  } else {
    nameEl.textContent = 'INVITADO';
  }
  const info = getColmHeroProgress();
  const lvlEl = document.getElementById('colmillosHCLevel');
  if(lvlEl){
    lvlEl.textContent = info.level;
    if(colmHCPrevLevel !== null && info.level > colmHCPrevLevel){
      lvlEl.classList.remove('pop'); void lvlEl.offsetWidth; lvlEl.classList.add('pop');
    }
  }
  colmHCPrevLevel = info.level;
  const lvlFillEl = document.getElementById('colmillosHCLevelFill');
  // barra = progreso total hacia el nivel 100 (no "hacia el siguiente nivel"), para que
  // coincida 1 a 1 con el numero de NIVEL que se ve justo arriba
  if(lvlFillEl) lvlFillEl.style.width = Math.round(info.progress * 100) + '%';
  const powerEl = document.getElementById('colmillosHCPower');
  if(powerEl) powerEl.textContent = info.power;
  const starsEl = document.getElementById('colmillosHCStars');
  if(starsEl){
    starsEl.innerHTML = Array.from({ length: 5 }, (_, i) =>
      '<span class="' + (i < info.stars ? 'filled' : '') + '">★</span>'
    ).join('');
    starsEl.title = info.nextStarLabel || '5 de 5 estrellas';
    if(colmHCPrevStars !== null && info.stars > colmHCPrevStars){
      starsEl.classList.remove('pop'); void starsEl.offsetWidth; starsEl.classList.add('pop');
    }
  }
  colmHCPrevStars = info.stars;
  const statsEl = document.getElementById('colmillosHCStats');
  if(statsEl){
    statsEl.innerHTML = Object.keys(COLM_POWER_BY_SLOT).map(field => {
      const power = COLM_POWER_BY_SLOT[field];
      const statKey = HERO_STAT_BY_SLOT[COLM_FIELD_SLOT[field]];
      const value = info.stats[statKey] || 0;
      const color = COLM_HERO_STAT_COLOR[statKey];
      const filled = Math.round(value / 100 * HERO_STAT_BLOCKS);
      const blocks = Array.from({ length: HERO_STAT_BLOCKS }, (_, i) =>
        '<span class="colm-hero-info-stat-block' + (i < filled ? ' filled' : '') + '" style="--block-color:' + color + '"></span>'
      ).join('');
      return '<div class="colm-hero-info-stat-row">' +
        '<span class="colm-hero-info-stat-icon">' + power.icon + '</span>' +
        '<span class="colm-hero-info-stat-label">' + power.label + '</span>' +
        '<span class="colm-hero-info-stat-track">' + blocks + '</span>' +
        '<span class="colm-hero-info-stat-num">' + value + '</span>' +
        '</div>';
    }).join('');
  }
  const equipNoteEl = document.getElementById('colmillosHCEquipNote');
  if(equipNoteEl) equipNoteEl.textContent = info.itemsOwned + ' de ' + info.itemsTotal + ' ítems coleccionados';
  const btnEl = document.getElementById('colmillosHCSelectBtn');
  if(btnEl){
    const complete = info.level >= 100;
    btnEl.textContent = complete ? 'COLECCIÓN COMPLETA ✓' : 'IR A LA TIENDA';
    btnEl.disabled = complete;
  }
}
/* modo de depuracion ?heroDebug=1 - botones para simular escenarios de coleccion sin tener
   que comprar/evolucionar de verdad, pensado para verificar la Ficha de Heroe */
let colmHeroDebugOverride = null;
function buildHeroDebugScenario(kind){
  const catalog = buildHeroCatalogForProgress();
  const rareables = catalog.filter(i => i.category === 'skin' || i.category === 'accessory');
  if(kind === 'empty') return { ownedIds: [], rarityById: {}, equippedTiers: [] };
  if(kind === 'full'){
    const ownedIds = catalog.filter(i => i.category !== 'raffle').map(i => i.id);
    const rarityById = {};
    rareables.forEach(i => { rarityById[i.id] = 5; });
    return { ownedIds, rarityById, equippedTiers: [5] };
  }
  if(kind === 'mythic'){
    const one = rareables[0];
    return { ownedIds: one ? [one.id] : [], rarityById: one ? { [one.id]: 5 } : {}, equippedTiers: [5] };
  }
  const pct = kind === '25' ? 0.25 : 0.5;
  const slice = rareables.slice(0, Math.round(rareables.length * pct));
  const rarityById = {};
  slice.forEach(i => { rarityById[i.id] = 5; });
  const ownedIds = catalog.filter(i => i.category === 'background').map(i => i.id).concat(slice.map(i => i.id));
  return { ownedIds, rarityById, equippedTiers: [] };
}
function initColmHeroDebugPanel(){
  if(!/heroDebug=1/.test(location.search)) return;
  if(document.getElementById('colmillosHeroDebugPanel')) return;
  const hero = document.querySelector('.colm-hero');
  if(!hero) return;
  const panel = document.createElement('div');
  panel.id = 'colmillosHeroDebugPanel';
  panel.style.cssText = 'position:absolute;z-index:30;top:3%;left:3%;display:flex;gap:4px;flex-wrap:wrap;max-width:50%';
  [['empty', '0 ítems'], ['25', '25%'], ['50', '50%'], ['mythic', '1 mítico'], ['full', '100%']].forEach(([kind, label]) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    b.style.cssText = 'font-size:10px;padding:3px 8px;border-radius:6px;border:1px solid #fff;background:#000;color:#fff;cursor:pointer';
    b.onclick = () => {
      colmHeroDebugOverride = buildHeroDebugScenario(kind);
      renderColmHeroCard();
      renderColmLevelHud();
    };
    panel.appendChild(b);
  });
  hero.appendChild(panel);
}
function renderColmillosShopPreview(){
  const bigEl = document.getElementById('colmillosCharPreviewBig');
  if(!bigEl) return;
  const skin = 'skin_id' in colmillosShopPreview ? colmillosShopPreview.skin_id : colmillosEquippedState.skin_id;
  const background = 'background_id' in colmillosShopPreview ? colmillosShopPreview.background_id : colmillosEquippedState.background_id;
  const accessoryIds = ACC_SLOTS.map(slot => {
    const field = 'accessory_' + slot + '_id';
    return field in colmillosShopPreview ? colmillosShopPreview[field] : colmillosEquippedState[field];
  }).filter(Boolean);
  bigEl.innerHTML = sharkImgMarkup(skin, accessoryIds, 190);
  const src = BG_IMG_PATHS[background];
  bigEl.style.backgroundImage = src ? ("url('" + src + "')") : '';
  bigEl.classList.toggle('has-bg', !!src);
}
/* "ficha del personaje": 6 poderes decorativos (el color + las 5 partes del cuerpo), cada uno
   al nivel de rareza de lo que de verdad tenes EQUIPADO ahi (no lo que estas previsualizando) -
   son solo para presumir, no cambian nada del minijuego/ruleta/trivia */
function renderColmPowerSheet(){
  const targets = document.querySelectorAll('.colm-power-sheet');
  if(!targets.length) return;
  const html = Object.keys(COLM_POWER_BY_SLOT).map(field => {
    const power = COLM_POWER_BY_SLOT[field];
    const itemId = colmillosEquippedState[field];
    const tierInfo = itemId ? COLM_RARITY_TIERS[colmillosItemRarity.get(itemId) || 1] : null;
    const valueHtml = tierInfo
      ? '<span class="colm-power-dot" style="background:' + tierInfo.color + '"></span>' + tierInfo.name
      : '<span class="colm-power-dot" style="background:var(--muted2)"></span>Sin equipar';
    return '<div class="colm-power-row"><span class="colm-power-icon">' + power.icon + '</span>' +
      '<span class="colm-power-text"><span class="colm-power-label">' + power.label + '</span>' +
      '<span class="colm-power-value">' + valueHtml + '</span></span></div>';
  }).join('');
  targets.forEach(el => { el.innerHTML = html; });
}
/* avatarcito del tiburon - se usa tanto en el botoncito de cuenta (arriba a la derecha) como
   en el circulo grande de "Mi perfil", en vez del emoji generico de siempre, para que se
   sienta que de verdad es "tu" tiburon (con sus accesorios, no solo el color base) en todos
   lados. Todo el mundo ve al menos el diseño basico (aunque no haya tocado la tienda
   todavia), y se recorta de la cintura para arriba (en vez del cuerpo completico) para que
   se note mas grande dentro del circulito - el recorte (x14-74,y8-68 del lienzo de 96x96) se
   logra con background-size/position en vez de un <img>, asi el mismo calculo sirve para
   cualquier tamaño de circulo. Los accesorios se apilan como capas de background adicionales
   (todas comparten el mismo recorte, por eso un solo size/position alcanza para todas) */
function applySharkAvatarCrop(el){
  if(!el) return;
  const skinId = colmillosEquippedState.skin_id;
  const skinSrc = (skinId && SHARK_IMG_PATHS[skinId]) ? SHARK_IMG_PATHS[skinId] : SHARK_IMG_PATHS.default;
  const accessoryIds = colmEquippedAccessoryIds(colmillosEquippedState);
  const layers = accessoryIds.slice().reverse().map(id => ACC_IMG_PATHS[id]).filter(Boolean);
  layers.push(skinSrc);
  el.textContent = '';
  el.style.backgroundImage = layers.map(src => "url('" + src + "')").join(', ');
  el.style.backgroundSize = '160% 160%';
  el.style.backgroundPosition = '38.9% 22.2%';
  el.style.backgroundRepeat = 'no-repeat';
  el.style.imageRendering = 'pixelated';
}
function renderAccountMiniAvatar(){
  applySharkAvatarCrop(document.getElementById('accountMiniBtn'));
  applySharkAvatarCrop(document.getElementById('profileAvatarCircle'));
}
async function loadAccountMiniAvatar(){
  if(!currentUser){ colmillosEquippedState = { ...COLM_EQUIPPED_DEFAULT }; renderAccountMiniAvatar(); return; }
  const { data } = await sbClient.from('user_colmillos_equipped')
    .select('skin_id,accessory_head_id,accessory_face_id,accessory_body_id,accessory_hands_id,accessory_feet_id,background_id')
    .eq('user_id', currentUser.id).maybeSingle();
  colmillosEquippedState = data || { ...COLM_EQUIPPED_DEFAULT };
  renderAccountMiniAvatar();
}
function renderColmHeroBackground(){
  const stage = document.getElementById('colmillosHeroStage');
  if(!stage) return;
  const src = BG_IMG_PATHS[colmillosEquippedState.background_id];
  stage.style.backgroundImage = src ? ("url('" + src + "')") : '';
  stage.classList.toggle('has-bg', !!src);
}

const COLM_DAILY_EVENT_TYPES = ['daily_visit', 'trivia_correct', 'minigame_played'];
async function refreshColmillosPageContent(){
  const balEl = document.getElementById('colmillosBigBalance');
  const nameEl = document.getElementById('colmillosPlayerName');
  const questCards = document.querySelectorAll('#colmillosQuestList .colmillos-quest[data-event]');
  if(!currentUser){
    balEl.textContent = '0';
    if(nameEl) nameEl.textContent = 'INVITADO';
    questCards.forEach(card => {
      const statusEl = card.querySelector('.colmillos-quest-status');
      statusEl.textContent = 'Inicia sesión';
      statusEl.className = 'colmillos-quest-status pending';
    });
    renderSharkPreviews();
    return;
  }
  const meta = currentUser.user_metadata || {};
  if(nameEl) nameEl.textContent = (meta.username || currentUser.email || 'JUGADOR').toUpperCase();
  const ageEl = document.getElementById('colmillosSharkAge');
  if(ageEl) ageEl.textContent = formatSharkAge(currentUser.created_at);
  const { data, error } = await sbClient.from('user_colmillos_events').select('event_type,amount,period_key');
  if(error){ console.warn('no se pudo leer colmillos para la pagina', error); return; }
  const rows = data || [];
  const total = rows.reduce((sum, r) => sum + r.amount, 0);
  animateColmBalance(total);
  const today = todayKeyUTC();
  questCards.forEach(card => {
    const type = card.dataset.event;
    const statusEl = card.querySelector('.colmillos-quest-status');
    const isDaily = COLM_DAILY_EVENT_TYPES.includes(type);
    const inLedger = isDaily
      ? rows.some(r => r.event_type === type && r.period_key === today)
      : rows.some(r => r.event_type === type);
    // "completar tu perfil" antes solo se marcaba si guardabas el nombre DESPUES de que
    // existiera esta mision - mucha gente (incluido Juan) ya tenia nombre de usuario de antes
    // y por eso se veia "Pendiente" para siempre. Ahora se verifica de verdad (¿tiene nombre
    // ahora mismo?) y si corresponde se le abona el premio que le faltaba, una sola vez.
    let done = inLedger;
    if(type === 'profile_completed' && !inLedger && meta.username){
      done = true;
      awardColmillos('profile_completed', 'once', 30).then(() => refreshColmillosPageContent());
    }
    statusEl.textContent = done ? (isDaily ? '✓ Listo hoy' : '✓ Listo') : (isDaily ? 'Hoy pendiente' : 'Pendiente');
    statusEl.className = 'colmillos-quest-status ' + (done ? 'done' : 'pending');
  });
  renderSharkPreviews();
}

/* ---- contador global de toques - una curiosidad compartida entre toda la comunidad, no
   otorga Colmillos. Usa una funcion de Postgres con incremento atomico (increment_global_taps,
   ver scripts/sql/create_colmillos_minigame.sql) para que no se pierdan toques si dos personas
   le dan clic a la moneda al mismo tiempo ---- */
async function loadGlobalTaps(){
  const { data, error } = await sbClient.from('colmillos_global_taps').select('total').eq('id', true).maybeSingle();
  if(error){ console.warn('no se pudo leer el contador global de toques', error); return; }
  const el = document.getElementById('colmillosGlobalTaps');
  if(el) el.textContent = (data ? data.total : 0).toLocaleString('es-CO');
}
async function bumpGlobalTaps(){
  const { data, error } = await sbClient.rpc('increment_global_taps');
  if(error){ console.warn('no se pudo sumar al contador global de toques', error); return; }
  const el = document.getElementById('colmillosGlobalTaps');
  if(el && typeof data === 'number') el.textContent = data.toLocaleString('es-CO');
}

/* ---- trivia diaria: todo el mundo ve la MISMA pregunta el mismo dia, sin necesitar una tabla
   de "pregunta de hoy". Es una COLA real (no un hash puro): se baraja todo el banco una vez
   por "ciclo" (un ciclo = tantos dias como preguntas activas haya) con una semilla fija por
   ciclo, y cada dia del ciclo consume la siguiente pregunta de esa baraja - asi ninguna
   pregunta se repite hasta que TODAS salieron, y el orden barajado cambia de un ciclo al
   siguiente (no es siempre la misma secuencia). .order('id') es necesario para que el orden
   que devuelve Supabase sea el MISMO para todo el mundo (si no, cada quien barajaria un orden
   base distinto y verian preguntas distintas el mismo dia).
   NOTA: igual que el resto de Colmillos, la respuesta correcta viaja al navegador junto con la
   pregunta (no hay Edge Function de por medio) - alguien muy necio podria verla en el inspector,
   pero no tiene sentido real hacerlo por una moneda de coleccion ---- */
let colmillosTriviaQuestions = [];
/* PRNG determinista (mulberry32) - mismo seed siempre da la misma secuencia, en cualquier
   navegador, para que el barajado de cada ciclo sea identico para todo el mundo */
function seededRandom(seed){
  let s = seed >>> 0;
  return function(){
    s = (s + 0x6D2B79F5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function seededShuffle(arr, seed){
  const a = arr.slice();
  const rand = seededRandom(seed);
  for(let i = a.length - 1; i > 0; i--){
    const j = Math.floor(rand() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
async function loadDailyTrivia(){
  if(!currentUser) return;
  if(!colmillosTriviaQuestions.length){
    const { data, error } = await sbClient.from('colmillos_trivia_questions').select('id,question,options,correct_index').eq('active', true).order('id');
    if(error){ console.warn('no se pudo leer la trivia', error); return; }
    colmillosTriviaQuestions = data || [];
  }
  if(!colmillosTriviaQuestions.length) return;
  const today = todayKeyUTC();
  const daysSinceEpoch = Math.floor(Date.parse(today + 'T00:00:00Z') / 86400000);
  const n = colmillosTriviaQuestions.length;
  const cycle = Math.floor(daysSinceEpoch / n);
  const order = seededShuffle(colmillosTriviaQuestions.map((_, i) => i), cycle + 1);
  const todayIndex = order[daysSinceEpoch % n];
  const q = colmillosTriviaQuestions[todayIndex];
  const qEl = document.getElementById('colmillosTriviaQuestion');
  const optsEl = document.getElementById('colmillosTriviaOptions');
  const resultEl = document.getElementById('colmillosTriviaResult');
  qEl.textContent = q.question;
  optsEl.innerHTML = '';
  resultEl.textContent = '';
  resultEl.className = 'colm-trivia-result';
  const { data: existing } = await sbClient.from('user_colmillos_events')
    .select('id').eq('event_type', 'trivia_correct').eq('period_key', today).maybeSingle();
  const alreadyAnswered = !!existing;
  q.options.forEach((opt, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'colm-trivia-opt';
    btn.textContent = opt;
    if(alreadyAnswered){
      btn.classList.add('disabled');
      if(i === q.correct_index) btn.classList.add('correct');
    } else {
      btn.addEventListener('click', () => answerDailyTrivia(i, q.correct_index, optsEl));
    }
    optsEl.appendChild(btn);
  });
  if(alreadyAnswered){
    resultEl.textContent = '✓ Ya respondiste hoy — vuelve mañana por una pregunta nueva.';
    resultEl.classList.add('done');
  }
}
async function answerDailyTrivia(chosenIndex, correctIndex, optsEl){
  const buttons = optsEl.querySelectorAll('.colm-trivia-opt');
  const resultEl = document.getElementById('colmillosTriviaResult');
  if(chosenIndex === correctIndex){
    buttons.forEach((b, i) => { b.classList.add('disabled'); if(i === correctIndex) b.classList.add('correct'); });
    resultEl.textContent = '✓ ¡Correcto! +8 Sharkoins';
    resultEl.classList.add('done');
    await awardColmillos('trivia_correct', todayKeyUTC(), 8);
    refreshColmillosPageContent();
  } else {
    buttons[chosenIndex].classList.add('wrong');
    resultEl.textContent = 'Esa no es — intenta de nuevo.';
    setTimeout(() => buttons[chosenIndex].classList.remove('wrong'), 350);
  }
}

/* ---- tienda / marketplace: comprar = una fila negativa en el mismo ledger de
   user_colmillos_events (period_key='once' para cosmeticos, un uuid por boleto para que los
   boletos de sorteo si se puedan comprar varias veces); equipar = fila en
   user_colmillos_equipped. Ver scripts/sql/create_colmillos_minigame.sql ---- */
// icono de la moneda real (el lado "tiburon" de las dos caras del Sharkoin, ver linea ~27571)
// para los precios de la tienda - antes se usaba el emoji generico 🦷, que se confundia con
// un diente de verdad en vez de la moneda que inventamos
const COLM_COIN_ICON_HTML = '<img src="assets/mascot/coin_tooth.png" alt="Sharkoins" style="width:14px;height:14px;vertical-align:-2px;image-rendering:pixelated;image-rendering:crisp-edges">';
const COLM_SHOP_ICONS = { skin_gold: '🦈', skin_red: '🦈', skin_abyss: '🦈', skin_emerald: '🦈', skin_cyan: '🦈', skin_pink: '🦈', skin_orange: '🦈', skin_ice: '🦈', skin_lime: '🦈', skin_violet: '🦈', skin_camo: '🦈', skin_tiger: '🦈', skin_galaxy: '🦈', skin_arcoiris: '🦈', skin_oroliquido: '🦈', skin_neon: '🦈', skin_dragon: '🦈', skin_martillo: '🦈', skin_rayosx: '🦈', acc_cap: '🧢', acc_shades: '🕶️', acc_chain: '📿', acc_scuba: '🤿', acc_scarf: '🧣', acc_headphones: '🎧', acc_crown: '👑', acc_cape: '🏴‍☠️', acc_sombrero: '🪄', acc_antifaz: '🦸', acc_aletarobot: '🤖', acc_collar: '🌺', acc_paraguas: '☂️', acc_guantes: '🥊', acc_microfono: '🎤', acc_bate: '⚾', acc_escudo: '🛡️', acc_espada: '⚔️', acc_mazo: '🔨', acc_raqueta: '🎾', acc_varita: '🪄', acc_aletasbuceo: '🤿', acc_botasnieve: '🥾', acc_botaspirata: '👢', acc_patines: '⛸️', acc_sandalias: '🩴', acc_tenis: '👟', bg_reef: '🪸', bg_abyss: '🌑', bg_surface: '☀️', bg_sunken_city: '🏛️', bg_volcano: '🌋', bg_night: '🌙', bg_nave: '🛸', bg_tormenta: '⛈️', bg_playa: '🏖️', bg_laboratorio: '🧪', bg_atardecer: '🌅', bg_selva: '🌴', bg_cueva: '💎', bg_neon: '🌃', bg_pradera: '🌼', bg_nieve: '❄️', bg_desierto: '🏜️', raffle_ticket: '🎟️' };
const COLM_EQUIP_FIELD = { skin: 'skin_id', background: 'background_id' };
const COLM_GRID_EL = { skin: 'colmillosShopSkins', accessory: 'colmillosShopAccessories', background: 'colmillosShopBackgrounds', raffle: 'colmillosShopRaffle' };
/* la tienda depende de 2 pedidos a Supabase (catalogo + ledger) - en una conexion lenta o
   inestable cualquiera de los dos puede fallar. Antes, si fallaba, la funcion se detenia en
   silencio y la tienda quedaba vacia para siempre sin avisar nada (se sentia como "no deja
   comprar nada"). Ahora se reintenta un par de veces con una pequeña espera entre intentos, y
   si de plano no se pudo, se muestra un mensaje real con boton de Reintentar en vez de dejar
   las cajitas vacias sin explicacion */
async function colmFetchWithRetry(fn, attempts){
  attempts = attempts || 3;
  let lastErr = null;
  for(let i = 0; i < attempts; i++){
    const { data, error } = await fn();
    if(!error) return { data, error: null };
    lastErr = error;
    if(i < attempts - 1) await new Promise(resolve => setTimeout(resolve, 700 * (i + 1)));
  }
  return { data: null, error: lastErr };
}
function showColmShopLoadError(){
  const grid = document.getElementById(COLM_GRID_EL.skin);
  if(!grid) return;
  grid.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.className = 'colm-shop-error';
  wrap.innerHTML = '<p>⚠️ No se pudo cargar la tienda — puede ser tu conexión.</p>';
  const retryBtn = document.createElement('button');
  retryBtn.type = 'button';
  retryBtn.className = 'colm-shop-item-btn';
  retryBtn.textContent = 'Reintentar';
  retryBtn.addEventListener('click', loadColmillosShop);
  wrap.appendChild(retryBtn);
  grid.appendChild(wrap);
}
async function loadColmillosShop(){
  if(!currentUser) return;
  colmillosShopPreview = {};
  if(!colmillosShopItemsCache.length){
    const { data: items, error: itemsErr } = await colmFetchWithRetry(() => sbClient.from('colmillos_shop_items').select('id,category,name,price').order('price'));
    if(itemsErr){ console.warn('no se pudo leer la tienda de colmillos', itemsErr); showColmShopLoadError(); return; }
    colmillosShopItemsCache = items || [];
  }
  const { data: ledgerRows, error: ledgerErr } = await colmFetchWithRetry(() => sbClient.from('user_colmillos_events').select('event_type,amount,period_key'));
  if(ledgerErr){ console.warn('no se pudo leer el saldo para la tienda', ledgerErr); showColmShopLoadError(); return; }
  const rows = ledgerRows || [];
  colmillosOwnedItemIds = new Set(
    rows.filter(r => r.event_type.indexOf('purchase_') === 0 && r.event_type !== 'purchase_raffle_ticket')
        .map(r => r.event_type.slice('purchase_'.length))
  );
  // rareza actual de cada familia poseida: Común (tier 1) en cuanto se compra, y sube un
  // escalon por cada fila evolve_<id>/tierN que exista en el ledger (ver COLM_EVOLVE_COST)
  colmillosItemRarity = new Map();
  colmillosOwnedItemIds.forEach(id => {
    let tier = 1;
    for(let t = 5; t >= 2; t--){
      if(rows.some(r => r.event_type === 'evolve_' + id && r.period_key === 'tier' + t)){ tier = t; break; }
    }
    colmillosItemRarity.set(id, tier);
  });
  // el dueno (Juan) YA NO tiene todo desbloqueado/al maximo de rareza gratis aca - para poder
  // probar la tienda y las evoluciones tal cual las ve cualquier usuario, su cuenta pasa por el
  // mismo calculo de arriba (ownedItemIds/rarity derivados 100% de su propio ledger), solo que
  // con un saldo bien grande de Sharkoins de prueba (ver scripts/sql/colm_owner_test_reset.sql)
  renderColmLevelHud();
  renderColmHeroCard();
  const raffleTickets = rows.filter(r => r.event_type === 'purchase_raffle_ticket').length;
  // maximo 1 boleto por mes (el periodKey de la compra es el mes 'YYYY-MM', ver buyColmillosItem)
  colmillosRaffleBoughtThisMonth = rows.some(r => r.event_type === 'purchase_raffle_ticket' && r.period_key === todayKeyUTC().slice(0, 7));
  const balance = rows.reduce((sum, r) => sum + r.amount, 0);
  const { data: equippedRow } = await sbClient.from('user_colmillos_equipped')
    .select('skin_id,accessory_head_id,accessory_face_id,accessory_body_id,accessory_hands_id,accessory_feet_id,background_id').eq('user_id', currentUser.id).maybeSingle();
  colmillosEquippedState = equippedRow || { ...COLM_EQUIPPED_DEFAULT };
  renderSharkPreviews();
  renderColmillosShopGrids(balance);
  const raffleEl = document.getElementById('colmillosRaffleCount');
  if(raffleEl) raffleEl.textContent = 'Tenés ' + raffleTickets + ' boleto' + (raffleTickets === 1 ? '' : 's') + '. Juan elige al ganador en los sorteos que anuncia en Telegram.';
}
/* a que "parte del cuerpo" va cada accesorio - cada parte tiene su propia columna en
   user_colmillos_equipped (accessory_head_id, accessory_face_id, ...), asi se pueden llevar
   puestas varias a la vez sin que una se quite a la otra */
const ACC_SLOT_MAP = {
  acc_cap: 'head', acc_crown: 'head', acc_sombrero: 'head', acc_headphones: 'head', acc_scuba: 'head',
  acc_shades: 'face', acc_antifaz: 'face', acc_laser: 'face', acc_corazon: 'face', acc_monoculo: 'face', acc_gafas3d: 'face', acc_cyberpunk: 'face', acc_buceo: 'face',
  acc_chain: 'body', acc_scarf: 'body', acc_cape: 'body', acc_collar: 'body', acc_aletarobot: 'body',
  acc_microfono: 'hands', acc_guantes: 'hands', acc_paraguas: 'hands', acc_bate: 'hands', acc_escudo: 'hands', acc_espada: 'hands', acc_mazo: 'hands', acc_raqueta: 'hands', acc_varita: 'hands',
  acc_aletasbuceo: 'feet', acc_botasnieve: 'feet', acc_botaspirata: 'feet', acc_patines: 'feet', acc_sandalias: 'feet', acc_tenis: 'feet',
};
function colmAccessoryFieldFor(itemId){ return 'accessory_' + (ACC_SLOT_MAP[itemId] || 'body') + '_id'; }
function renderColmillosShopGrids(balance){
  ['skin', 'accessory', 'background', 'raffle'].forEach(cat => {
    const grid = document.getElementById(COLM_GRID_EL[cat]);
    if(!grid) return;
    grid.innerHTML = '';
    grid.classList.toggle('colm-shop-bg-grid', cat === 'background');
    if(cat === 'accessory'){
      // una cajita de "Ninguno" POR CADA parte del cuerpo (no una sola para todo el
      // accesorio), para poder quitarte solo lo de la cabeza sin afectar cara/cuerpo/manos
      ACC_SLOTS.forEach(slot => {
        const field = 'accessory_' + slot + '_id';
        const isDefaultEquipped = !colmillosEquippedState[field];
        const card = document.createElement('div');
        card.className = 'colm-shop-item';
        card.dataset.slot = slot;
        const swatch = document.createElement('div');
        swatch.className = 'colm-shop-item-swatch';
        swatch.textContent = '🚫';
        swatch.style.cursor = 'pointer';
        swatch.title = 'Ver cómo se ve';
        swatch.addEventListener('click', () => {
          colmillosShopPreview[field] = null;
          renderColmillosShopPreview();
        });
        const name = document.createElement('div');
        name.className = 'colm-shop-item-name';
        name.textContent = 'Ninguno';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'colm-shop-item-btn' + (isDefaultEquipped ? ' equipped' : ' owned');
        btn.textContent = isDefaultEquipped ? '✓ Equipado' : 'Equipar';
        btn.disabled = isDefaultEquipped;
        if(!isDefaultEquipped) btn.addEventListener('click', () => equipColmillosItem(field, null));
        card.appendChild(swatch); card.appendChild(name); card.appendChild(btn);
        grid.appendChild(card);
      });
    } else if(cat === 'background'){
      const equipField = COLM_EQUIP_FIELD[cat];
      const isDefaultEquipped = !colmillosEquippedState[equipField];
      const card = document.createElement('div');
      card.className = 'colm-shop-bg-item';
      const swatch = document.createElement('div');
      swatch.className = 'colm-shop-bg-swatch';
      swatch.textContent = '🌊';
      swatch.style.cursor = 'pointer';
      swatch.title = 'Ver cómo se ve';
      swatch.addEventListener('click', () => {
        colmillosShopPreview[equipField] = null;
        renderColmillosShopPreview();
      });
      const name = document.createElement('div');
      name.className = 'colm-shop-bg-name';
      name.textContent = 'Default';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'colm-shop-item-btn' + (isDefaultEquipped ? ' equipped' : ' owned');
      btn.textContent = isDefaultEquipped ? '✓ Equipado' : 'Equipar';
      btn.disabled = isDefaultEquipped;
      if(!isDefaultEquipped) btn.addEventListener('click', () => equipColmillosItem(equipField, null));
      card.appendChild(swatch); card.appendChild(name); card.appendChild(btn);
      grid.appendChild(card);
    }
    colmillosShopItemsCache.filter(it => it.category === cat).forEach(item => {
      const isBg = cat === 'background';
      const card = document.createElement('div');
      card.className = isBg ? 'colm-shop-bg-item' : 'colm-shop-item';
      if(cat === 'accessory') card.dataset.slot = ACC_SLOT_MAP[item.id] || 'body';
      const swatch = document.createElement('div');
      swatch.className = isBg ? 'colm-shop-bg-swatch' : 'colm-shop-item-swatch';
      swatch.style.cursor = 'pointer';
      swatch.title = 'Ver cómo se ve';
      const equipField = cat === 'accessory' ? colmAccessoryFieldFor(item.id) : COLM_EQUIP_FIELD[cat];
      if(cat === 'skin'){
        swatch.innerHTML = sharkImgMarkup(item.id, colmEquippedAccessoryIds(colmillosEquippedState), 64);
        swatch.style.background = 'none';
      } else if(cat === 'accessory'){
        const otherIds = colmEquippedAccessoryIds(colmillosEquippedState).filter(id => ACC_SLOT_MAP[id] !== ACC_SLOT_MAP[item.id]);
        swatch.innerHTML = sharkImgMarkup(colmillosEquippedState.skin_id, [...otherIds, item.id], 64);
        swatch.style.background = 'none';
      } else if(isBg && BG_IMG_PATHS[item.id]){
        swatch.style.backgroundImage = "url('" + BG_IMG_PATHS[item.id] + "')";
        swatch.style.backgroundSize = 'cover';
        swatch.style.backgroundPosition = 'center bottom';
      } else {
        swatch.textContent = COLM_SHOP_ICONS[item.id] || '🦷';
      }
      if(COLM_RARITY_CATEGORIES.has(cat) && colmillosOwnedItemIds.has(item.id)){
        // gema de color en la esquina = rareza actual de esta familia (como el "diamantico"
        // de los juegos de coleccion) - solo se muestra si ya se tiene, nada que presumir antes
        const tierInfo = COLM_RARITY_TIERS[colmillosItemRarity.get(item.id) || 1];
        const gem = document.createElement('div');
        gem.className = 'colm-rarity-gem';
        gem.style.background = tierInfo.color;
        gem.title = tierInfo.name;
        swatch.appendChild(gem);
      }
      if(cat !== 'raffle'){
        swatch.addEventListener('click', () => {
          colmillosShopPreview[equipField] = item.id;
          renderColmillosShopPreview();
        });
      }
      const name = document.createElement('div');
      name.className = isBg ? 'colm-shop-bg-name' : 'colm-shop-item-name';
      name.textContent = item.name;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'colm-shop-item-btn';
      card.appendChild(swatch); card.appendChild(name); card.appendChild(btn);
      if(cat === 'raffle'){
        if(colmillosRaffleBoughtThisMonth){
          btn.textContent = '✓ Ya tenés tu boleto de este mes';
          btn.classList.add('owned');
          btn.disabled = true;
        } else {
          btn.innerHTML = item.price + ' ' + COLM_COIN_ICON_HTML + ' comprar boleto';
          btn.disabled = balance < item.price;
          btn.addEventListener('click', () => buyColmillosItem(item));
        }
      } else {
        const owned = colmillosOwnedItemIds.has(item.id);
        const isEquipped = owned && colmillosEquippedState[equipField] === item.id;
        if(isEquipped){
          btn.textContent = '✓ Equipado';
          btn.classList.add('equipped');
          btn.disabled = true;
        } else if(owned){
          btn.textContent = 'Equipar';
          btn.classList.add('owned');
          btn.addEventListener('click', () => equipColmillosItem(equipField, item.id));
        } else {
          btn.innerHTML = item.price + ' ' + COLM_COIN_ICON_HTML + ' comprar';
          btn.disabled = balance < item.price;
          btn.addEventListener('click', () => buyColmillosItem(item));
          // antes la unica forma de "probarselo" era tocar la imagen, nada le decia a la gente
          // que podian ver como se veria ANTES de comprarlo - ahora hay un boton explicito para
          // eso, separado del de comprar (mismo mecanismo que ya usaba el click en la imagen)
          const viewBtn = document.createElement('button');
          viewBtn.type = 'button';
          viewBtn.className = 'colm-view-btn';
          viewBtn.textContent = '👁️ Visualizar';
          viewBtn.addEventListener('click', () => {
            colmillosShopPreview[equipField] = item.id;
            renderColmillosShopPreview();
          });
          card.insertBefore(viewBtn, btn);
        }
        if(COLM_RARITY_CATEGORIES.has(cat) && owned){
          // evolucionar: la MISMA pieza sube de rareza (nunca se compra una nueva) - hay que
          // ir en orden, un escalon a la vez, y cada escalon cuesta mas que el anterior
          const tier = colmillosItemRarity.get(item.id) || 1;
          if(tier < 5){
            const nextTier = tier + 1;
            const cost = COLM_EVOLVE_COST[nextTier];
            const nextInfo = COLM_RARITY_TIERS[nextTier];
            const evoBtn = document.createElement('button');
            evoBtn.type = 'button';
            evoBtn.className = 'colm-evolve-btn';
            evoBtn.innerHTML = '⬆️ Evolucionar a ' + nextInfo.name + ' — ' + cost + ' ' + COLM_COIN_ICON_HTML;
            evoBtn.disabled = balance < cost;
            evoBtn.addEventListener('click', () => evolveColmillosItem(item, tier));
            card.appendChild(evoBtn);
          } else {
            const maxedEl = document.createElement('div');
            maxedEl.className = 'colm-rarity-maxed';
            maxedEl.textContent = '✨ Mítico (máx)';
            card.appendChild(maxedEl);
          }
        }
      }
      grid.appendChild(card);
    });
  });
  applyColmShopSubtabFilter();
}
async function buyColmillosItem(item){
  if(!currentUser) return;
  const { data: rows } = await sbClient.from('user_colmillos_events').select('amount');
  const balance = (rows || []).reduce((sum, r) => sum + r.amount, 0);
  if(balance < item.price){ loadColmillosShop(); return; }
  const isRaffle = item.category === 'raffle';
  const eventType = isRaffle ? 'purchase_raffle_ticket' : ('purchase_' + item.id);
  // el boleto de sorteo usa el MES actual como period_key (en vez de un uuid por compra) para
  // que el unique(user_id,event_type,period_key) de la tabla bloquee solo, sin logica aparte,
  // una segunda compra el mismo mes - maximo 1 boleto por cuenta por mes (pedido explicito,
  // el premio es real asi que no puede ser ilimitado)
  const periodKey = isRaffle ? todayKeyUTC().slice(0, 7) : 'once';
  const { error } = await sbClient.from('user_colmillos_events').insert({
    user_id: currentUser.id, event_type: eventType, period_key: periodKey, amount: -item.price,
  });
  if(error && error.code === '23505' && isRaffle){
    alert('Ya compraste tu boleto de este mes — el próximo se habilita el 1.');
    await loadColmillosShop();
    return;
  }
  if(error && error.code !== '23505'){ alert(friendlyErrMsg(error)); return; }
  await loadColmillosShop();
  loadColmillosBalance(true);
}
/* evolucionar una familia que ya se tiene a la siguiente rareza - paga COLM_EVOLVE_COST[nextTier]
   y queda una fila mas en el mismo ledger de siempre (event_type='evolve_<id>',
   period_key='tier<N>'), nunca una compra nueva ni un item distinto */
async function evolveColmillosItem(item, currentTier){
  if(!currentUser) return;
  const nextTier = currentTier + 1;
  const cost = COLM_EVOLVE_COST[nextTier];
  if(!cost) return;
  const { data: rows } = await sbClient.from('user_colmillos_events').select('amount');
  const balance = (rows || []).reduce((sum, r) => sum + r.amount, 0);
  if(balance < cost){ loadColmillosShop(); return; }
  const { error } = await sbClient.from('user_colmillos_events').insert({
    user_id: currentUser.id, event_type: 'evolve_' + item.id, period_key: 'tier' + nextTier, amount: -cost,
  });
  if(error && error.code !== '23505'){ alert(friendlyErrMsg(error)); return; }
  await loadColmillosShop();
  loadColmillosBalance(true);
}
async function equipColmillosItem(field, itemId){
  if(!currentUser) return;
  const payload = {
    user_id: currentUser.id,
    skin_id: colmillosEquippedState.skin_id,
    accessory_head_id: colmillosEquippedState.accessory_head_id,
    accessory_face_id: colmillosEquippedState.accessory_face_id,
    accessory_body_id: colmillosEquippedState.accessory_body_id,
    accessory_hands_id: colmillosEquippedState.accessory_hands_id,
    accessory_feet_id: colmillosEquippedState.accessory_feet_id,
    background_id: colmillosEquippedState.background_id,
    updated_at: new Date().toISOString(),
  };
  payload[field] = itemId;
  const { error } = await sbClient.from('user_colmillos_equipped').upsert(payload, { onConflict: 'user_id' });
  if(error){ console.warn('no se pudo equipar', error); return; }
  await loadColmillosShop();
}

/* ---- minijuego: version propia del "dinosaurio" de Chrome, con el tiburon saltando rocas -
   el fondo/obstaculos siguen en vectores, pero el personaje ahora es el sprite real de
   assets/mascot/ dibujado con drawImage. +3 Colmillos una vez al dia si se llega a 150. ---- */
/* sonidos del minijuego sintetizados con el propio navegador (osciladores de Web Audio),
   sin archivos de audio que descargar - igual que el "beep" del salto y el golpe del dino
   de Chrome. El AudioContext solo se crea/retoma dentro de un gesto real del usuario (el
   primer salto), que es justo cuando los navegadores lo permiten */
let colmAudioCtx = null;
// preferencia de silencio del minijuego - se guarda en localStorage para que quede recordada
// la proxima vez que alguien entre, igual que el mejor puntaje del dia
let colmGameMuted = false;
try { colmGameMuted = localStorage.getItem('colm_game_muted') === '1'; } catch(e){}
function colmPlayTone(freq, duration, type, gainStart){
  if(colmGameMuted) return;
  try {
    if(!colmAudioCtx) colmAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if(colmAudioCtx.state === 'suspended') colmAudioCtx.resume();
    const osc = colmAudioCtx.createOscillator();
    const gain = colmAudioCtx.createGain();
    osc.type = type || 'square';
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(gainStart || 0.12, colmAudioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, colmAudioCtx.currentTime + duration);
    osc.connect(gain);
    gain.connect(colmAudioCtx.destination);
    osc.start();
    osc.stop(colmAudioCtx.currentTime + duration);
  } catch(e){ /* navegador sin Web Audio o bloqueado - el juego sigue andando sin sonido */ }
}
function colmPlayJumpSound(){ colmPlayTone(620, 0.09, 'square', 0.1); }
function colmPlayMilestoneSound(){ colmPlayTone(880, 0.07, 'sine', 0.08); }
function colmPlayGameOverSound(){ colmPlayTone(160, 0.35, 'sawtooth', 0.12); }

function updateColmGameMuteBtn(){
  const btn = document.getElementById('colmGameMuteBtn');
  if(!btn) return;
  btn.textContent = colmGameMuted ? '🔇' : '🔊';
  btn.classList.toggle('muted', colmGameMuted);
  btn.title = colmGameMuted ? 'Activar sonido del juego' : 'Silenciar sonido del juego';
}
document.getElementById('colmGameMuteBtn').addEventListener('click', () => {
  colmGameMuted = !colmGameMuted;
  try { localStorage.setItem('colm_game_muted', colmGameMuted ? '1' : '0'); } catch(e){}
  updateColmGameMuteBtn();
});
updateColmGameMuteBtn();

/* antes la caja de colision del tiburon (60x28, fija) era MAS ANCHA que el sprite que
   realmente se veia (46x46 forzado a cuadrado sin respetar su proporcion real) - por eso a
   veces "chocaba" sin que se viera el golpe, y de paso el sprite se veia estirado/"espichado".
   Ahora el tamaño de dibujo y la caja de colision salen de la MISMA cuenta
   (getColmSharkDrawBox, basada en el ancho/alto real de la imagen), asi nunca se desincronizan */
const COLM_JUMP_VY = -12.6;
const COLM_GRAVITY = 0.81;
const COLM_INITIAL_SPEED = 6.3;
const COLM_SPEED_INC = 0.00375;
const colmGame = { canvas: null, ctx: null, raf: null, state: 'idle', sharkY: 206, sharkVY: 0, groundY: 206, jumping: false, obstacles: [], clouds: [], groundOffset: 0, speed: COLM_INITIAL_SPEED, score: 0, lastSpawn: 0, frame: 0, lastMilestone: 0 };
function initColmGameOnce(){
  if(colmGame.canvas) return;
  colmGame.canvas = document.getElementById('colmillosGameCanvas');
  colmGame.ctx = colmGame.canvas.getContext('2d');
  colmGame.ctx.imageSmoothingEnabled = false;
  colmGame.groundY = colmGame.canvas.height - 14;
  colmGame.sharkY = colmGame.groundY;
  // nubes decorativas tipo dino de Chrome, repartidas al ancho real del canvas
  colmGame.clouds = [0, 1, 2].map((i) => ({
    x: (colmGame.canvas.width / 3) * i + Math.random() * 60,
    y: 22 + Math.random() * 40,
    s: 0.8 + Math.random() * 0.5,
  }));
  const jump = () => {
    if(colmGame.state === 'idle' || colmGame.state === 'over'){ startColmGame(); return; }
    if(colmGame.state === 'playing' && !colmGame.jumping){ colmGame.jumping = true; colmGame.sharkVY = COLM_JUMP_VY; colmPlayJumpSound(); }
  };
  colmGame.canvas.addEventListener('click', jump);
  window.addEventListener('keydown', (e) => {
    if(e.code === 'Space' && colmGame.canvas.offsetParent !== null){ e.preventDefault(); jump(); }
  });
}
function startColmGame(){
  colmGame.state = 'playing';
  colmGame.sharkY = colmGame.groundY;
  colmGame.sharkVY = 0;
  colmGame.jumping = false;
  colmGame.obstacles = [];
  colmGame.groundOffset = 0;
  colmGame.speed = COLM_INITIAL_SPEED;
  colmGame.score = 0;
  colmGame.frame = 0;
  colmGame.lastSpawn = 0;
  colmGame.lastMilestone = 0;
  document.getElementById('colmillosGameHint').textContent = 'Saltá tocando el juego o con ESPACIO';
  cancelAnimationFrame(colmGame.raf);
  colmGameLoop();
}
function colmGameLoop(){
  colmGame.frame++;
  colmGame.sharkVY += COLM_GRAVITY;
  colmGame.sharkY += colmGame.sharkVY;
  if(colmGame.sharkY >= colmGame.groundY){ colmGame.sharkY = colmGame.groundY; colmGame.sharkVY = 0; colmGame.jumping = false; }
  if(colmGame.frame - colmGame.lastSpawn > Math.max(45, 90 - colmGame.score / 8)){
    colmGame.lastSpawn = colmGame.frame;
    colmGame.obstacles.push({ x: colmGame.canvas.width, w: 20 + Math.random() * 16, h: 30 + Math.random() * 26 });
  }
  colmGame.obstacles.forEach(o => { o.x -= colmGame.speed; });
  colmGame.obstacles = colmGame.obstacles.filter(o => o.x + o.w > 0);
  colmGame.groundOffset += colmGame.speed;
  colmGame.clouds.forEach(c => {
    c.x -= colmGame.speed * 0.18;
    if(c.x < -60){ c.x = colmGame.canvas.width + Math.random() * 40; c.y = 20 + Math.random() * 44; c.s = 0.8 + Math.random() * 0.5; }
  });
  colmGame.speed += COLM_SPEED_INC;
  colmGame.score++;
  document.getElementById('colmillosGameScore').textContent = colmGame.score;
  const milestone = Math.floor(colmGame.score / 100);
  if(milestone > colmGame.lastMilestone){ colmGame.lastMilestone = milestone; colmPlayMilestoneSound(); }
  const sb = getColmSharkDrawBox(getSharkImg(colmillosEquippedState.skin_id));
  // caja de colision un poco mas chica que el dibujo real (igual que el dino de Chrome, que
  // tambien perdona el contorno exacto del sprite) para que el choque se sienta justo
  const sharkBox = { x: sb.dx + sb.dw * 0.18, y: sb.dy + sb.dh * 0.12, w: sb.dw * 0.64, h: sb.dh * 0.8 };
  const hit = colmGame.obstacles.some(o => {
    const baseY = colmGame.canvas.height - 14 - o.h;
    const oBox = { x: o.x + o.w * 0.12, y: baseY + o.h * 0.08, w: o.w * 0.76, h: o.h * 0.92 };
    return sharkBox.x < oBox.x + oBox.w && sharkBox.x + sharkBox.w > oBox.x && sharkBox.y < oBox.y + oBox.h && sharkBox.y + sharkBox.h > oBox.y;
  });
  if(hit){ endColmGame(); return; }
  drawColmGame();
  colmGame.raf = requestAnimationFrame(colmGameLoop);
}
/* estilo "dino de Chrome": mismo fondo plano del sitio (nada de imagen/degradado propio) y
   obstaculos como siluetas blancas solidas, no cuadros de color - lo unico que cambia frente
   al dino original es el muñeco, que sigue siendo el tiburon equipado de cada quien */
function drawColmObstacle(ctx, o, canvas){
  const baseY = canvas.height - 14;
  const topY = baseY - o.h;
  ctx.fillStyle = '#f4f4f4';
  // "cactus" simple: un cuerpo central mas dos brazos cortos, todo en silueta solida
  const bodyW = o.w * 0.44;
  const bodyX = o.x + (o.w - bodyW) / 2;
  ctx.fillRect(bodyX, topY, bodyW, o.h);
  const armW = o.w * 0.3, armH = o.h * 0.4;
  ctx.fillRect(o.x, topY + o.h * 0.18, armW, armH);
  ctx.fillRect(o.x + o.w - armW, topY + o.h * 0.38, armW, armH);
}
function drawColmCloud(ctx, c){
  ctx.beginPath();
  ctx.ellipse(c.x, c.y, 22 * c.s, 11 * c.s, 0, 0, Math.PI * 2);
  ctx.ellipse(c.x + 16 * c.s, c.y - 6 * c.s, 15 * c.s, 10 * c.s, 0, 0, Math.PI * 2);
  ctx.ellipse(c.x - 16 * c.s, c.y - 4 * c.s, 13 * c.s, 9 * c.s, 0, 0, Math.PI * 2);
  ctx.fill();
}
// el tamaño/posicion de dibujo del tiburon y su caja de colision salen de la MISMA cuenta
// (ancho/alto reales de la imagen) para que nunca se desincronicen entre si
function getColmSharkDrawBox(sharkImg){
  const maxSize = 64;
  const ratio = (sharkImg && sharkImg.naturalWidth) ? sharkImg.naturalWidth / sharkImg.naturalHeight : 1;
  const dw = ratio >= 1 ? maxSize : maxSize * ratio;
  const dh = ratio >= 1 ? maxSize / ratio : maxSize;
  return { dx: 18, dy: colmGame.sharkY + 8 - dh, dw, dh };
}
function drawColmGame(){
  const { ctx, canvas } = colmGame;
  ctx.fillStyle = '#080c20';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = 'rgba(255,255,255,.14)';
  colmGame.clouds.forEach(c => drawColmCloud(ctx, c));

  const groundLineY = canvas.height - 14;
  ctx.strokeStyle = 'rgba(255,255,255,.5)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, groundLineY);
  ctx.lineTo(canvas.width, groundLineY);
  ctx.stroke();
  // guiones del "camino" que se desplazan con groundOffset - el dino original tambien trae
  // esta textura, antes aca solo habia una linea sola
  ctx.fillStyle = 'rgba(255,255,255,.35)';
  const dashW = 18, dashGap = 14, dashSpan = dashW + dashGap;
  const offset = colmGame.groundOffset % dashSpan;
  for(let x = -offset; x < canvas.width; x += dashSpan){
    ctx.fillRect(x, groundLineY + 5, dashW, 3);
  }

  colmGame.obstacles.forEach(o => drawColmObstacle(ctx, o, canvas));

  const sharkImg = getSharkImg(colmillosEquippedState.skin_id);
  if(sharkImg.complete && sharkImg.naturalWidth){
    const sb = getColmSharkDrawBox(sharkImg);
    ctx.drawImage(sharkImg, sb.dx, sb.dy, sb.dw, sb.dh);
  }

  if(colmGame.state === 'idle'){
    ctx.fillStyle = 'rgba(255,255,255,.85)';
    ctx.font = 'bold 16px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('TOCÁ PARA EMPEZAR', canvas.width / 2, canvas.height / 2);
  }
}
function endColmGame(){
  colmGame.state = 'over';
  cancelAnimationFrame(colmGame.raf);
  colmPlayGameOverSound();
  const bestKey = 'colm_best_' + todayKeyUTC();
  let best = 0;
  try { best = parseInt(localStorage.getItem(bestKey) || '0', 10) || 0; } catch(e){}
  if(colmGame.score > best){
    best = colmGame.score;
    try { localStorage.setItem(bestKey, String(best)); } catch(e){}
  }
  document.getElementById('colmillosGameBest').textContent = best;
  document.getElementById('colmillosGameHint').textContent = 'Te chocaste — puntaje ' + colmGame.score + '. Tocá para volver a intentar.';
  drawColmGame();
  const { ctx, canvas } = colmGame;
  ctx.fillStyle = 'rgba(0,0,0,.45)';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 22px monospace';
  ctx.textAlign = 'center';
  ctx.fillText('GAME OVER', canvas.width / 2, canvas.height / 2 - 10);
  ctx.font = '14px monospace';
  ctx.fillText('toca para reintentar', canvas.width / 2, canvas.height / 2 + 20);
  if(colmGame.score >= 1500 && typeof awardColmillos === 'function'){
    awardColmillos('minigame_played', todayKeyUTC(), 10).then(() => refreshColmillosPageContent());
  }
  // cada partida jugada (con puntaje > 0) queda en el historial para el ranking semanal/mensual
  // (ver scripts/sql/create_colm_leaderboard.sql) - el "mejor de la semana/mes" se calcula alla
  // mismo con MAX(score), asi que mandar cada partida (no solo el record) es lo correcto
  if(currentUser && colmGame.score > 0){
    sbClient.from('colm_game_scores').insert({ user_id: currentUser.id, score: colmGame.score }).then(({ error }) => {
      if(error) console.warn('no se pudo guardar el puntaje para el ranking', error);
      else if(typeof loadColmLeaderboard === 'function') loadColmLeaderboard(colmLbPeriod);
    });
  }
}

/* ---- pestañas internas de la pagina (Inicio/Trivia/Minijuego/Tienda) ---- */
/* ---- ruleta: solo diversion, apuesta y gana/pierde Colmillos al azar. Valor esperado
   neutro (ni favorece a la casa ni al jugador) - 4 de 8 segmentos pierden la apuesta, los
   otros 4 pagan 1.5x/2x/3x, promediando exactamente 1x. Usa el mismo ledger de siempre
   (event_type='casino_spin', period_key aleatorio porque se puede jugar muchas veces) ---- */
const ROULETTE_SEGMENTS = [
  { mult: 0, color: '#2c2140', label: '0x' },
  { mult: 1.5, color: '#d9a441', label: '1.5x' },
  { mult: 0, color: '#2c2140', label: '0x' },
  { mult: 2, color: '#c23b4a', label: '2x' },
  { mult: 0, color: '#2c2140', label: '0x' },
  { mult: 1.5, color: '#d9a441', label: '1.5x' },
  { mult: 3, color: '#4ade80', label: '3x' },
  { mult: 0, color: '#2c2140', label: '0x' },
];
let colmRouletteSpinning = false;
let colmRouletteTotalRotation = 0;
/* antes la rueda era solo un div con un conic-gradient de colores - no decia en ningun lado
   que era cada pedazo. Ahora se dibuja como SVG con el multiplicador escrito en cada gajo
   (texto blanco con borde oscuro, se lee igual de bien sobre cualquier color de fondo) y
   abajo una leyenda aparte con que gana/pierde cada uno - mismos ROULETTE_SEGMENTS/logica de
   siempre, esto solo cambia como se dibuja */
function initColmRouletteWheel(){
  const wheelEl = document.getElementById('colmRouletteWheel');
  if(!wheelEl || wheelEl.dataset.ready) return;
  const cx = 110, cy = 110, r = 107;
  const segDeg = 360 / ROULETTE_SEGMENTS.length;
  const wedges = ROULETTE_SEGMENTS.map((seg, i) => {
    const start = i * segDeg, end = start + segDeg;
    const startRad = (start - 90) * Math.PI / 180, endRad = (end - 90) * Math.PI / 180;
    const x1 = cx + r * Math.cos(startRad), y1 = cy + r * Math.sin(startRad);
    const x2 = cx + r * Math.cos(endRad), y2 = cy + r * Math.sin(endRad);
    const path = 'M' + cx + ',' + cy + ' L' + x1.toFixed(2) + ',' + y1.toFixed(2) +
      ' A' + r + ',' + r + ' 0 0 1 ' + x2.toFixed(2) + ',' + y2.toFixed(2) + ' Z';
    const midRad = (start + segDeg / 2 - 90) * Math.PI / 180;
    const tx = (cx + r * 0.64 * Math.cos(midRad)).toFixed(2);
    const ty = (cy + r * 0.64 * Math.sin(midRad)).toFixed(2);
    return '<path d="' + path + '" fill="' + seg.color + '" stroke="#0b0d18" stroke-width="2"/>' +
      '<text x="' + tx + '" y="' + ty + '" text-anchor="middle" dominant-baseline="central" ' +
      'font-family="Space Mono,monospace" font-weight="800" font-size="15" fill="#fff" ' +
      'stroke="#0b0d18" stroke-width="3" paint-order="stroke">' + seg.label + '</text>';
  }).join('');
  wheelEl.innerHTML = wedges;
  wheelEl.dataset.ready = '1';

  const legendEl = document.getElementById('colmRouletteLegend');
  if(legendEl){
    const seen = new Set();
    legendEl.innerHTML = ROULETTE_SEGMENTS.filter(seg => {
      if(seen.has(seg.label)) return false;
      seen.add(seg.label);
      return true;
    }).map(seg => {
      const text = seg.mult === 0 ? 'pierdes la apuesta' : ('ganas ' + seg.label + ' tu apuesta');
      return '<div class="colm-roulette-legend-item"><span class="colm-roulette-legend-dot" style="background:' + seg.color + '"></span>' + seg.label + ' — ' + text + '</div>';
    }).join('');
  }
}
async function spinColmRoulette(){
  if(colmRouletteSpinning || !currentUser) return;
  const betInput = document.getElementById('colmRouletteBet');
  const resultEl = document.getElementById('colmRouletteResult');
  // antes esto corregia en silencio cualquier numero invalido (ej. escribir 2 se convertia
  // en 5 sin avisar) - ahora un numero fuera de rango o que no sea multiplo de 5 se rechaza
  // con un error, no se le cambia el numero a la persona por su cuenta
  const rawBet = parseInt(betInput.value, 10);
  if(!Number.isFinite(rawBet) || rawBet < 5 || rawBet > 50 || rawBet % 5 !== 0){
    resultEl.textContent = '⚠️ La apuesta debe ser un número entre 5 y 50, de 5 en 5 (5, 10, 15… 50).';
    return;
  }
  const bet = rawBet;
  const { data: rows } = await sbClient.from('user_colmillos_events').select('amount');
  const balance = (rows || []).reduce((sum, r) => sum + r.amount, 0);
  if(balance < bet){ resultEl.textContent = 'No tenés suficientes Sharkoins para esa apuesta.'; return; }
  colmRouletteSpinning = true;
  const spinBtn = document.getElementById('colmRouletteSpinBtn');
  spinBtn.disabled = true;
  betInput.disabled = true;
  const segDeg = 360 / ROULETTE_SEGMENTS.length;
  const segIndex = Math.floor(Math.random() * ROULETTE_SEGMENTS.length);
  const segment = ROULETTE_SEGMENTS[segIndex];
  const wheelEl = document.getElementById('colmRouletteWheel');
  const extraSpins = 4 + Math.floor(Math.random() * 3);
  // BUG real que encontro Juan: esto calculaba el angulo final como si la rueda siempre
  // arrancara en 0 grados, pero colmRouletteTotalRotation se va ACUMULANDO giro tras giro -
  // a partir del segundo giro la posicion visual (donde de verdad queda la rueda) y el
  // segmento ya sorteado (el texto del resultado) dejaban de coincidir. Ahora se calcula
  // cuanto le falta a la rueda, desde su posicion ACTUAL (modulo 360), para llegar al
  // segmento sorteado - "delta" siempre es la vuelta que falta, nunca negativa
  const targetMod = (360 - (segIndex * segDeg + segDeg / 2) + 360) % 360;
  const currentMod = ((colmRouletteTotalRotation % 360) + 360) % 360;
  const delta = (targetMod - currentMod + 360) % 360;
  colmRouletteTotalRotation += 360 * extraSpins + delta;
  wheelEl.style.transform = 'rotate(' + colmRouletteTotalRotation + 'deg)';
  resultEl.textContent = 'Girando...';
  setTimeout(async () => {
    const net = Math.round(bet * segment.mult) - bet;
    if(net !== 0){
      await sbClient.from('user_colmillos_events').insert({
        user_id: currentUser.id, event_type: 'casino_spin',
        period_key: (crypto.randomUUID ? crypto.randomUUID() : (Date.now() + '-' + Math.random())),
        amount: net,
      });
    }
    resultEl.textContent = segment.mult === 0
      ? ('😬 Salió 0x — perdiste ' + bet + ' Sharkoins. ¡Otra vez!')
      : ('🎉 ¡Salió ' + segment.label + '! Ganaste ' + net + ' Sharkoins.');
    loadColmillosBalance(true);
    refreshColmillosPageContent();
    colmRouletteSpinning = false;
    spinBtn.disabled = false;
    betInput.disabled = false;
  }, 3700);
}
document.getElementById('colmRouletteSpinBtn').addEventListener('click', spinColmRoulette);

function switchColmillosTab(tab){
  document.querySelectorAll('#colmillosTabs .colm-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.colm-tabpanel').forEach(p => { p.style.display = (p.dataset.tabpanel === tab) ? 'block' : 'none'; });
  /* la pestaña de Tienda se "presta" al recuadro grande del tiburon cuando se abre con MENU -
     se mueve el mismo nodo del DOM (sin duplicar nada) y se devuelve a su lugar original
     (marcado por #colmillosTiendaSlot) al salir, para no romper el resto de la logica de tabs */
  const hero = document.getElementById('colmillosHero');
  const heroOverlay = document.getElementById('colmillosHeroOverlay');
  const tiendaPanel = document.querySelector('.colm-tabpanel[data-tabpanel="tienda"]');
  const tiendaSlot = document.getElementById('colmillosTiendaSlot');
  // Sharkoins, Minijuego, Trivia y Ruleta son pantallas propias, cada una sola - ni el
  // escenario del tiburon ni el HUD tienen nada que hacer ahi (quedaban "pegados" arriba,
  // empujando el contenido real de cada pestaña a una franja chiquita abajo en celular), por
  // eso se oculta el recuadro grande completo y esas pestañas usan todo el ancho/alto
  const heroCol = document.querySelector('.colm-left');
  const HERO_HIDDEN_TABS = ['megadientes', 'juego', 'trivia', 'ruleta', 'ayuda'];
  if(heroCol) heroCol.style.display = HERO_HIDDEN_TABS.includes(tab) ? 'none' : '';
  if(tab === 'tienda'){
    if(heroOverlay && tiendaPanel && tiendaPanel.parentElement !== heroOverlay) heroOverlay.appendChild(tiendaPanel);
    if(heroOverlay) heroOverlay.style.display = 'block';
    if(hero) hero.classList.add('menu-open');
  } else {
    if(tiendaSlot && tiendaPanel && tiendaPanel.parentElement !== tiendaSlot.parentElement) tiendaSlot.after(tiendaPanel);
    if(heroOverlay) heroOverlay.style.display = 'none';
    if(hero) hero.classList.remove('menu-open');
  }
  if(tab === 'trivia') loadDailyTrivia();
  if(tab === 'tienda') loadColmillosShop();
  // el juego y la ruleta ya no arrancan solos al entrar a la pestaña - ahora cada uno vive
  // en su propia ventana emergente, que se abre al tocar su cajita (ver openColmGameModal /
  // openColmRouletteModal)
}
document.getElementById('colmillosTabs').addEventListener('click', (e) => {
  const btn = e.target.closest('.colm-tab');
  if(btn) switchColmillosTab(btn.dataset.tab);
});
document.querySelectorAll('[data-goto-tab]').forEach(el => {
  el.addEventListener('click', () => switchColmillosTab(el.dataset.gotoTab));
});

/* ---- Minijuegos y Casino: cada juego vive en su propia ventana emergente (mismo sistema
   de modal que ya usan Telegram/Bitunix), no pegado a la pestaña - se abre al tocar su
   cajita en el grid y se cierra con la X, clic afuera o ESC (igual que cualquier otro modal) ---- */
const colmGameModal = document.getElementById('colmGameModal');
const colmGamePanel = colmGameModal.querySelector('.modal-panel');
const closeColmGame = document.getElementById('closeColmGame');
function openColmGameModal(){
  initColmGameOnce();
  let best = 0;
  try { best = parseInt(localStorage.getItem('colm_best_' + todayKeyUTC()) || '0', 10) || 0; } catch(e){}
  document.getElementById('colmillosGameBest').textContent = best;
  if(colmGame.state !== 'playing') drawColmGame();
  loadColmLeaderboard(colmLbPeriod);
  openModalGeneric(colmGameModal, colmGamePanel, closeColmGame);
}
function closeColmGameModal(){
  if(colmGame.state === 'playing'){ cancelAnimationFrame(colmGame.raf); colmGame.state = 'idle'; }
  closeModalGeneric(colmGameModal);
}
closeColmGame.addEventListener('click', closeColmGameModal);
colmGameModal.addEventListener('click', (e) => { if(e.target === colmGameModal) closeColmGameModal(); });
document.getElementById('colmOpenSharkGameBtn').addEventListener('click', openColmGameModal);

/* ---- ranking semanal/mensual del minijuego (ver scripts/sql/create_colm_leaderboard.sql) -
   top 10 del periodo EN CURSO, leido con el RPC get_colm_leaderboard (nunca directo de la
   tabla, asi nadie ve las partidas de otra persona una por una, solo el resumen ya armado) ---- */
let colmLbPeriod = 'weekly';
async function loadColmLeaderboard(period){
  const listEl = document.getElementById('colmLeaderboardList');
  if(!listEl) return;
  listEl.innerHTML = '<p class="colm-lb-empty">Cargando…</p>';
  const { data, error } = await sbClient.rpc('get_colm_leaderboard', { p_period: period });
  if(error){
    listEl.innerHTML = '<p class="colm-lb-empty">No se pudo cargar el ranking.</p>';
    console.warn('no se pudo leer el ranking del minijuego', error);
    return;
  }
  if(!data || !data.length){
    const emptyWhen = period === 'weekly' ? 'esta semana' : period === 'monthly' ? 'este mes' : 'todavía';
    listEl.innerHTML = '<p class="colm-lb-empty">Nadie ha jugado ' + emptyWhen + '. ¡Sé el primero!</p>';
    return;
  }
  const myName = currentUser ? getDisplayName(currentUser) : null;
  listEl.innerHTML = data.map(row => {
    const classes = ['colm-lb-row'];
    if(row.rank <= 3) classes.push('top3');
    if(myName && row.username === myName) classes.push('me');
    return '<div class="' + classes.join(' ') + '"><span class="colm-lb-rank">#' + row.rank + '</span>' +
      '<span class="colm-lb-name">' + escapeHtml(row.username) + '</span>' +
      '<span class="colm-lb-score">' + row.score + '</span></div>';
  }).join('');
}
document.querySelectorAll('.colm-lb-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    if(btn.classList.contains('active')) return;
    colmLbPeriod = btn.dataset.lbperiod;
    document.querySelectorAll('.colm-lb-tab').forEach(b => {
      b.classList.toggle('active', b === btn);
      b.setAttribute('aria-selected', b === btn ? 'true' : 'false');
    });
    loadColmLeaderboard(colmLbPeriod);
  });
});

const colmRouletteModal = document.getElementById('colmRouletteModal');
const colmRoulettePanel = colmRouletteModal.querySelector('.modal-panel');
const closeColmRoulette = document.getElementById('closeColmRoulette');
function openColmRouletteModal(){
  initColmRouletteWheel();
  openModalGeneric(colmRouletteModal, colmRoulettePanel, closeColmRoulette);
}
function closeColmRouletteModal(){ closeModalGeneric(colmRouletteModal); }
closeColmRoulette.addEventListener('click', closeColmRouletteModal);
colmRouletteModal.addEventListener('click', (e) => { if(e.target === colmRouletteModal) closeColmRouletteModal(); });
document.getElementById('colmOpenRouletteBtn').addEventListener('click', openColmRouletteModal);
/* la guia de rareza/poderes YA NO es un modal emergente (pedido explicito de Juan: "no que sea
   emergente como esta ahorita") - ahora vive como una pestaña de verdad (Ayuda), con sus
   propias sub-pestañas internas. Este boton de la tienda solo navega hasta alla. */
function switchColmHelpTopic(topic){
  document.querySelectorAll('#colmillosHelpSubtabs .colm-help-subtab').forEach(b => b.classList.toggle('active', b.dataset.helptopic === topic));
  document.querySelectorAll('.colm-help-panel').forEach(p => p.classList.toggle('active', p.dataset.helppanel === topic));
}
document.getElementById('colmillosHelpSubtabs').addEventListener('click', (e) => {
  const btn = e.target.closest('.colm-help-subtab');
  if(btn) switchColmHelpTopic(btn.dataset.helptopic);
});
document.getElementById('colmRarityInfoBtn').addEventListener('click', () => {
  switchColmillosTab('ayuda');
  switchColmHelpTopic('rareza');
});
document.getElementById('colmHeroCardInfoBtn').addEventListener('click', () => {
  switchColmillosTab('ayuda');
  switchColmHelpTopic('rareza');
});
/* sub-pestañas DENTRO de la tienda (Colores/Cabeza/Cara/Cuerpo/Manos/Fondos/Sorteos) - antes
   todo estaba en una sola columna larga y tocaba bajar mucho scroll; ahora solo se muestra
   una categoria a la vez. Cabeza/Cara/Cuerpo/Manos comparten la misma categoria real
   "accessory" (ACC_SLOT_MAP) - no hace falta una columna nueva en la base de datos, el
   agrupamiento por "parte del cuerpo" es solo visual */
const COLM_SLOT_LABELS = { head: '🎩 ACCESORIOS DE CABEZA', face: '😎 ACCESORIOS DE CARA', body: '👔 ACCESORIOS DE CUERPO', hands: '✊ ACCESORIOS PARA LAS MANOS', feet: '👟 ACCESORIOS DE PIES' };
function applyColmShopSubtabFilter(){
  const activeBtn = document.querySelector('.colm-shop-subtab.active');
  if(!activeBtn) return;
  const cat = activeBtn.dataset.shopcat;
  const slot = activeBtn.dataset.slot || null;
  document.querySelectorAll('.colm-shop-section').forEach(s => { s.style.display = (s.dataset.cat === cat) ? 'block' : 'none'; });
  if(cat === 'accessory'){
    document.querySelectorAll('#colmillosShopAccessories .colm-shop-item, #colmillosShopAccessories .colm-shop-bg-item').forEach(card => {
      card.style.display = (!slot || card.dataset.slot === slot) ? 'flex' : 'none';
    });
    const label = document.getElementById('colmillosAccSectionLabel');
    if(label && slot) label.textContent = COLM_SLOT_LABELS[slot] || '🕶️ ACCESORIOS';
  }
}
document.getElementById('colmillosShopSubtabs').addEventListener('click', (e) => {
  const btn = e.target.closest('.colm-shop-subtab');
  if(!btn) return;
  document.querySelectorAll('.colm-shop-subtab').forEach(b => b.classList.toggle('active', b === btn));
  applyColmShopSubtabFilter();
});

/* ---- pagina propia (no modal flotante) con su ruta /sharkoins (el nombre de la moneda -
   "colmillos" es solo el nombre interno en variables/funciones, nunca debe verse en pantalla
   ni en la URL), igual que un indicador - mismo patron de mostrar/ocultar que
   showCategoryOverview()/showCategoryDetail() pero aislado del sistema de categorias para no
   interferir con su propio manejo de historial. Siempre arranca en la pantalla de "JUGAR" -
   como un cabinet de arcade de verdad, no se salta directo al contenido ---- */
function showColmillosPage(){
  closeAnyOpenToolInline();
  categoryOverviewGrid.style.display = 'none';
  categoryDetailView.style.display = 'none';
  document.getElementById('marketDashboardBlock').style.display = 'none';
  document.getElementById('favoritesSection').style.display = 'none';
  const hero = document.querySelector('.hero-mascot');
  const ticker = document.querySelector('.crypto-ticker');
  if(hero) hero.style.display = 'none';
  if(ticker) ticker.style.display = 'none';
  colmillosPageView.style.display = 'block';
  setPageTitle('Sharkoins');
  pushRoute({ skillcashDepth: 'sharkoins' }, '/sharkoins');
  colmillosContent.style.display = 'none';
  document.getElementById('colmillosTabs').style.display = 'none';
  switchColmillosTab('inicio');
  loadGlobalTaps();
  renderSharkPreviews();
  colmillosPageView.scrollIntoView({ behavior: 'smooth', block: 'start' });
  // ya no hay pantalla de "JUGAR" intermedia - entrar a Colmillos pasa derecho por la carga
  startColmillosLoadSequence();
}
function startColmillosLoadSequence(){
  colmillosLoading.style.display = 'flex';
  colmillosLoading.classList.remove('run');
  void colmillosLoading.offsetWidth;
  colmillosLoading.classList.add('run');
  // la carga REAL (balance, tienda, ficha de heroe) arranca YA, al mismo tiempo que la
  // animacion de 3s - no despues de que la animacion termine. Los 3s son solo un minimo para
  // que la animacion se vea completa (le dan tiempo al internet de la persona sin que se
  // sienta instantaneo/brusco), pero si la carga real tarda MAS de 3s (conexion lenta), se
  // espera a que de verdad termine en vez de mostrar contenido a medio cargar.
  clearTimeout(window._colmillosLoadTimer);
  const minDelay = new Promise(resolve => { window._colmillosLoadTimer = setTimeout(resolve, 3000); });
  const realLoad = Promise.all([refreshColmillosPageContent(), loadColmillosShop()]);
  Promise.all([minDelay, realLoad]).then(() => {
    colmillosLoading.style.display = 'none';
    colmillosContent.style.display = 'block';
    document.getElementById('colmillosTabs').style.display = 'flex';
    // refreshColmillosPageContent()/loadColmillosShop() (parte de realLoad) ya habian llamado
    // a sizeAndRenderHeroChar() mientras colmillosContent todavia estaba display:none (para
    // mostrar la pantalla de carga encima) - en ese momento el escenario mide 0x0, asi que el
    // tiburon quedaba parado en una posicion en pixeles congelada e invalida (el pedestal se ve
    // bien porque usa % en CSS, que se recalcula solo; el tiburon no, por eso "desaparecia").
    // Ahora que el contenido real ya es visible y mide lo que mide de verdad, se vuelve a medir.
    sizeAndRenderHeroChar(colmEquippedAccessoryIds(colmillosEquippedState));
    renderColmHeroParticles();
    colmSessionStartTs = Date.now();
    clearInterval(window._colmSessionTimerInterval);
    window._colmSessionTimerInterval = setInterval(updateColmSessionTimer, 1000);
    updateColmSessionTimer();
  });
}
function hideColmillosPage(){
  const wasInColmillos = colmillosPageView.style.display === 'block';
  if(colmGame.state === 'playing'){ cancelAnimationFrame(colmGame.raf); colmGame.state = 'idle'; }
  clearInterval(window._colmSessionTimerInterval);
  colmillosPageView.style.display = 'none';
  categoryOverviewGrid.style.display = 'grid';
  document.getElementById('marketDashboardBlock').style.display = 'block';
  document.getElementById('favoritesSection').style.display = '';
  const hero = document.querySelector('.hero-mascot');
  const ticker = document.querySelector('.crypto-ticker');
  if(hero) hero.style.display = '';
  if(ticker) ticker.style.display = '';
  setPageTitle(null);
  if(wasInColmillos && !closingFromPopstate && history.state && history.state.skillcashDepth === 'sharkoins'){
    suppressNextPopstate = true;
    history.back();
  } else if(wasInColmillos && !closingFromPopstate){
    replaceRoute(null, '/');
  }
  categoryOverviewGrid.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
colmillosBackBtn.addEventListener('click', hideColmillosPage);
colmillosWalletBtn.addEventListener('click', showColmillosPage);
colmillosBigCoin.addEventListener('click', (e) => {
  const coin = e.currentTarget;
  coin.classList.remove('spin');
  void coin.offsetWidth;
  coin.classList.add('spin');
  const spark = document.createElement('div');
  spark.className = 'colm-spark';
  spark.textContent = ['✨', '🦈', '💰', '⚡'][Math.floor(Math.random() * 4)];
  spark.style.left = (38 + Math.random() * 24) + '%';
  spark.style.top = '28%';
  const sparkHost = coin.closest('.colm-wallet-page') || coin.closest('.colm-hero') || coin.parentElement;
  if(sparkHost) sparkHost.appendChild(spark);
  setTimeout(() => spark.remove(), 900);
  // la moneda tiene dos caras (el diente y el logo CC de Sharkoins) - al girar cae en una
  // al azar, como una moneda real. El cambio de imagen pasa a la mitad del giro (de canto,
  // invisible) para que se sienta como que en verdad cambio de cara
  const coinImg = coin.querySelector('img');
  if(coinImg){
    setTimeout(() => {
      coinImg.src = 'assets/mascot/' + (Math.random() < 0.5 ? 'coin_tooth.png' : 'coin_charcoins.png');
    }, 350);
  }
  bumpGlobalTaps();
});
