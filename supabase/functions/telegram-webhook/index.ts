// Supabase Edge Function: telegram-webhook
//
// Reemplaza el polling de scripts/poll_telegram_links.py (que en la practica solo corria
// como paso final de los robots horarios de deslistados/nuevos listados, asi que vincular
// Telegram podia tardar hasta casi una hora). Telegram llama a esta funcion AL INSTANTE
// (en segundos) cada vez que alguien le manda un mensaje al bot, usando un webhook en vez de
// que nosotros tengamos que ir a preguntarle con getUpdates.
//
// IMPORTANTE: getUpdates (lo que usa poll_telegram_links.py) y un webhook activo son
// mutuamente excluyentes - mientras este webhook este registrado, cualquier llamado a
// getUpdates del MISMO bot responde 409 Conflict. Por eso, una vez este webhook este
// funcionando de verdad, hay que:
//   1) borrar .github/workflows/poll-telegram-links.yml
//   2) quitar el paso "Revisar vinculos de Telegram pendientes" (poll_telegram_links.py) de
//      update-exchange-delistings.yml y update-new-listings.yml
//   3) archivar scripts/poll_telegram_links.py (ver scripts/legacy/README.md)
// Ver scripts/set_telegram_webhook.sh para como registrar/revertir el webhook en Telegram.
//
// --- Como desplegarla (una sola vez, desde el dashboard de Supabase) ---
// 1. Entra a tu proyecto en supabase.com -> Edge Functions -> "Deploy a new function".
// 2. Nombre de la funcion: telegram-webhook (tiene que ser exactamente ese nombre, es la
//    ultima parte de la URL que se registra como webhook en Telegram).
// 3. Pega el contenido de este archivo completo en el editor y dale deploy.
// 4. MUY IMPORTANTE - esta funcion la llama Telegram, no el navegador con sesion de
//    Supabase, asi que nunca llega un JWT de usuario. Hay que desactivar "Enforce JWT
//    Verification" para esta funcion especifica (toggle en la pagina de la funcion dentro
//    del dashboard, junto al nombre). Sin esto, Supabase rechaza la llamada de Telegram con
//    401 antes de que el codigo de aca abajo alcance a correr.
// 5. Ve a Edge Functions -> Secrets y agrega (si no existen ya):
//      TELEGRAM_BOT_TOKEN           - el mismo token que ya usan los robots de GitHub Actions
//      TELEGRAM_WEBHOOK_SECRET      - un secreto nuevo, random, de 32+ caracteres, SOLO
//                                     A-Za-z0-9_- (es el alfabeto que Telegram acepta en
//                                     secret_token). Generar con, por ejemplo:
//                                       openssl rand -hex 32
//    (SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY ya existen automaticamente en toda funcion.)
// 6. Registra el webhook en Telegram UNA sola vez - ver scripts/set_telegram_webhook.sh.

import { createClient } from "npm:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN")!;
const TELEGRAM_WEBHOOK_SECRET = Deno.env.get("TELEGRAM_WEBHOOK_SECRET")!;

const LINK_CODE_RE = /^[A-Za-z0-9_-]{1,64}$/;

// comparacion a tiempo constante - evita que alguien adivine el secreto midiendo cuanto
// tarda la respuesta cuando los primeros caracteres coinciden vs cuando no
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function sendMessage(chatId: number, text: string): Promise<void> {
  try {
    await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text }),
    });
  } catch (e) {
    // un fallo mandando el mensaje de vuelta nunca debe tumbar el procesamiento del update
    console.error("no se pudo responder al chat", chatId, e);
  }
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("solo POST", { status: 405 });
  }

  // autenticidad: Telegram manda este header en cada peticion del webhook con el valor
  // exacto que se configuro al registrar el webhook (secret_token) - sin esto, cualquiera
  // que adivine la URL podria mandar updates falsos y vincular codigos ajenos
  const incomingSecret = req.headers.get("X-Telegram-Bot-Api-Secret-Token") || "";
  if (!TELEGRAM_WEBHOOK_SECRET || !timingSafeEqual(incomingSecret, TELEGRAM_WEBHOOK_SECRET)) {
    return new Response("unauthorized", { status: 401 });
  }

  let update: any;
  try {
    update = await req.json();
  } catch {
    // body no es JSON valido - nada que procesar, pero no es un fallo transitorio nuestro
    return new Response("ok", { status: 200 });
  }

  try {
    const msg = update?.message;
    const text = String(msg?.text || "").trim();
    const chatId = msg?.chat?.id;

    // solo nos interesan mensajes de texto con chat_id - cualquier otro tipo de update
    // (ediciones, reacciones, etc.) se reconoce con 200 y se ignora
    if (!chatId || !text.startsWith("/start")) {
      return new Response("ok", { status: 200 });
    }

    const admin = createClient(SUPABASE_URL, SERVICE_ROLE_KEY);

    // acepta tanto "/start <codigo>" como "/start@BotUsername <codigo>" (asi llega cuando
    // el bot esta en un grupo, segun la documentacion de Telegram)
    const parts = text.split(/\s+/);
    const code = (parts[1] || "").trim();

    if (!code) {
      await sendMessage(
        chatId,
        "👋 ¡Hola! Soy el bot de avisos de SkillCash Tools.\n\n" +
          "Para conectarte, entra a juanskillcash.com → inicia sesión → Mi perfil → " +
          '"Conectar Telegram". Desde ahí te traigo de vuelta aquí con el link correcto.',
      );
      return new Response("ok", { status: 200 });
    }

    if (!LINK_CODE_RE.test(code)) {
      await sendMessage(chatId, "⚠️ Ese código no es válido. Genera uno nuevo en Mi perfil del sitio (juanskillcash.com).");
      return new Response("ok", { status: 200 });
    }

    const { data: link, error: findErr } = await admin
      .from("user_telegram_links")
      .select("user_id,chat_id,linked_at")
      .eq("link_code", code)
      .maybeSingle();

    if (findErr) {
      // fallo real de Supabase (no "no encontrado") - respondemos 5xx para que Telegram
      // reintente solo, en vez de darle al usuario un mensaje de error permanente
      console.error("fallo consultando user_telegram_links", findErr);
      return new Response("supabase error", { status: 502 });
    }

    if (!link) {
      await sendMessage(chatId, "⚠️ Ese código no es válido o ya se usó. Genera uno nuevo en Mi perfil del sitio (juanskillcash.com).");
      return new Response("ok", { status: 200 });
    }

    // idempotencia: Telegram puede reenviar el mismo update si no recibio un 2xx a tiempo -
    // si este codigo YA quedo vinculado al mismo chat que esta escribiendo, no hay nada que
    // hacer (ni reescribir linked_at, ni mandar el mensaje de bienvenida otra vez)
    if (link.linked_at) {
      if (String(link.chat_id) === String(chatId)) {
        return new Response("ok", { status: 200 });
      }
      // el codigo ya se uso desde otro chat - no se reasigna solo, el usuario genera uno nuevo
      await sendMessage(chatId, "⚠️ Ese código ya se usó. Genera uno nuevo en Mi perfil del sitio (juanskillcash.com).");
      return new Response("ok", { status: 200 });
    }

    const { error: updateErr } = await admin
      .from("user_telegram_links")
      .update({ chat_id: chatId, linked_at: new Date().toISOString() })
      .eq("user_id", link.user_id)
      .is("linked_at", null); // doble seguro contra una carrera con otro update concurrente

    if (updateErr) {
      console.error("fallo guardando el vinculo de telegram", updateErr);
      return new Response("supabase error", { status: 502 });
    }

    await sendMessage(
      chatId,
      "✅ ¡Cuenta conectada! A partir de ahora te aviso aquí cuando una moneda de tu " +
        "Mi Lista aparezca en el Radar de Deslistados o de Nuevos Listados.\n\n" +
        "Para dejar de seguir alguna, hazlo desde el mismo radar en juanskillcash.com.",
    );
    return new Response("ok", { status: 200 });
  } catch (e) {
    // fallo inesperado nuestro (no del usuario) - 5xx para que Telegram reintente
    console.error("fallo inesperado procesando el webhook de telegram", e);
    return new Response("internal error", { status: 500 });
  }
});
