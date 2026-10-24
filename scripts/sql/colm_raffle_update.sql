-- Actualiza el boleto de sorteo: precio mas alto (el premio es real) y recuerda que el tope de
-- 1 boleto por cuenta por mes YA esta cubierto por el unique(user_id,event_type,period_key) que
-- trae user_colmillos_events desde create_colmillos.sql - no hace falta tocar nada mas aca, el
-- codigo (assets/js/colmillos.js, buyColmillosItem) ahora usa el mes actual ('YYYY-MM') como
-- period_key de la compra en vez de un uuid aleatorio, asi que una segunda compra el mismo mes
-- choca con esa unique y queda bloqueada por la base de datos misma.
--
-- Ejecutar una sola vez en el SQL editor de Supabase.

update colmillos_shop_items set price = 1000 where id = 'raffle_ticket';

-- Nota aparte (no es una migracion, es solo contexto): el requisito de "tener Bitunix
-- conectado con el codigo de Juan para poder participar" todavia NO esta aplicado aca ni en el
-- codigo - por ahora el boleto se puede comprar sin esa validacion, solo se avisa en el texto
-- de la pagina que va a ser un requisito proximamente (pedido explicito de Juan: que se sepa,
-- pero sin bloquear todavia). Cuando se active de verdad, hace falta:
--   1) en buyColmillosItem (colmillos.js), antes de dejar comprar un 'raffle_ticket', revisar
--      que exista una fila en user_exchange_connections para ese user_id con exchange='bitunix'
--      y status='connected' (o el check especial de OWNER_USER_ID que ya existe en loadBitunixStatus);
--   2) decidir que pasa si alguien compra el boleto, lo tiene guardado, y DESPUES desconecta
--      Bitunix antes del sorteo (¿se le respeta el boleto ya comprado o no participa?).
