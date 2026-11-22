# Estilo de imágenes para banners de categoría ("tiburones estilo La Guarida")

Este documento guarda, palabra por palabra, el estilo visual que a Juan
le encantó para las fotos de banner de las categorías de "Tus
Herramientas" (`.tool-section-banner` y `.indic-index-banner`), para
poder reaplicarlo en el futuro sin tener que redescubrirlo por prueba y
error. Se llegó a esta fórmula después de VARIAS iteraciones fallidas —
ver sección "Por qué NO funcionó" más abajo, es tan importante como la
fórmula que sí funciona.

## El descriptor de estilo clave (lo más importante del documento)

La frase exacta que determina el "tipo de dibujo" es:

> **"Semi-realistic painterly illustration"**

NO usar en su lugar (se probó y da un resultado distinto, más plano,
más "gráfico/sticker", menos pintura, a Juan no le gustó):
- "Epic underwater fantasy digital painting"
- "photorealistic digital painting" / "photorealistic... highly detailed"

Juan fue explícito: *"Hay algo que en ese prompt hiciste que hace que se
vea así y ahora no se ve así... revisa cuál fue ese prompt que me
lograste dar"*. La única diferencia real entre el prompt que SÍ
funcionó y los que NO, era este descriptor de apertura. Todo lo demás
(colores, composición, elementos) daba igual si no se abría con esta
frase exacta.

## Prompt plantilla (reusable, ya probado 2 veces con éxito)

Estructura exacta que ya funcionó para La Guarida (Rango de Manada,
imagen original que a Juan le encantó) y para Sonar de Mercado
(reaplicando la misma estructura, solo cambiando el objeto central):

```
Semi-realistic painterly illustration of [OBJETO CENTRAL: ancient rank
insignia wall / ancient sonar device / ancient control console / etc.]
carved into a rocky reef wall, resting on the ocean floor at dusk, deep
blue-purple twilight ambient lighting, faint fading sunbeams barely
reaching from above. A [pack of sharks / large shark] swimming [in
formation / close beside the object] at the exact same height, as if
[organized by rank / patrolling its territory], glowing bioluminescent
markings along their sides in teal and gold. [El objeto central] is
carved from stone and bronze, embedded in the rock wall, [detalle de
qué brilla y cómo: ej. "emitting soft pulsing blue light rings" /
"its dials and circular gauges glowing with soft pulsing golden
light"], roughly the same size and visual weight as the shark so both
are equally prominent. Carved into the rock wall beside it, a row of
glowing rank insignia/badges embedded in coral, lit from within. A
shipwreck faintly visible in the dark background, also centered
vertically. Generous empty dark water space above and below this
central band, nothing important near the top or bottom edges.
Colorful coral in muted pink, orange and purple tones along the band.
Landscape orientation, 3:2 aspect ratio, wide banner composition, all
key elements confined to the middle third of the frame vertically.
```

Solo se cambia: (1) qué es el objeto central tallado en la roca, (2) qué
tipo de luz emite ese objeto, (3) el verbo de qué hace el tiburón junto
a él. El resto de la plantilla (apertura, iluminación ambiental,
tiburón, insignias, barco hundido, composición en tercio medio, 3:2) se
mantiene intacto.

## Descripción exacta del tiburón (para que se vea "igualito" siempre)

Cuando el prompt no describe el tiburón con suficiente detalle, el
modelo a veces lo dibuja con marcas de un solo color sólido (ej. verde
parejo) en vez de la mezcla correcta. Si hace falta ser más explícito,
usar esta descripción (ya validada por Juan comparando imagen por
imagen):

- Piel base: gris oscuro/grafito casi negro arriba, se aclara a gris-
  blanco en el vientre.
- Las marcas bioluminiscentes son líneas finas tipo tribal/circuito que
  corren a lo largo del lomo y los costados, angostándose hacia la
  cola.
- Color de las marcas: **mezcla de dos tonos** — líneas en **teal/verde-
  azulado** + puntitos pequeños individuales en **amarillo-dorado**
  salpicados dentro del patrón. NO es un solo color sólido (ni todo
  verde, ni todo azul, ni todo amarillo).
- Ojos oscuros, sin brillo.
- El patrón se lee como tatuajes tribales o circuitos impresos en la
  piel, no como un overlay plano/pegatina encima.

## Ambientación general

- Atardecer azul-púrpura profundo ("dusk"), con buena visibilidad —
  **nunca negro total / sin luz** (se probó una versión "very dark,
  almost black ambient water" y a Juan no le gustó nada: *"es como todo
  negro"*). El punto correcto es oscuro pero rico en detalle, se debe
  poder distinguir el fondo (ciudad, barco, ruinas) claramente.
- Rayos de luz tenues bajando desde la superficie, cada vez más débiles
  (no un solo rayo brillante central tipo "dios rayo").
- Barco hundido en silueta al fondo, centrado verticalmente con el resto
  de la composición.
- Una fila de medallones/insignias circulares talladas en la roca,
  incrustadas en coral, iluminadas desde dentro en dorado/ámbar cálido
  (como antorchas) — cada medallón con un símbolo distinto (aleta,
  flecha/tridente, onda, estrella, diamante, garra, etc.)
- Coral de colores apagados (rosa, naranja, púrpura) como acento, no
  protagonista.
- Composición: SIEMPRE pedir que los elementos clave queden confinados
  al tercio medio vertical del encuadre, con espacio vacío de agua
  oscura arriba y abajo — esto es clave porque la caja real del banner
  en el sitio es MUCHO más panorámica (ratio ~3.7:1 a ~4.2:1) que el
  3:2 que entrega el generador de imágenes, así que dejar aire arriba y
  abajo da margen para recortar sin perder nada importante.

## Por qué NO funcionó (intentos descartados, para no repetirlos)

1. **"Epic underwater fantasy digital painting... photorealistic"** —
   estilo de render distinto (más "foto/CGI"), aunque se describieran
   los mismos colores y elementos, el tipo de trazo/pincelada no se
   parecía al original. Causa raíz identificada después de 2-3
   iteraciones fallidas.
2. **Fondo "very dark and moody, almost black ambient water"** — se
   pidió así pensando que igualaría el tono oscuro de La Guarida, pero
   quedó demasiado negro/sombrío parejo. El tono correcto es "dusk"
   (atardecer), oscuro pero visible, no negro.
3. **Describir el tiburón con un solo color de marca** (ej. "glowing
   green bioluminescent markings") — el modelo lo resuelve con un verde
   sólido parejo, pierde el contraste de dos tonos (teal + puntos
   dorados) que tiene el original.
4. **Un objeto central mucho más grande que el tiburón, o viceversa** —
   cuando uno de los dos protagonistas domina la composición, el otro
   se ve "de relleno". Hay que pedir explícitamente tamaño/peso visual
   similar entre ambos.

## Dónde ya se aplicó este estilo exacto (vs. el estilo "Atlantis" anterior)

Importante: el sitio pasó por una primera ronda de banners con un estilo
distinto ("ruinas de la Atlántida con runas azul-cian brillantes", sin
tiburones, ver commits de Zona de Caza/El Banco/La Coraza). Juan luego
pidió migrar TODO a este estilo de tiburones de La Guarida (*"quiero
todas las imágenes con la misma onda"*). Estado a la fecha de este
documento:

- ✅ **La Guarida** (`rangos`, `assets/menu-principal/rango.webp`) — el
  original, referencia de estilo.
- ✅ **Sonar de Mercado** (`indicadores`,
  `assets/sonar/profundidad-banner.webp`) — ya migrado a este estilo
  (sonar + tiburón).
- ✅ **Mi Arrecife** (`portafolio`,
  `assets/menu-principal/portafolio.webp`) — prompt ya entregado a
  Juan con esta fórmula (consola + tiburón), pendiente de que Juan
  genere la imagen y la mande para aplicar.
- ⏳ **El Banco** (`inversion`, `assets/menu-principal/aliados.webp`) —
  todavía con el estilo "Atlantis" anterior (volcán + tesoro, sin
  tiburón). Pendiente de migrar si Juan lo pide.
- ⏳ **Zona de Caza** (`trading`, `assets/menu-principal/zonacaza.webp`)
  — todavía con el estilo "Atlantis" anterior (tiburón cazando entre
  ruinas, pero con el descriptor de estilo "Epic underwater fantasy...
  photorealistic", NO con "Semi-realistic painterly illustration").
  Pendiente de migrar si Juan lo pide.
- ⏳ **La Coraza** (`seguridad`, `assets/menu-principal/seguridad.webp`)
  — todavía con el estilo "Atlantis" anterior (escudo/domo, sin
  tiburón). Pendiente de migrar si Juan lo pide.

## Metodología de recorte (sin cambios, ya establecida)

1. Medir la caja REAL del banner en el sitio con Playwright
   (`getBoundingClientRect()` sobre `.tool-section-banner` o
   `.indic-index-banner` a 1400px de viewport) — nunca asumir el ratio.
2. Generar una imagen de diagnóstico con líneas de cuadrícula cada 20px
   (PIL `ImageDraw`) para ubicar con precisión dónde cae cada elemento
   clave (tiburón, objeto central, texto en inglés a evitar, watermark
   "Made with AI").
3. Calcular el recorte: ancho completo (1248), alto = `1248 / ratio_real`.
4. Elegir el `top` del recorte priorizando, en este orden: (a) que no se
   vea texto en inglés ni el watermark, (b) que ambos protagonistas
   (tiburón + objeto) se vean lo más completos posible — cuando hay
   conflicto entre mostrar texto/watermark y cortar un poco al sujeto,
   se prioriza SIEMPRE ocultar el texto/watermark.
5. Guardar como `.webp` (`quality=85, method=6`).
6. Reemplazar el archivo real en `assets/...`, actualizar
   `width`/`height` del `<img>` si cambiaron, verificar con Playwright
   (1400px y 390px, sin overflow, sin errores de consola), commit +
   push + sync a `main`.
