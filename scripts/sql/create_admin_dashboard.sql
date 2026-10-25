-- Panel de administrador (solo para Juan): metricas agregadas del sitio y una tabla por
-- usuario (volumen de Bitunix, saldo de Sharkoins, nivel interno, conexiones). Pensado para
-- verse en index.html SOLO si auth.uid() = OWNER_USER_ID (mismo UUID hardcodeado que ya usa
-- el frontend) - pero esa comprobacion en el navegador es solo cosmetica (cualquiera con
-- devtools podria saltarsela): la proteccion real esta aca, en las dos funciones
-- security definer de abajo, que SIEMPRE revisan auth.uid() en el servidor antes de devolver
-- un solo dato, sin importar como las llamen. A proposito NO se tocan las policies de
-- select existentes en user_exchange_volume/user_telegram_links/user_exchange_connections/
-- user_colmillos_events (cada usuario sigue viendo solo lo suyo directo de esas tablas) -
-- el admin lee todo exclusivamente a traves de estas dos funciones, nunca de las tablas.
--
-- NO incluye que moneda sigue cada usuario (su watchlist), por decision explicita de Juan.
--
-- Ejecutar una sola vez en el SQL editor de Supabase (despues de create_bitunix_volume.sql,
-- create_telegram_links.sql, create_user_exchange_connections.sql y create_colmillos.sql).

-- Ledger de uso de herramientas (para activos por dia/semana y categorias mas usadas). Mismo
-- patron append-only + period_key que user_colmillos_events: una fila por usuario/categoria/
-- dia, nunca se actualiza. Sin policy de select - solo se lee a traves de
-- get_admin_summary_stats (abajo), nunca directo, asi nadie ve el detalle de otro usuario.
create table if not exists tool_usage_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    category text not null,
    period_key text not null, -- 'YYYY-MM-DD' (UTC) del dia en que se uso
    created_at timestamptz not null default now(),
    unique (user_id, category, period_key)
);
create index if not exists tool_usage_events_created_at_idx on tool_usage_events(created_at);

alter table tool_usage_events enable row level security;

create policy "usuario registra su propio uso"
    on tool_usage_events for insert
    with check (auth.uid() = user_id);

-- tabla por persona: volumen de Bitunix, nivel interno, Sharkoins, conexiones. Username con
-- el mismo orden de prioridad que el resto del sitio (ver create_colm_leaderboard.sql).
create or replace function public.get_admin_user_table()
returns table(
    username text,
    bitunix_connected boolean,
    month_volume_usd numeric,
    current_rank text,
    telegram_connected boolean,
    sharkoins_balance bigint,
    sharkoins_24h bigint
)
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
begin
  if auth.uid() <> 'e4309251-6078-4233-aab3-6ab8d6c624e1'::uuid then
    raise exception 'solo el owner puede ver esto';
  end if;

  return query
    select
      coalesce(u.raw_user_meta_data->>'username', u.raw_user_meta_data->>'full_name',
                u.raw_user_meta_data->>'name', split_part(u.email, '@', 1), 'Usuario') as username,
      exists(
        select 1 from user_exchange_connections c
        where c.user_id = u.id and c.status = 'connected'
      ) as bitunix_connected,
      coalesce(v.month_volume_usd, 0) as month_volume_usd,
      coalesce(v.current_rank, 'sin_rango') as current_rank,
      exists(
        select 1 from user_telegram_links t
        where t.user_id = u.id and t.chat_id is not null
      ) as telegram_connected,
      coalesce((
        select sum(e.amount) from user_colmillos_events e where e.user_id = u.id
      ), 0)::bigint as sharkoins_balance,
      coalesce((
        select sum(e.amount) from user_colmillos_events e
        where e.user_id = u.id and e.created_at > now() - interval '24 hours'
      ), 0)::bigint as sharkoins_24h
    from auth.users u
    left join user_exchange_volume v on v.user_id = u.id
    order by month_volume_usd desc nulls last, username asc;
end;
$$;
revoke all on function public.get_admin_user_table() from public;
grant execute on function public.get_admin_user_table() to authenticated;

-- resumen agregado del sitio, en un solo jsonb (mas facil de consumir en el frontend que
-- varias filas sueltas).
create or replace function public.get_admin_summary_stats()
returns jsonb
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_total_users integer;
  v_telegram_count integer;
  v_bitunix_count integer;
  v_rank_distribution jsonb;
  v_sharkoins_today bigint;
  v_sharkoins_week bigint;
  v_dau integer;
  v_wau integer;
  v_top_categories jsonb;
  v_new_signups_week integer;
begin
  if auth.uid() <> 'e4309251-6078-4233-aab3-6ab8d6c624e1'::uuid then
    raise exception 'solo el owner puede ver esto';
  end if;

  select count(*) into v_total_users from auth.users;

  select count(*) into v_telegram_count
    from user_telegram_links where chat_id is not null;

  select count(*) into v_bitunix_count
    from user_exchange_connections where status = 'connected';

  select coalesce(jsonb_object_agg(current_rank, cnt), '{}'::jsonb) into v_rank_distribution
    from (
      select current_rank, count(*) as cnt
      from user_exchange_volume
      group by current_rank
    ) r;

  select coalesce(sum(amount), 0) into v_sharkoins_today
    from user_colmillos_events where created_at >= date_trunc('day', now());

  select coalesce(sum(amount), 0) into v_sharkoins_week
    from user_colmillos_events where created_at >= date_trunc('week', now());

  select count(distinct user_id) into v_dau
    from tool_usage_events where created_at >= date_trunc('day', now());

  select count(distinct user_id) into v_wau
    from tool_usage_events where created_at >= date_trunc('week', now());

  select coalesce(jsonb_agg(jsonb_build_object('category', category, 'count', cnt) order by cnt desc), '[]'::jsonb)
    into v_top_categories
    from (
      select category, count(*) as cnt
      from tool_usage_events
      where created_at >= now() - interval '7 days'
      group by category
      order by count(*) desc
      limit 5
    ) c;

  select count(*) into v_new_signups_week
    from auth.users where created_at >= date_trunc('week', now());

  return jsonb_build_object(
    'total_users', v_total_users,
    'telegram_connected_count', v_telegram_count,
    'bitunix_connected_count', v_bitunix_count,
    'rank_distribution', v_rank_distribution,
    'sharkoins_today', v_sharkoins_today,
    'sharkoins_week', v_sharkoins_week,
    'dau', v_dau,
    'wau', v_wau,
    'top_categories', v_top_categories,
    'new_signups_week', v_new_signups_week
  );
end;
$$;
revoke all on function public.get_admin_summary_stats() from public;
grant execute on function public.get_admin_summary_stats() to authenticated;

-- Historial de volumen mensual: user_exchange_volume (arriba) PISA la fila de cada usuario
-- cada vez que corre el robot (solo guarda el mes EN CURSO, por diseño - ver
-- create_bitunix_volume.sql), asi que nunca hubo forma de ver meses pasados. A partir de
-- este cambio, scripts/update_bitunix_volume.py ADEMAS guarda una copia aca cada vez que
-- corre, con upsert por (user_id, month) - cada mes se va refrescando con el numero mas
-- reciente hasta que termina, y ahi se queda fijo para siempre. Ojo: esto NO recupera meses
-- anteriores a cuando se activo esto, esos datos ya se perdieron porque nunca se guardaron.
--
-- Sin ninguna policy de select: ni siquiera el propio usuario puede leer esta tabla directo -
-- solo se lee a traves de get_admin_volume_history()/get_admin_available_months() (abajo),
-- que revisan auth.uid() contra el owner igual que el resto del panel de admin. Solo el
-- robot (service role, que se salta RLS) escribe aca.
create table if not exists user_exchange_volume_history (
    user_id uuid not null references auth.users(id) on delete cascade,
    month text not null, -- 'YYYY-MM' (UTC)
    trade_count integer not null default 0,
    month_volume_usd numeric not null default 0,
    current_rank text not null default 'sin_rango',
    updated_at timestamptz not null default now(),
    primary key (user_id, month)
);

alter table user_exchange_volume_history enable row level security;

create or replace function public.get_admin_available_months()
returns text[]
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
begin
  if auth.uid() <> 'e4309251-6078-4233-aab3-6ab8d6c624e1'::uuid then
    raise exception 'solo el owner puede ver esto';
  end if;

  return coalesce((select array_agg(distinct month order by month desc) from user_exchange_volume_history), '{}'::text[]);
end;
$$;
revoke all on function public.get_admin_available_months() from public;
grant execute on function public.get_admin_available_months() to authenticated;

create or replace function public.get_admin_volume_history(p_month text)
returns table(username text, month_volume_usd numeric, trade_count integer, current_rank text)
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
begin
  if auth.uid() <> 'e4309251-6078-4233-aab3-6ab8d6c624e1'::uuid then
    raise exception 'solo el owner puede ver esto';
  end if;

  return query
    select
      coalesce(u.raw_user_meta_data->>'username', u.raw_user_meta_data->>'full_name',
                u.raw_user_meta_data->>'name', split_part(u.email, '@', 1), 'Usuario') as username,
      h.month_volume_usd,
      h.trade_count,
      h.current_rank
    from user_exchange_volume_history h
    join auth.users u on u.id = h.user_id
    where h.month = p_month
    order by h.month_volume_usd desc;
end;
$$;
revoke all on function public.get_admin_volume_history(text) from public;
grant execute on function public.get_admin_volume_history(text) to authenticated;
