-- Agrega al catalogo de la tienda de Colmillos (ver create_colmillos_minigame.sql): 6
-- accesorios de ojos (van en la "cara", igual que acc_shades/acc_antifaz) y 6 fondos con
-- tema cripto para el tiburon. Los assets (PNG) ya estan en el repo:
--   assets/mascot/accessories/acc_ojos_*.png (96x96, transparente)
--   assets/mascot/backgrounds/fondo_cripto_*.png (320x200)
--
-- Ejecutar una sola vez en el SQL editor de Supabase (despues de create_colmillos_minigame.sql).
-- Seguro de correr mas de una vez (on conflict do nothing).

insert into colmillos_shop_items (id, category, name, price) values
    ('acc_laser', 'accessory', 'Ojos Láser', 55),
    ('acc_corazon', 'accessory', 'Gafas de Corazón', 40),
    ('acc_monoculo', 'accessory', 'Monóculo', 45),
    ('acc_gafas3d', 'accessory', 'Gafas 3D', 40),
    ('acc_cyberpunk', 'accessory', 'Visor Cyberpunk', 60),
    ('acc_buceo', 'accessory', 'Careta de Buceo', 50),
    ('bg_cripto_bitcoin', 'background', 'Bóveda Minera (Bitcoin)', 90),
    ('bg_cripto_ethereum', 'background', 'Valle de Cristal (Ethereum)', 85),
    ('bg_cripto_solana', 'background', 'Pista Veloz (Solana)', 85),
    ('bg_cripto_monero', 'background', 'Callejón Privado (Monero)', 80),
    ('bg_cripto_pepe', 'background', 'Estanque de Ranas (Pepe)', 75),
    ('bg_cripto_dogecoin', 'background', 'Shiba a la Luna (Dogecoin)', 75)
on conflict do nothing;
