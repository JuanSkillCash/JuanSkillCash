-- Dashboard personalizable de "Mi Arrecife" (Fase 1): un layout de widgets por usuario.
--
-- Una sola fila por usuario. layout es un array JSON de posiciones/tamanos de gridstack,
-- nunca HTML ni contenido: [{ "id":"w-fngsummary", "x":0, "y":0, "w":3, "h":2, "cfg":{} }, ...]
-- "id" es el id del widget en WIDGET_REGISTRY (index.html); "cfg" es para preferencias futuras
-- por widget (ej. rango temporal de un grafico), vacio en Fase 1.
--
-- schema_version existe para poder migrar el formato de layout mas adelante sin romper los
-- paneles ya guardados (la pagina descarta ids que ya no existan y ajusta w/h a los limites
-- vigentes al cargar, pero un cambio de forma mas grande se distingue por este numero).
--
-- Ejecutar una sola vez en el SQL editor de Supabase. Seguro de correr mas de una vez.

create table if not exists user_dashboards (
    user_id uuid primary key references auth.users(id) on delete cascade,
    layout jsonb not null default '[]'::jsonb,
    schema_version int not null default 1,
    updated_at timestamptz not null default now(),
    constraint user_dashboards_layout_is_array check (jsonb_typeof(layout) = 'array'),
    constraint user_dashboards_layout_max check (jsonb_array_length(layout) <= 40)
);

alter table user_dashboards enable row level security;
drop policy if exists "usuario ve su dashboard" on user_dashboards;
create policy "usuario ve su dashboard" on user_dashboards for select using (auth.uid() = user_id);
drop policy if exists "usuario crea su dashboard" on user_dashboards;
create policy "usuario crea su dashboard" on user_dashboards for insert with check (auth.uid() = user_id);
drop policy if exists "usuario edita su dashboard" on user_dashboards;
create policy "usuario edita su dashboard" on user_dashboards for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "usuario borra su dashboard" on user_dashboards;
create policy "usuario borra su dashboard" on user_dashboards for delete using (auth.uid() = user_id);

create or replace function user_dashboards_touch() returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end; $$;
drop trigger if exists user_dashboards_touch on user_dashboards;
create trigger user_dashboards_touch before update on user_dashboards
    for each row execute function user_dashboards_touch();

-- Borrar la cuenta ya borra esta fila sola (on delete cascade via auth.users), pero si algun
-- dia "Eliminar mi cuenta" pasa a borrar tablas una por una en vez de depender del cascade,
-- user_dashboards tiene que agregarse a esa lista igual que las demas tablas por user_id.
