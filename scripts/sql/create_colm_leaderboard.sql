-- Ranking semanal/mensual del minijuego "Salto del Tiburón" (ver scripts/sql/create_colmillos.sql
-- y create_colmillos_minigame.sql). Guarda UN puntaje por partida jugada (nunca se actualiza/
-- borra, es historial puro) y expone dos funciones para leerlo:
--
--   get_colm_leaderboard(p_period)        -> top 10 del periodo EN CURSO ('weekly'/'monthly'),
--                                            con username (nunca user_id). Pensada para el
--                                            frontend - cualquier usuario logueado puede llamarla.
--   get_colm_leaderboard_for_award(ini,fin) -> top 10 de un rango de fechas exacto, con user_id
--                                            incluido. Solo para el robot que otorga los premios
--                                            (scripts/award_colm_leaderboard.py, con la service
--                                            role key) - nadie mas puede ejecutarla.
--
-- Ejecutar una sola vez en el SQL editor de Supabase (despues de create_colmillos_minigame.sql).

create table if not exists colm_game_scores (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    score integer not null check (score >= 0),
    created_at timestamptz not null default now()
);
create index if not exists colm_game_scores_created_at_idx on colm_game_scores(created_at);
create index if not exists colm_game_scores_user_created_idx on colm_game_scores(user_id, created_at);

alter table colm_game_scores enable row level security;
drop policy if exists "usuario registra su propio puntaje" on colm_game_scores;
create policy "usuario registra su propio puntaje"
    on colm_game_scores for insert
    with check (auth.uid() = user_id);
-- sin policy de select: el ranking se lee SOLO a traves de get_colm_leaderboard (abajo), nunca
-- directo a la tabla, asi nadie puede ver todas las partidas de otra persona.

-- nombre a mostrar: mismo orden de prioridad que getDisplayName() en index.html (username
-- elegido al registrarse -> nombre de Google -> lo que venga antes de la @ del correo).
create or replace function public.get_colm_leaderboard(p_period text)
returns table(rank integer, username text, score integer)
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_cutoff timestamptz;
begin
  if p_period = 'weekly' then
    v_cutoff := date_trunc('week', now());
  elsif p_period = 'monthly' then
    v_cutoff := date_trunc('month', now());
  else
    raise exception 'periodo invalido: %', p_period;
  end if;

  return query
    select
      row_number() over (order by max(s.score) desc, min(s.created_at) asc)::integer as rank,
      coalesce(u.raw_user_meta_data->>'username', u.raw_user_meta_data->>'full_name',
                u.raw_user_meta_data->>'name', split_part(u.email, '@', 1), 'Usuario') as username,
      max(s.score)::integer as score
    from colm_game_scores s
    join auth.users u on u.id = s.user_id
    where s.created_at >= v_cutoff
    group by u.id
    order by max(s.score) desc, min(s.created_at) asc
    limit 10;
end;
$$;
revoke all on function public.get_colm_leaderboard(text) from public;
grant execute on function public.get_colm_leaderboard(text) to authenticated;

-- version para el robot de premios: rango de fechas exacto (el periodo YA TERMINADO, calculado
-- en Python - nunca "ahora", porque para cuando corre el robot ya estamos en el periodo
-- siguiente) y SI incluye user_id, para poder acreditarle los Sharkoins a la cuenta correcta.
create or replace function public.get_colm_leaderboard_for_award(p_start timestamptz, p_end timestamptz)
returns table(user_id uuid, username text, score integer, rnk integer)
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
begin
  return query
    select
      u.id as user_id,
      coalesce(u.raw_user_meta_data->>'username', u.raw_user_meta_data->>'full_name',
                u.raw_user_meta_data->>'name', split_part(u.email, '@', 1), 'Usuario') as username,
      max(s.score)::integer as score,
      row_number() over (order by max(s.score) desc, min(s.created_at) asc)::integer as rnk
    from colm_game_scores s
    join auth.users u on u.id = s.user_id
    where s.created_at >= p_start and s.created_at < p_end
    group by u.id
    order by max(s.score) desc, min(s.created_at) asc
    limit 10;
end;
$$;
revoke all on function public.get_colm_leaderboard_for_award(timestamptz, timestamptz) from public;
grant execute on function public.get_colm_leaderboard_for_award(timestamptz, timestamptz) to service_role;
