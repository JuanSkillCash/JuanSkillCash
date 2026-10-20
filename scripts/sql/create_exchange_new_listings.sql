-- Radar de Nuevos Listados: tabla hermana de exchange_delistings, misma forma general.
-- Ejecutar una sola vez en el SQL editor de Supabase.

create table if not exists exchange_new_listings (
    id bigint generated always as identity primary key,
    exchange text not null,
    symbol text not null,
    pair_base text not null,
    market text,                 -- 'spot' | 'futures' | null
    asset_class text not null default 'crypto',  -- 'crypto' | 'stock' | 'index' | 'commodity'
    announced_at timestamptz,
    listed_at timestamptz,       -- cuando empieza a operar, si el aviso lo trae (si no, null = ya esta live)
    title text not null,
    source_url text not null,
    status text not null default 'live',  -- 'upcoming' | 'live'
    created_at timestamptz not null default now(),
    unique (exchange, symbol, source_url)
);

create index if not exists idx_exchange_new_listings_listed_at on exchange_new_listings (listed_at);
create index if not exists idx_exchange_new_listings_exchange on exchange_new_listings (exchange);
create index if not exists idx_exchange_new_listings_asset_class on exchange_new_listings (asset_class);

alter table exchange_new_listings enable row level security;

create policy "Lectura publica de exchange_new_listings"
    on exchange_new_listings for select
    using (true);
