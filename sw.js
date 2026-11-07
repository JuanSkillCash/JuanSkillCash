/* Service worker minimo, solo para cumplir el requisito de "instalable" de Chrome/Android (sin
   este archivo registrado, el navegador nunca ofrece el boton de "Instalar App") - a proposito
   no cachea nada: el sitio depende de datos en vivo (Supabase, el proxy de Cloudflare, APIs de
   mercado), cachear esas respuestas mostraria precios e indicadores viejos sin que el usuario
   se de cuenta.
   El listener de "fetch" de abajo antes interceptaba CADA peticion de la pagina (imagenes,
   APIs, todo) solo para volver a pedirla igual con fetch(event.request) y devolverla iqual -
   no cacheaba nada, asi que no sumaba ningun beneficio, solo el costo extra de pasar cada
   peticion por el service worker antes de que siguiera a la red (medido en la auditoria de
   rendimiento como sobrecarga innecesaria). Se deja el listener (algunos criterios viejos de
   instalabilidad lo pedian) pero sin llamar a event.respondWith(): asi el navegador maneja la
   peticion directo, sin el viaje de ida y vuelta por este archivo. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
