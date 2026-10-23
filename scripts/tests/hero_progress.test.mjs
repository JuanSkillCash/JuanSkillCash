// Tests de getHeroProgress (Ficha del Heroe, Sharkoins) - corre con:  node --test
// No depende de un framework externo, solo node:test/node:assert (incluidos desde Node 18+).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { getHeroProgress, HERO_STAT_KEYS } = require('../../assets/js/hero-progress.js');

// catalogo sintetico con la MISMA forma que el real (19 skins, 5/8/5/9/6 accesorios por
// slot, 23 fondos) para que las pruebas de "toda la tienda" sean representativas de verdad
function buildCatalog(){
  const catalog = [];
  for(let i = 0; i < 19; i++) catalog.push({ id: 'skin_' + i, category: 'skin', slot: 'skin' });
  const slots = { head: 5, face: 8, body: 5, hands: 9, feet: 6 };
  Object.entries(slots).forEach(([slot, count]) => {
    for(let i = 0; i < count; i++) catalog.push({ id: 'acc_' + slot + '_' + i, category: 'accessory', slot });
  });
  for(let i = 0; i < 23; i++) catalog.push({ id: 'bg_' + i, category: 'background' });
  catalog.push({ id: 'raffle_ticket', category: 'raffle' });
  return catalog;
}

test('0 items poseidos -> nivel 1, 0 estrellas, stats en el piso base', () => {
  const catalog = buildCatalog();
  const result = getHeroProgress({ catalog, ownedIds: [], rarityById: {}, equippedTiers: [] });
  assert.equal(result.level, 1);
  assert.equal(result.stars, 0);
  assert.equal(result.itemsOwned, 0);
  assert.equal(result.itemsTotal, 75); // 19 + 5+8+5+9+6 + 23, sin contar el boleto de sorteo
  HERO_STAT_KEYS.forEach(k => assert.equal(result.stats[k], 5)); // solo la base
  assert.equal(result.power, 5);
});

test('toda la tienda poseida y evolucionada a mitico -> nivel 100, 5 estrellas, stats ~100', () => {
  const catalog = buildCatalog();
  const ownedIds = catalog.filter(i => i.category !== 'raffle').map(i => i.id);
  const rarityById = {};
  catalog.forEach(i => { if(i.category === 'skin' || i.category === 'accessory') rarityById[i.id] = 5; });
  const result = getHeroProgress({ catalog, ownedIds, rarityById, equippedTiers: [5] });
  assert.equal(result.level, 100);
  assert.equal(result.stars, 5);
  assert.equal(result.itemsOwned, 75);
  HERO_STAT_KEYS.forEach(k => assert.ok(result.stats[k] >= 98, k + ' deberia estar cerca de 100, dio ' + result.stats[k]));
  assert.ok(result.power >= 98);
});

test('un solo item mitico equipado -> 5 estrellas aunque el nivel sea bajo', () => {
  const catalog = buildCatalog();
  const result = getHeroProgress({
    catalog,
    ownedIds: ['acc_face_0'],
    rarityById: { acc_face_0: 5 },
    equippedTiers: [5],
  });
  assert.ok(result.level < 20, 'el nivel deberia ser bajo con un solo item');
  assert.equal(result.stars, 5, 'un mitico equipado debe dar la 5ta estrella sin importar el nivel');
});

test('progreso parcial (mitad del peso total) da nivel ~50 y stars escalonadas', () => {
  const catalog = buildCatalog();
  // posee la mitad de los skins y accesorios, todos en tier 5 (mitico) para alcanzar ~50% del peso
  const half = catalog.filter(i => i.category === 'skin' || i.category === 'accessory').slice(0, 26);
  const rarityById = {};
  half.forEach(i => { rarityById[i.id] = 5; });
  const result = getHeroProgress({ catalog, ownedIds: half.map(i => i.id), rarityById, equippedTiers: [] });
  assert.ok(result.level > 20 && result.level < 80, 'nivel deberia quedar en un rango intermedio, dio ' + result.level);
  assert.ok(result.stars >= 1 && result.stars <= 4);
});

test('estrellas siguen los umbrales 20/40/60/80 sin mitico equipado', () => {
  // catalogo de 100 items, todos los POSEIDOS evolucionados a Mitico (tier 5) - asi el % de
  // items poseidos coincide 1 a 1 con el nivel (ver maxWeight: siempre asume tier 5 como techo)
  const fullCatalog = Array.from({ length: 100 }, (_, i) => ({ id: 's' + i, category: 'skin', slot: 'skin' }));
  for(const [ownedCount, expectedStars] of [[19, 0], [20, 1], [39, 1], [40, 2], [60, 3], [80, 4], [99, 4]]){
    const ownedIds = Array.from({ length: ownedCount }, (_, i) => 's' + i);
    const rarityById = {};
    ownedIds.forEach(id => { rarityById[id] = 5; });
    const result = getHeroProgress({ catalog: fullCatalog, ownedIds, rarityById, equippedTiers: [] });
    assert.equal(result.level, ownedCount, 'con ' + ownedCount + ' items al maximo, el nivel deberia ser ' + ownedCount);
    assert.equal(result.stars, expectedStars, 'nivel ' + result.level + ' deberia dar ' + expectedStars + ' estrellas');
  }
});

test('las stats sin ningun item mapeado a ese slot se quedan en la base (nunca negativas ni NaN)', () => {
  const catalog = [{ id: 'only_bg', category: 'background' }];
  const result = getHeroProgress({ catalog, ownedIds: ['only_bg'], rarityById: {}, equippedTiers: [] });
  HERO_STAT_KEYS.forEach(k => assert.equal(result.stats[k], 5));
  assert.equal(result.power, 5);
});
