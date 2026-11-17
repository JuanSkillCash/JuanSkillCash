-- Fase 3 de "Mi Arrecife": varios paneles (pestañas) por usuario, en vez de uno solo.
--
-- Reemplaza a user_dashboards (Fase 1, una sola fila por usuario) - ahora cada usuario puede
-- tener VARIAS filas, una por pestaña/panel ("Predeterminado", "Trading", lo que arme) ya que
-- position decide el orden de las pestañas. user_dashboards NO se borra ni se toca - se deja
-- intacta por seguridad, pero el frontend deja de leerla/escribirla desde este cambio.
--
-- layout es un array JSON de posiciones/tamanos de gridstack, nunca HTML ni contenido:
-- [{ "id":"w-fngsummary", "x":0, "y":0, "w":3, "h":2, "cfg":{} }, ...]
-- "id" es el id del widget en WIDGET_REGISTRY (index.html); "cfg" es para preferencias futuras
-- por widget (ej. rango temporal de un grafico), vacio por ahora.
--
-- schema_version existe para poder migrar el formato de layout mas adelante sin romper los
-- paneles ya guardados.
--
-- Ejecutar una sola vez en el SQL editor de Supabase. Seguro de correr mas de una vez.

create table if not exists user_arrecife_boards (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null check (char_length(name) between 1 and 40),
    layout jsonb not null default '[]'::jsonb,
    schema_version int not null default 1,
    position int not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint user_arrecife_boards_layout_is_array check (jsonb_typeof(layout) = 'array'),
    constraint user_arrecife_boards_layout_max check (jsonb_array_length(layout) <= 40)
);
create index if not exists user_arrecife_boards_user_position on user_arrecife_boards (user_id, position);

alter table user_arrecife_boards enable row level security;
drop policy if exists "usuario ve sus paneles" on user_arrecife_boards;
create policy "usuario ve sus paneles" on user_arrecife_boards for select using (auth.uid() = user_id);
drop policy if exists "usuario crea sus paneles" on user_arrecife_boards;
create policy "usuario crea sus paneles" on user_arrecife_boards for insert with check (auth.uid() = user_id);
drop policy if exists "usuario edita sus paneles" on user_arrecife_boards;
create policy "usuario edita sus paneles" on user_arrecife_boards for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "usuario borra sus paneles" on user_arrecife_boards;
create policy "usuario borra sus paneles" on user_arrecife_boards for delete using (auth.uid() = user_id);

create or replace function user_arrecife_boards_touch() returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end; $$;
drop trigger if exists user_arrecife_boards_touch on user_arrecife_boards;
create trigger user_arrecife_boards_touch before update on user_arrecife_boards
    for each row execute function user_arrecife_boards_touch();

-- Migracion de datos: cada usuario que ya tenia un panel guardado en user_dashboards (Fase 1)
-- pasa a tener una sola fila aqui, nombrada "Mi panel", position 0 - solo si todavia no tiene
-- NINGUNA fila en user_arrecife_boards (asi correr este script 2 veces no duplica nada).
insert into user_arrecife_boards (user_id, name, layout, schema_version, position)
select ud.user_id, 'Mi panel', ud.layout, ud.schema_version, 0
from user_dashboards ud
where not exists (
    select 1 from user_arrecife_boards b where b.user_id = ud.user_id
)
and jsonb_array_length(ud.layout) > 0;

-- Borrar la cuenta ya borra estas filas solas (on delete cascade via auth.users), pero si algun
-- dia "Eliminar mi cuenta" pasa a borrar tablas una por una en vez de depender del cascade,
-- user_arrecife_boards tiene que agregarse a esa lista igual que las demas tablas por user_id.
