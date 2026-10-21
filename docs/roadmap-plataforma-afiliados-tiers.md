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

## Preguntas abiertas (resolver antes de construir, no ahora)

- ¿Solo Bitunix al principio, o multi-exchange desde el día uno?
- ¿Qué herramientas específicas valen la pena reservar detrás de un tier, y
  cuáles se quedan gratis para todos (para no perder el valor educativo
  abierto que ya tiene el sitio)?
- ¿Volumen acumulado de por vida, o ventana móvil (ej. últimos 30 días), para
  que un tier se pueda "bajar" si alguien deja de operar?
- ¿Qué pasa si alguien ya tenía cuenta en Bitunix antes de usar el link de
  Juan? ¿Cuenta su volumen viejo o solo el nuevo?

## Riesgo / responsabilidad a tener en cuenta

Tocar API keys de exchanges de terceros es un salto real de responsabilidad
frente a todo lo construido hasta ahora (que es solo lectura de datos
públicos). Aunque la key sea de solo-lectura, sigue siendo información
sensible de la cuenta del usuario — hay que ser explícito en los términos de
uso sobre qué se hace con ella, y limitar el alcance de los permisos pedidos
al mínimo indispensable desde el primer día.

## Estado

Solo documentado. No se ha empezado a construir nada de esto. Próximo paso,
cuando Juan quiera retomarlo: resolver las preguntas abiertas de arriba y
definir la Fase 1 concreta (probablemente: conectar Bitunix en modo lectura +
mostrar el volumen/tier actual, sin desbloquear nada todavía).
