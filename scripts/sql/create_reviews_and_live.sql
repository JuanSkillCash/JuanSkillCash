-- Reseñas de la plataforma + indicador "EN VIVO" + numeros publicos de la comunidad.
--
-- 1) platform_reviews: cada usuario registrado puede dejar UNA reseña (estrellas 1-5 + comentario)
--    y editarla o borrarla cuando quiera. Cualquiera (incluso sin cuenta) puede leerlas. El nombre
--    que se muestra lo pone la base de datos desde el perfil (no lo manda la pagina), asi nadie
--    puede firmar con el nombre de otro. El dueño (Juan) puede ocultar o borrar cualquier reseña.
-- 2) site_status: una sola fila con "estoy en vivo si/no" + el link al directo. Solo el dueño
--    la puede cambiar (desde el Panel de admin de la pagina, o con el UPDATE de abajo).
-- 3) get_public_stats(): cuantos usuarios registrados hay (para la seccion "Creado por Juan
--    SkillCash"), sin exponer ningun dato de nadie.
--
-- Ejecutar una sola vez en el SQL editor de Supabase. Seguro de correr mas de una vez.

-- ===== 1) Reseñas =====
create table if not exists platform_reviews (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique references auth.users(id) on delete cascade,
    display_name text not null default 'Usuario',
    rating integer not null check (rating between 1 and 5),
    comment text not null check (char_length(trim(comment)) between 3 and 500),
    hidden boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table platform_reviews enable row level security;

drop policy if exists "reseñas visibles para todos" on platform_reviews;
create policy "reseñas visibles para todos"
    on platform_reviews for select
    using (hidden = false or auth.uid() = user_id or auth.uid() = 'e4309251-6078-4233-aab3-6ab8d6c624e1'::uuid);

drop policy if exists "usuario crea su reseña" on platform_reviews;
create policy "usuario crea su reseña"
    on platform_reviews for insert
    with check (auth.uid() = user_id);

drop policy if exists "usuario edita su reseña o el dueño modera" on platform_reviews;
create policy "usuario edita su reseña o el dueño modera"
    on platform_reviews for update
    using (auth.uid() = user_id or auth.uid() = 'e4309251-6078-4233-aab3-6ab8d6c624e1'::uuid);

drop policy if exists "usuario borra su reseña o el dueño modera" on platform_reviews;
create policy "usuario borra su reseña o el dueño modera"
    on platform_reviews for delete
    using (auth.uid() = user_id or auth.uid() = 'e4309251-6078-4233-aab3-6ab8d6c624e1'::uuid);

-- el nombre visible sale del perfil real, y solo el dueño puede ocultar/mostrar una reseña
create or replace function platform_reviews_before_write()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    is_owner boolean := auth.uid() = 'e4309251-6078-4233-aab3-6ab8d6c624e1'::uuid;
begin
    if tg_op = 'INSERT' or new.user_id = auth.uid() then
        select coalesce(nullif(trim(u.raw_user_meta_data->>'username'), ''), 'Usuario')
          into new.display_name
          from auth.users u where u.id = new.user_id;
    end if;
    if tg_op = 'INSERT' and not is_owner then
        new.hidden := false;
    elsif tg_op = 'UPDATE' and not is_owner then
        new.hidden := old.hidden;
    end if;
    new.updated_at := now();
    return new;
end;
$$;

drop trigger if exists platform_reviews_before_write on platform_reviews;
create trigger platform_reviews_before_write
    before insert or update on platform_reviews
    for each row execute function platform_reviews_before_write();

-- ===== 2) Indicador EN VIVO =====
create table if not exists site_status (
    id integer primary key default 1 check (id = 1),
    is_live boolean not null default false,
    live_url text not null default 'https://www.tiktok.com/@juanskll/live',
    updated_at timestamptz not null default now()
);
insert into site_status (id) values (1) on conflict do nothing;

alter table site_status enable row level security;

drop policy if exists "estado visible para todos" on site_status;
create policy "estado visible para todos"
    on site_status for select using (true);

drop policy if exists "solo el dueño cambia el estado" on site_status;
create policy "solo el dueño cambia el estado"
    on site_status for update
    using (auth.uid() = 'e4309251-6078-4233-aab3-6ab8d6c624e1'::uuid);

-- Para prender/apagar el EN VIVO a mano (tambien hay un boton en el Panel de admin):
--   update site_status set is_live = true,  updated_at = now() where id = 1;
--   update site_status set is_live = false, updated_at = now() where id = 1;

-- ===== 3) Numeros publicos =====
create or replace function get_public_stats()
returns json
language sql
security definer
set search_path = public
as $$
    select json_build_object(
        'users', (select count(*) from auth.users),
        'reviews', (select count(*) from platform_reviews where hidden = false),
        'avg_rating', (select round(avg(rating)::numeric, 1) from platform_reviews where hidden = false)
    );
$$;
grant execute on function get_public_stats() to anon, authenticated;
