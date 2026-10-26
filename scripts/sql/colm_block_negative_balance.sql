-- Bloquea en la BASE DE DATOS cualquier gasto de Sharkoins que deje el saldo en negativo
-- (compras, evoluciones, apuestas perdidas del casino - todo lo que entra al ledger con
-- amount < 0).
--
-- Hasta ahora el "¿te alcanza?" solo lo revisaba la pagina, y eso se puede saltar: varios
-- clics muy rapidos en comprar (cada uno ve el mismo saldo antes de que el otro se guarde),
-- un error de lectura como el de las 1000 filas, o alguien manipulando la pagina a mano.
-- Con este trigger la propia base de datos rechaza el gasto, pase lo que pase en la pagina.
--
-- El pg_advisory_xact_lock hace que los gastos de una MISMA persona se procesen de a uno
-- (el segundo clic espera a que termine el primero y ya ve el saldo descontado) - los de
-- personas distintas no se esperan entre si.
--
-- Los ingresos (amount > 0) no se tocan, y si alguien ya tuviera saldo negativo de antes,
-- puede seguir ganando normal; solo no puede gastar hasta volver a tener con que.
--
-- Ejecutar una sola vez en el SQL editor de Supabase. Seguro de correr mas de una vez.

create or replace function colm_check_balance_before_spend()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    current_balance bigint;
begin
    if new.amount >= 0 then
        return new;
    end if;

    perform pg_advisory_xact_lock(hashtextextended('colm_balance_' || new.user_id::text, 0));

    select coalesce(sum(amount), 0) into current_balance
    from user_colmillos_events
    where user_id = new.user_id;

    if current_balance + new.amount < 0 then
        raise exception 'No tenés suficientes Sharkoins para esto (saldo: %, costo: %).',
            current_balance, -new.amount
            using errcode = 'P0001', hint = 'colm_saldo_insuficiente';
    end if;

    return new;
end;
$$;

drop trigger if exists colm_check_balance_before_spend on user_colmillos_events;
create trigger colm_check_balance_before_spend
    before insert on user_colmillos_events
    for each row execute function colm_check_balance_before_spend();
