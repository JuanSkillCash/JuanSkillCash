-- Correr UNA SOLA VEZ en el SQL Editor de Supabase, después de haber creado y desplegado
-- la Edge Function "daily-mcap-update" (Dashboard -> Edge Functions -> Deploy a new function -> Via Editor).
-- Esto programa esa función para que se ejecute sola, todos los días a las 23:55 UTC, sin que
-- nadie abra la página ni nada de Claude tenga que correr nada.

create extension if not exists pg_cron with schema extensions;
create extension if not exists pg_net with schema extensions;

select cron.schedule(
  'daily-mcap-coingecko',
  '55 23 * * *',
  $$
  select net.http_post(
    url := 'https://nbvgyouzjscwtfukzxok.supabase.co/functions/v1/daily-mcap-update',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer sb_publishable_uxAz2gqnTnMQup_lonppvw_0_EdXlRz'
    ),
    body := '{}'::jsonb
  );
  $$
);

-- Para revisar que corrió bien cualquier día (Dashboard -> SQL Editor):
--   select * from cron.job_run_details order by start_time desc limit 5;
-- Para ver los datos que ya se guardaron:
--   select * from mcap_index_history where source = 'coingecko' order by day desc limit 20;
