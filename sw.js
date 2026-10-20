/* Service worker minimo, solo para cumplir el requisito de "instalable" de Chrome/Android (sin
   este archivo registrado, el navegador nunca ofrece el boton de "Instalar App") - a proposito
   no cachea nada: el sitio depende de datos en vivo (Supabase, el proxy de Cloudflare, APIs de
   mercado), cachear esas respuestas mostraria precios e indicadores viejos sin que el usuario
   se de cuenta. Cada peticion simplemente se deja pasar directo a la red. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});
