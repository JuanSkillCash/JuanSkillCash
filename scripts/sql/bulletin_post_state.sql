-- Evita que el boletin cripto diario (scripts/post_crypto_bulletin_telegram.py) se mande dos
-- veces el mismo dia: ahora hay DOS caminos que pueden dispararlo (el disparo manual diario a
-- las 8am Colombia + el "schedule" nativo de GitHub Actions como respaldo, por si el disparo
-- manual falla o se queda atascado - ver conversacion con Juan, 28-30 oct 2026, cuando el
-- disparo manual se salto dos dias seguidos). Una sola fila: la fecha (UTC) del ultimo envio.
--
-- Ejecutar una sola vez en el SQL editor de Supabase.

create table if not exists bulletin_post_state (
    id smallint primary key default 1,
    last_posted_date date,
    constraint bulletin_post_state_singleton check (id = 1)
);

alter table bulletin_post_state enable row level security;
-- sin ninguna policy: solo el robot (service role) lee/escribe aca
