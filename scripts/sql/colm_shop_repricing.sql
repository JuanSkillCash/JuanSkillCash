-- Re-precio completo de la tienda de Colmillos (ver create_colmillos_minigame.sql y
-- add_colm_eyes_and_crypto_backgrounds.sql). Antes casi todo costaba parecido (30-110) y los
-- fondos cripto no se sentian especiales. Ahora cada cosa varia segun que tan "rarita"/vistosa
-- es, con 3 escalones para skins/accesorios/fondos normales:
--   Basico    (colores/objetos simples)      ~1 semana de juego dedicado
--   Tematico  (con mas diseño/personalidad)  ~2-3 semanas
--   Premium   (lo mas vistoso de su tipo)    ~3-4 semanas
-- y los fondos cripto en su propio escalon, por encima de TODO lo demas (son el "premio
-- mayor" de la tienda) - Bitcoin llega al tope que permite el sistema (500, ver el check de
-- user_colmillos_events.amount).
--
-- Son puros UPDATE (las filas ya existen) - seguro de correr mas de una vez.
-- Ejecutar una sola vez en el SQL editor de Supabase.

-- ===== SKINS =====
-- Basicos (colores lisos)
update colmillos_shop_items set price = 100 where id = 'skin_cyan';
update colmillos_shop_items set price = 105 where id = 'skin_lime';
update colmillos_shop_items set price = 110 where id = 'skin_emerald';
update colmillos_shop_items set price = 115 where id = 'skin_violet';
update colmillos_shop_items set price = 120 where id = 'skin_pink';
update colmillos_shop_items set price = 125 where id = 'skin_ice';
update colmillos_shop_items set price = 130 where id = 'skin_gold';
update colmillos_shop_items set price = 135 where id = 'skin_orange';
update colmillos_shop_items set price = 150 where id = 'skin_red'; -- "Tiburón SkillCash", el color de marca
-- Tematicos (patrones/forma distinta)
update colmillos_shop_items set price = 210 where id = 'skin_abyss';
update colmillos_shop_items set price = 230 where id = 'skin_camo';
update colmillos_shop_items set price = 240 where id = 'skin_tiger';
update colmillos_shop_items set price = 260 where id = 'skin_martillo'; -- forma de tiburón martillo, no solo color
-- Premium (los mas vistosos de todo el catalogo de skins)
update colmillos_shop_items set price = 300 where id = 'skin_rayosx';
update colmillos_shop_items set price = 320 where id = 'skin_galaxy';
update colmillos_shop_items set price = 330 where id = 'skin_neon';
update colmillos_shop_items set price = 350 where id = 'skin_arcoiris';
update colmillos_shop_items set price = 360 where id = 'skin_oroliquido';
update colmillos_shop_items set price = 370 where id = 'skin_dragon';

-- ===== ACCESORIOS =====
-- Basicos
update colmillos_shop_items set price = 90  where id = 'acc_sandalias';
update colmillos_shop_items set price = 100 where id = 'acc_scarf';
update colmillos_shop_items set price = 100 where id = 'acc_collar';
update colmillos_shop_items set price = 105 where id = 'acc_tenis';
update colmillos_shop_items set price = 110 where id = 'acc_cap';
update colmillos_shop_items set price = 110 where id = 'acc_shades';
update colmillos_shop_items set price = 115 where id = 'acc_aletasbuceo';
update colmillos_shop_items set price = 115 where id = 'acc_botasnieve';
update colmillos_shop_items set price = 120 where id = 'acc_paraguas';
update colmillos_shop_items set price = 125 where id = 'acc_gafas3d';
update colmillos_shop_items set price = 130 where id = 'acc_corazon';
-- Tematicos
update colmillos_shop_items set price = 155 where id = 'acc_mazo';
update colmillos_shop_items set price = 155 where id = 'acc_raqueta';
update colmillos_shop_items set price = 160 where id = 'acc_guantes';
update colmillos_shop_items set price = 160 where id = 'acc_bate';
update colmillos_shop_items set price = 165 where id = 'acc_antifaz';
update colmillos_shop_items set price = 165 where id = 'acc_microfono';
update colmillos_shop_items set price = 170 where id = 'acc_scuba';
update colmillos_shop_items set price = 170 where id = 'acc_espada';
update colmillos_shop_items set price = 180 where id = 'acc_sombrero';
update colmillos_shop_items set price = 180 where id = 'acc_varita';
update colmillos_shop_items set price = 175 where id = 'acc_headphones';
update colmillos_shop_items set price = 185 where id = 'acc_botaspirata';
update colmillos_shop_items set price = 190 where id = 'acc_patines';
update colmillos_shop_items set price = 190 where id = 'acc_buceo';
update colmillos_shop_items set price = 195 where id = 'acc_escudo';
update colmillos_shop_items set price = 200 where id = 'acc_monoculo';
-- Premium
update colmillos_shop_items set price = 260 where id = 'acc_cape';
update colmillos_shop_items set price = 280 where id = 'acc_chain';
update colmillos_shop_items set price = 300 where id = 'acc_laser';
update colmillos_shop_items set price = 310 where id = 'acc_aletarobot';
update colmillos_shop_items set price = 320 where id = 'acc_crown';
update colmillos_shop_items set price = 330 where id = 'acc_cyberpunk';

-- ===== FONDOS NORMALES =====
-- Basicos
update colmillos_shop_items set price = 110 where id = 'bg_surface';
update colmillos_shop_items set price = 115 where id = 'bg_abyss';
update colmillos_shop_items set price = 120 where id = 'bg_reef';
update colmillos_shop_items set price = 130 where id = 'bg_pradera';
update colmillos_shop_items set price = 140 where id = 'bg_playa';
-- Tematicos
update colmillos_shop_items set price = 175 where id = 'bg_desierto';
update colmillos_shop_items set price = 180 where id = 'bg_nieve';
update colmillos_shop_items set price = 190 where id = 'bg_selva';
update colmillos_shop_items set price = 195 where id = 'bg_night';
update colmillos_shop_items set price = 200 where id = 'bg_atardecer';
update colmillos_shop_items set price = 210 where id = 'bg_sunken_city';
update colmillos_shop_items set price = 215 where id = 'bg_volcano';
update colmillos_shop_items set price = 220 where id = 'bg_tormenta';
-- Premium (los mas elaborados de los fondos "normales")
update colmillos_shop_items set price = 270 where id = 'bg_laboratorio';
update colmillos_shop_items set price = 290 where id = 'bg_cueva';
update colmillos_shop_items set price = 310 where id = 'bg_neon';
update colmillos_shop_items set price = 320 where id = 'bg_nave';

-- ===== FONDOS CRIPTO (el escalon mas caro de TODA la tienda) =====
update colmillos_shop_items set price = 350 where id = 'bg_cripto_pepe';
update colmillos_shop_items set price = 370 where id = 'bg_cripto_dogecoin';
update colmillos_shop_items set price = 400 where id = 'bg_cripto_monero';
update colmillos_shop_items set price = 440 where id = 'bg_cripto_solana';
update colmillos_shop_items set price = 470 where id = 'bg_cripto_ethereum';
update colmillos_shop_items set price = 500 where id = 'bg_cripto_bitcoin'; -- tope del sistema: el item mas caro de toda la tienda

-- ===== BOLETO DE SORTEO =====
-- sigue siendo barato a proposito (se puede comprar varias veces), pero ya no tan regalado
update colmillos_shop_items set price = 50 where id = 'raffle_ticket';
