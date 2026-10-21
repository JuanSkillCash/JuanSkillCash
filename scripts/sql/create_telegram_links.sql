-- Notificaciones por Telegram: el usuario genera un codigo desde "Mi perfil", le da Start
-- al bot de Telegram con ese codigo (link t.me/<bot>?start=<codigo>), y un robot aparte
-- (scripts/poll_telegram_links.py, corre cada ~5 min via GitHub Actions) revisa los mensajes
-- nuevos del bot (Telegram getUpdates) y, si encuentra el codigo, guarda el chat_id de esa
-- persona aqui. Una vez vinculado, watchlist_notify.py le manda el aviso por Telegram ademas
-- de la notificacion dentro del sitio.
--
-- No hay politica de UPDATE para el usuario: solo el robot (con la service role key, que se
-- salta RLS) puede escribir chat_id/linked_at - el usuario solo puede pedir un codigo nuevo
-- (insert) o desvincularse (delete).
--
-- Ejecutar una sola vez en el SQL editor de Supabase.

create table if not exists user_telegram_links (
    user_id uuid primary key references auth.users(id) on delete cascade,
    link_code text unique,
    chat_id bigint,
    requested_at timestamptz not null default now(),
    linked_at timestamptz
);

alter table user_telegram_links enable row level security;

create policy "usuario ve su propio vinculo de telegram"
    on user_telegram_links for select
    using (auth.uid() = user_id);

create policy "usuario pide su propio codigo"
    on user_telegram_links for insert
    with check (auth.uid() = user_id);

create policy "usuario se puede desvincular"
    on user_telegram_links for delete
    using (auth.uid() = user_id);


-- fila unica (id=1) que recuerda hasta donde ya se leyeron los mensajes del bot (offset de
-- Telegram getUpdates) - sin esto, cada corrida del poller volveria a leer los mismos
-- mensajes viejos una y otra vez. Nadie necesita leer/escribir esto desde el navegador, solo
-- el robot con la service role key - RLS habilitado sin ninguna policy = nadie mas entra.
create table if not exists telegram_poll_state (
    id smallint primary key default 1,
    last_update_id bigint not null default 0,
    constraint telegram_poll_state_singleton check (id = 1)
);
insert into telegram_poll_state (id, last_update_id) values (1, 0) on conflict (id) do nothing;

alter table telegram_poll_state enable row level security;
