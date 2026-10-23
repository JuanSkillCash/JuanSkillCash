-- Notificaciones por Telegram: el usuario genera un codigo desde "Mi perfil", le da Start
-- al bot de Telegram con ese codigo (link t.me/<bot>?start=<codigo>), y la Edge Function
-- supabase/functions/telegram-webhook/index.ts (que Telegram llama AL INSTANTE via webhook,
-- no por polling) guarda el chat_id de esa persona aqui apenas le llega el "/start <codigo>".
-- Una vez vinculado, watchlist_notify.py le manda el aviso por Telegram ademas de la
-- notificacion dentro del sitio.
--
-- (Version anterior, archivada: scripts/legacy/poll_telegram_links.py revisaba los mensajes
-- del bot por polling cada cierto tiempo via GitHub Actions - se reemplazo por el webhook de
-- arriba porque el polling tardaba demasiado, hasta casi una hora en la practica.)
--
-- No hay politica de UPDATE para el usuario: solo la Edge Function (con la service role key,
-- que se salta RLS) puede escribir chat_id/linked_at - el usuario solo puede pedir un codigo
-- nuevo (insert) o desvincularse (delete).
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


-- SIN USO desde que se paso al webhook (ver arriba) - solo la usaba scripts/legacy/poll_telegram_links.py
-- para recordar hasta donde ya se habian leido los mensajes del bot (offset de Telegram
-- getUpdates); el webhook no necesita ningun offset. Se deja la tabla tal cual por si algun
-- dia hay que volver al polling.
create table if not exists telegram_poll_state (
    id smallint primary key default 1,
    last_update_id bigint not null default 0,
    constraint telegram_poll_state_singleton check (id = 1)
);
insert into telegram_poll_state (id, last_update_id) values (1, 0) on conflict (id) do nothing;

alter table telegram_poll_state enable row level security;
