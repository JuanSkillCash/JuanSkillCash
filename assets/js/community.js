/* Comunidad: indicador "EN VIVO", seccion "Creado por Juan SkillCash" y reseñas de la plataforma.
   Todo depende de scripts/sql/create_reviews_and_live.sql - si esas tablas todavia no existen en
   Supabase, cada parte se queda quieta (sin romper el resto de la pagina): el EN VIVO no aparece,
   el contador de usuarios queda en "—" y las reseñas muestran un aviso. */
(function(){
if(typeof sbClient === 'undefined') return;

const OWNER_ID = 'e4309251-6078-4233-aab3-6ab8d6c624e1';

const $ = id => document.getElementById(id);
const fmt = n => Number(n).toLocaleString('es-CO');
const isOwner = () => !!(currentUser && currentUser.id === OWNER_ID);

/* ---- las secciones del inicio se muestran/ocultan junto con las cajas de herramientas
   (cuando se entra a una categoria, a Sharkoins, etc. desaparecen igual que ellas) ---- */
const grid = $('categoryOverviewGrid');
function syncHomeMirror(){
  const hidden = grid && grid.style.display === 'none';
  document.querySelectorAll('.home-mirror').forEach(el => { el.style.display = hidden ? 'none' : ''; });
}
if(grid){
  new MutationObserver(syncHomeMirror).observe(grid, { attributes: true, attributeFilter: ['style'] });
  syncHomeMirror();
}

/* ================= EN VIVO ================= */
let liveState = null;
async function loadLiveStatus(){
  const { data, error } = await sbClient.from('site_status').select('is_live,live_url').eq('id', 1).maybeSingle();
  if(error || !data) return;
  liveState = data;
  const pill = $('livePill');
  if(pill){
    pill.style.display = data.is_live ? 'inline-flex' : 'none';
    if(data.live_url) pill.href = data.live_url;
  }
  renderAdminLiveBtn();
}
function renderAdminLiveBtn(){
  const btn = $('adminLiveToggle');
  if(!btn) return;
  if(!liveState){ btn.textContent = 'Falta correr el SQL'; btn.disabled = true; return; }
  btn.disabled = false;
  btn.classList.toggle('on', liveState.is_live);
  btn.textContent = liveState.is_live ? '● Prendido — apagar' : 'Apagado — prender';
}
// el boton vive ahora dentro de assets/js/admin.js (pagina /administrador, el HTML se arma de
// nuevo cada vez que se abre - no existe todavia cuando este script corre al cargar la pagina)
// - por eso el bind del click y el pintado se repiten cada vez que admin.js lo pide, en vez de
// una sola vez al cargar como antes (cuando vivia fijo dentro del modal viejo).
function bindAdminLiveBtn(){
  const btn = $('adminLiveToggle');
  if(!btn) return;
  if(!btn.dataset.liveBound){
    btn.dataset.liveBound = '1';
    btn.addEventListener('click', async () => {
      if(!liveState || !isOwner()) return;
      btn.disabled = true;
      const { error } = await sbClient.from('site_status')
        .update({ is_live: !liveState.is_live, updated_at: new Date().toISOString() }).eq('id', 1);
      if(error) alert(error.message);
      await loadLiveStatus();
    });
  }
  renderAdminLiveBtn();
}
window.refreshAdminLiveBtn = bindAdminLiveBtn;
loadLiveStatus();
setInterval(loadLiveStatus, 120000);

/* ================= Creado por Juan SkillCash =================
   TikTok (10.000+), lineas de codigo (43.000+, sin contar 404.html que es copia del inicio ni
   librerias de terceros) y Telegram (200+) estan escritos a mano en index.html - actualizarlos
   ahi cuando cambien. Herramientas e indicadores se cuentan solos */
async function loadAboutStats(){
  const toolsEl = $('aboutStatTools');
  if(toolsEl && typeof TOOL_LABELS === 'object') toolsEl.textContent = Object.keys(TOOL_LABELS).length;
  const indicEl = $('aboutStatIndic');
  const badge = $('indicCountBadge');
  if(indicEl && badge) indicEl.textContent = (badge.textContent.match(/\d+/) || ['—'])[0];
  const { data, error } = await sbClient.rpc('get_public_stats');
  if(error || !data) return;
  renderReviewsSummary(data);
}

/* ================= Reseñas ================= */
const PAGE = 6;
let reviewsShown = PAGE;
let reviewsCache = [];
let myReview = null;
let pickedRating = 0;

function starsText(n){ return '★★★★★'.slice(0, n) + '☆☆☆☆☆'.slice(0, 5 - n); }
function timeAgo(iso){
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if(d < 3600) return 'hace ' + Math.max(1, Math.round(d / 60)) + ' min';
  if(d < 86400) return 'hace ' + Math.round(d / 3600) + ' h';
  if(d < 86400 * 30) return 'hace ' + Math.round(d / 86400) + ' d';
  return new Date(iso).toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' });
}
function renderReviewsSummary(stats){
  const el = $('reviewsSummary');
  if(!el) return;
  if(!stats || !stats.reviews){ el.textContent = ''; return; }
  el.innerHTML = '<b>' + Number(stats.avg_rating).toFixed(1) + '</b><span class="rs-stars">' +
    starsText(Math.round(stats.avg_rating)) + '</span>' + fmt(stats.reviews) + ' reseña' + (stats.reviews === 1 ? '' : 's');
}
function reviewCard(r){
  const card = document.createElement('div');
  card.className = 'review-card' + (r.hidden ? ' is-hidden' : '');
  const head = document.createElement('div'); head.className = 'review-card-head';
  const name = document.createElement('span'); name.className = 'review-card-name'; name.textContent = r.display_name;
  const stars = document.createElement('span'); stars.className = 'review-card-stars'; stars.textContent = starsText(r.rating);
  head.append(name, stars);
  const text = document.createElement('p'); text.className = 'review-card-text'; text.textContent = r.comment;
  const foot = document.createElement('div'); foot.className = 'review-card-foot';
  const when = document.createElement('span');
  when.textContent = timeAgo(r.created_at) + (r.updated_at && (new Date(r.updated_at) - new Date(r.created_at)) > 60000 ? ' · editada' : '');
  foot.append(when);
  // moderacion: solo el dueño ve estos botones (y la base de datos igual lo revisa)
  if(isOwner()){
    const mod = document.createElement('span');
    const hideBtn = document.createElement('button'); hideBtn.type = 'button'; hideBtn.className = 'review-link-btn';
    hideBtn.textContent = r.hidden ? 'Mostrar' : 'Ocultar';
    hideBtn.addEventListener('click', async () => {
      const { error } = await sbClient.from('platform_reviews').update({ hidden: !r.hidden }).eq('id', r.id);
      if(error) alert(error.message); else loadReviews();
    });
    const delBtn = document.createElement('button'); delBtn.type = 'button'; delBtn.className = 'review-link-btn';
    delBtn.textContent = 'Borrar'; delBtn.style.marginLeft = '10px';
    delBtn.addEventListener('click', async () => {
      if(!confirm('¿Borrar esta reseña de ' + r.display_name + '?')) return;
      const { error } = await sbClient.from('platform_reviews').delete().eq('id', r.id);
      if(error) alert(error.message); else loadReviews();
    });
    mod.append(hideBtn, delBtn);
    foot.append(mod);
  }
  card.append(head, text, foot);
  return card;
}
function renderReviewsList(){
  const list = $('reviewsList');
  const more = $('reviewsMoreBtn');
  if(!list) return;
  list.innerHTML = '';
  if(!reviewsCache.length){
    const empty = document.createElement('div');
    empty.className = 'review-empty';
    empty.textContent = 'Todavía no hay reseñas. ¡Sé el primero en contar qué te parece SkillCash!';
    list.append(empty);
  } else {
    reviewsCache.slice(0, reviewsShown).forEach(r => list.append(reviewCard(r)));
  }
  if(more) more.style.display = reviewsCache.length > reviewsShown ? 'block' : 'none';
}
async function loadReviews(){
  const { data, error } = await sbClient.from('platform_reviews')
    .select('id,user_id,display_name,rating,comment,hidden,created_at,updated_at')
    .order('created_at', { ascending: false }).limit(200);
  if(error){
    const list = $('reviewsList');
    if(list) list.innerHTML = '<div class="review-empty">Las reseñas todavía no están disponibles.</div>';
    return;
  }
  reviewsCache = data || [];
  myReview = currentUser ? (reviewsCache.find(r => r.user_id === currentUser.id) || null) : null;
  renderReviewsList();
  renderReviewForm();
  loadAboutStats();
}

function paintStars(){
  document.querySelectorAll('#reviewStarsInput button').forEach(b => b.classList.toggle('on', Number(b.dataset.v) <= pickedRating));
}
function renderReviewForm(){
  const form = $('reviewForm'), note = $('reviewLoginNote');
  if(!form || !note) return;
  const logged = !!currentUser;
  form.style.display = logged ? '' : 'none';
  note.style.display = logged ? 'none' : '';
  if(!logged) return;
  $('reviewFormLabel').textContent = myReview ? 'Tu reseña (puedes editarla)' : 'Tu calificación';
  $('reviewSubmitBtn').textContent = myReview ? 'Guardar cambios' : 'Publicar reseña';
  $('reviewDeleteBtn').style.display = myReview ? '' : 'none';
  if(myReview && !form.dataset.touched){
    pickedRating = myReview.rating;
    $('reviewComment').value = myReview.comment;
  }
  $('reviewCounter').textContent = $('reviewComment').value.length + '/500';
  paintStars();
}
function setMsg(text, kind){
  const el = $('reviewMsg');
  el.textContent = text || '';
  el.className = 'review-msg' + (kind ? ' ' + kind : '');
}

document.querySelectorAll('#reviewStarsInput button').forEach(b => {
  b.addEventListener('click', () => { pickedRating = Number(b.dataset.v); $('reviewForm').dataset.touched = '1'; paintStars(); });
});
const commentEl = $('reviewComment');
if(commentEl){
  commentEl.addEventListener('input', () => {
    $('reviewForm').dataset.touched = '1';
    $('reviewCounter').textContent = commentEl.value.length + '/500';
  });
}
const loginBtn = $('reviewLoginBtn');
if(loginBtn) loginBtn.addEventListener('click', () => { if(typeof openAuthModal === 'function') openAuthModal(); });

const reviewForm = $('reviewForm');
if(reviewForm){
  reviewForm.addEventListener('submit', async e => {
    e.preventDefault();
    if(!currentUser) return;
    const comment = commentEl.value.trim();
    if(!pickedRating){ setMsg('Elige de 1 a 5 estrellas.', 'err'); return; }
    if(comment.length < 3){ setMsg('Escribe al menos unas palabras.', 'err'); return; }
    const btn = $('reviewSubmitBtn');
    btn.disabled = true;
    setMsg('Guardando…');
    const payload = { rating: pickedRating, comment };
    const { error } = myReview
      ? await sbClient.from('platform_reviews').update(payload).eq('id', myReview.id)
      : await sbClient.from('platform_reviews').insert({ ...payload, user_id: currentUser.id });
    btn.disabled = false;
    if(error){ setMsg(typeof friendlyErrMsg === 'function' ? friendlyErrMsg(error) : error.message, 'err'); return; }
    delete reviewForm.dataset.touched;
    setMsg(myReview ? '¡Reseña actualizada!' : '¡Gracias por tu reseña!', 'ok');
    await loadReviews();
  });
}
const deleteBtn = $('reviewDeleteBtn');
if(deleteBtn){
  deleteBtn.addEventListener('click', async () => {
    if(!myReview || !confirm('¿Borrar tu reseña?')) return;
    const { error } = await sbClient.from('platform_reviews').delete().eq('id', myReview.id);
    if(error){ setMsg(error.message, 'err'); return; }
    pickedRating = 0; commentEl.value = ''; delete reviewForm.dataset.touched;
    setMsg('Reseña borrada.', 'ok');
    await loadReviews();
  });
}
const moreBtn = $('reviewsMoreBtn');
if(moreBtn) moreBtn.addEventListener('click', () => { reviewsShown += PAGE; renderReviewsList(); });

sbClient.auth.onAuthStateChange(() => { setTimeout(() => { loadReviews(); renderAdminLiveBtn(); }, 0); });
loadReviews();
})();
