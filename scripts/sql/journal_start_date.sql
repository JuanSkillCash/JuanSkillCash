-- Permite que un usuario de la Bitacora "empiece de cero" desde una fecha: las operaciones
-- anteriores a journal_start_date se ocultan de la vista y de las estadisticas (no se borran -
-- siguen en trade_journal_trades, si se vuelve a poner journal_start_date en null, reaparecen
-- tal cual estaban). Pedido explicito de Juan para su propia cuenta (quiere que su Bitacora
-- arranque en noviembre 2026, sin agosto/septiembre/octubre), pero queda disponible para
-- cualquier usuario - ver assets/js/journal.js (filtro en loadAll).
--
-- Ejecutar una sola vez en el SQL editor de Supabase. Seguro de correr mas de una vez.

alter table trade_journal_settings
    add column if not exists journal_start_date date;

-- Para aplicarselo a Juan (arranca en noviembre 2026):
-- insert into trade_journal_settings (user_id, journal_start_date)
--     values ('e4309251-6078-4233-aab3-6ab8d6c624e1', '2026-11-01')
--     on conflict (user_id) do update set journal_start_date = excluded.journal_start_date;
