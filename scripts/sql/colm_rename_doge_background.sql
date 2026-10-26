-- Renombra el fondo de Dogecoin: antes decia "Shiba a la Luna", pero Shiba Inu es otra
-- moneda distinta y confundia - ahora solo hace referencia a Dogecoin.
--
-- Ejecutar una sola vez en el SQL editor de Supabase. Seguro de correr mas de una vez.

update colmillos_shop_items set name = 'Doge a la Luna (Dogecoin)' where id = 'bg_cripto_dogecoin';
