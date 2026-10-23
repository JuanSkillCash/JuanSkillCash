-- Re-precio de la tienda de Colmillos + sistema de rareza/evolucion (ver create_colmillos_
-- minigame.sql y add_colm_eyes_and_crypto_backgrounds.sql).
--
-- SKINS y ACCESORIOS ahora tienen rareza: el precio del catalogo (de aqui abajo) es solo el
-- de la version "Comun" (tier 1, el precio de ENTRADA a esa familia - ej. comprar el Tiburon
-- Dorado por primera vez). Una vez la tienes, la puedes EVOLUCIONAR pagando Sharkoins extra -
-- Raro, Epico, Legendario y Mitico - sin comprar nada nuevo, es la MISMA pieza mejorando (como
-- en Axie Infinity). Esos costos de evolucion son un numero fijo e igual para CUALQUIER skin o
-- accesorio (no estan en esta tabla, estan en assets/js/colmillos.js, constante COLM_EVOLVE_COST):
--   Raro (tier 2): 75   Epico (tier 3): 150   Legendario (tier 4): 275   Mitico (tier 5): 450
-- (recalibrado despues de validar contra lo que gana alguien jugando normal, sin ganarse rifas
-- ni el top del leaderboard: evolucionar un solo item hasta Mitico debia tardar un par de meses,
-- no casi 4 - ver el commit que bajo estos numeros para el detalle del calculo)
-- La rareza alcanzada se guarda como una fila mas en el ledger de siempre
-- (user_colmillos_events: event_type='evolve_<item_id>', period_key='tier2'/'tier3'/...), asi
-- que no hace falta ninguna tabla nueva - el mismo unique constraint evita evolucionar dos
-- veces al mismo escalon.
--
-- FONDOS y el BOLETO DE SORTEO NO tienen rareza (son "uno solo", sin evolucionar) - sus precios
-- de aqui abajo son el precio final, igual que antes.
--
-- Son puros UPDATE (las filas ya existen) - seguro de correr mas de una vez.
-- Ejecutar una sola vez en el SQL editor de Supabase.

-- Los costos de evolucion (hasta 900) superan el tope viejo de +-500 en los montos del ledger -
-- se amplia otra vez (ya se habia ampliado antes de +-20 a +-500).
alter table user_colmillos_events drop constraint if exists user_colmillos_events_amount_check;
alter table user_colmillos_events add constraint user_colmillos_events_amount_check
    check (amount <> 0 and amount between -1200 and 1200);

-- ===== SKINS (precio de entrada, tier Comun) =====
-- Basicos (colores lisos)
update colmillos_shop_items set price = 60  where id = 'skin_cyan';
update colmillos_shop_items set price = 65  where id = 'skin_lime';
update colmillos_shop_items set price = 70  where id = 'skin_emerald';
update colmillos_shop_items set price = 70  where id = 'skin_violet';
update colmillos_shop_items set price = 75  where id = 'skin_pink';
update colmillos_shop_items set price = 75  where id = 'skin_ice';
update colmillos_shop_items set price = 80  where id = 'skin_gold';
update colmillos_shop_items set price = 85  where id = 'skin_orange';
update colmillos_shop_items set price = 90  where id = 'skin_red'; -- "Tiburón SkillCash", el color de marca
-- Tematicos (patrones/forma distinta)
update colmillos_shop_items set price = 110 where id = 'skin_abyss';
update colmillos_shop_items set price = 115 where id = 'skin_camo';
update colmillos_shop_items set price = 120 where id = 'skin_tiger';
update colmillos_shop_items set price = 130 where id = 'skin_martillo';
-- Premium (los mas vistosos de todo el catalogo de skins)
update colmillos_shop_items set price = 150 where id = 'skin_rayosx';
update colmillos_shop_items set price = 160 where id = 'skin_galaxy';
update colmillos_shop_items set price = 165 where id = 'skin_neon';
update colmillos_shop_items set price = 175 where id = 'skin_arcoiris';
update colmillos_shop_items set price = 180 where id = 'skin_oroliquido';
update colmillos_shop_items set price = 190 where id = 'skin_dragon';

-- ===== ACCESORIOS (precio de entrada, tier Comun) =====
-- Basicos
update colmillos_shop_items set price = 55  where id = 'acc_sandalias';
update colmillos_shop_items set price = 60  where id = 'acc_scarf';
update colmillos_shop_items set price = 60  where id = 'acc_collar';
update colmillos_shop_items set price = 65  where id = 'acc_tenis';
update colmillos_shop_items set price = 70  where id = 'acc_cap';
update colmillos_shop_items set price = 70  where id = 'acc_shades';
update colmillos_shop_items set price = 70  where id = 'acc_aletasbuceo';
update colmillos_shop_items set price = 70  where id = 'acc_botasnieve';
update colmillos_shop_items set price = 75  where id = 'acc_paraguas';
update colmillos_shop_items set price = 75  where id = 'acc_gafas3d';
update colmillos_shop_items set price = 80  where id = 'acc_corazon';
-- Tematicos
update colmillos_shop_items set price = 95  where id = 'acc_mazo';
update colmillos_shop_items set price = 95  where id = 'acc_raqueta';
update colmillos_shop_items set price = 100 where id = 'acc_guantes';
update colmillos_shop_items set price = 100 where id = 'acc_bate';
update colmillos_shop_items set price = 100 where id = 'acc_antifaz';
update colmillos_shop_items set price = 100 where id = 'acc_microfono';
update colmillos_shop_items set price = 105 where id = 'acc_scuba';
update colmillos_shop_items set price = 105 where id = 'acc_espada';
update colmillos_shop_items set price = 105 where id = 'acc_headphones';
update colmillos_shop_items set price = 110 where id = 'acc_sombrero';
update colmillos_shop_items set price = 110 where id = 'acc_varita';
update colmillos_shop_items set price = 115 where id = 'acc_botaspirata';
update colmillos_shop_items set price = 115 where id = 'acc_patines';
update colmillos_shop_items set price = 115 where id = 'acc_buceo';
update colmillos_shop_items set price = 120 where id = 'acc_escudo';
update colmillos_shop_items set price = 120 where id = 'acc_monoculo';
-- Premium
update colmillos_shop_items set price = 160 where id = 'acc_cape';
update colmillos_shop_items set price = 170 where id = 'acc_chain';
update colmillos_shop_items set price = 180 where id = 'acc_laser';
update colmillos_shop_items set price = 185 where id = 'acc_aletarobot';
update colmillos_shop_items set price = 190 where id = 'acc_crown';
update colmillos_shop_items set price = 195 where id = 'acc_cyberpunk';

-- ===== FONDOS NORMALES (sin rareza, precio final) =====
update colmillos_shop_items set price = 110 where id = 'bg_surface';
update colmillos_shop_items set price = 115 where id = 'bg_abyss';
update colmillos_shop_items set price = 120 where id = 'bg_reef';
update colmillos_shop_items set price = 130 where id = 'bg_pradera';
update colmillos_shop_items set price = 140 where id = 'bg_playa';
update colmillos_shop_items set price = 175 where id = 'bg_desierto';
update colmillos_shop_items set price = 180 where id = 'bg_nieve';
update colmillos_shop_items set price = 190 where id = 'bg_selva';
update colmillos_shop_items set price = 195 where id = 'bg_night';
update colmillos_shop_items set price = 200 where id = 'bg_atardecer';
update colmillos_shop_items set price = 210 where id = 'bg_sunken_city';
update colmillos_shop_items set price = 215 where id = 'bg_volcano';
update colmillos_shop_items set price = 220 where id = 'bg_tormenta';
update colmillos_shop_items set price = 270 where id = 'bg_laboratorio';
update colmillos_shop_items set price = 290 where id = 'bg_cueva';
update colmillos_shop_items set price = 310 where id = 'bg_neon';
update colmillos_shop_items set price = 320 where id = 'bg_nave';

-- ===== FONDOS CRIPTO (sin rareza, el escalon mas caro de TODA la tienda) =====
update colmillos_shop_items set price = 350 where id = 'bg_cripto_pepe';
update colmillos_shop_items set price = 370 where id = 'bg_cripto_dogecoin';
update colmillos_shop_items set price = 400 where id = 'bg_cripto_monero';
update colmillos_shop_items set price = 440 where id = 'bg_cripto_solana';
update colmillos_shop_items set price = 470 where id = 'bg_cripto_ethereum';
update colmillos_shop_items set price = 500 where id = 'bg_cripto_bitcoin';

-- ===== BOLETO DE SORTEO (sin rareza) =====
update colmillos_shop_items set price = 50 where id = 'raffle_ticket';
