// Edge Function: avisa por Telegram AL INSTANTE cuando el usuario agrega o quita algo de
// "Mi Lista" (user_watchlist) - distinto del aviso de "se deslisto/listo una moneda que
// sigues", que ya manda scripts/watchlist_notify.py desde los robots de GitHub Actions.
//
// Esto SI puede ser instantaneo (a diferencia del resto del proyecto, que corre por robots
// en GitHub Actions cada hora) porque corre como funcion servidor dentro de Supabase - el
// token del bot vive aca como secreto de la funcion, nunca en el navegador.
//
// Seguridad: valida el JWT de sesion del usuario que llama (con la service role key, que
// nunca sale de aca) para sacar su user_id real - nunca confia en un user_id que venga en
// el body, así nadie puede pedir que se le mande un aviso al chat de otra persona.
//
// Pegar este codigo tal cual en el editor de Edge Functions del panel de Supabase (Project
// Settings > Edge Functions > Create a new function > nombrarla
// "watchlist-telegram-notify") y desplegar. Secretos necesarios (Edge Functions > Secrets):
//   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, TELEGRAM_BOT_TOKEN
// (SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY ya existen automaticamente como variables de
// entorno en toda funcion de Supabase - solo falta agregar TELEGRAM_BOT_TOKEN a mano.)

import { createClient } from "npm:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN")!;

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Content-Type": "application/json",
};

const RADAR_LABELS: Record<string, string> = {
  delistings: "Deslistados",
  new_listings: "Nuevos Listados",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }

  try {
    const jwt = (req.headers.get("Authorization") || "").replace("Bearer ", "");
    if (!jwt) {
      return new Response(JSON.stringify({ error: "falta autenticacion" }), { status: 401, headers: CORS_HEADERS });
    }

    const admin = createClient(SUPABASE_URL, SERVICE_ROLE_KEY);
    const { data: userData, error: userErr } = await admin.auth.getUser(jwt);
    if (userErr || !userData?.user) {
      return new Response(JSON.stringify({ error: "sesion invalida" }), { status: 401, headers: CORS_HEADERS });
    }
    const userId = userData.user.id;

    const body = await req.json();
    const action = body.action as "add" | "remove";
    const symbol = String(body.symbol || "").toUpperCase();
    const exchanges = Array.isArray(body.exchanges) ? body.exchanges : [];
    const radar = String(body.radar || "");
    if (!action || !symbol || exchanges.length === 0 || !RADAR_LABELS[radar]) {
      return new Response(JSON.stringify({ error: "faltan datos" }), { status: 400, headers: CORS_HEADERS });
    }

    const { data: link } = await admin
      .from("user_telegram_links")
      .select("chat_id")
      .eq("user_id", userId)
      .maybeSingle();

    if (!link?.chat_id) {
      // no tiene Telegram conectado todavia - no es un error, simplemente no hay a quien avisarle
      return new Response(JSON.stringify({ sent: false, reason: "sin_telegram" }), { status: 200, headers: CORS_HEADERS });
    }

    const exchangeLabels = exchanges.map((e: string) => (e === "any" ? "cualquier exchange" : e)).join(", ");
    const actionLabel = action === "add" ? "⭐ Agregaste" : "🗑 Quitaste";
    const text = `${actionLabel} ${symbol} (${exchangeLabels}) de tu lista de ${RADAR_LABELS[radar]}.`;

    const tgResp = await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: link.chat_id, text }),
    });

    return new Response(JSON.stringify({ sent: tgResp.ok }), { status: 200, headers: CORS_HEADERS });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: CORS_HEADERS });
  }
});
