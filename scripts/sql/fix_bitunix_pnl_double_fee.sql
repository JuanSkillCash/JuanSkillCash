-- Corrige las filas de trade_journal_trades YA GUARDADAS por la clave personal de Bitunix
-- (source='bitunix') que quedaron con el "P&L neto" mal calculado: Bitunix manda realizedPNL ya
-- NETO de comision, pero supabase/functions/trade-journal-sync/index.ts (antes de este fix) lo
-- guardaba tal cual en la columna `pnl` (que en TODO el esquema es BRUTO), asi que journal.js
-- (net = pnl - fees + funding) restaba la comision una SEGUNDA vez - el neto mostrado quedaba
-- mas bajo de lo real, al punto de voltear un dia ganador en perdedor (caso real de Juan, 27
-- oct 2026: dos operaciones que sumaban +$0.22 reales se mostraban como -$0.64).
--
-- Esto solo arregla los datos YA guardados - el fix de verdad (que las sincronizaciones nuevas
-- no se dañen otra vez) esta en la Edge Function; hay que volver a desplegarla despues de correr
-- esto (Supabase -> Edge Functions -> trade-journal-sync -> pegar el archivo actualizado).
--
-- Seguro de correr mas de una vez SOLO si se corre una vez por cada redeploy - si se corre dos
-- veces SIN redeploy de por medio, sumaria la comision otra vez (ida y vuelta, mal). El id de la
-- operacion (external_id) no cambia entre corridas de este script, asi que confirma con el
-- SELECT de abajo antes de correr el UPDATE si no estas seguro de si ya se corrio.

-- 1) Revisar antes de corregir (dos filas de ejemplo, 27 oct 2026 - deberian sumar pnl+fees):
-- select external_id, pnl, fees, pnl + fees as pnl_corregido
--     from trade_journal_trades where source = 'bitunix' and status = 'closed';

update trade_journal_trades
set pnl = pnl + fees
where source = 'bitunix' and status = 'closed';
