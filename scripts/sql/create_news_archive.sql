-- Historial buscable de "Noticias" (Cripto / Macro y Economía) - antes las noticias solo vivían
-- en el caché de 30 min del Worker (workers/rss-news/) y cuando un titular salía del RSS del
-- medio (normalmente trae los últimos 20-50 nada más) desaparecía para siempre, sin forma de
-- volver a verlo. Juan pidió poder ver noticias de las últimas 24h Y buscar noticias viejas.
--
-- scripts/update_news_archive.py (via GitHub Actions, scripts/sql y patrón ya usado en
-- economic_calendar_ff_cache) le pide al propio Worker de noticias (que ya traduce + resume +
-- analiza sentimiento) sus últimos titulares y los guarda aquí - "link" es único a propósito:
-- on_conflict=link con resolution=ignore-duplicates (NO merge-duplicates) hace que una noticia
-- que ya se guardó una vez NUNCA se vuelva a sobreescribir en corridas futuras, así el resumen
-- de IA solo se gasta la primera vez que se ve esa noticia, nunca de nuevo (igual que prometido
-- a Juan sobre el gasto de Workers AI).
--
-- Lectura pública (el sitio la busca sin que la persona haya iniciado sesión) pero SIN policy de
-- escritura - solo el service role (usado por el script de GitHub Actions) puede escribir, mismo
-- patrón que economic_calendar_ff_cache/exchange_scraper_status.
--
-- Ejecutar una sola vez en el SQL editor de Supabase. Seguro de correr más de una vez.

create table if not exists news_archive (
    id bigserial primary key,
    link text not null unique,
    title text not null,
    source text,
    category text not null check (category in ('crypto', 'macro')),
    published_at timestamptz,
    resumen text,
    resumen_largo text,
    imagen text,
    sentimiento text check (sentimiento in ('alcista', 'bajista', 'neutral') or sentimiento is null),
    inserted_at timestamptz not null default now()
);

-- orden por fecha (vista "últimas 24h" y resultados de búsqueda, más nuevo primero) y filtro por
-- categoría son las dos consultas que hace el sitio - sin estos índices una tabla grande se
-- volvería lenta de buscar con el tiempo
create index if not exists news_archive_published_at_idx on news_archive (published_at desc);
create index if not exists news_archive_category_idx on news_archive (category);

alter table news_archive enable row level security;

drop policy if exists "Lectura publica de news_archive" on news_archive;
create policy "Lectura publica de news_archive"
    on news_archive for select
    using (true);
