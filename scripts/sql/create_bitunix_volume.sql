-- Volumen de trading real (en USD) por usuario conectado a Bitunix, usado para calcular el
-- rango de la cajita "Rango de Manada". Se acumula de forma incremental: cada corrida del
-- robot (scripts/update_bitunix_volume.py) suma el volumen generado desde la ultima revision
-- (last_checked_at) hasta ahora, y lo agrega a cumulative_volume_usd - asi nunca hace falta
-- pedirle a la API de Bitunix mas de ~180 dias de historial en una sola llamada (su limite).
--
-- No hay politica de UPDATE/INSERT para el usuario: solo el robot (con la service role key)
-- escribe aca - el usuario solo puede LEER su propia fila, para mostrarla en la cajita.
--
-- Ejecutar una sola vez en el SQL editor de Supabase.

create table if not exists user_exchange_volume (
    user_id uuid primary key references auth.users(id) on delete cascade,
    exchange text not null default 'bitunix',
    uid text not null,
    cumulative_volume_usd numeric not null default 0,
    current_rank text not null default 'cria',
    last_checked_at timestamptz,
    updated_at timestamptz not null default now()
);

alter table user_exchange_volume enable row level security;

create policy "usuario ve su propio volumen"
    on user_exchange_volume for select
    using (auth.uid() = user_id);
