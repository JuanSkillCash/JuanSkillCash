# Graph Report - JuanSkillCash  (2026-09-09)

## Corpus Check
- 5 files · ~148,090 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 159 nodes · 166 edges · 26 communities (11 shown, 8 thin omitted)
- Extraction: 93% EXTRACTED · 6% INFERRED · 1% AMBIGUOUS · INFERRED: 10 edges (avg confidence: 0.8)
- Token cost: 233,715 input · 0 output

## Community Hubs (Navigation)
- Crypto Analysis Tools & Dashboards
- Trading Calculators (Fees, Breakeven, Financial Freedom)
- Mentoría Curriculum & Partner Tiers
- Modal Close Handlers
- Landing Pages & Partner Program Overview
- Price Data APIs
- Risk Profile Quiz
- Bitcoin Halving Charts
- Portfolio Simulator
- Supabase Authentication
- Wallet Comparison Tool
- Crypto Glossary
- Fear & Greed Index
- Common Mistakes Library
- Unit Converter
- Digital Inheritance Planner
- Favorites Persistence
- Timezone Clock Tool
- Brand Logo Assets

## God Nodes (most connected - your core abstractions)
1. `SkillCash Tools App` - 36 edges
2. `openModalGeneric()` - 13 edges
3. `closeModalGeneric()` - 12 edges
4. `Mentoría SkillCash (sistema estructurado de aprendizaje cripto)` - 11 edges
5. `SkillCash Mentoría Landing Page` - 7 edges
6. `SkillCash Partners Program Page` - 6 edges
7. `Programa Oficial SkillCash Partners (afiliados)` - 5 edges
8. `Hotmart (plataforma de pagos/afiliados)` - 4 edges
9. `renderPortfolioItems()` - 4 edges
10. `Plan Básico - Tutoriales ($47)` - 3 edges

## Surprising Connections (you probably didn't know these)
- `SkillCash Mentoría Landing Page` --semantically_similar_to--> `SkillCash Partners Program Page`  [INFERRED] [semantically similar]
  index.html → skillcash-partners.html
- `Categoría 'Partners' del sidebar (vitrinas de exchanges asociados)` --conceptually_related_to--> `SkillCash Partners Program Page`  [AMBIGUOUS]
  skillcash-herramientas.html → skillcash-partners.html
- `Plan Básico - Tutoriales ($47)` --semantically_similar_to--> `Nivel Partner (60% comisión, 0 ventas)`  [INFERRED] [semantically similar]
  index.html → skillcash-partners.html
- `Plan Premium - Tutoriales + Acompañamiento 1 a 1 ($127)` --semantically_similar_to--> `Nivel Partner Elite (75% comisión, 60 ventas)`  [INFERRED] [semantically similar]
  index.html → skillcash-partners.html
- `FAQ de la mentoría (no es señales de trading, sin experiencia previa requerida)` --semantically_similar_to--> `FAQ del programa de Partners (gratis, pagos vía Hotmart, sin experiencia requerida)`  [INFERRED] [semantically similar]
  index.html → skillcash-partners.html

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Patrón repetido de persistencia en localStorage (favoritos, checklist, herencia, aprobaciones, glosario, notificaciones)** — skillcash_herramientas_loadfavorites, skillcash_herramientas_loadcheckliststate, skillcash_herramientas_loadinheritancestate, skillcash_herramientas_loadapprovalsstate, skillcash_herramientas_loadglossfavs, skillcash_herramientas_isbellenabled [INFERRED 0.85]
- **Patrón compartido de apertura/cierre de modales para cada calculadora/herramienta** — skillcash_herramientas_openmodalgeneric, skillcash_herramientas_closemodalgeneric, skillcash_herramientas_openbreakevenmodal, skillcash_herramientas_opencoinmmodal, skillcash_herramientas_openfeesmodal, skillcash_herramientas_openquizmodal, skillcash_herramientas_openwalletcomparemodal, skillcash_herramientas_openfifreedommodal, skillcash_herramientas_openportfoliomodal [EXTRACTED 1.00]
- **Sistema de diseño compartido SkillCash (tokens CSS, tipografías, WhatsApp float, footer) entre index.html y skillcash-partners.html** — index_page, skillcash_partners_page, whatsapp_support_widget [INFERRED 0.85]

## Communities (26 total, 8 thin omitted)

### Community 0 - "Crypto Analysis Tools & Dashboards"
Cohesion: 0.06
Nodes (25): Hyperliquid API (funding rates), Bitcoin en Balances Corporativos, Beacons.ai/skillcash (todas las redes), calc() - trading calculator, Calculadora de Rentabilidad, Calculadora de Trading, Checklist de Seguridad, Coinbase Premium (+17 more)

### Community 1 - "Trading Calculators (Fees, Breakeven, Financial Freedom)"
Cohesion: 0.10
Nodes (16): Calculadora de Break-even, Calculadora Coin-M, Calculadora de Comisiones, Calculadora de Porcentajes, computeAllPct(), computeBreakeven(), computeCoinm(), computeFees() (+8 more)

### Community 2 - "Mentoría Curriculum & Partner Tiers"
Cohesion: 0.15
Nodes (17): Hotmart (plataforma de pagos/afiliados), Mentoría SkillCash (sistema estructurado de aprendizaje cripto), Módulo 00: Bienvenida y hoja de ruta, Módulo 01: Fundamentos - tu primer Exchange, Módulo 02: Aprende a leer el mercado, Módulo 03: Wallets no custodiales, Módulo 04: Modelos de generación de ingresos, Módulo 05: Construye tu portafolio (+9 more)

### Community 4 - "Landing Pages & Partner Program Overview"
Cohesion: 0.24
Nodes (11): Hotmart Affiliate Recruiting (aplicación de Partners), FAQ de la mentoría (no es señales de trading, sin experiencia previa requerida), SkillCash Mentoría Landing Page, Testimonios de alumnos (Felipe, Mario Munar, Lucho Romel) via Telegram, Bitunix Exchange - promo afiliado (vipCode SKLL20), Enlace 'Quiero entrar a la mentoría' -> juanskillcash.github.io/JuanSkillCash/, Categoría 'Partners' del sidebar (vitrinas de exchanges asociados), FAQ del programa de Partners (gratis, pagos vía Hotmart, sin experiencia requerida) (+3 more)

### Community 5 - "Price Data APIs"
Cohesion: 0.29
Nodes (7): CoinGecko API (COINGECKO_API_KEY), CryptoCompare API (CRYPTOCOMPARE_API_KEY), TwelveData API (TWELVE_DATA_API_KEY), ccUrl() - CryptoCompare URL builder, cgUrl() - CoinGecko URL builder, Claves de API de terceros (CoinGecko/TwelveData/CryptoCompare) embebidas en JS del cliente, tdUrl() - TwelveData URL builder

### Community 6 - "Risk Profile Quiz"
Cohesion: 0.33
Nodes (5): openQuizModal(), Perfil de Riesgo (quiz), renderQuizQuestion(), resetQuiz(), showQuizResult()

### Community 7 - "Bitcoin Halving Charts"
Cohesion: 0.40
Nodes (5): Binance API (klines BTCUSDT), Blockchain.info API (market-price / charts), Ciclos de Halving de Bitcoin, renderHalvingAllTimeChart(), renderHalvingChart()

### Community 8 - "Portfolio Simulator"
Cohesion: 0.50
Nodes (4): openPortfolioModal(), renderPieChart(), renderPortfolioItems(), Simulador de Portafolio

### Community 9 - "Supabase Authentication"
Cohesion: 0.67
Nodes (4): Supabase (auth backend, nbvgyouzjscwtfukzxok.supabase.co), renderAuthState(), sbClient (Supabase client instance), setAuthMode()

### Community 10 - "Wallet Comparison Tool"
Cohesion: 0.50
Nodes (3): Comparador de Wallets, computeWalletCompare(), openWalletCompareModal()

### Community 12 - "Fear & Greed Index"
Cohesion: 0.67
Nodes (3): Alternative.me Fear & Greed API, Índice de Miedo y Codicia (Fear & Greed), renderFngChart()

## Ambiguous Edges - Review These
- `SkillCash Partners Program Page` → `Categoría 'Partners' del sidebar (vitrinas de exchanges asociados)`  [AMBIGUOUS]
  skillcash-herramientas.html · relation: conceptually_related_to

## Knowledge Gaps
- **30 isolated node(s):** `Módulo 00: Bienvenida y hoja de ruta`, `Módulo 01: Fundamentos - tu primer Exchange`, `Módulo 02: Aprende a leer el mercado`, `Módulo 03: Wallets no custodiales`, `Módulo 04: Modelos de generación de ingresos` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 76 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `SkillCash Partners Program Page` and `Categoría 'Partners' del sidebar (vitrinas de exchanges asociados)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `SkillCash Tools App` connect `Crypto Analysis Tools & Dashboards` to `Trading Calculators (Fees, Breakeven, Financial Freedom)`, `Landing Pages & Partner Program Overview`, `Risk Profile Quiz`, `Bitcoin Halving Charts`, `Portfolio Simulator`, `Wallet Comparison Tool`, `Crypto Glossary`, `Fear & Greed Index`, `Common Mistakes Library`, `Unit Converter`, `Digital Inheritance Planner`, `Timezone Clock Tool`?**
  _High betweenness centrality (0.499) - this node is a cross-community bridge._
- **Why does `SkillCash Mentoría Landing Page` connect `Landing Pages & Partner Program Overview` to `Mentoría Curriculum & Partner Tiers`?**
  _High betweenness centrality (0.165) - this node is a cross-community bridge._
- **Why does `Enlace 'Quiero entrar a la mentoría' -> juanskillcash.github.io/JuanSkillCash/` connect `Landing Pages & Partner Program Overview` to `Crypto Analysis Tools & Dashboards`?**
  _High betweenness centrality (0.161) - this node is a cross-community bridge._
- **What connects `Módulo 00: Bienvenida y hoja de ruta`, `Módulo 01: Fundamentos - tu primer Exchange`, `Módulo 02: Aprende a leer el mercado` to the rest of the system?**
  _30 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Crypto Analysis Tools & Dashboards` be split into smaller, more focused modules?**
  _Cohesion score 0.0625 - nodes in this community are weakly interconnected._
- **Should `Trading Calculators (Fees, Breakeven, Financial Freedom)` be split into smaller, more focused modules?**
  _Cohesion score 0.09523809523809523 - nodes in this community are weakly interconnected._