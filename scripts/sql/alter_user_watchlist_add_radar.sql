-- Mi Lista: separa el seguimiento por radar. Al principio una fila de user_watchlist
-- aplicaba a Deslistados Y Nuevos Listados a la vez (sin distincion); el usuario pidio que
-- la opcion de "seguir esta moneda" viva DENTRO de cada indicador por separado (Radar de
-- Deslistados / Radar de Nuevos Listados), asi que ahora cada fila dice para cual de los
-- dos es, y ya no se mezclan entre si.
--
-- Ejecutar una sola vez en el SQL editor de Supabase, DESPUES de
-- create_user_watchlist_notifications.sql.

alter table user_watchlist add column if not exists radar text;
update user_watchlist set radar = 'delistings' where radar is null;
alter table user_watchlist alter column radar set not null;

do $$ begin
    if not exists (
        select 1 from pg_constraint where conname = 'user_watchlist_radar_check'
    ) then
        alter table user_watchlist add constraint user_watchlist_radar_check
            check (radar in ('delistings', 'new_listings'));
    end if;
end $$;

alter table user_watchlist drop constraint if exists user_watchlist_user_id_symbol_exchange_key;
alter table user_watchlist add constraint user_watchlist_user_id_symbol_exchange_radar_key
    unique (user_id, symbol, exchange, radar);
