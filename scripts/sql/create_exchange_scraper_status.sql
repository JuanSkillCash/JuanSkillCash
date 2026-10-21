-- Tabla compartida por los dos radares (Nuevos Listados y Deslistados): guarda el ESTADO
-- de la corrida mas reciente de cada scraper, para poder distinguir en el panel "este
-- exchange no tiene nada nuevo ahora mismo" (sin fila aca, o status='ok' con 0 filas) de
-- "no se pudo ni revisar esta vez" (status='blocked' - bloqueo de red/WAF/rate-limit,
-- confirmado por el scraper mismo via ExchangeBlocked). Un solo registro por
-- (exchange, radar): siempre pisa el anterior, solo interesa el estado mas reciente.
-- Ejecutar una sola vez en el SQL editor de Supabase.

create table if not exists exchange_scraper_status (
    exchange text not null,
    radar text not null,              -- 'new_listings' | 'delistings'
    status text not null default 'ok',  -- 'ok' | 'blocked'
    detail text,                      -- mensaje corto del motivo (403, Access Denied, etc.)
    checked_at timestamptz not null default now(),
    primary key (exchange, radar)
);

alter table exchange_scraper_status enable row level security;

create policy "Lectura publica de exchange_scraper_status"
    on exchange_scraper_status for select
    using (true);
