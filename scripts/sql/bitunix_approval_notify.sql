-- Aviso cuando una conexion de Bitunix queda aprobada: notificacion dentro del sitio
-- (campanita, user_notifications) siempre, y ademas por Telegram si la persona ya vinculo su
-- Telegram y marco la casilla "avisame por Telegram" al pedir la conexion.
--
-- Ejecutar una sola vez en el SQL editor de Supabase. Seguro de correr mas de una vez.

alter table user_exchange_connections
    add column if not exists notify_telegram boolean not null default false;

-- user_notifications se creo pensado solo en los radares de Deslistados/Nuevos Listados
-- (scripts/sql/create_user_watchlist_notifications.sql) - se le agrega "kind" para poder
-- guardar otros tipos de aviso (como este) sin tocar las columnas que ya usa el radar.
-- "symbol" deja de ser obligatorio porque un aviso de aprobacion de Bitunix no tiene moneda.
alter table user_notifications
    add column if not exists kind text not null default 'watchlist';
alter table user_notifications
    alter column symbol drop not null;
