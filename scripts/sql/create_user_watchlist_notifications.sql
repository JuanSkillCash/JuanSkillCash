-- Mi Lista + Notificaciones: le permite a un usuario logueado (ya tenemos auth via
-- Supabase, tabla auth.users) marcar que moneda tiene en que exchange, y recibir un aviso
-- dentro del sitio cuando esa moneda aparece en el Radar de Deslistados o de Nuevos
-- Listados para ese exchange (o cualquier exchange, si exchange='any').
--
-- RLS: el usuario solo puede leer/escribir SU PROPIA fila de user_watchlist, y solo LEER
-- (nunca crear) sus propias notificaciones - las notificaciones las crea el robot con la
-- service role key (que se salta RLS), nunca el usuario desde el navegador.
--
-- Ejecutar una sola vez en el SQL editor de Supabase.

create table if not exists user_watchlist (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    symbol text not null,            -- ticker en mayuscula, ej 'BTC' (sin el quote USDT pegado)
    exchange text not null default 'any',  -- 'any' = cualquier exchange, o el nombre exacto (ej 'okx')
    created_at timestamptz not null default now(),
    unique (user_id, symbol, exchange)
);

create index if not exists idx_user_watchlist_symbol on user_watchlist (symbol);

alter table user_watchlist enable row level security;

create policy "usuario ve su propia lista"
    on user_watchlist for select
    using (auth.uid() = user_id);

create policy "usuario agrega a su propia lista"
    on user_watchlist for insert
    with check (auth.uid() = user_id);

create policy "usuario borra de su propia lista"
    on user_watchlist for delete
    using (auth.uid() = user_id);


create table if not exists user_notifications (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    radar text not null,             -- 'delistings' | 'new_listings'
    exchange text not null,
    symbol text not null,
    title text not null,
    source_url text not null,
    event_at timestamptz,            -- delist_at / listed_at / announced_at del aviso, el que haya
    created_at timestamptz not null default now(),
    read_at timestamptz,
    unique (user_id, source_url)
);

create index if not exists idx_user_notifications_user_unread on user_notifications (user_id, read_at);

alter table user_notifications enable row level security;

create policy "usuario ve sus notificaciones"
    on user_notifications for select
    using (auth.uid() = user_id);

create policy "usuario marca sus notificaciones como leidas"
    on user_notifications for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);
