# Roadmap (futuro): Plataforma de volumen por afiliado → desbloqueo de herramientas

Visión de Juan, capturada en conversación con Claude Code tras revisar
`docs/referencia-bcd-dashboard.md`. NO es para construir ahora — es la nota de
roadmap para no perder la idea entre sesiones.

## La idea en una frase

El usuario conecta su cuenta de Bitunix (vía API key **solo lectura**, nunca de
retiro ni trading) usando el link de afiliado de SkillCash. A medida que genera
volumen de trading real ahí, desbloquea niveles ("tiers") que dan acceso a
**herramientas de trading reales dentro de SkillCash Tools** — no puntos para
gastar en cosméticos de un avatar (eso es lo que hace BCD, ver sección 11 de
`referencia-bcd-dashboard.md`).

## Por qué este modelo y no el de BCD

- BCD paga puntos por CADA trade, por volumen, por racha de días en verde, con
  multiplicador de hasta 4x por tier — eso empuja a sobreoperar, sobre todo con
  apalancamiento x10.
- Aquí el desbloqueo es consecuencia de un volumen que el usuario ya genera por
  su cuenta, no algo que el sitio incentive activamente a base de puntos. Lo que
  se entrega a cambio es ayuda real para operar mejor (herramientas), no una
  recompensa artificial para seguir operando.
- Mantiene la posición educativa de SkillCash en vez de convertirse en "gana
  puntos por arriesgar más".

## Objetivo de negocio

Juan quiere vivir de esto: trading + comisiones de afiliado (Bitunix ya paga
comisión por volumen, confirmado con el banner "20% de cashback" que ya existe
en el sitio). Este sistema de tiers es el mecanismo para convertir "gente usando
las herramientas gratis" en "gente operando por el link de afiliado de Juan".

## Piezas técnicas necesarias (alto nivel, sin diseñar aún)

1. **Flujo "Conectar Bitunix"** — mismo patrón de UX que ya se uso para
   Telegram (instrucciones claras + confirmación), pero mucho más sensible:
   el usuario crea una API key en Bitunix con permiso **SOLO LECTURA**
   (explícitamente sin retiro, sin trading) y la pega en el sitio.
2. **Manejo seguro de la API key** — nunca debe quedar legible desde el
   navegador ni en texto plano en Supabase. Probablemente:
   - Una Edge Function (como la de Telegram) que reciba la key, la use para
     consultar volumen en Bitunix, y decida si hace falta persistirla cifrada
     o si alcanza con pedir cosas puntuales cada vez.
   - Si hay que guardarla, cifrada con una clave que solo la Edge Function
     conozca (nunca el service role key sola, que ya la tienen varios robots).
3. **Robot/calculo periódico de volumen** — igual patrón que los scrapers
   actuales: un robot (GitHub Actions) o una Edge Function que calcule, por
   usuario, el volumen generado y lo guarde en Supabase.
4. **Tabla de tiers** — cuánto volumen = qué tier, y qué herramienta(s)
   desbloquea cada tier. Podrían ser herramientas nuevas, o herramientas ya
   existentes del sitio que se re-categoricen como "premium por volumen".
5. **Verificación de que el volumen es por EL link de Juan** — Bitunix
   normalmente deja verificar esto con su propio sistema de afiliados/VIP
   code, no hay que inventarlo desde cero.

## Rangos definidos (decidido en sesion del 2026-10-22, corregido el mismo dia)

5 rangos, por volumen de trading DEL MES EN CURSO (se reinicia cada mes -
decision explicita de Juan: "necesito que la gente haga volumen... que no
pierdan su rango y si dejan de operar, siguen usando mi plataforma, y yo no
gano". Sin reinicio mensual, con el tiempo todo el mundo termina en Alfa sin
seguir operando, y el sistema deja de cumplir su proposito):

| Rango        | Condicion dentro del mes en curso |
|--------------|-------------------------------------|
| 🐣 Cria       | Al menos 1 operacion real (no hace falta volumen minimo) |
| 🐟 Explorador | $10,000 de volumen |
| 🦈 Cazador    | $50,000 de volumen |
| 🐬 Depredador | $150,000 de volumen |
| 👑 Alfa       | $500,000 de volumen |

Antes de la primera operacion del mes, el usuario no tiene ningun rango
todavia (ni siquiera Cria) - Cria se desbloquea, no es el estado por
defecto.

Implementacion: en vez de acumular volumen de por vida, cada corrida del
robot (scripts/update_bitunix_volume.py) vuelve a sumar desde el dia 1 del
mes en curso (UTC) hasta ahora - como nunca pasa de ~31 dias, siempre cabe
en el limite de 180 dias por llamada de la API de Bitunix, y el "reinicio"
pasa solo, sin ningun cron especial, en cuanto cambia el mes.

Ya estan puestos como shell visual en la cajita "Rango de Manada" de
index.html (sin logica real de calculo de volumen conectada todavia).

## Preguntas abiertas (resolver antes de construir, no ahora)

- ¿Solo Bitunix al principio, o multi-exchange desde el día uno?
- ¿Qué herramientas específicas valen la pena reservar detrás de cada rango
  (y cuántas en total), y cuáles se quedan gratis para todos (para no perder
  el valor educativo abierto que ya tiene el sitio)? Pendiente hasta que
  existan herramientas que desbloquear.
- ¿Qué pasa si alguien ya tenía cuenta en Bitunix antes de usar el link de
  Juan? ¿Cuenta su volumen viejo o solo el nuevo?

## Riesgo / responsabilidad a tener en cuenta

Tocar API keys de exchanges de terceros es un salto real de responsabilidad
frente a todo lo construido hasta ahora (que es solo lectura de datos
públicos). Aunque la key sea de solo-lectura, sigue siendo información
sensible de la cuenta del usuario — hay que ser explícito en los términos de
uso sobre qué se hace con ella, y limitar el alcance de los permisos pedidos
al mínimo indispensable desde el primer día.

## Sesión 2026-11-03: investigación a fondo de un competidor + orden de construcción acordado

Juan pidió investigar en profundidad (vía otra sesión de Claude con navegador real, cuenta
propia de Juan) la plataforma "Marines Live Platform" (melapela.ai) - mismo modelo que este
roadmap (volumen real → desbloqueo de herramientas). Cuatro rondas de investigación quedaron
guardadas como oro en `docs/referencia-competencia-mlp.md` (dossier técnico: endpoints, campos
JSON reales, fórmulas de sus indicadores verificadas con datos reales - Radar, Mapa Tendencial,
Tactical, La Cubierta, sus 3 minijuegos, y su panel de Noticias completo). Léelo antes de
diseñar cualquier pieza de este roadmap - ya resuelve varias de las "preguntas abiertas" de
arriba por comparación directa con quien ya lo construyó.

### Corrección importante: Rango de Manada NO se abre al público

Una ronda anterior de esta misma conversación sugirió abrir la Bitácora de trading a todo el
mundo sin candado. **Juan lo corrigió explícitamente: no.** El modelo se mantiene 100% cerrado
por volumen, igual que el roadmap original de arriba ya decía:
- Para siquiera ENTRAR a la categoría "Rango de Manada" hace falta mínimo 1 operación real con
  el link de afiliado de Juan (equivalente al rango 🐣 Cría ya definido arriba).
- Las herramientas DE ADENTRO (Bitácora y las que se construyan después) se desbloquean por
  volumen, no quedan abiertas a quien no cumple el mínimo.
- Ninguna herramienta de "Rango de Manada" se abre gratis a quien no haya conectado Bitunix con
  el link de Juan y generado al menos ese volumen mínimo.

### Orden de construcción acordado (de más fácil a más difícil)

Juan pidió explícitamente dejar TODO lo que vive dentro de "Rango de Manada" para el final
(justo lo de esta sección del roadmap), porque es lo que más detalle necesita. Orden decidido:

1. **12 Logros de trading en la Bitácora** (badges tipo Primer Disparo, Racha Dorada, etc. -
   ver `referencia-competencia-mlp.md` sección "Extras aprovechables" de la v4) - usa datos que
   `journal.js` ya calcula, no necesita dato externo nuevo.
2. **Panel de Noticias y Mercado** - agregación de fuentes públicas gratis (Alternative.me,
   CoinGecko, OKX) + un par de widgets embebidos (TradingView, Investing.com). Empezar con
   versión fija (sin drag-and-drop) y agregar personalización después si se quiere. Pendiente
   de decidir: si incluir contenido de la "Agenda de Trump" (es contenido de política de EE.UU.,
   Juan no ha confirmado si encaja con la marca).
3. **Tarjeta compartible de operación con QR de referido** - extiende la tarjeta para compartir
   que ya existe (la del tiburón) a un trade cerrado de la Bitácora.
4. **Minijuego tipo "BTC 5 minutos"** con Sharkoins (apuesta binaria sube/baja en ventana corta,
   fórmula de pago propia y transparente).
5. **Mapa Tendencial** (indicador de confluencia multi-temporalidad, ver sección C de la v2 del
   dossier) - más esfuerzo porque calcula un indicador real (tipo SuperTrend) en 8 temporalidades,
   pero es solo informativo, sin el riesgo de un generador de señales.
6. **La Cubierta** (red social de trading, feed + calls verificables + contenido exclusivo por
   rango) - proyecto grande en sí mismo; el contenido exclusivo por rango de todas formas
   necesita que el sistema de rangos (punto 9) ya exista.
7. **Radar / Tactical** (generador de señales reales con SL/TP/apalancamiento sugerido) - el
   más potente pero también el que más cuidado legal/de responsabilidad necesita (estaríamos
   diciendo "entra aquí con este apalancamiento"); merece conversación aparte antes de construir.
8. **Rango de Manada completo** (de último) - la tabla de rangos propia, el motor que conecta
   el volumen real de Bitunix con cada herramienta de arriba, la escalera visual, el anillo de
   progreso. Se deja de último porque amarra todo lo anterior - tiene más sentido construirlo
   ya sabiendo qué herramientas exactas está gateando.

### Ideas nuevas de Juan (mismo día) - por desarrollar más adelante

- **"Mi Arrecife" como el nuevo dashboard de widgets personalizables.** Juan propone reutilizar
  la tarjeta/categoría existente "Mi Arrecife" como el lugar donde vive el panel de Noticias y
  Mercado tipo "lienzo" (inspirado en el de melapela.ai, ver v4 del dossier) - y redistribuir
  en otras cajas del sitio lo que hoy vive dentro de Mi Arrecife. Sin decidir todavía qué pasa
  exactamente con cada cosa que hoy tiene Mi Arrecife; es una idea a madurar antes de tocar código.
- **Incluir el contenido de "en vivo"** (conferencias/videos en vivo embebidos, al estilo del
  widget "Conferencias" de melapela) dentro de esos widgets personalizables - a Juan le gustó
  poder ver un video en vivo directo ahí mismo.
- **"Profundidad" visual en ciertas cajas** - Juan quiere que, más adelante, algunas cajas del
  sitio (hoy todas con el mismo contorno azul aguamarina plano) tengan algo de profundidad
  visual en casos puntuales - todavía sin decidir en cuáles ni cómo se vería. Pendiente de
  retomar la conversación cuando Juan tenga tiempo de pensarlo con calma.

### Estado

Solo documentado y acordado el orden - **nada se ha construido todavía de este roadmap.** Juan
se quedó sin límite semanal de uso; retoma después del jueves (reinicio del límite). Próximo
paso cuando retome: empezar por el ítem 1 del orden de arriba (los 12 logros de trading).
