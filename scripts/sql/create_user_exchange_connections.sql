-- Conexion de exchange por UID (sin API key): el usuario pide conectar su cuenta de Bitunix
-- por dos caminos posibles (connect_path):
--   'referral_new'      -> se registra de cero con el link de afiliado de Juan y pega su UID.
--   'transfer_existing' -> ya tenia cuenta antes; pide traslado manual pegando su UID y
--                          subiendo una captura de su panel (la revisa el propio soporte de
--                          Bitunix, no un robot nuestro).
--
-- No hay politica de UPDATE para el usuario: el cambio de status (pending -> connected /
-- rejected) lo hace Juan a mano desde el SQL editor de Supabase (o mas adelante un panel de
-- admin), nunca el usuario desde el navegador - asi nadie se "auto-aprueba".
--
-- Ejecutar una sola vez en el SQL editor de Supabase.

create table if not exists user_exchange_connections (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    exchange text not null default 'bitunix',
    connect_path text not null check (connect_path in ('referral_new', 'transfer_existing')),
    uid text not null,
    screenshot_path text,
    status text not null default 'pending' check (status in ('pending', 'connected', 'rejected')),
    review_note text,
    requested_at timestamptz not null default now(),
    reviewed_at timestamptz,
    unique (user_id, exchange)
);

alter table user_exchange_connections enable row level security;

create policy "usuario ve su propia conexion de exchange"
    on user_exchange_connections for select
    using (auth.uid() = user_id);

create policy "usuario pide su propia conexion de exchange"
    on user_exchange_connections for insert
    with check (auth.uid() = user_id);

-- si una solicitud queda rechazada o quiere corregir el UID antes de que se revise, puede
-- volver a intentar borrando su propia fila pendiente/rechazada (nunca una ya 'connected')
create policy "usuario borra su propia conexion no aprobada"
    on user_exchange_connections for delete
    using (auth.uid() = user_id and status <> 'connected');


-- Storage: bucket privado para las capturas de pantalla de "ya tengo cuenta" (traslado
-- manual). No es publico - solo el propio usuario puede subir a su carpeta, y solo Juan
-- (service role, desde el dashboard de Supabase) puede leerlas para revisar.
insert into storage.buckets (id, name, public)
values ('exchange-screenshots', 'exchange-screenshots', false)
on conflict (id) do nothing;

create policy "usuario sube su propia captura de exchange"
    on storage.objects for insert
    with check (
        bucket_id = 'exchange-screenshots'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy "usuario ve su propia captura de exchange"
    on storage.objects for select
    using (
        bucket_id = 'exchange-screenshots'
        and (storage.foldername(name))[1] = auth.uid()::text
    );
