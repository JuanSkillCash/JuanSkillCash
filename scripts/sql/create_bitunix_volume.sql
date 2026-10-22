-- Volumen de trading real (en USD) del MES EN CURSO por usuario conectado a Bitunix, usado
-- para calcular el rango de la cajita "Rango de Manada". El rango se reinicia cada mes
-- (decision explicita de Juan, para que la gente tenga que seguir operando) - por eso esta
-- tabla NO acumula de por vida: cada corrida de scripts/update_bitunix_volume.py vuelve a
-- sumar desde el dia 1 del mes en curso (UTC) hasta ahora y PISA month_volume_usd/trade_count
-- con el total fresco. Como un mes nunca pasa de 31 dias, siempre cabe en el limite de 180
-- dias por llamada de la API de Bitunix, y el "reinicio" pasa solo en cuanto cambia el mes,
-- sin ningun cron especial para resetear nada.
--
-- No hay politica de UPDATE/INSERT para el usuario: solo el robot (con la service role key)
-- escribe aca - el usuario solo puede LEER su propia fila, para mostrarla en la cajita.
--
-- Ejecutar una sola vez en el SQL editor de Supabase.

create table if not exists user_exchange_volume (
    user_id uuid primary key references auth.users(id) on delete cascade,
    exchange text not null default 'bitunix',
    uid text not null,
    month text not null, -- 'YYYY-MM' (UTC) del mes que reflejan las columnas de abajo
    trade_count integer not null default 0,
    month_volume_usd numeric not null default 0,
    current_rank text not null default 'sin_rango', -- sin_rango|cria|explorador|cazador|depredador|alfa
    updated_at timestamptz not null default now()
);

alter table user_exchange_volume enable row level security;

create policy "usuario ve su propio volumen"
    on user_exchange_volume for select
    using (auth.uid() = user_id);
