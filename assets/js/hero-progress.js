/* Sistema de progreso de la Ficha del Heroe (Sharkoins) - funcion PURA y testeable, sin
   acceso a DOM/red/variables globales del resto del sitio. La llama colmillos.js pasandole
   el catalogo + lo que el usuario posee, y la reusa scripts/tests/hero_progress.test.mjs para
   probarla con Node, sin necesidad de un navegador.

   Mapeo item -> stat: se reusa el mismo slot que ya existia para la "Ficha del Personaje"
   (COLM_POWER_BY_SLOT en colmillos.js) - cada item.slot que llega aqui ya viene resuelto por
   el llamador (skin='skin', accesorios por ACC_SLOT_MAP: head/face/body/hands/feet). Fondos y
   boleto de sorteo no tienen slot (no aportan a ninguna stat, solo al nivel de coleccion). */
const HERO_STAT_KEYS = ['instinto', 'astucia', 'vision', 'resistencia', 'fuerza', 'velocidad'];
const HERO_STAT_BY_SLOT = { skin: 'instinto', head: 'astucia', face: 'vision', body: 'resistencia', hands: 'fuerza', feet: 'velocidad' };
/* pesos por rareza para el NIVEL (progreso de coleccion) - un mitico pesa mucho mas que un
   comun, para que completar la tienda entera (todo evolucionado a mitico) sea de verdad la
   meta de "coleccionista completo" */
const HERO_RARITY_WEIGHT = { 1: 1, 2: 2, 3: 4, 4: 7, 5: 12 };
/* puntos por rareza para las STATS (independiente del peso de nivel) */
const HERO_RARITY_STAT_POINTS = { 1: 4, 2: 8, 3: 14, 4: 22, 5: 35 };
const HERO_STAT_BASE = 5; // ninguna stat empieza en 0 - se ve "viva" desde el primer momento
const HERO_MAX_RARITY = 5;
const HERO_STAR_THRESHOLDS = [20, 40, 60, 80]; // nivel que da cada estrella 1-4

/* catalog: [{id, category:'skin'|'accessory'|'background'|'raffle', slot?:'skin'|'head'|...}]
   ownedIds: Set o array de ids que el usuario posee (sin contar boletos de sorteo)
   rarityById: {itemId: tier 1-5} - solo para skins/accesorios poseidos
   equippedTiers: array de tiers (1-5) de lo que tiene EQUIPADO ahora mismo (para la estrella 5) */
function getHeroProgress({ catalog, ownedIds, rarityById, equippedTiers } = {}){
  catalog = Array.isArray(catalog) ? catalog : [];
  const owned = ownedIds instanceof Set ? ownedIds : new Set(ownedIds || []);
  rarityById = rarityById || {};
  equippedTiers = Array.isArray(equippedTiers) ? equippedTiers : [];

  let maxWeight = 0, curWeight = 0, itemsTotal = 0, itemsOwned = 0;
  const maxRawBySlot = {}, rawBySlot = {};
  HERO_STAT_KEYS.forEach(k => { maxRawBySlot[k] = 0; rawBySlot[k] = 0; });

  catalog.forEach(item => {
    if(!item || item.category === 'raffle') return;
    itemsTotal++;
    const isRareable = item.category === 'skin' || item.category === 'accessory';
    maxWeight += isRareable ? HERO_RARITY_WEIGHT[HERO_MAX_RARITY] : 1;
    const stat = isRareable ? HERO_STAT_BY_SLOT[item.slot] : null;
    if(stat) maxRawBySlot[stat] += HERO_RARITY_STAT_POINTS[HERO_MAX_RARITY];
  });

  owned.forEach(id => {
    const item = catalog.find(i => i.id === id);
    if(!item || item.category === 'raffle') return;
    itemsOwned++;
    const isRareable = item.category === 'skin' || item.category === 'accessory';
    const tier = isRareable ? (rarityById[id] || 1) : 1;
    curWeight += isRareable ? (HERO_RARITY_WEIGHT[tier] || HERO_RARITY_WEIGHT[1]) : 1;
    const stat = isRareable ? HERO_STAT_BY_SLOT[item.slot] : null;
    if(stat) rawBySlot[stat] += (HERO_RARITY_STAT_POINTS[tier] || HERO_RARITY_STAT_POINTS[1]);
  });

  const stats = {};
  HERO_STAT_KEYS.forEach(k => {
    const factor = maxRawBySlot[k] > 0 ? (100 - HERO_STAT_BASE) / maxRawBySlot[k] : 0;
    stats[k] = Math.max(0, Math.min(100, Math.round(HERO_STAT_BASE + rawBySlot[k] * factor)));
  });
  const power = Math.round(HERO_STAT_KEYS.reduce((sum, k) => sum + stats[k], 0) / HERO_STAT_KEYS.length);

  const progress = maxWeight > 0 ? Math.min(1, curWeight / maxWeight) : 0;
  const level = Math.max(1, Math.min(100, Math.floor(progress * 100)));

  let stars = 0;
  HERO_STAR_THRESHOLDS.forEach((t, i) => { if(level >= t) stars = i + 1; });
  const hasMythicEquipped = equippedTiers.some(t => t === HERO_MAX_RARITY);
  if(level === 100 || hasMythicEquipped) stars = 5;

  let nextStarLabel = null;
  if(stars < 5){
    nextStarLabel = stars < 4
      ? ('Próxima estrella: nivel ' + HERO_STAR_THRESHOLDS[stars])
      : 'Consigue un ítem mítico';
  }

  return { level, progress, stars, power, stats, itemsOwned, itemsTotal, nextStarLabel };
}

if(typeof module !== 'undefined' && module.exports){
  module.exports = {
    getHeroProgress, HERO_STAT_KEYS, HERO_STAT_BY_SLOT, HERO_RARITY_WEIGHT,
    HERO_RARITY_STAT_POINTS, HERO_STAT_BASE, HERO_MAX_RARITY, HERO_STAR_THRESHOLDS,
  };
}
