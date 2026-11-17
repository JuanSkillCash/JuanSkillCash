-- Copia de Forex Factory (horario/importancia/prevision/anterior) del calendario economico,
-- refrescada por scripts/update_economic_calendar_ff.py via GitHub Actions en vez de por el
-- Cron Trigger del Worker de Cloudflare (workers/economic-calendar/worker.js).
--
-- Por que: Forex Factory empezo a devolver 429 (demasiadas peticiones) a las IPs compartidas de
-- Cloudflare Workers de forma sostenida desde el 17-nov-2026 (confirmado en vivo con Juan) - no
-- por trafico nuestro (una peticion cada 30 min desde siempre), sino porque esas IPs se
-- comparten entre miles de clientes de Cloudflare. Las IPs de los runners de GitHub Actions son
-- un rango distinto, asi que el refresco se mueve para alla.
--
-- Una sola fila (id=1, se sobreescribe en cada corrida) con el array completo de eventos ya
-- transformado - el Worker sigue haciendo el resto (enriquecer con Nasdaq/FRED, filtrar por
-- fecha/pais) igual que antes, solo cambia de donde saca la base de Forex Factory.
--
-- Lectura publica (el Worker la lee con la llave publica anon, sin necesitar un secreto nuevo
-- del lado de Cloudflare) pero SIN policy de escritura - solo el service role (usado por el
-- script de GitHub Actions) puede escribir, igual que en exchange_scraper_status.
--
-- Ejecutar una sola vez en el SQL editor de Supabase. Seguro de correr mas de una vez.

create table if not exists economic_calendar_ff_cache (
    id smallint primary key default 1,
    eventos jsonb not null default '[]'::jsonb,
    actualizado timestamptz not null default now(),
    constraint economic_calendar_ff_cache_singleton check (id = 1)
);

alter table economic_calendar_ff_cache enable row level security;

drop policy if exists "Lectura publica de economic_calendar_ff_cache" on economic_calendar_ff_cache;
create policy "Lectura publica de economic_calendar_ff_cache"
    on economic_calendar_ff_cache for select
    using (true);
