-- Cashback de Bitunix que cada usuario ha recibido en su cuenta spot por el 20% de descuento
-- que ofrece Juan (ver docs/bitunix-partner-api.md, endpoint totalTransaction con
-- userType=user) - pedido explicito de Juan: que se vea bien resaltado en la Bitacora cuanto
-- se ha ganado en esos reembolsos, porque no es un simple descuento sino plata de vuelta.
--
-- Se guarda UNA fila por usuario/mes (se va actualizando con el total mas reciente de ese mes
-- cada vez que corre el robot, igual que user_exchange_volume) - el saldo historico total es
-- la suma de todas las filas de ese usuario.
--
-- Ejecutar una sola vez en el SQL editor de Supabase.

create table if not exists user_bitunix_cashback (
    user_id uuid not null references auth.users(id) on delete cascade,
    month text not null, -- 'YYYY-MM' (UTC)
    cashback_usdt numeric not null default 0,
    updated_at timestamptz not null default now(),
    primary key (user_id, month)
);

alter table user_bitunix_cashback enable row level security;

create policy "usuario ve su propio cashback"
    on user_bitunix_cashback for select
    using (auth.uid() = user_id);
-- sin policy de insert/update: solo el robot (service role) escribe aca
