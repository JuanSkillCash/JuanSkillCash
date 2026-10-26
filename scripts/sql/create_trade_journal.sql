-- Bitacora de trading (herramienta de Rango de Manada; por ahora solo la ve el dueño).
--
-- 1) trade_journal_trades: cada operacion, venga de registro manual (source='manual') o de la
--    sincronizacion automatica con Bitunix (source='bitunix', external_id = positionId de
--    Bitunix, asi una re-sincronizacion actualiza en vez de duplicar). Todo en dolares (USDT).
--      pnl     = P&L realizado bruto (sin comisiones ni funding)
--      fees    = comisiones pagadas (positivo = costo)
--      funding = funding cobrado (+) o pagado (-)
--      neto    = pnl - fees + funding   (lo calcula la pagina)
-- 2) trade_journal_settings / trade_journal_capital: capital inicial por defecto y, si se
--    quiere, uno distinto para cada mes (para la rentabilidad % y el drawdown %).
-- 3) trade_journal_sync: estado de la conexion automatica (lo puede leer el usuario).
--    trade_journal_secrets: la API key y el secreto CIFRADOS. Tiene RLS activado y NINGUNA
--    politica: desde el navegador no se puede leer ni escribir nada ahi, ni siquiera el propio
--    dueño de la clave. Solo la Edge Function trade-journal-sync (con la service_role key) la
--    toca, y solo guarda el secreto cifrado con AES-GCM (clave en el secret
--    JOURNAL_ENCRYPTION_KEY de la funcion, que nunca esta en la base de datos).
--
-- Ejecutar una sola vez en el SQL editor de Supabase. Seguro de correr mas de una vez.

-- ===== 1) Operaciones =====
create table if not exists trade_journal_trades (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    source text not null default 'manual' check (source in ('manual', 'bitunix')),
    external_id text,
    symbol text not null check (char_length(symbol) between 1 and 30),
    side text not null check (side in ('long', 'short')),
    status text not null default 'closed' check (status in ('open', 'closed')),
    leverage numeric check (leverage is null or (leverage > 0 and leverage <= 500)),
    margin numeric check (margin is null or margin >= 0),
    qty numeric check (qty is null or qty >= 0),
    entry_price numeric check (entry_price is null or entry_price >= 0),
    exit_price numeric check (exit_price is null or exit_price >= 0),
    stop_loss numeric,
    take_profit numeric,
    pnl numeric,
    fees numeric not null default 0,
    funding numeric not null default 0,
    opened_at timestamptz not null default now(),
    closed_at timestamptz,
    setup text check (setup is null or char_length(setup) <= 60),
    tags text[] not null default '{}',
    emotion text check (emotion is null or char_length(emotion) <= 30),
    rating smallint check (rating is null or rating between 1 and 5),
    notes text check (notes is null or char_length(notes) <= 2000),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, source, external_id)
);
create index if not exists trade_journal_trades_user_closed on trade_journal_trades (user_id, closed_at desc);

alter table trade_journal_trades enable row level security;
drop policy if exists "usuario ve sus operaciones" on trade_journal_trades;
create policy "usuario ve sus operaciones" on trade_journal_trades for select using (auth.uid() = user_id);
drop policy if exists "usuario crea sus operaciones" on trade_journal_trades;
create policy "usuario crea sus operaciones" on trade_journal_trades for insert with check (auth.uid() = user_id);
drop policy if exists "usuario edita sus operaciones" on trade_journal_trades;
create policy "usuario edita sus operaciones" on trade_journal_trades for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "usuario borra sus operaciones" on trade_journal_trades;
create policy "usuario borra sus operaciones" on trade_journal_trades for delete using (auth.uid() = user_id);

create or replace function trade_journal_touch() returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end; $$;
drop trigger if exists trade_journal_trades_touch on trade_journal_trades;
create trigger trade_journal_trades_touch before update on trade_journal_trades
    for each row execute function trade_journal_touch();

-- ===== 2) Capital =====
create table if not exists trade_journal_settings (
    user_id uuid primary key references auth.users(id) on delete cascade,
    default_capital numeric not null default 1000 check (default_capital > 0),
    updated_at timestamptz not null default now()
);
alter table trade_journal_settings enable row level security;
drop policy if exists "usuario maneja sus ajustes de bitacora" on trade_journal_settings;
create policy "usuario maneja sus ajustes de bitacora" on trade_journal_settings for all
    using (auth.uid() = user_id) with check (auth.uid() = user_id);

create table if not exists trade_journal_capital (
    user_id uuid not null references auth.users(id) on delete cascade,
    month text not null check (month ~ '^\d{4}-\d{2}$'),
    starting_capital numeric not null check (starting_capital > 0),
    primary key (user_id, month)
);
alter table trade_journal_capital enable row level security;
drop policy if exists "usuario maneja su capital mensual" on trade_journal_capital;
create policy "usuario maneja su capital mensual" on trade_journal_capital for all
    using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ===== 3) Conexion automatica =====
create table if not exists trade_journal_sync (
    user_id uuid not null references auth.users(id) on delete cascade,
    exchange text not null default 'bitunix',
    status text not null default 'disconnected' check (status in ('connected', 'error', 'disconnected')),
    api_key_hint text,
    last_sync_at timestamptz,
    last_error text,
    trades_synced integer not null default 0,
    connected_at timestamptz,
    primary key (user_id, exchange)
);
alter table trade_journal_sync enable row level security;
drop policy if exists "usuario ve el estado de su conexion" on trade_journal_sync;
create policy "usuario ve el estado de su conexion" on trade_journal_sync for select using (auth.uid() = user_id);
-- (sin insert/update/delete para el usuario: solo la Edge Function cambia el estado)

create table if not exists trade_journal_secrets (
    user_id uuid not null references auth.users(id) on delete cascade,
    exchange text not null default 'bitunix',
    api_key_enc text not null,
    api_secret_enc text not null,
    updated_at timestamptz not null default now(),
    primary key (user_id, exchange)
);
alter table trade_journal_secrets enable row level security;
-- a proposito SIN politicas: nadie la puede leer/escribir desde el navegador
