-- Panel de admin v2: pagina propia (/administrador, no modal), con filtros, tabla mas
-- completa (UID del exchange, estado de la conexion, fechas) y graficos de tendencia -
-- pedido explicito de Juan para reemplazar el modal basico de create_admin_dashboard.sql.
--
-- No reemplaza las funciones viejas (get_admin_summary_stats/get_admin_user_table/
-- get_admin_available_months/get_admin_volume_history) - esas se siguen usando para los
-- resumenes y el historial por mes. Esto SOLO agrega lo que faltaba: el detalle de cada
-- conexion de exchange (uid, estado, fechas) y series de tiempo para graficar tendencia.
--
-- Mismo candado que el resto del panel: SECURITY DEFINER + auth.uid() = OWNER_USER_ID
-- revisado en el servidor, sin importar quien llame la funcion.
--
-- Ejecutar una sola vez en el SQL editor de Supabase (despues de create_admin_dashboard.sql).

create or replace function public.get_admin_dashboard_users()
returns table(
    user_id uuid,
    username text,
    signup_at timestamptz,
    exchange text,
    exchange_uid text,
    connect_path text,
    connection_status text,
    connection_requested_at timestamptz,
    connection_reviewed_at timestamptz,
    month_volume_usd numeric,
    current_rank text,
    telegram_connected boolean,
    telegram_linked_at timestamptz,
    sharkoins_balance bigint
)
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
begin
  if auth.uid() <> 'e4309251-6078-4233-aab3-6ab8d6c624e1'::uuid then
    raise exception 'solo el owner puede ver esto';
  end if;

  -- un usuario, una fila - si en el futuro se agrega un segundo exchange y alguien conecta
  -- los dos, esta fila solo trae UNO (el left join no esta pensado para eso todavia); revisar
  -- esto el dia que exista un segundo exchange de verdad.
  return query
    select
      u.id as user_id,
      coalesce(u.raw_user_meta_data->>'username', u.raw_user_meta_data->>'full_name',
                u.raw_user_meta_data->>'name', split_part(u.email, '@', 1), 'Usuario') as username,
      u.created_at as signup_at,
      c.exchange,
      c.uid as exchange_uid,
      c.connect_path,
      c.status as connection_status,
      c.requested_at as connection_requested_at,
      c.reviewed_at as connection_reviewed_at,
      coalesce(v.month_volume_usd, 0) as month_volume_usd,
      coalesce(v.current_rank, 'sin_rango') as current_rank,
      (t.chat_id is not null) as telegram_connected,
      t.linked_at as telegram_linked_at,
      coalesce((select sum(e.amount) from user_colmillos_events e where e.user_id = u.id), 0)::bigint as sharkoins_balance
    from auth.users u
    left join user_exchange_connections c on c.user_id = u.id
    left join user_exchange_volume v on v.user_id = u.id
    left join user_telegram_links t on t.user_id = u.id
    order by u.created_at desc;
end;
$$;
revoke all on function public.get_admin_dashboard_users() from public;
grant execute on function public.get_admin_dashboard_users() to authenticated;

-- serie diaria (ultimos p_days dias, incluye dias en 0) para graficar tendencia: registros
-- nuevos, conexiones de Bitunix aprobadas, Telegram vinculado.
create or replace function public.get_admin_dashboard_timeseries(p_days integer default 30)
returns table(day date, new_signups integer, new_bitunix_connections integer, new_telegram_links integer)
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
      d::date as day,
      (select count(*) from auth.users u where u.created_at::date = d::date)::integer as new_signups,
      (select count(*) from user_exchange_connections c
        where c.exchange = 'bitunix' and c.status = 'connected' and c.reviewed_at::date = d::date)::integer as new_bitunix_connections,
      (select count(*) from user_telegram_links t where t.linked_at::date = d::date)::integer as new_telegram_links
    from generate_series(current_date - (greatest(p_days, 1) - 1), current_date, interval '1 day') d
    order by day;
end;
$$;
revoke all on function public.get_admin_dashboard_timeseries(integer) from public;
grant execute on function public.get_admin_dashboard_timeseries(integer) to authenticated;
