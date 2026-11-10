# SkillCash Tools

Antes de trabajar en el screener/dashboard, lee docs/referencia-bcd-dashboard.md

Antes de diagnosticar un indicador/dato "desactualizado" o decidir de dónde
traer un dato nuevo, lee docs/fuentes-de-datos-indicadores.md — ahí está
mapeado, indicador por indicador, con qué fuente y mecanismo (en vivo desde
el navegador vs. robot de GitHub Actions + qué script + qué frecuencia) se
actualiza cada cosa del sitio.

## Íconos de las tool-card (tarjetas de herramientas con banner de foto)

Los íconos chiquitos junto al número en `.tool-card-head .tool-icon` (Zona de
Caza, Mi Arrecife, Blindaje, etc.) tienen que verse como un simple contorno
azul (color `var(--accent)`), igual que el círculo del número al lado — SIN
relleno de color, SIN gradientes, SIN dorado/amarillo/verde brillante.

Esto NO se controla con CSS (`color`, `filter`) de forma confiable: depende
de si el caracter Unicode que uses tiene por defecto "presentación de texto"
(se dibuja como contorno simple, SÍ toma el `color` de CSS — esto es lo que
queremos) o "presentación de emoji forzada" (el navegador SIEMPRE lo dibuja
con su arte a color nativo, ignorando cualquier CSS — esto rompe la
consistencia, como pasó con 🔑 que salía amarillo/dorado sólido mientras
🛡️👛✅🔎 salían como contorno azul).

**Regla**: antes de usar un emoji nuevo en `tool-icon`, pedir a Juan una
captura real de cómo se ve en su dispositivo, o de entrada asumir que
cualquier emoji de "objeto" (llave, trofeo, medalla, gema, fuego, moneda
dorada, etc.) va a salir con color forzado y en su lugar dibujar un SVG de
líneas a mano: `viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"` (mismo
estilo ya usado en el chevron de `#sbCatToggleAll`). Así se garantiza el
mismo contorno azul sin importar el dispositivo, sin depender de qué fuente
de emoji tenga el navegador de quien lo vea.

Ejemplo ya aplicado (ícono de llave, Herencia Digital en Blindaje):
```html
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="7" cy="7" r="4"/><line x1="10" y1="10" x2="20" y2="20"/><line x1="14" y1="14" x2="16.3" y2="11.7"/><line x1="17" y1="17" x2="19.3" y2="14.7"/></svg>
```

## Degradado de las "cajas" (`--grad-caja`)

Variable en `:root` reusada en 6 secciones de la home (categorías, panorama
del mercado, sesiones, eventos y noticias, quién está detrás). Juan es MUY
sensible a que este degradado se vea "lavado"/blanco/gris — ya pasó varias
veces que un ajuste lo dejó así sin querer:

- **Nunca** un extremo cercano a blanco, gris o un tono sin saturación de
  azul perceptible — las dos puntas del degradado deben leerse como azul
  oscuro, solo que una punta un poco menos oscura que la otra.
- **Nunca** una capa translúcida clara encima (`rgba(255,255,255,...)` ni
  siquiera `rgba(91,141,239,...)` con opacidad) para simular "profundidad" o
  brillo — a cualquier opacidad perceptible se ve pálido/lavado. La única
  forma de dar sensación de profundidad que Juan ha aceptado es `box-shadow`
  EXTERIOR (nunca inset, nunca un highlight claro).
- Si pide "oscurecer" o "cambiar el tono", por defecto mantener la MISMA
  forma/dirección del degradado (no cambiar de radial a linear ni la
  posición del ancla) y solo ajustar la luminosidad de los colores — ya
  reaccionó mal una vez a un cambio de diseño cuando solo pidió un ajuste de
  color.
- `.cat-flip-back` (el reverso de las 7 tarjetas de categoría al voltearse)
  deliberadamente NO usa `--grad-caja` — se quedó con su degradado viejo a
  propósito, pendiente de que Juan pida cambios ahí por separado.

## `assets/js/tarjetas-magicas.js` — NUNCA tocar el tilt/glow de "Tus Herramientas"

Controla, en las 7 tarjetas de categoría de la home (`.cat-overview-card`):
inclinación 3D al pasar el mouse, borde que se ilumina donde está el cursor,
ondita de click y una lineita de gráfico decorativa. Juan pidió una sola vez
quitar un efecto adicional que había ahí (un foco/resplandor rojo que seguía
el cursor por toda la sección, clase `.mg-foco`) — eso ya se quitó y debe
seguir quitado. Pero el tilt 3D / glow del borde / lineita NUNCA han sido
parte de esa queja y no se deben alterar al tocar este archivo por otra
razón: ya pasó que una edición incompleta (variables huérfanas tras quitar
el foco) rompió el tilt entero sin que nadie lo pidiera. Antes de editar
este archivo por cualquier motivo, verificar después con Playwright que
`getComputedStyle(card).transform` sigue dando un `matrix3d(...)` real al
mover el mouse sobre una tarjeta (no `"none"`).

## Cloudflare Workers AI (`workers/rss-news/worker.js`)

- El Worker se llama `skillcash-noticias` (no uno viejo con nombre botado
  tipo `jolly-waterfall-...`). Ver `workers/rss-news/README.md`.
- Requiere un binding llamado EXACTAMENTE `AI` (Settings → Bindings →
  Workers AI) para que `env.AI` exista — si falta, la traducción falla en
  silencio (no truena, solo deja el texto en inglés).
- Modelos en uso: traducción `@cf/meta/m2m100-1.2b`; análisis de
  sentimiento/resumen y moderación de reseñas `@cf/meta/llama-3.1-8b-instruct-fast`.
  Los IDs de modelo de Workers AI se deprecian con el tiempo (ya pasó con
  `@cf/meta/llama-3.1-8b-instruct`) — si un modelo empieza a fallar, buscar
  primero si hay un reemplazo "-fast" o similar antes de asumir otra causa.
- NO usar APIs gratuitas de traducción de terceros (MyMemory, el endpoint no
  oficial de Google Translate) desde este Worker — ambas devuelven HTTP 429
  consistentemente por las IPs de salida compartidas de Cloudflare, aunque
  funcionen bien desde un navegador normal. Por eso se usa Workers AI en vez
  de eso.
- Cache de 30 min (`CACHE_SECONDS`) + caché del navegador: al probar un
  cambio recién desplegado, usar una URL con un parámetro que cambie en
  cada prueba (`&v=2`, `&v=3`...) o va a parecer que el cambio "no hizo
  nada" cuando en realidad es una respuesta vieja cacheada.

## Comunicación con Juan

- No es técnico; muchos mensajes vienen dictados por voz y pueden salir con
  palabras trabadas/mal transcritas — si algo no cuadra gramaticalmente,
  interpretar por el contexto antes de pedir aclaración.
- Cuando manda una captura de pantalla anotada (flechas, círculos, texto
  encima), la POSICIÓN exacta de esa marca importa tanto como la intención
  general — revisar con cuidado dónde señaló, no solo qué pidió en palabras.
- Verificar siempre con Playwright antes de dar un cambio visual por
  terminado: sin errores de consola, estilos computados correctos, sin
  desborde horizontal en escritorio (1400px) y celular (390px), y revisar la
  captura antes de hacer commit — Juan no puede leer el código, solo ve el
  resultado en su navegador.
