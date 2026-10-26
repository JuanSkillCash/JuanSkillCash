// Supabase Edge Function: trade-journal-sync
//
// Conexion automatica de la Bitacora de trading con la cuenta de FUTUROS de Bitunix del usuario
// (con SU propia API key de solo lectura - no tiene nada que ver con la Partner API de afiliados
// que usa scripts/bitunix_api.py). Acciones (body JSON: { action, ... }):
//   connect    { apiKey, apiSecret } -> prueba la clave contra Bitunix, la guarda CIFRADA y sincroniza
//   sync       {}                   -> trae las posiciones cerradas (y abiertas) y las guarda
//   disconnect {}                   -> borra la clave guardada
//
// La clave y el secreto se guardan cifrados con AES-GCM en trade_journal_secrets (tabla que el
// navegador no puede leer: RLS sin politicas). La llave de cifrado vive SOLO en el secret
// JOURNAL_ENCRYPTION_KEY de esta funcion.
//
// --- Como desplegarla (una sola vez) ---
// 1. Supabase -> Edge Functions -> "Deploy a new function", nombre: trade-journal-sync
//    (exactamente ese, la pagina llama sbClient.functions.invoke('trade-journal-sync')).
// 2. Pega este archivo completo y dale deploy.
// 3. Edge Functions -> Secrets:
//      SUPABASE_SERVICE_ROLE_KEY  (si no esta ya; la misma que usa delete-account)
//      JOURNAL_ENCRYPTION_KEY     32 bytes aleatorios en base64. Se genera en cualquier
//                                 terminal con:  openssl rand -base64 32
//                                 (si se cambia despues, hay que volver a conectar la clave)
// 4. (opcional) JOURNAL_ALLOWED_USER_IDS: ids separados por coma que pueden usarla. Si no se
//    pone, solo el dueño (Juan). Cuando la Bitacora se abra por volumen, se quita ese candado.
//
// API de Bitunix usada (https://openapidoc.bitunix.com, futuros):
//   firma: digest = SHA256(nonce + timestamp + apiKey + queryParams + body)
//          sign   = SHA256(digest + secretKey)
//          queryParams = parametros ordenados por nombre, pegados "nombrevalor" sin separadores
//   GET /api/v1/futures/account?marginCoin=USDT            (probar que la clave sirve)
//   GET /api/v1/futures/position/get_history_positions     (posiciones cerradas, max 100 por pagina)
//   GET /api/v1/futures/position/get_pending_positions     (posiciones abiertas)

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const OWNER_ID = 'e4309251-6078-4233-aab3-6ab8d6c624e1';
const BASE = 'https://fapi.bitunix.com';
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, 'Content-Type': 'application/json' } });

// ---------- cifrado ----------
const enc = new TextEncoder();
const dec = new TextDecoder();
const b64 = (u: Uint8Array) => btoa(String.fromCharCode(...u));
const unb64 = (s: string) => Uint8Array.from(atob(s), c => c.charCodeAt(0));
async function cryptoKey(): Promise<CryptoKey> {
  const raw = Deno.env.get('JOURNAL_ENCRYPTION_KEY');
  if (!raw) throw new Error('Falta el secret JOURNAL_ENCRYPTION_KEY en la Edge Function.');
  const bytes = unb64(raw.trim());
  if (bytes.length !== 32) throw new Error('JOURNAL_ENCRYPTION_KEY debe ser de 32 bytes en base64 (openssl rand -base64 32).');
  return crypto.subtle.importKey('raw', bytes, 'AES-GCM', false, ['encrypt', 'decrypt']);
}
async function encrypt(text: string): Promise<string> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, await cryptoKey(), enc.encode(text)));
  return b64(iv) + ':' + b64(ct);
}
async function decrypt(blob: string): Promise<string> {
  const [iv, ct] = blob.split(':');
  const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(iv) }, await cryptoKey(), unb64(ct));
  return dec.decode(pt);
}

// ---------- Bitunix ----------
async function sha256hex(s: string): Promise<string> {
  const h = new Uint8Array(await crypto.subtle.digest('SHA-256', enc.encode(s)));
  return Array.from(h, b => b.toString(16).padStart(2, '0')).join('');
}
function nonce(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  const r = crypto.getRandomValues(new Uint8Array(32));
  return Array.from(r, x => chars[x % chars.length]).join('');
}
async function bitunixGet(path: string, params: Record<string, string | number | undefined>, apiKey: string, secret: string) {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== '')) as Record<string, string | number>;
  const keys = Object.keys(clean).sort();
  const queryForSign = keys.map(k => k + String(clean[k])).join('');
  const qs = keys.map(k => encodeURIComponent(k) + '=' + encodeURIComponent(String(clean[k]))).join('&');
  const n = nonce();
  const ts = String(Date.now());
  const digest = await sha256hex(n + ts + apiKey + queryForSign + '');
  const sign = await sha256hex(digest + secret);
  const res = await fetch(BASE + path + (qs ? '?' + qs : ''), {
    headers: { 'api-key': apiKey, nonce: n, timestamp: ts, sign, language: 'en-US', 'Content-Type': 'application/json' },
  });
  const body = await res.json().catch(() => null);
  if (!res.ok || !body || (body.code !== 0 && body.code !== '0')) {
    const msg = body?.msg || body?.message || ('HTTP ' + res.status);
    throw new Error('Bitunix respondió: ' + msg);
  }
  return body.data;
}

const num = (v: unknown): number | null => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const iso = (ms: unknown): string | null => {
  const n = Number(ms);
  return Number.isFinite(n) && n > 0 ? new Date(n).toISOString() : null;
};
// una posicion de Bitunix -> una fila de trade_journal_trades
function mapPosition(p: Record<string, unknown>, userId: string, open: boolean) {
  const entry = num(p.entryPrice ?? p.avgOpenPrice);
  const qty = num(p.maxQty ?? p.qty);
  const lev = num(p.leverage);
  const side = String(p.side || '').toUpperCase().includes('SHORT') || String(p.side || '').toUpperCase() === 'SELL' ? 'short' : 'long';
  const margin = num(p.margin) ?? (entry && qty && lev ? (entry * qty) / lev : null);
  return {
    user_id: userId,
    source: 'bitunix',
    external_id: String(p.positionId),
    symbol: String(p.symbol || '').toUpperCase(),
    side,
    status: open ? 'open' : 'closed',
    leverage: lev,
    margin: margin !== null ? Math.round(margin * 100) / 100 : null,
    qty,
    entry_price: entry,
    exit_price: open ? null : num(p.closePrice),
    pnl: num(p.realizedPNL) ?? 0,
    fees: Math.abs(num(p.fee ?? p.fees) ?? 0),
    funding: num(p.funding) ?? 0,
    opened_at: iso(p.ctime) ?? new Date().toISOString(),
    closed_at: open ? null : (iso(p.mtime) ?? new Date().toISOString()),
  };
}

async function syncUser(admin: ReturnType<typeof createClient>, userId: string, apiKey: string, secret: string) {
  const { data: state } = await admin.from('trade_journal_sync').select('last_sync_at').eq('user_id', userId).eq('exchange', 'bitunix').maybeSingle();
  // primera vez: el ultimo año; despues: desde 3 dias antes de la ultima sincronizacion
  const now = Date.now();
  const DAY = 86400000;
  let from = state?.last_sync_at ? new Date(state.last_sync_at).getTime() - 3 * DAY : now - 365 * DAY;
  const rows: ReturnType<typeof mapPosition>[] = [];
  // ventanas de 30 dias para no depender del rango maximo que acepte el endpoint
  while (from < now) {
    const to = Math.min(from + 30 * DAY, now);
    let skip = 0;
    for (let guard = 0; guard < 50; guard++) {
      const data = await bitunixGet('/api/v1/futures/position/get_history_positions',
        { startTime: from, endTime: to, skip, limit: 100 }, apiKey, secret);
      const list = (data?.positionList || data?.list || []) as Record<string, unknown>[];
      list.forEach(p => rows.push(mapPosition(p, userId, false)));
      if (list.length < 100) break;
      skip += 100;
    }
    from = to;
  }
  const pending = await bitunixGet('/api/v1/futures/position/get_pending_positions', {}, apiKey, secret).catch(() => []);
  const openList = (Array.isArray(pending) ? pending : (pending?.positionList || [])) as Record<string, unknown>[];
  openList.forEach(p => rows.push(mapPosition(p, userId, true)));

  // las abiertas que ya se cerraron dejan de estar en "pending": se borran las abiertas
  // viejas de Bitunix y se vuelven a escribir las actuales (las cerradas llegan por historial)
  await admin.from('trade_journal_trades').delete().eq('user_id', userId).eq('source', 'bitunix').eq('status', 'open');
  for (let i = 0; i < rows.length; i += 500) {
    const { error } = await admin.from('trade_journal_trades')
      .upsert(rows.slice(i, i + 500), { onConflict: 'user_id,source,external_id' });
    if (error) throw new Error('No se pudieron guardar las operaciones: ' + error.message);
  }
  const { count } = await admin.from('trade_journal_trades').select('id', { count: 'exact', head: true })
    .eq('user_id', userId).eq('source', 'bitunix');
  await admin.from('trade_journal_sync').upsert({
    user_id: userId, exchange: 'bitunix', status: 'connected', last_sync_at: new Date().toISOString(),
    last_error: null, trades_synced: count ?? rows.length,
  });
  return { imported: rows.length, total: count ?? rows.length };
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });
  try {
    const jwt = (req.headers.get('Authorization') || '').replace('Bearer ', '');
    if (!jwt) return json({ error: 'Falta el token de sesión.' }, 401);
    const admin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!);
    const { data: userData, error: userErr } = await admin.auth.getUser(jwt);
    if (userErr || !userData?.user) return json({ error: 'Sesión inválida.' }, 401);
    const userId = userData.user.id;
    const allowed = (Deno.env.get('JOURNAL_ALLOWED_USER_IDS') || OWNER_ID).split(',').map(s => s.trim());
    if (!allowed.includes(userId)) return json({ error: 'La Bitácora todavía no está disponible para tu cuenta.' }, 403);

    const body = await req.json().catch(() => ({}));
    const action = body.action;

    if (action === 'connect') {
      const apiKey = String(body.apiKey || '').trim();
      const apiSecret = String(body.apiSecret || '').trim();
      if (apiKey.length < 8 || apiSecret.length < 8) return json({ error: 'Revisa la API key y el secreto.' }, 400);
      // probar la clave antes de guardarla
      await bitunixGet('/api/v1/futures/account', { marginCoin: 'USDT' }, apiKey, apiSecret);
      await admin.from('trade_journal_secrets').upsert({
        user_id: userId, exchange: 'bitunix',
        api_key_enc: await encrypt(apiKey), api_secret_enc: await encrypt(apiSecret), updated_at: new Date().toISOString(),
      });
      await admin.from('trade_journal_sync').upsert({
        user_id: userId, exchange: 'bitunix', status: 'connected', api_key_hint: '…' + apiKey.slice(-4),
        connected_at: new Date().toISOString(), last_sync_at: null, last_error: null,
      });
      const result = await syncUser(admin, userId, apiKey, apiSecret);
      return json({ ok: true, ...result });
    }

    if (action === 'sync') {
      const { data: sec } = await admin.from('trade_journal_secrets').select('api_key_enc,api_secret_enc')
        .eq('user_id', userId).eq('exchange', 'bitunix').maybeSingle();
      if (!sec) return json({ error: 'No hay una cuenta de Bitunix conectada.' }, 400);
      try {
        const result = await syncUser(admin, userId, await decrypt(sec.api_key_enc), await decrypt(sec.api_secret_enc));
        return json({ ok: true, ...result });
      } catch (err) {
        await admin.from('trade_journal_sync').update({ status: 'error', last_error: String((err as Error).message).slice(0, 300) })
          .eq('user_id', userId).eq('exchange', 'bitunix');
        throw err;
      }
    }

    if (action === 'disconnect') {
      await admin.from('trade_journal_secrets').delete().eq('user_id', userId).eq('exchange', 'bitunix');
      await admin.from('trade_journal_sync').upsert({
        user_id: userId, exchange: 'bitunix', status: 'disconnected', api_key_hint: null, last_error: null,
      });
      return json({ ok: true });
    }

    return json({ error: 'Acción desconocida.' }, 400);
  } catch (err) {
    return json({ error: (err as Error).message || 'Error inesperado.' }, 500);
  }
});
