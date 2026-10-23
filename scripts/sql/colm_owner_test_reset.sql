-- Resetea la cuenta del dueño (Juan) en la tienda de Colmillos para poder PROBAR skins,
-- accesorios y evoluciones tal cual las ve cualquier usuario normal (antes su cuenta tenia
-- todo desbloqueado y al maximo de rareza gratis, sin pasar por la tienda - eso ya se quito
-- del codigo). En su lugar:
--   1) Borra todo lo que haya comprado/evolucionado (como si no hubiera adquirido nada).
--   2) Le da un saldo grande de Sharkoins de prueba para poder comprar y evolucionar a gusto.
--
-- Es SEGURO correrlo mas de una vez cuando quieras "reiniciar" la prueba: el paso 1 deshace
-- cualquier compra/evolucion que hayas hecho (eso tambien te devuelve esos Sharkoins), y el
-- paso 2 no duplica el credito (on conflict do nothing) - asi que correrlo de nuevo te deja
-- otra vez con el mismo saldo grande, sin acumular cada vez que lo corras.
--
-- Ejecutar en el SQL editor de Supabase cada vez que quieras "empezar de cero" en la tienda.

delete from user_colmillos_events
  where user_id = 'e4309251-6078-4233-aab3-6ab8d6c624e1'
    and (event_type like 'purchase_%' or event_type like 'evolve_%');

delete from user_colmillos_equipped
  where user_id = 'e4309251-6078-4233-aab3-6ab8d6c624e1';

-- 50 filas de 1000 (el tope por fila del ledger es 1200) = 50,000 Sharkoins de prueba. No es
-- "infinito" (el ledger no lo permite en una sola fila), pero alcanza de sobra para comprar y
-- evolucionar a Mitico TODO el catalogo varias veces.
insert into user_colmillos_events (user_id, event_type, period_key, amount)
select 'e4309251-6078-4233-aab3-6ab8d6c624e1', 'owner_test_credit', 'credit_' || gs, 1000
from generate_series(1, 50) as gs
on conflict do nothing;
