# SkillCash Tools

Antes de trabajar en el screener/dashboard, lee docs/referencia-bcd-dashboard.md

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
