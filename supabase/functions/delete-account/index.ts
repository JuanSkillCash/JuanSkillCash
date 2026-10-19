// Supabase Edge Function: delete-account
//
// Termina de cerrar una cuenta que el usuario ya pidió eliminar desde "Mi perfil"
// en la pagina. El frontend (con la clave publica) ya borra sus propios datos
// (portfolios/portfolio_items) via RLS antes de llamar esta funcion - lo unico
// que esta funcion hace es lo que el navegador NUNCA puede hacer por si solo:
// borrar el registro de auth.users (correo + contraseña) via la service_role key,
// que por seguridad no puede vivir en el navegador.
//
// --- Como desplegarla (una sola vez, ~2 minutos, desde el dashboard de Supabase) ---
// 1. Entra a tu proyecto en supabase.com -> Edge Functions -> "Deploy a new function".
// 2. Nombre de la funcion: delete-account (tiene que ser exactamente ese nombre,
//    el frontend ya esta llamando sbClient.functions.invoke('delete-account')).
// 3. Pega el contenido de este archivo completo en el editor y dale deploy.
// 4. Ve a Edge Functions -> Secrets y agrega SUPABASE_SERVICE_ROLE_KEY con el mismo
//    valor que ya usas en los Secrets de GitHub Actions (la service_role key de tu
//    proyecto, Project Settings -> API). SUPABASE_URL ya la provee Supabase sola.
// Listo - una vez desplegada, el boton "Eliminar mi cuenta" cierra todo de una.
// Si no la despliegas, el boton igual borra los datos del usuario y le pide
// escribir a contacto@juanskillcash.com para cerrar el acceso manualmente.

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

Deno.serve(async (req) => {
  try {
    const authHeader = req.headers.get('Authorization') || '';
    const jwt = authHeader.replace('Bearer ', '');
    if (!jwt) {
      return new Response(JSON.stringify({ error: 'Falta el token de sesión.' }), { status: 401 });
    }

    const supabaseAdmin = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
    );

    // nunca confiar en un user id que mande el cliente - se valida el JWT y se saca
    // el id real desde ahi, asi nadie puede pedir borrar la cuenta de otra persona
    const { data: userData, error: userErr } = await supabaseAdmin.auth.getUser(jwt);
    if (userErr || !userData?.user) {
      return new Response(JSON.stringify({ error: 'Sesión inválida.' }), { status: 401 });
    }
    const userId = userData.user.id;

    // defensa en profundidad: el frontend ya borro esto con la clave publica antes
    // de llamar aqui, pero se repite con la service_role key por si acaso
    const { data: portfolios } = await supabaseAdmin.from('portfolios').select('id').eq('user_id', userId);
    const ids = (portfolios || []).map((p: { id: string }) => p.id);
    if (ids.length) {
      await supabaseAdmin.from('portfolio_items').delete().in('portfolio_id', ids);
      await supabaseAdmin.from('portfolios').delete().eq('user_id', userId);
    }

    const { error: deleteErr } = await supabaseAdmin.auth.admin.deleteUser(userId);
    if (deleteErr) {
      return new Response(JSON.stringify({ error: deleteErr.message }), { status: 500 });
    }

    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), { status: 500 });
  }
});
