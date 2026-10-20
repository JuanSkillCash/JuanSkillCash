-- Agrega asset_class a exchange_delistings (ya existente) para que tenga la misma
-- clasificación crypto/acción/índice/commodity que exchange_new_listings.
-- Ejecutar una sola vez en el SQL editor de Supabase, ANTES de correr el backfill.

alter table exchange_delistings
    add column if not exists asset_class text not null default 'crypto';

create index if not exists idx_exchange_delistings_asset_class on exchange_delistings (asset_class);
