-- Permite un tercer "source" en trade_journal_trades: 'bitunix_partner' - operaciones traidas
-- con el Partner API de Juan (ver docs/bitunix-partner-api.md) para quien es su referido pero
-- NO conecto su propia API key personal de Bitunix. Las que sí conectan su clave siguen usando
-- source='bitunix' (via supabase/functions/trade-journal-sync), con mas detalle (comisiones y
-- funding exactos) - scripts/sync_journal_partner.py se salta a cualquiera que ya tenga la
-- clave personal conectada, para no duplicar operaciones entre las dos fuentes.
--
-- Ejecutar una sola vez en el SQL editor de Supabase. Seguro de correr mas de una vez.

alter table trade_journal_trades drop constraint if exists trade_journal_trades_source_check;
alter table trade_journal_trades add constraint trade_journal_trades_source_check
    check (source in ('manual', 'bitunix', 'bitunix_partner'));
