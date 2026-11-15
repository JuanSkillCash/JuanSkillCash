# gridstack.js (vendorizado)

Versión **14.1.0** (MIT), descargada del tarball oficial de npm
(`registry.npmjs.org/gridstack/-/gridstack-14.1.0.tgz`) el 15-nov-2026, sin modificar.

Se sirve self-hosted (no CDN) para no depender de un tercero en producción. Archivos:
- `gridstack-all.js` — build completo (core + drag/drop), sin dependencias.
- `gridstack.min.css` — estilos base de la grilla.

No requiere `gridstack-extra.css` (ya no existe desde v12 — columnas vía variables CSS).

Para actualizar de versión: descargar el tarball de la versión nueva desde npm, reemplazar
estos dos archivos, y revisar el changelog de gridstack.js por cambios de API antes de
actualizar (la API vanilla JS se mantuvo estable de v12 a v14; el único cambio de v14 fue en
el wrapper de Angular, que no usamos aquí).
