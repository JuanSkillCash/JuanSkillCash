# Informe técnico: viabilidad de monitoreo/copy-trading sobre FOMO (fomo.family)

**Fecha:** 2026-09-11
**Alcance:** Investigación pasiva basada en fuentes públicas (motor de búsqueda). **No se ejecutó ninguna operación, no se conectó ninguna wallet, no se introdujeron credenciales y no se intentó eludir autenticación, rate limits, CAPTCHA ni Cloudflare.**

---

## 0. Limitación metodológica importante (léase primero)

Este informe se preparó dentro de un entorno de ejecución en la nube con una política de red restrictiva: el proxy de salida (`agent-proxy`) **bloquea el acceso HTTP saliente a dominios arbitrarios** (`fomo.family`, `en.wikipedia.org`, `www.fomoscan.sh`, e incluso `github.com` en acceso directo devolvieron `403`/bloqueo de política). Verificación:

```
$ curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://fomo.family/
curl: (56) CONNECT tunnel failed, response 403
```

Esto significa que **no pude**:
- Inspeccionar directamente el HTML/JS de fomo.family ni su pestaña de red (DevTools).
- Descargar ni analizar bundles JavaScript de la app.
- Conectarme a ningún WebSocket real (el propio proxy documenta que los *WebSocket upgrades* tampoco están soportados).
- Verificar en vivo que un endpoint responde 200 y con qué payload exacto.

Por lo tanto, **todo lo que sigue proviene de resultados de búsqueda web (snippets indexados) de fuentes públicas** — blog oficial de fomo.family, cobertura de prensa, Wikipedia, y sobre todo **tres servicios de terceros no afiliados** que documentan públicamente cómo obtienen datos de FOMO. Cada afirmación está citada. Donde no encontré confirmación directa, lo digo explícitamente en vez de asumir un endpoint.

**Consecuencia práctica:** no puedo certificar con inspección directa "este endpoint existe y responde así". Antes de construir nada más allá del prototipo de solo-lectura incluido aquí, alguien con acceso normal a Internet debería reproducir estos hallazgos abriendo fomo.family en un navegador con DevTools → Network, exactamente como se describe en la sección F.

---

## 1. ¿Qué es FOMO (fomo.family)?

FOMO es una app social de trading cripto (fundada en 2025 por Paul Erlanger, Se Yong Park y Prashan Dharmesena) que permite operar memecoins/altcoins/stablecoins en Solana, Base, BNB Chain y Monad desde un único saldo en USD, sin gestión manual de wallets ni gas. Cerró una Serie B de 75M USD liderada por Index Ventures (junio 2026). [Fintech Global](https://fintech.global/2026/06/23/fomo-raises-75m-series-b-to-scale-on-chain-trading-app/), [Index Ventures](https://www.indexventures.com/perspectives/on-chain-trading-goes-mainstream-fomos-75-million-series-b/), [Wikipedia](https://en.wikipedia.org/wiki/Fomo_(platform)).

**Punto arquitectónico clave para este proyecto:** FOMO **no es custodio puro**. Usa wallets embebidas (una por usuario) vía **Privy** como proveedor de infraestructura de wallets:
- En Solana: wallet embebida gestionada con Privy, con la clave privada dividida mediante *Shamir's Secret Sharing* (ningún actor único tiene la clave completa; el usuario puede exportarla). [Privy Blog](https://privy.io/blog/turning-trading-into-a-social-experience-with-fomo)
- En cadenas EVM (Base, BNB Chain, Monad): smart-contract wallets basados en el estándar de account abstraction **ERC-4337**, lo que permite onboarding sin seed phrase y sin gas visible para el usuario. [Insights4.vc](https://insights4.vc/blog/fomo-behind-the-75-series-b/)
- No hay un bridge unificado: la abstracción "un solo saldo, varias chains" vive en la capa de aplicación de FOMO, no on-chain. [Privy Blog](https://privy.io/blog/turning-trading-into-a-social-experience-with-fomo)

**Esto implica que cada operación de un usuario de FOMO se liquida como una transacción real y pública en la blockchain correspondiente (Solana / Base / BNB / Monad), asociada a la dirección de la wallet embebida de ese usuario.** Es la pieza más importante de todo el informe: significa que, en principio, las operaciones no son un secreto interno de FOMO — son datos de blockchain pública, siempre que se conozca la dirección de wallet asociada al handle del trader.

---

## 2. A) API — ¿Existe una API pública/documentada de FOMO?

**Conclusión: No hay evidencia de una API pública ni documentación para desarrolladores publicada oficialmente por FOMO Labs / fomo.family.**

- Búsquedas dirigidas a `docs.fomo.family`, `developers.fomo.family`, `help.fomo.family`, `api.fomo.family` y `app.fomo.family` no devolvieron ningún resultado indexado de esos subdominios.
- Un resumen de búsqueda lo confirma explícitamente: *"fomo is a consumer-facing product and does not publish a public developer API, SDKs, or API documentation."*
- Sí existe una página de soporte (`support@fomo.family`, según snippets) y un blog (`fomo.family/blog`), pero no un portal de developers.
- **No confundir con "Fomo" (usefomo.com / fomo.com)**, una herramienta de marketing de "social proof" (notificaciones de "Juan compró X hace 2 min" en e-commerce) que **sí** tiene API pública documentada, SDKs oficiales en Python/PHP (`github.com/usefomo/fomo-python-sdk`, `github.com/usefomo/fomo-php-sdk`) y un knowledge base (`help.fomo.com`). Es una empresa completamente distinta que sólo comparte el nombre. Varios resultados de búsqueda mezclan ambas — hay que filtrar con cuidado.
- Tampoco confundir con `fomo-framework` (un microframework PHP en GitHub, sin relación) ni con "Fomo" wallets de terceros mencionadas en directorios de wallets — mismo problema de nombre genérico.

**Lo que sí encontré: tres servicios de terceros NO afiliados** que ofrecen API sobre datos relacionados con FOMO:

| Servicio | Qué ofrece | Afiliación oficial |
|---|---|---|
| **FomoScan** (`fomoscan.sh`) | REST API que resuelve *handle de FOMO ↔ wallet verificada* (Solana y EVM), grafo de seguidores, holdings. Índice de solo lectura. | Explícitamente **no afiliado**: *"FomoScan is an independent, unofficial tool that is not affiliated with, endorsed by, or sponsored by fomo.family."* |
| **FOMO API** (`fomoapi.io`) | REST + WebSocket. Leaderboards, perfiles, trades, streaming en tiempo real (ver sección B). | No afiliado — ofrecido como producto independiente de datos, sin declaración de partnership con FOMO Labs encontrada. |
| **FomoTop** (`fomotop.money`) y **Solana Tracker** (`solanatracker.io/leaderboard/fomo`) | Leaderboards de wallets que operan a través de FOMO, con PnL/ROI/volumen/win-rate. Solana Tracker además ofrece un SDK oficial (`@solana-tracker/data-api`) para su propia API general de datos on-chain. | No afiliados a FOMO; son productos de analítica on-chain que etiquetan wallets como "usuarios de FOMO". |

Ninguno de estos tres es citado por fomo.family como socio oficial en las fuentes que pude consultar. **Deben tratarse como terceros no verificados**: útiles como pista de qué es técnicamente observable, pero no como "la API oficial de FOMO", y su propio cumplimiento de los términos de FOMO es responsabilidad de ellos, no algo que yo pueda garantizar.

### Métodos HTTP / autenticación (del único servicio con documentación pública, `fomoapi.io`)
- Autenticación: cabecera `Authorization: Bearer YOUR_API_KEY`.
- Nivel gratuito sin key para leaderboards/perfiles/trades con límites bajos; keys de pago para más cuota.
- Rate limits documentados: Free 60 req/min, Starter ($49/mes) 150 req/min, Growth ($599/mes) 600 req/min + stream on-chain, Scale ($1500/mes) el tope más alto. Límite por API key, no por IP; exceso → HTTP 429.
- **No pude verificar esto contra el servidor real** (bloqueo de red del sandbox); es lo que indexa su propia documentación pública (`fomoapi.io/docs`, `fomoapi.io/pricing`).

**No se han usado, comprado ni configurado credenciales de ningún servicio de terceros en esta investigación**, conforme a las restricciones del encargo.

---

## 3. B) WebSocket

**FOMO (la app oficial) probablemente usa WebSocket o push internamente** para las notificaciones "en tiempo real" que describe su propio blog (alertas instantáneas cuando un trader seguido compra/vende), pero **no encontré el endpoint WebSocket propio de fomo.family** — no está documentado públicamente y no pude inspeccionar el tráfico de red de la app (ver limitación en sección 0).

Lo único con especificación pública es, de nuevo, el servicio de terceros **`fomoapi.io`**:

- Endpoint: `wss://api.fomoapi.io/ws/alerts?key=YOUR_API_KEY`
- Dos streams distintos:
  - `/ws/alerts` — replica el feed de actividad de la app FOMO (incluido en todos los planes, incluso el gratuito).
  - `/ws/trades` — stream on-chain (requiere plan Growth o Scale).
- Estructura de evento (según su propia documentación indexada): tipo `"alert"`, con `alertType` ∈ {`buy`, `sell`, `thesis`, `whale`, `price`, `trade`}, `source` ∈ {`"feed"` (feed social), `"push"` (notificación móvil)}. Cada mensaje incluiría: trader, token + dirección de contrato, chain, lado (buy/sell) y tamaño.
- Su propio marketing (`x.com/getfomoapi`) lo describe como: *"turn any fomo handle into their real onchain wallets, live websocket of trades from any fomo handle, thesis data per user or token, live now."*

**Interpretación:** todo indica que `fomoapi.io` construye este feed combinando (a) datos on-chain indexados en tiempo real de las wallets que ya identificaron como pertenecientes a usuarios de FOMO, y posiblemente (b) alguna forma de acceso al feed social/push de la app — este segundo punto **no está confirmado** y, si implica scraping del feed privado de FOMO, sería un problema de cumplimiento *de ellos*, no algo que hayamos verificado ni replicado nosotros.

**No verifiqué esto contra el servidor real** (no se abrió ninguna conexión WebSocket, ni con ni sin key, consistente con "no introducir credenciales" y con la imposibilidad técnica del sandbox de hacer upgrades WebSocket).

**No hay ninguna documentación pública de cómo un cliente se suscribe a la actividad de UN trader específico dentro del WebSocket propio de FOMO** (p. ej. un mensaje tipo `{"action":"subscribe","trader_id":"..."}`). Esto sigue siendo una incógnita real que solo se puede resolver inspeccionando el tráfico de la app oficial con DevTools/proxy MITM autorizado por el propio usuario en su propia sesión — no algo que deba inferirse o inventarse.

---

## 4. C) Traders — identificación y métricas públicas

Fuentes coinciden en que el **leaderboard de FOMO es una superficie pública** (visible dentro de la app/web sin necesidad de estar autenticado como el trader seguido) con al menos estas métricas:

- **PnL** (realizado, en USD)
- **ROI** (%)
- **Win rate** (%)
- **Volumen** de trading
- Filtros por periodo: 24h, 7d, 30d
- Datos de ejemplo citados por terceros (con fecha "4 de septiembre"): PnL combinado del top-20 ≈ 82.38M USD, media ≈ 4.12M USD, mediana ≈ 2.91M USD; win rate medio 74.9% en el segmento $0–$100 (tamaño de cuenta) y 72.9% en el segmento $10K+.

No encontré mención pública de **drawdown**, **número exacto de operaciones**, **seguidores por trader** o **historial operación-por-operación** como campos garantizados de la superficie oficial de FOMO — esos campos sí aparecen ofrecidos por los terceros (`fomoapi.io` afirma dar "full trade history with timestamps and amounts"; FomoScan da "follower graph").

**¿Forma programática de obtener el ranking?** No hay una API oficial de FOMO para esto. Programáticamente, hoy, la única vía documentada pasa por terceros no afiliados (`fomoapi.io`, `solanatracker.io/leaderboard/fomo`, `fomotop.money`) — cada uno con su propio nivel de confiabilidad, sin verificar por FOMO Labs.

Un dato relevante repetido en varias fuentes: *"the data is read directly from blockchains, so it cannot be faked or manipulated"* — refuerza que el ranking se reconstruye a partir de las wallets on-chain, no de un campo "PnL" autoreportado por el usuario.

---

## 5. D) Seguimiento ("Follow")

Según el blog oficial de FOMO (vía snippets) y guías de uso de terceros:

- El usuario sigue a un trader (identificado por su **handle** dentro de FOMO) desde el feed o el leaderboard.
- Al seguir a alguien, el usuario **recibe notificaciones** (push móvil y/o en el feed de actividad) cada vez que ese trader compra o vende, con opción de filtrar por tamaño mínimo de operación (p. ej. "solo avisarme si la operación es ≥ $1000").
- El "copy trading" en FOMO **no es automático por defecto**: el usuario ve la alerta y decide manualmente si replica la operación ("you still have to place every trade yourself" / "Copy trading gives you control—you decide whether to execute each trade").
- No encontré documentación pública de un mecanismo de **auto-copy** dentro de FOMO (ejecución automática sin intervención humana) — lo que existe descrito es notificación + réplica manual.

**¿Forma de recibir esos eventos sin usar la interfaz manualmente?** No hay un mecanismo oficial documentado. La única superficie programática existente para "eventos cuando un trader sigue operando" es, otra vez, el WebSocket de terceros (`fomoapi.io`) descrito en la sección B, que **no es una función de FOMO**, es una reconstrucción independiente hecha por un tercero.

---

## 6. E) Seguridad y Términos de Servicio

Fuente: `fomo.family/terms` (vía snippets indexados; no pude leer el documento completo directamente por el bloqueo de red del sandbox — se recomienda verificar el texto íntegro y vigente antes de tomar cualquier decisión).

Hallazgos relevantes y textuales (entrecomillado = cita directa recuperada de snippets):

1. **Bots / automatización de la cuenta — prohibido explícitamente:**
   > "using automated scripts, bots, software, or any automated means to create accounts, send messages, post content, execute trades, or otherwise control or interact with account activity on the Services"

2. **Scraping / recolección automatizada de datos — prohibido explícitamente:**
   > "using any automated tool, scraper, crawler, spider, or unauthorized third-party application to extract, collect, harvest, or compile data from the Services, including but not limited to user-generated content, transaction data, pricing information, or account information"

3. **Uso comercial no autorizado:**
   > uso de los Services "for any unauthorized commercial purpose or the benefit of a third party" está prohibido salvo que los Términos lo permitan.

4. **Ingeniería inversa / derivados:**
   > prohibido modificar, desensamblar, descompilar, adaptar, alterar, traducir o realizar ingeniería inversa de los Services.

5. **Terceros y disclaimers:** FOMO facilita acceso a materiales/tecnologías de terceros (DEXs, etc.) sin controlarlos ni responsabilizarse por ellos.

6. **Arbitraje y renuncia a acción colectiva / juicio con jurado** (estándar en ToS de fintech/cripto US).

**Lectura práctica para este proyecto:**
- **Scrapear fomo.family (web, app, o su API/WS privados) para construir el monitor está expresamente prohibido por el punto 1 y 2.** Esto aplica incluso si el endpoint es "públicamente visible" en el navegador — "públicamente visible sin login" no equivale a "autorizado para recolección automatizada" bajo estos Términos.
- Ejecutar operaciones vía bot dentro de FOMO también está expresamente prohibido (punto 1) — coincide con la restricción que el propio usuario impuso para esta fase.
- Los Términos **no dicen nada, en lo que pude recuperar, sobre el uso de datos on-chain públicos independientes de FOMO** (porque, lógicamente, FOMO no puede reclamar propiedad sobre transacciones públicas de Solana/Base/BNB/Monad que no controla). Esa es la vía que sí queda abierta — ver sección F.
- El estatus de cumplimiento de terceros como `fomoapi.io` o FomoScan **no está claro** desde esta investigación: si obtienen parte de sus datos scrapeando el feed privado de FOMO, ellos estarían en tensión con estos mismos Términos; si sólo indexan blockchain pública + verificación voluntaria de wallet por el propio trader, no lo estarían. No se pudo determinar cuál es el caso real sin inspección técnica directa de esos servicios (fuera del alcance de "no ejecutar/no usar credenciales" de esta fase, y bloqueado por la red del sandbox de todas formas).

---

## 7. Arquitectura actual de FOMO (síntesis)

```
┌─────────────────────────────┐
│   App móvil / Web (fomo.family) │  ← cliente propietario, sin API pública documentada
└───────────────┬─────────────┘
                │ (API/WS privados, NO documentados, NO verificados en este informe)
                ▼
┌─────────────────────────────┐
│   Backend de FOMO Labs, Inc. │  ← orquesta feed social, leaderboard, notificaciones,
│                               │     onboarding (email/Apple ID), gas sponsorship
└───────────────┬─────────────┘
                │
        ┌───────┴────────┐
        ▼                ▼
┌───────────────┐  ┌──────────────────────┐
│ Privy (wallets  │  │ Ejecución on-chain    │
│ embebidas,      │  │ real:                 │
│ Shamir SSS en   │→ │ Solana / Base / BNB   │
│ Solana; smart    │  │ Chain / Monad         │
│ accounts         │  │ (transacciones        │
│ ERC-4337 en EVM)  │  │ PÚBLICAS)             │
└───────────────┘  └──────────────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │ Blockchains públicas        │ ← fuente de verdad verificable
              │ (RPC, exploradores, índices)│    de forma independiente a FOMO
              └───────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  FomoScan (handle↔wallet)  fomoapi.io (REST/WS)  Solana Tracker / FomoTop
  — terceros no afiliados, construidos indexando la blockchain pública (y, en un caso no confirmado, posiblemente también el feed de FOMO)
```

**Fuentes de esta sección:** Privy Blog, Insights4.vc, fomoscan.sh (snippets), fomoapi.io (snippets), Index Ventures/Fintech Global (financiación), Wikipedia (fundadores/fecha).

---

## 8. Limitaciones de esta investigación

1. **No se pudo hacer inspección directa de red** (DevTools/HAR/MITM) de fomo.family por la política de egress del sandbox — todo lo relativo a "endpoints exactos de FOMO" queda como **no confirmado**, tal como pidió el encargo ("no asumas endpoints, comprueba que existen").
2. Los datos sobre `fomoapi.io`, FomoScan, FomoTop y Solana Tracker provienen de **su propio marketing/documentación indexada**, no de pruebas independientes contra sus servidores. Podrían estar desactualizados, ser inexactos, o exagerar capacidades.
3. No verifiqué el texto íntegro y vigente de `fomo.family/terms` — solo fragmentos indexados por buscadores. **Antes de construir nada, se debe leer el documento completo y actual directamente en el navegador.**
4. Existe alta contaminación de nombre: "Fomo/FOMO" es usado por al menos 6-7 productos no relacionados (marketing SaaS, frameworks de código, plataformas de scam-alert, apps de noticias). Filtré lo que corresponde a `fomo.family` con la mayor precisión posible, citando cada fuente.

---

## 9. Riesgos

- **Legal/ToS:** construir un scraper o cliente automatizado contra la app/API/WS *privados* de FOMO violaría los Términos citados (prohibición explícita de bots y scraping). Riesgo de suspensión de cuenta, bloqueo de IP, o acción legal según los propios Términos (incluyen cláusula de arbitraje).
- **Dependencia de terceros no verificados:** construir sobre `fomoapi.io`/FomoScan implica depender de un proveedor no oficial, sin SLA conocido, cuyo propio cumplimiento normativo no está garantizado, y que podría desaparecer o cambiar sin aviso.
- **Calidad del dato on-chain puro:** monitorear wallets on-chain directamente da certeza sobre *qué hizo esa wallet*, pero **no** identifica automáticamente *qué handle de FOMO es*, ni distingue operaciones hechas dentro de FOMO de operaciones hechas por la misma persona fuera de FOMO (la wallet embebida podría usarse igual desde otro cliente si el usuario exporta la key).
- **Copy trading real (ejecución):** fuera de alcance en esta fase por instrucción explícita; cuando se aborde, la vía legítima es una API oficial de exchange (ver sección 10.5), nunca automatizar la cuenta de FOMO.

---

## 10. Conclusión de viabilidad

### 10.1 Qué se puede hacer legal/técnicamente **con una API oficial de FOMO**
Actualmente: **nada**, porque no existe una API oficial pública. Si FOMO llegara a publicar una, habría que releer sus Términos de Servicio de developer específicos en ese momento.

### 10.2 Qué se puede hacer **únicamente con datos públicos** (sin tocar FOMO en absoluto)
- Monitorear **directamente en la blockchain** (Solana RPC, indexadores públicos, exploradores de Base/BNB/Monad) la actividad de wallets **cuya asociación a un trader/handle de FOMO se conozca por una fuente legítima** (el propio trader publicándolo, o un servicio de verificación de terceros que el usuario decida usar bajo su propio criterio de riesgo).
- Esto es 100% independiente de fomo.family: no se toca su web, su app, ni su API/WS — son transacciones públicas de la blockchain, no "datos de FOMO".
- Es la base del prototipo entregado en la sección 11.

### 10.3 Qué **NO** se debería hacer
- Scrapear fomo.family (web/app) o su tráfico de red privado, con o sin autenticación, de forma automatizada (viola ToS explícitamente).
- Conectarse al WebSocket/API interno de FOMO sin autorización explícita de FOMO Labs.
- Automatizar acciones dentro de la cuenta de FOMO (login, follow, trade) con bots (viola ToS explícitamente y viola la restricción del propio encargo).
- Depender de terceros no verificados como si fueran "la fuente oficial" sin due diligence adicional (revisar sus propios Términos, su modelo de negocio, y de dónde sacan realmente el dato).

### 10.4 Qué se necesita para un **prototipo de monitoreo** (próxima fase razonable)
1. Una lista de **wallets on-chain de interés**, obtenida de forma legítima: auto-declaración del trader, o un servicio de mapeo handle↔wallet que el usuario elija usar bajo su propio riesgo/términos (p. ej. revisar personalmente los Términos de FomoScan/fomoapi.io antes de usarlos).
2. Acceso a **infraestructura on-chain pública**: RPC de Solana (público o vía proveedor como Helius/QuickNode), y equivalentes EVM para Base/BNB/Monad (Etherscan-compatible APIs, Alchemy, etc.).
3. Un motor de **selección de "buenos traders"** que NO dependa de scrapear FOMO: se puede construir de forma independiente calculando PnL/ROI/win-rate directamente de las transacciones on-chain de una wallet conocida — exactamente lo que dicen hacer FomoScan/fomoapi.io, pero se puede replicar de forma propia y 100% legítima sin ellos.
4. Decisión explícita del usuario sobre si acepta el riesgo de usar un proveedor de terceros no oficial para la fase de "descubrimiento de traders" (handle → wallet), o si prefiere una fuente 100% propia (p. ej. traders que voluntariamente comparten su wallet en redes sociales).

### 10.5 Qué se necesitará luego para **ejecución/copy-trading real**
- Elegir un exchange/venue con **API oficial de trading** (p. ej. Binance, OKX, Coinbase, o un DEX aggregator como Jupiter en Solana con una wallet propia del usuario) — nunca la cuenta de FOMO.
- Credenciales de API del usuario (API key/secret o wallet privada) gestionadas de forma segura — **fuera de alcance de esta fase**, y solo debe implementarse con consentimiento informado explícito del usuario final, límites de riesgo (tamaño máx. por operación, stop-loss, allowlist de tokens), y logging/auditoría.
- Un motor de réplica que traduzca "trader X abrió posición en token Y por Z" (detectado on-chain) en una orden equivalente en el venue elegido, con lógica de escalado de tamaño, slippage, y control de duplicados/latencia.
- Cumplimiento regulatorio propio del usuario/jurisdicción respecto a asesoría financiera automatizada / copy trading (fuera del alcance técnico de este informe).

---

## 11. Prototipo entregado

Ver `research/fomo-monitor/prototype/`. Es un monitor **local, de solo lectura**, que:
- Se conecta **únicamente** a RPC público de Solana (`api.mainnet-beta.solana.com`, endpoint oficial de la Fundación Solana, documentado en `solana.com`, sin autenticación) — **no toca fomo.family ni ningún servicio de terceros no verificado**.
- Suscribe (`logsSubscribe` sobre WebSocket JSON-RPC estándar de Solana) a una o más direcciones de wallet que el usuario le indique por configuración (no incluidas por defecto, no se asume ninguna wallet de ningún trader real).
- Imprime en consola cada transacción nueva detectada para esas wallets (firma, slot, éxito/fallo, logs del programa), sin ejecutar ninguna operación ni firmar nada.
- **No pude ejecutarlo en vivo dentro de este sandbox** (sin salida de red a `api.mainnet-beta.solana.com`). Está escrito para correr en un entorno con acceso normal a Internet; el README del prototipo explica cómo probarlo y qué esperar.

Este prototipo es intencionalmente genérico (monitoreo on-chain de una wallet dada) porque es la única pieza de la cadena de valor que pude **fundamentar con una fuente pública, oficial y estable** (la propia documentación de Solana), sin inventar ni asumir ningún endpoint de FOMO.

---

# PARTE II — FASE 2: de "transacción detectada" a "operación interpretada"

**Fecha:** 2026-09-11 (misma sesión, continuación de la Fase 1)
**Alcance:** igual que la Fase 1 — solo lectura, sin ejecutar operaciones, sin conectar wallets privadas, sin claves privadas, sin tocar FOMO, sin scraping, sin evadir protecciones. Todo lo nuevo se conecta **únicamente** al mismo RPC público oficial de Solana ya usado en la Fase 1.

## 12. Qué hace falta para interpretar correctamente una transacción de Solana

Antes de escribir código se investigó (vía búsqueda web, citando fuente oficial en cada caso) el esquema exacto de `getTransaction` y por qué **no se puede** decodificar una operación de swap leyendo directamente la instrucción:

- `getTransaction` con `encoding=jsonParsed` solo decodifica ("parsea") instrucciones de programas **nativos/conocidos por el nodo RPC** (System Program, SPL Token, Associated Token Account, ComputeBudget, etc.). Para programas custom como Jupiter, Raydium u Orca, la instrucción vuelve en forma **"partially decoded"**: `{accounts, data (base58 sin decodificar), programId}` — sin campos como `amountIn`/`amountOut`. Confirmado en [`solana.com/docs/rpc/json-structures`](https://solana.com/docs/rpc/json-structures) y en el issue público [`solana-labs/solana#31701`](https://github.com/solana-labs/solana/issues/31701).
- Por eso la única forma **agnóstica al protocolo** de saber qué entró y qué salió de una wallet es comparar `meta.preTokenBalances`/`meta.postTokenBalances` (tokens SPL, con `accountIndex`, `mint`, `owner`, `uiTokenAmount`) y `meta.preBalances`/`meta.postBalances` (SOL, en lamports) — documentado en [`solana.com/docs/rpc/http/gettransaction`](https://solana.com/docs/rpc/http/gettransaction). Es exactamente el enfoque que pidió el encargo ("compara los balances antes y después... determine qué activo salió y cuál entró"), y es también, según lo que indexan sus propias páginas, el mismo enfoque que usan los terceros mencionados en la Fase 1 (`fomoapi.io`, FomoScan): leer blockchain, no decodificar instrucciones de cada DEX.
- El `programId` de las instrucciones (de nivel superior y de `meta.innerInstructions`, cuando el swap real ocurre vía CPI dentro de un agregador) **sí** sirve para identificar el protocolo/DEX usado — pero solo para eso, nunca para inferir montos.
- Las transacciones **versionadas** (v0, con Address Lookup Tables) pueden referenciar cuentas que no están en `accountKeys` y que hay que resolver con `meta.loadedAddresses.writable`/`.readonly` — documentado en la misma página de RPC JSON Structures, y se requiere `maxSupportedTransactionVersion: 0` en la llamada o el nodo rechaza la respuesta. Esto es relevante porque **Jupiter usa ALT con frecuencia** en producción.

Todos los IDs de programa y de mint usados en el código (`KNOWN_PROGRAMS`, `QUOTE_ASSETS`, `INFRA_PROGRAMS`) están citados individualmente junto a su constante en `prototype/transaction_parser.py`, con la fuente donde se confirmaron (Solscan, Solana Explorer, docs.raydium.io, docs.orca.so, github.com/pump-fun/pump-public-docs, etc.). **No se verificaron por consulta RPC directa** en este sandbox (misma limitación de red que la Fase 1) — deben revalidarse contra un explorador antes de confiar en ellos en producción.

## 13. Diseño implementado (`prototype/transaction_parser.py`)

- **Estructura normalizada `TradeEvent`**: exactamente los 12 campos pedidos (`wallet`, `signature`, `timestamp`, `action`, `token_in`, `token_in_amount`, `token_out`, `token_out_amount`, `estimated_price`, `estimated_usd_value`, `protocol`, `confidence`) más algunos campos adicionales claramente marcados como extensión (`token_in_symbol`/`token_out_symbol`, `price_unit` — en qué unidad está expresado `estimated_price`, crítico porque no siempre es USD —, `notes` con la explicación legible de la clasificación, y `programs_seen` con los program IDs detectados).
- **Comparación de balances, no de instrucciones**: `_token_deltas_for_owner` reconstruye cuánto ganó/perdió la wallet de cada mint SPL sumando todas sus cuentas de token; `_sol_delta_lamports` hace lo mismo para SOL nativo, **restando el efecto de la fee de red** cuando la wallet es quien paga (invariante documentada: el fee payer es siempre `accountKeys[0]`).
- **Filtro de "ruido de rent"**: abrir una Associated Token Account nueva cuesta un rent-exempt mínimo (típicamente ~0.002 SOL) que aparece como una salida de SOL sin ser parte real del precio del swap. Se implementó como heurística explícita (`RENT_NOISE_LAMPORTS_THRESHOLD`, documentada como heurística ajustable, no como constante de protocolo) que solo descarta la pata de SOL cuando es pequeña **y** ya hay otra pata de token que explica la operación.
- **Clasificación BUY/SELL/SWAP/UNKNOWN** basada en cuántos activos cambiaron netamente:
  - Exactamente 1 salida + 1 entrada, y una de las dos es un "quote asset" (SOL/USDC/USDT) y la otra no → **BUY** (si lo gastado es el quote) o **SELL** (si lo gastado es el no-quote).
  - Exactamente 1 salida + 1 entrada, pero ambas son quote assets (ej. SOL↔USDC) o ninguna lo es (ej. tokenA↔tokenB) → **SWAP** (no se fuerza un BUY/SELL arbitrario).
  - Solo 1 activo cambió (0 salidas+1 entrada o viceversa) → **UNKNOWN**: parece transferencia simple, no swap.
  - Más de 2 activos cambiaron netamente (rutas multi-hop con residuales) → **UNKNOWN**: no se adivina cuál par es "la operación principal".
  - `meta.err != null` (transacción revertida on-chain) → **UNKNOWN**, confidence 0.0.
  - Ningún cambio relevante → **UNKNOWN**, confidence 0.0.
- **Detección de protocolo**: se recolectan todos los `programId` (nivel superior + `innerInstructions`, resolviendo tanto `programId` ya resuelto como `programIdIndex` numérico — ambas formas están documentadas y ambas aparecen en la práctica) excluyendo programas de infraestructura (System, Token, ATA, ComputeBudget), y se hace match contra un registro (`KNOWN_PROGRAMS`) que cubre Jupiter v6, Raydium (AMM v4, CLMM, CPMM), Orca Whirlpool, Pump.fun (bonding curve + PumpSwap) y Meteora DLMM, priorizando el agregador (Jupiter) sobre el AMM interno cuando aparecen ambos.
- **`confidence`**: arranca en 0.95 (BUY/SELL limpio) u 0.80 (SWAP limpio), y se penaliza -0.30 si no se reconoció ningún programa de la lista (la clasificación sigue siendo válida por balances, pero no se pudo confirmar el venue) y -0.05 si hubo que descartar una pata de SOL ambigua por la heurística de rent. Los casos UNKNOWN llevan confidence 0.0–0.25 según el motivo (ver `notes` de cada evento).
- **Precio y USD**: `estimated_price` se expresa siempre "por unidad del token no-quote", en la unidad indicada por `price_unit` (USDC, USDT, SOL, o un ratio tokenA/tokenB) — **no es automáticamente USD**. `estimated_usd_value` solo se calcula cuando una de las dos patas es un stablecoin (aproximación ~1:1, ignora depeg) o cuando el llamador provee explícitamente un `sol_usd_price` externo; si no, queda en `None` en vez de inventarse. Este es el límite real de este módulo — ver punto 16.

## 14. Tests con "transacciones históricas reales" — y por qué no lo son del todo

El encargo pidió usar transacciones reales cuando fuera posible. **No fue posible descargar ninguna transacción real** en este sandbox por la misma razón que en la Fase 1: no hay salida de red hacia `api.mainnet-beta.solana.com` (verificado de nuevo: mismo bloqueo `403` del proxy de egress). En su lugar, `tests/fixtures/` contiene 7 transacciones **sintéticas construidas a mano siguiendo el esquema oficial documentado** (citado arriba), cubriendo: BUY limpio vía Jupiter→Raydium, SELL limpio directo en Raydium, SWAP token-a-token en Orca, transacción fallida, transferencia simple (no-swap), ruta multi-hop ambigua, y compra en bonding curve de Pump.fun. `tests/fixtures/README.md` explica esto con total transparencia, cita las fuentes de cada dirección de programa/mint usada, e incluye instrucciones exactas (`curl` a `getTransaction`) para que, en un entorno con red normal, se reemplacen por transacciones reales y se valide el parser contra ellas — señalando explícitamente el punto más frágil (el orden de resolución de cuentas en transacciones versionadas con Address Lookup Tables) como lo primero a verificar con una transacción real de Jupiter.

Los 24 tests (`tests/test_transaction_parser.py`, `python -m unittest discover -s tests -v`) corren 100% offline contra esos fixtures y pasan.

## 15. Respuestas directas a lo que se preguntó al final del encargo

### 1. ¿Qué tan confiable es detectar BUY/SELL?

**Muy confiable quirúrgicamente, cuando la operación es "de dos patas" (un activo sale, otro entra) y el programa involucrado está en el registro conocido**: la comparación de balances no puede mentir sobre qué mint entró y cuál salió (a diferencia de intentar decodificar instrucciones), así que ese núcleo es sólido. Con esas condiciones, `confidence` ≈ 0.95. Baja a ≈ 0.65 si el swap es limpio pero el programa no está en `KNOWN_PROGRAMS` (sigue siendo BUY/SELL correcto, solo no se puede nombrar el venue). Se degrada intencionalmente a UNKNOWN (no a un BUY/SELL adivinado) en: transacciones fallidas, transferencias de una sola pata, y rutas con más de dos activos netos — ahí la confiabilidad real es "no lo sé", y el módulo lo dice en vez de fingir certeza.

### 2. ¿Qué DEX/protocolos podemos identificar?

Con las fuentes citadas: **Jupiter Aggregator v6** (dos deployments), **Raydium** (AMM v4, CLMM, CPMM), **Orca Whirlpool**, **Pump.fun** (bonding curve y PumpSwap post-graduación) y **Meteora DLMM**. Cualquier otro programa (Phoenix, Lifinity, Meteora DBC, pools nuevos, versiones futuras) simplemente no se nombra — la operación se sigue clasificando bien por balances, pero `protocol=None` y `confidence` baja.

### 3. ¿Qué casos todavía no podemos interpretar?

- Rutas multi-hop con residuales (3+ activos netos) — por diseño, no se adivina cuál es "la operación principal".
- Transferencias simples, airdrops, o pagos que no son swaps (una sola pata) — correctamente NO se marcan como BUY/SELL.
- Transacciones versionadas con Address Lookup Tables — la lógica de resolución de cuentas está implementada según la convención documentada, pero **no verificada contra una transacción real** (ver limitación de red); es el punto más frágil.
- Programas de DEX no incluidos en `KNOWN_PROGRAMS` (el registro es una lista fija, no se actualiza sola).
- Swaps "parciales" donde la wallet observada no es la firmante (ej. una PDA/vault de un vault de yield) — el parser busca la wallet en `accountKeys`, pero no sigue relaciones indirectas de custodia.
- Cualquier cosa que dependa del *contenido* de la instrucción (por ejemplo, distinguir un swap "normal" de un arbitraje interno o de una liquidación) — eso requeriría el IDL específico de cada programa, deliberadamente fuera de alcance porque no es necesario para BUY/SELL/SWAP/UNKNOWN.

### 4. ¿Qué información falta para calcular correctamente el precio?

Dos cosas concretas:
- **Un oráculo de precio SOL/USD** (y, en general, de cualquier token que no sea stablecoin) para las operaciones cuya contrapartida es SOL nativo — hoy `estimated_usd_value` se deja en `None` salvo que el llamador provea `sol_usd_price` manualmente. El módulo ya tiene el punto de extensión (`sol_usd_price` como parámetro, documentado como "plug-in" para una fase futura) pero **no** consulta ningún proveedor externo por sí mismo — eso sería añadir una dependencia/fuente de datos nueva que no estaba en el alcance de esta fase.
- **Precios de tokens no-quote** cuando el swap es token-a-token puro (ej. Orca `TokenA↔TokenB`): sin un oráculo externo (Pyth, Birdeye, CoinGecko, o el propio libro de pools on-chain) no hay forma de expresar esa operación en USD, solo el ratio entre los dos tokens (`price_unit` lo deja explícito).

### 5. ¿Qué necesitaríamos para monitorear 100, 500 o 1.000 wallets simultáneamente?

El diseño actual (una suscripción `logsSubscribe` por wallet sobre una única conexión WebSocket, más una llamada `getTransaction` por firma detectada) **no escala** a esos volúmenes contra el RPC público gratuito de Solana:
- `api.mainnet-beta.solana.com` tiene rate limits no pensados para esto (compartido con toda la red pública) y puede cerrar/limitar conexiones con muchas suscripciones simultáneas.
- Con 500-1000 wallets activas, el volumen de `getTransaction` (una por cada firma detectada, y las wallets activas de FOMO operan frecuentemente) puede fácilmente superar cualquier límite gratuito.
- Necesitaríamos: (a) un **proveedor de RPC dedicado** con plan pago (Helius, QuickNode, Triton, etc.) con mayor rate limit y, preferiblemente, **gRPC/Geyser streaming** en vez de WebSocket JSON-RPC clásico (mucho más eficiente para volumen alto); (b) **batching** de `getTransaction` (`getTransactions` en lote donde el proveedor lo soporte, o pipelining de llamadas); (c) una **cola de procesamiento** (ej. un worker pool) para separar "recibir firma" de "interpretar transacción", con reintentos y backoff; (d) opcionalmente, en vez de seguir una lista de wallets tipo `logsSubscribe`, suscribirse a nivel de **programa** (ej. todas las transacciones de Jupiter/Raydium/Orca) y filtrar por la lista de wallets de interés en el propio proceso — esto es lo que hacen en la práctica indexadores como los que vimos en la Fase 1 (`fomoapi.io`, Solana Tracker), y es la única forma realista de llegar a cientos/miles de wallets sin miles de suscripciones individuales; (e) una base de datos para persistir el estado (última firma procesada por wallet, deduplicación, histórico) — hoy todo vive solo en memoria del proceso.

### 6. ¿Qué debería ser la FASE 3 del proyecto?

Con lo construido en Fases 1 y 2, una Fase 3 razonable (siempre en modo de solo lectura, sin tocar FOMO ni ejecutar nada) sería:
1. **Escalar el monitoreo** siguiendo el punto 5: proveedor RPC dedicado, suscripción a nivel de programa + filtro propio, cola de procesamiento, persistencia.
2. **Cerrar el círculo de identificación de traders**: integrar (bajo criterio y riesgo propio del usuario, con due diligence de sus Términos) una fuente de mapeo *handle de FOMO → wallet* (de las descritas en la Fase 1), para poder alimentar la lista de wallets a monitorear con "traders de FOMO reales" en vez de direcciones puestas a mano.
3. **Integrar un oráculo de precio** (Pyth, Birdeye, o similar) para completar `estimated_usd_value` en los casos hoy `None` — esto es un consumo de datos públicos adicional, no toca FOMO.
4. **Persistencia y analítica histórica**: guardar los `TradeEvent` generados (base de datos), y sobre eso sí poder calcular métricas propias (PnL realizado, win rate, volumen) de cada wallet observada, de forma 100% independiente e igual de verificable que la de los terceros vistos en la Fase 1 — sin depender de ellos.
5. **Alertas reales** (no solo consola): Telegram/Discord/email cuando una wallet seguida genera un evento BUY/SELL con confidence alta.
6. Seguir **sin** avanzar hacia ejecución/copy-trading automático hasta que el usuario decida explícitamente abrir esa fase — y, cuando la abra, hacerlo contra una API oficial de un exchange/DEX elegido por el usuario con sus propias credenciales, nunca contra la cuenta de FOMO (ver Fase 1, sección 10.5).
