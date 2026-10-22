-- "Colmillos": moneda de coleccion/engagement, TOTALMENTE separada del volumen de trading y
-- del rango de "Rango de Manada" - se gana por USAR la plataforma (visitar, conectar
-- Telegram/Bitunix, completar el perfil), nunca por operar mas. A proposito no se ata a
-- trading para no repetir el error de BCD (puntos por volumen que empujan a sobreoperar, ver
-- docs/referencia-bcd-dashboard.md seccion 11).
--
-- Es un ledger (solo se inserta, nunca se actualiza/borra) - el saldo de cada quien es la suma
-- de sus propias filas. period_key hace de llave de deduplicacion: para eventos diarios es la
-- fecha ('2026-10-22'), para hitos de una sola vez en la vida es el texto literal 'once' - el
-- unique de abajo cubre ambos casos con la misma columna, asi un evento nunca se puede volver a
-- otorgar dos veces el mismo dia (o dos veces en la vida, para los hitos).
--
-- RLS: cada quien ve y registra SOLO sus propios colmillos. No hay policy de update/delete -
-- el ledger es append-only.
--
-- Ejecutar una sola vez en el SQL editor de Supabase.

create table if not exists user_colmillos_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    event_type text not null,
    period_key text not null,
    amount integer not null check (amount > 0 and amount <= 20),
    created_at timestamptz not null default now(),
    unique (user_id, event_type, period_key)
);

alter table user_colmillos_events enable row level security;

create policy "usuario ve sus propios colmillos"
    on user_colmillos_events for select
    using (auth.uid() = user_id);

create policy "usuario registra sus propios colmillos"
    on user_colmillos_events for insert
    with check (auth.uid() = user_id);
