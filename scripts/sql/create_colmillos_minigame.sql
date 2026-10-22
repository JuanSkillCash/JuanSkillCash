-- Extiende el sistema de Colmillos (ver scripts/sql/create_colmillos.sql) con: trivia diaria,
-- minijuego, y la tienda de personalizacion del tiburon. Todo sigue 100% aparte del volumen de
-- trading / Rango de Manada - esto es solo coleccion/engagement.
--
-- Ejecutar una sola vez en el SQL editor de Supabase (DESPUES de create_colmillos.sql).

-- 1) El ledger de user_colmillos_events ahora tambien registra COMPRAS en la tienda (montos
--    negativos) ademas de lo que ya ganaba (montos positivos) - se amplia el rango permitido.
--    NOTA DE SEGURIDAD: igual que el resto del sistema de Colmillos, esto confia en el cliente
--    para el monto exacto (no hay Edge Function que valide el saldo antes de la compra) - es a
--    proposito, porque los Colmillos no tienen valor real todavia, solo coleccion.
alter table user_colmillos_events drop constraint if exists user_colmillos_events_amount_check;
alter table user_colmillos_events add constraint user_colmillos_events_amount_check
    check (amount <> 0 and amount between -500 and 20);

-- 2) Preguntas de trivia diaria - una tabla chica de preguntas basicas de cripto/trading, se
--    elige una distinta cada dia (todo el mundo ve la MISMA pregunta el mismo dia, calculado en
--    el navegador con la fecha UTC como semilla - no hace falta una tabla de "pregunta de hoy").
--    Catalogo publico (todos pueden leer las preguntas, igual que cualquier trivia).
create table if not exists colmillos_trivia_questions (
    id uuid primary key default gen_random_uuid(),
    question text not null,
    options jsonb not null,
    correct_index smallint not null check (correct_index between 0 and 3),
    active boolean not null default true
);
alter table colmillos_trivia_questions enable row level security;
drop policy if exists "catalogo publico de trivia" on colmillos_trivia_questions;
create policy "catalogo publico de trivia"
    on colmillos_trivia_questions for select
    using (active);

insert into colmillos_trivia_questions (question, options, correct_index) values
    ('¿Cuál es el límite máximo de Bitcoin que existirá?', '["21 millones","100 millones","1 millón","Ilimitado"]', 0),
    ('¿Qué significa "HODL" en la jerga cripto?', '["Una orden de venta","Mantener tu inversión a largo plazo","Un tipo de wallet","Un exchange"]', 1),
    ('¿Qué es una "stablecoin"?', '["Una moneda que nunca sube de precio","Una cripto diseñada para mantener un valor estable (ej. atada al dólar)","Un tipo de minería","Una wallet fría"]', 1),
    ('¿Qué hace un "stop loss" en trading?', '["Garantiza ganancias","Cierra tu posición automáticamente para limitar pérdidas","Aumenta tu apalancamiento","Te da más Colmillos"]', 1),
    ('¿Qué es el "halving" de Bitcoin?', '["Cuando se duplica el precio","Cuando se reduce a la mitad la recompensa por minar un bloque","Un tipo de hackeo","Una fork de la red"]', 1),
    ('¿Qué significa DCA en inversión?', '["Dollar Cost Averaging: comprar montos fijos periódicamente","Un tipo de exchange descentralizado","Un indicador técnico","Un impuesto cripto"]', 0),
    ('¿Qué es una wallet "fría" (cold wallet)?', '["Una wallet conectada a internet","Una wallet guardada sin conexión a internet (más segura)","Una wallet gratis","Una wallet de un solo uso"]', 1),
    ('¿Qué significa "apalancamiento" (leverage) en futuros?', '["Operar con más capital del que tienes, prestado por el exchange","Guardar cripto a largo plazo","Un tipo de comisión","Transferir entre exchanges"]', 0),
    ('¿Qué es el "FOMO" en trading?', '["Fear Of Missing Out: miedo a quedarte fuera de una subida","Un indicador técnico","Un tipo de orden","Una wallet"]', 0),
    ('¿Qué es un "rug pull"?', '["Una subida fuerte de precio","Una estafa donde los creadores de un proyecto desaparecen con el dinero","Un tipo de staking","Una actualización de red"]', 1),
    ('¿Qué es el "staking"?', '["Vender toda tu cripto de golpe","Bloquear tus monedas para ayudar a validar la red y ganar recompensas","Un tipo de préstamo bancario","Comprar en el punto más alto"]', 1),
    ('¿Qué significa que una red sea "descentralizada"?', '["La controla un solo banco","No depende de una autoridad central única","Solo funciona en un país","Es más lenta siempre"]', 1),
    ('¿Qué es el "spot trading"?', '["Comprar/vender el activo real de inmediato, sin apalancamiento","Operar solo con futuros","Un tipo de staking","Pedir un préstamo"]', 0),
    ('¿Qué es un "exchange centralizado" (CEX)?', '["Una plataforma donde una empresa gestiona tus fondos y operaciones (ej. Bitunix)","Una wallet personal","Un tipo de blockchain","Un contrato inteligente"]', 0),
    ('¿Qué es el "market cap" de una cripto?', '["El precio de una sola moneda","Precio por unidad multiplicado por el total de monedas en circulación","El volumen diario","La comisión del exchange"]', 1)
on conflict do nothing;

-- 3) Catalogo de la tienda: skins, accesorios y fondos para personalizar el tiburon. Catalogo
--    publico (todos ven los precios), pero solo el propio usuario puede "comprar" (ver el
--    ledger de arriba) y equipar.
create table if not exists colmillos_shop_items (
    id text primary key,
    category text not null check (category in ('skin', 'accessory', 'background', 'raffle')),
    name text not null,
    price integer not null check (price > 0)
);
alter table colmillos_shop_items enable row level security;
drop policy if exists "catalogo publico de la tienda" on colmillos_shop_items;
create policy "catalogo publico de la tienda"
    on colmillos_shop_items for select
    using (true);

insert into colmillos_shop_items (id, category, name, price) values
    ('skin_gold', 'skin', 'Tiburón Dorado', 60),
    ('skin_red', 'skin', 'Tiburón SkillCash', 60),
    ('skin_abyss', 'skin', 'Tiburón del Abismo', 80),
    ('skin_emerald', 'skin', 'Tiburón Esmeralda', 65),
    ('skin_cyan', 'skin', 'Tiburón Cian', 65),
    ('skin_pink', 'skin', 'Tiburón Rosa Choque', 70),
    ('skin_orange', 'skin', 'Tiburón Fuego', 65),
    ('skin_ice', 'skin', 'Tiburón Hielo', 60),
    ('skin_lime', 'skin', 'Tiburón Lima', 65),
    ('skin_violet', 'skin', 'Tiburón Violeta', 70),
    ('skin_camo', 'skin', 'Tiburón Camuflaje', 90),
    ('skin_tiger', 'skin', 'Tiburón Tigre', 90),
    ('skin_galaxy', 'skin', 'Tiburón Galaxia', 100),
    ('skin_arcoiris', 'skin', 'Tiburón Arcoíris Metálico', 110),
    ('skin_oroliquido', 'skin', 'Tiburón Oro Líquido', 110),
    ('skin_neon', 'skin', 'Tiburón Neón Cyberpunk', 110),
    ('skin_dragon', 'skin', 'Tiburón Escamas de Dragón', 110),
    ('skin_martillo', 'skin', 'Tiburón Martillo', 95),
    ('skin_rayosx', 'skin', 'Tiburón Rayos X', 100),
    ('acc_cap', 'accessory', 'Gorra de Capitán', 40),
    ('acc_shades', 'accessory', 'Gafas de Sol', 40),
    ('acc_chain', 'accessory', 'Cadena de Oro', 70),
    ('acc_scuba', 'accessory', 'Casco de Buzo', 55),
    ('acc_scarf', 'accessory', 'Bufanda', 35),
    ('acc_headphones', 'accessory', 'Audífonos Gamer', 55),
    ('acc_crown', 'accessory', 'Corona Dorada', 85),
    ('acc_cape', 'accessory', 'Capa de Pirata', 75),
    ('acc_sombrero', 'accessory', 'Sombrero de Mago', 60),
    ('acc_antifaz', 'accessory', 'Antifaz de Superhéroe', 45),
    ('acc_aletarobot', 'accessory', 'Aleta Robot (Cyborg)', 80),
    ('acc_collar', 'accessory', 'Collar Hawaiano', 35),
    ('acc_paraguas', 'accessory', 'Paraguas Pequeño', 40),
    ('acc_guantes', 'accessory', 'Guantes de Boxeo', 50),
    ('acc_microfono', 'accessory', 'Micrófono de Rapero', 50),
    ('acc_bate', 'accessory', 'Bate de Béisbol', 50),
    ('acc_escudo', 'accessory', 'Escudo Medieval', 60),
    ('acc_espada', 'accessory', 'Espada de Juguete', 50),
    ('acc_mazo', 'accessory', 'Mazo de Juguete', 45),
    ('acc_raqueta', 'accessory', 'Raqueta de Tenis', 45),
    ('acc_varita', 'accessory', 'Varita Mágica', 55),
    ('acc_aletasbuceo', 'accessory', 'Aletas de Buceo', 40),
    ('acc_botasnieve', 'accessory', 'Botas de Nieve', 40),
    ('acc_botaspirata', 'accessory', 'Botas de Pirata', 50),
    ('acc_patines', 'accessory', 'Patines de Ruedas', 55),
    ('acc_sandalias', 'accessory', 'Sandalias de Playa', 30),
    ('acc_tenis', 'accessory', 'Tenis Deportivos', 40),
    ('bg_reef', 'background', 'Arrecife', 50),
    ('bg_abyss', 'background', 'Abismo', 50),
    ('bg_surface', 'background', 'Superficie', 50),
    ('bg_sunken_city', 'background', 'Ciudad Hundida', 70),
    ('bg_volcano', 'background', 'Volcán Submarino', 70),
    ('bg_night', 'background', 'Noche Estrellada', 70),
    ('bg_nave', 'background', 'Nave Espacial / Portal', 90),
    ('bg_tormenta', 'background', 'Tormenta con Rayos', 75),
    ('bg_playa', 'background', 'Playa Tropical', 70),
    ('bg_laboratorio', 'background', 'Laboratorio Submarino', 85),
    ('bg_atardecer', 'background', 'Atardecer Dorado', 75),
    ('bg_selva', 'background', 'Selva', 70),
    ('bg_cueva', 'background', 'Cueva de Cristales', 85),
    ('bg_neon', 'background', 'Ciudad Neón', 90),
    ('bg_pradera', 'background', 'Pradera de Flores', 65),
    ('bg_nieve', 'background', 'Nieve / Polo', 70),
    ('bg_desierto', 'background', 'Desierto', 70),
    ('raffle_ticket', 'raffle', 'Boleto de Sorteo', 25)
on conflict do nothing;

-- 5) Boletos de sorteo comprados: a diferencia de los cosmeticos (que se compran una sola vez
--    en la vida, period_key='once'), un boleto se puede comprar varias veces - por eso cada
--    compra usa un period_key distinto (un uuid generado en el navegador), asi el unique de
--    user_colmillos_events nunca bloquea una segunda/tercera compra. Para ver cuantos boletos
--    tiene alguien: contar filas con event_type='purchase_raffle_ticket'. Juan elige ganador a
--    mano (fuera de la app) mirando esas filas - no hace falta tabla ni robot aparte.

-- 6) Contador global de "toques" a la moneda - un numero compartido que sube cada vez que
--    cualquiera le da clic a la moneda grande en la pagina de Colmillos. Es solo una curiosidad
--    (no otorga Colmillos), por eso es una fila unica aparte, no el ledger. Se usa una funcion
--    con incremento atomico (en vez de leer-y-escribir desde el navegador) para que no se
--    pierdan toques si dos personas le dan clic al mismo tiempo.
create table if not exists colmillos_global_taps (
    id boolean primary key default true,
    total bigint not null default 0,
    check (id)
);
insert into colmillos_global_taps (id, total) values (true, 0) on conflict do nothing;
alter table colmillos_global_taps enable row level security;
drop policy if exists "todos ven el contador global de toques" on colmillos_global_taps;
create policy "todos ven el contador global de toques"
    on colmillos_global_taps for select
    using (true);

create or replace function increment_global_taps()
returns bigint
language sql
security definer
set search_path = public
as $$
    update colmillos_global_taps set total = total + 1 where id = true returning total;
$$;
grant execute on function increment_global_taps() to anon, authenticated;

-- 7) Ruleta: solo diversion, sin relacion con dinero real (se apuestan y ganan/pierden los
-- mismos Colmillos, nunca dinero). Las apuestas van de 5 a 50 Colmillos pagando hasta 3x, asi
-- que una ganancia puede superar el tope de +20 que tenian los eventos de "usar la plataforma"
-- (ese tope era anti-trampa solo para esos eventos especificos) - se amplia el rango otra vez.
-- Si ya corriste este archivo antes, correrlo de nuevo no rompe nada (los pasos de arriba son
-- idempotentes) - esto solo actualiza la restriccion del monto.
alter table user_colmillos_events drop constraint if exists user_colmillos_events_amount_check;
alter table user_colmillos_events add constraint user_colmillos_events_amount_check
    check (amount <> 0 and amount between -500 and 500);

-- 4) Qué tiene equipado cada usuario ahora mismo (null = el default gratis de cada categoria).
--    No es un ledger - es estado mutable, por eso es una tabla aparte que el usuario puede
--    actualizar libremente (siempre y cuando sea algo que ya "compro" segun el ledger - eso lo
--    valida el propio frontend, no hay Edge Function de por medio, mismo nivel de confianza que
--    el resto del sistema de Colmillos).
create table if not exists user_colmillos_equipped (
    user_id uuid primary key references auth.users(id) on delete cascade,
    skin_id text references colmillos_shop_items(id),
    accessory_id text references colmillos_shop_items(id),
    background_id text references colmillos_shop_items(id),
    updated_at timestamptz not null default now()
);
alter table user_colmillos_equipped enable row level security;
drop policy if exists "usuario ve su equipo" on user_colmillos_equipped;
create policy "usuario ve su equipo"
    on user_colmillos_equipped for select
    using (auth.uid() = user_id);
drop policy if exists "usuario crea su equipo" on user_colmillos_equipped;
create policy "usuario crea su equipo"
    on user_colmillos_equipped for insert
    with check (auth.uid() = user_id);
drop policy if exists "usuario cambia su equipo" on user_colmillos_equipped;
create policy "usuario cambia su equipo"
    on user_colmillos_equipped for update
    using (auth.uid() = user_id);

-- 8) Accesorios independientes por "parte del cuerpo": antes existia una sola columna
--    accessory_id, asi que ponerte una cosa de la cabeza quitaba lo que tenias en la cara (o
--    donde fuera) porque todo competia por la misma columna. Se reemplaza por 4 columnas, una
--    por cada parte (cabeza/cara/cuerpo/manos), para poder combinarlos todos a la vez. Lo que
--    ya estaba equipado en la columna vieja se migra a la columna nueva que le corresponda -
--    todo este bloque es seguro de correr mas de una vez (revisa si accessory_id todavia
--    existe antes de migrar/borrarla).
alter table user_colmillos_equipped add column if not exists accessory_head_id text references colmillos_shop_items(id);
alter table user_colmillos_equipped add column if not exists accessory_face_id text references colmillos_shop_items(id);
alter table user_colmillos_equipped add column if not exists accessory_body_id text references colmillos_shop_items(id);
alter table user_colmillos_equipped add column if not exists accessory_hands_id text references colmillos_shop_items(id);

do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_name = 'user_colmillos_equipped' and column_name = 'accessory_id'
    ) then
        update user_colmillos_equipped set accessory_head_id = accessory_id
            where accessory_id in ('acc_cap', 'acc_crown', 'acc_sombrero', 'acc_headphones', 'acc_scuba');
        update user_colmillos_equipped set accessory_face_id = accessory_id
            where accessory_id in ('acc_shades', 'acc_antifaz');
        update user_colmillos_equipped set accessory_body_id = accessory_id
            where accessory_id in ('acc_chain', 'acc_scarf', 'acc_cape', 'acc_collar', 'acc_aletarobot');
        update user_colmillos_equipped set accessory_hands_id = accessory_id
            where accessory_id in ('acc_microfono', 'acc_guantes', 'acc_paraguas');
        alter table user_colmillos_equipped drop column accessory_id;
    end if;
end $$;

-- 9) Quinta parte del cuerpo: pies (zapatos/calzado) - categoria nueva, no habia nada que
--    migrar, solo se agrega la columna.
alter table user_colmillos_equipped add column if not exists accessory_feet_id text references colmillos_shop_items(id);
