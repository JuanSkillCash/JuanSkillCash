-- Agrega lo que hace falta a news_archive (ver create_news_archive.sql) para las alertas de
-- Telegram de noticias cripto clave que pidió Juan (ver scripts/post_important_news_telegram.py):
--
-- "importancia": la clasificación que ahora hace la misma llamada a Workers AI del Worker de
-- noticias (workers/rss-news/worker.js) - "alta" solo si la noticia entra en una de las 12
-- categorías exactas que Juan eligió (ETF, SEC/regulación, Fed, hackeo grande, quiebra/fraude
-- grande, movimiento de precio fuerte, adopción institucional, país adoptando cripto, upgrade de
-- red grande, empresa grande no-cripto con producto cripto, ballena grande, figura política).
--
-- "telegram_enviado": para no mandar la misma noticia dos veces a Telegram - el script que
-- revisa esta tabla cada 30 min (justo después de que se guardan las noticias nuevas) solo
-- considera filas con telegram_enviado=false, y las marca true apenas las manda (o decide no
-- mandarlas por el filtro de monedas excluidas - ver abajo).
--
-- Ejecutar una sola vez en el SQL editor de Supabase. Seguro de correr más de una vez.

alter table news_archive add column if not exists importancia text
    check (importancia in ('alta', 'baja') or importancia is null);

alter table news_archive add column if not exists telegram_enviado boolean not null default false;

-- la consulta real del script es "category=crypto AND importancia=alta AND telegram_enviado=false,
-- ordenado por published_at" - este índice parcial cubre exactamente esa combinación sin tener
-- que escanear toda la tabla a medida que crezca
create index if not exists news_archive_telegram_pendientes_idx
    on news_archive (published_at)
    where category = 'crypto' and importancia = 'alta' and telegram_enviado = false;
