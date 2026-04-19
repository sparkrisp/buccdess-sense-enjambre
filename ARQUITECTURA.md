# Arquitectura — Buccdess Sense · Enjambre

Diseño técnico del fork de MiroFish con extensión electoral argentina (cohorte
CABA 2023). Documenta componentes, flujos de datos, endpoints, modelo
probabilístico y decisiones arquitectónicas.

**Companion docs:**
- [`README.md`](./README.md) — landing del proyecto, quickstart.
- [`research/fase0/DOCUMENTACION.md`](./research/fase0/DOCUMENTACION.md) —
  documentación extensa del módulo caba_cohort: fases 0/1/2/B/C, sampler,
  ecological inference, pros/contras, limitaciones.

---

## Tabla de contenidos

1. [Visión general de sistemas](#1-visión-general-de-sistemas)
2. [Diagrama de componentes](#2-diagrama-de-componentes)
3. [Flujos de datos principales](#3-flujos-de-datos-principales)
4. [Backend — estructura de código](#4-backend--estructura-de-código)
5. [Frontend — estructura de código](#5-frontend--estructura-de-código)
6. [Contratos API](#6-contratos-api)
7. [Modelo de datos (archivos)](#7-modelo-de-datos-archivos)
8. [Modelo probabilístico del sampler](#8-modelo-probabilístico-del-sampler)
9. [Integraciones externas](#9-integraciones-externas)
10. [Decisiones arquitectónicas clave (ADRs)](#10-decisiones-arquitectónicas-clave-adrs)
11. [Seguridad y secrets](#11-seguridad-y-secrets)
12. [Deploy y operación](#12-deploy-y-operación)
13. [Puntos de extensión](#13-puntos-de-extensión)

---

## 1. Visión general de sistemas

Buccdess Sense es una extensión de **MiroFish** (motor de simulación
multi-agente basado en OASIS / CAMEL-AI) que agrega un flujo alternativo
para disparar simulaciones con **cohortes sintéticas** cuya distribución
demográfica y preferencia electoral coincide con la del electorado porteño
real (Censo INDEC 2022 + DINE Generales 2023).

### Dos flujos coexisten en el mismo backend

```
                         ┌─────────────────────────────────┐
                         │       Frontend (Vue 3)          │
                         └─────────────────────────────────┘
                          │                               │
          ┌───────────────▼──────────┐    ┌───────────────▼──────────┐
          │   Flujo MiroFish clásico │    │   Flujo Buccdess cohort  │
          │   (Zep + documento)      │    │   (Censo + DINE + LLM)   │
          └──────────────────────────┘    └──────────────────────────┘
                          │                               │
                          └──────────────┬────────────────┘
                                         │
                         ┌───────────────▼───────────────┐
                         │     Backend (Flask + uv)      │
                         │     OASIS simulación          │
                         │     Persistencia en disco     │
                         └───────────────────────────────┘
```

- **Clásico**: sube un documento → LLM extrae ontología → GraphRAG en Zep →
  perfiles generados → config LLM → OASIS corre → report + interacción.
- **Cohort**: pega un artículo → sampler genera N perfiles sintéticos
  con distribución real → OASIS corre → chat directo con cada agente +
  (opcional) ontología LLM/Zep del artículo.

Ambos comparten la misma máquina OASIS, misma persistencia y mismos
endpoints de status/posts/actions.

---

## 2. Diagrama de componentes

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Vue 3 + Vite)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Home.vue   CohortSetup.vue  CohortResult.vue  CohortRun.vue        │
│     │              │                │                   │           │
│     └──────────────┴────────────────┴───────────────────┘           │
│                              │                                      │
│                ┌─────────────▼──────────────┐                       │
│                │   api/simulation.js        │                       │
│                │   (axios, baseURL :5001)   │                       │
│                └─────────────┬──────────────┘                       │
│                              │                                      │
│   Components: OntologyPanel  CohortHistoryList  HistoryDatabase     │
│               (d3.js)        (axios)            (axios)             │
│                                                                     │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
                         HTTP JSON (CORS)
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                    BACKEND (Flask 3 + Python 3.11 + uv)             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  app/api/simulation.py  (blueprint)                                 │
│     │                                                               │
│     ├── /prepare-from-cohort  ─┐                                    │
│     ├── /cohort-history        │                                    │
│     ├── /cohort/<id>/ontology/ │                                    │
│     │   build (llm/zep)        │                                    │
│     ├── /cohort/<id>/chat      │                                    │
│     ├── /cohort/<id>  DELETE   │                                    │
│     │                          │                                    │
│     ├── /prepare               │                                    │
│     ├── /start, /stop          │                                    │
│     └── /run-status, /actions, │                                    │
│         /posts, /comments      │                                    │
│                                │                                    │
│  app/services/                 │                                    │
│  ├── simulation_manager.py  ◄──┘                                    │
│  ├── caba_cohort/                                                   │
│  │   ├── censo_parser.py    (xlsx INDEC)                            │
│  │   ├── electoral_parser.py (CSV DINE)                             │
│  │   ├── cohort_builder.py  (sample + EI)                           │
│  │   ├── ecological_inference.py (OLS)                              │
│  │   ├── source.py          (adapter OasisAgentProfile)             │
│  │   └── data/              (CSVs + xlsx locales)                   │
│  ├── article_ontology.py    (LLM structured output)                 │
│  ├── zep_article_graph.py   (Zep Cloud)                             │
│  ├── oasis_profile_generator.py (flujo Zep tradicional)             │
│  ├── simulation_runner.py   (OASIS subprocess manager)              │
│  └── simulation_config_generator.py                                 │
│                                                                     │
│  uploads/simulations/<sim_id>/                                      │
│  ├── state.json                                                     │
│  ├── cohort_meta.json        (flujo cohort solamente)               │
│  ├── reddit_profiles.json                                           │
│  ├── twitter_profiles.csv                                           │
│  ├── simulation_config.json                                         │
│  ├── article_ontology_llm.json   (cache)                            │
│  ├── article_ontology_zep.json   (cache)                            │
│  ├── reddit_simulation.db    (OASIS SQLite)                         │
│  └── twitter_simulation.db                                          │
│                                                                     │
└──────────┬──────────────────┬──────────────────┬────────────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
    ┌────────────┐    ┌──────────────┐    ┌────────────────┐
    │  Gemini    │    │  Zep Cloud   │    │  CAMEL-AI /    │
    │  2.5 Flash │    │  (opcional)  │    │  OASIS runtime │
    │  (OpenAI   │    │  GraphRAG    │    │  (subprocess)  │
    │  compat.)  │    │              │    │                │
    └────────────┘    └──────────────┘    └────────────────┘
```

---

## 3. Flujos de datos principales

### 3.1 Creación de cohorte

```
[Usuario en UI]
  │
  │ POST /api/simulation/prepare-from-cohort
  │ body: { simulation_requirement, cohort_config }
  │
  ▼
[SimulationManager.prepare_simulation(profile_source="caba_cohort_2023")]
  │
  ├─► compute_cohort_hash(req, cfg)
  │     find_cohort_by_hash ──► si existe: return already_exists=true
  │
  ├─► _prepare_from_caba_cohort()
  │     │
  │     ├─► CabaCohortSource.generate_profiles(CohortConfig)
  │     │     │
  │     │     └─► CohortBuilder.sample(n, comuna, edad_min, ...)
  │     │           ├─► Leer censo (pandas via openpyxl) → DataFrame tidy
  │     │           ├─► (Opt) Fit EcologicalModel OLS sobre 15 comunas
  │     │           ├─► Muestreo estratificado (celda, actividad, edu, voto)
  │     │           └─► Devuelve List[Perfil]
  │     │
  │     ├─► perfil_to_oasis(Perfil) × N → List[OasisAgentProfile]
  │     │     (genera name, username, bio, persona textual rioplatense)
  │     │
  │     ├─► _save_reddit_json + _save_twitter_csv
  │     │     → uploads/simulations/<sim_id>/reddit_profiles.json
  │     │
  │     ├─► Config default: SimulationParameters con AgentActivityConfig
  │     │   por perfil + EventConfig con initial_post = artículo
  │     │     → simulation_config.json
  │     │
  │     └─► Guardar cohort_meta.json (hash + filtros + fecha)
  │
  └─► Response { simulation_id, status: "ready", profiles_count, ... }
```

### 3.2 Chat con agente (sin OASIS corriendo)

```
[UI: modal con tab "Entrevista"]
  │ POST /api/simulation/cohort/<id>/chat
  │ body: { agent_id, message, history }
  │
  ▼
[cohort_agent_chat endpoint]
  │
  ├─► Leer reddit_profiles.json → encontrar agent_id
  ├─► Leer cohort_meta.json → obtener artículo asociado
  ├─► Armar system prompt:
  │     persona
  │     + "Respondé en primera persona, rioplatense, 1-3 oraciones"
  │     + artículo (opcional, 1500 chars)
  ├─► messages = [system, ...history, user_message]
  ├─► Gemini 2.5 Flash client.chat.completions.create()
  │     extra_body: { reasoning_effort: "none" }
  │
  └─► Response { reply, agent_name }
```

### 3.3 Grafo del artículo (LLM vs Zep)

```
[UI: OntologyPanel · toggle LLM / Zep]
  │ POST /api/simulation/cohort/<id>/ontology/build
  │ body: { source: "llm" | "zep", force: bool }
  │
  ▼
[build_cohort_ontology endpoint]
  │
  ├─► Resolver artículo (cohort_meta → fallback simulation_config)
  ├─► Si cache existe y !force → return cache
  │
  ├─► source=="llm":
  │     extract_ontology_from_article(article)
  │       → Gemini structured JSON output
  │       → { entities[20], relationships[25], themes[3-7] }
  │
  ├─► source=="zep":
  │     extract_ontology_via_zep(article)
  │       → Crear graph_id nuevo en Zep
  │       → Chunkear + upload (2000 chars, overlap 100)
  │       → Poll _wait_for_processing (timeout 120s)
  │       → Fetch nodes + edges
  │       → Normalizar al mismo formato que LLM
  │
  └─► Guardar article_ontology_<source>.json + return
```

### 3.4 Simulación OASIS (enjambre en vivo)

```
[UI: CohortResultView · "Correr simulación OASIS"]
  │ POST /api/simulation/start
  │
  ▼
[SimulationRunner.start]
  │
  ├─► Subprocess: python backend/scripts/run_parallel_simulation.py
  │     --config uploads/simulations/<id>/simulation_config.json
  │
  ├─► OASIS (camel-ai) levanta agentes paralelos
  │   Por cada ronda:
  │     Para N agentes activos:
  │       Gemini call con persona + feed del momento + initial_post
  │       → Acción: POST | LIKE | COMMENT | FOLLOW | DO_NOTHING
  │     Persistir en reddit_simulation.db + twitter_simulation.db
  │
  └─► UI hace polling cada 3s:
        GET /run-status  → progreso, actions_count, round actual
        GET /actions?limit=50 → últimas acciones
        GET /agent-stats → ranking de actividad
```

---

## 4. Backend — estructura de código

```
backend/
├── pyproject.toml            # uv deps: flask, openai, zep-cloud, camel-ai,
│                             #          openpyxl, numpy, pandas, pydantic
├── run.py                    # Entrypoint: valida config, arranca Flask
├── scripts/                  # OASIS run scripts (subprocess)
│   ├── run_parallel_simulation.py
│   ├── run_reddit_simulation.py
│   ├── run_twitter_simulation.py
│   └── action_logger.py
└── app/
    ├── __init__.py          # create_app: blueprints, CORS
    ├── config.py            # Config class (LLM, Zep, OASIS)
    ├── api/                 # Flask blueprints
    │   ├── graph.py         # /api/graph/* (Zep flow)
    │   ├── simulation.py    # /api/simulation/* (todos los endpoints)
    │   └── report.py        # /api/report/*
    ├── models/              # Task state, project state
    ├── utils/
    │   ├── logger.py
    │   ├── locale.py        # i18n server-side
    │   └── zep_paging.py
    └── services/
        ├── simulation_manager.py       # Orquesta flujos Zep + cohort
        ├── simulation_runner.py        # OASIS subprocess
        ├── simulation_config_generator.py  # LLM → SimulationParameters
        ├── oasis_profile_generator.py  # Flujo Zep
        ├── text_processor.py           # PDF/MD/TXT → chunks
        ├── graph_builder.py            # Zep GraphRAG
        ├── zep_entity_reader.py
        ├── ontology_generator.py
        ├── report_agent.py             # ReportAgent con 4 tools
        ├── article_ontology.py         # NEW — LLM structured output
        ├── zep_article_graph.py        # NEW — Zep para artículo
        └── caba_cohort/                # NEW — módulo cohort CABA
            ├── __init__.py
            ├── source.py               # CabaCohortSource + CohortConfig
            ├── censo_parser.py         # xlsx INDEC → DataFrame
            ├── electoral_parser.py     # CSV DINE → voto por comuna
            ├── cohort_builder.py       # sample() + EI switch
            ├── ecological_inference.py # Goodman OLS
            └── data/                   # CSV + xlsx empaquetados
                ├── generales_2023_caba.csv
                ├── c2022_caba_actividad_economica_c2_1.xlsx
                └── c2022_caba_educacion_c3_1.xlsx
```

### Composición del SimulationManager

Un solo objeto orquesta ambos flujos via dispatch por `profile_source`:

```python
def prepare_simulation(
    self, simulation_id, requirement, document_text,
    profile_source="zep",           # <── dispatch key
    cohort_config=None, ...
):
    if profile_source == "caba_cohort_2023":
        return self._prepare_from_caba_cohort(...)  # bypass Zep + config-gen-LLM
    # ... flujo Zep original intacto
```

Métodos nuevos agregados (mantienen la interfaz):
- `compute_cohort_hash(req, cfg) -> str` · staticmethod · SHA-256 deterministic
- `find_cohort_by_hash(hash) -> Optional[sim_id]` · dedup
- `list_cohort_simulations(limit) -> List[Dict]` · para historial
- `delete_simulation(sim_id) -> bool` · `shutil.rmtree`
- `_prepare_from_caba_cohort(state, req, cfg, cb)` · flujo paralelo

---

## 5. Frontend — estructura de código

```
frontend/
├── package.json             # Vue 3, vue-router, vue-i18n, axios, d3
├── vite.config.js           # proxy /api → localhost:5001
├── index.html               # lang=es, title Buccdess Sense
└── src/
    ├── main.js
    ├── App.vue
    ├── api/
    │   ├── index.js         # axios instance + interceptors
    │   ├── graph.js
    │   ├── simulation.js    # incluye prepareFromCohort, getCohortHistory,
    │   │                    # deleteCohortSimulation, buildCohortOntology,
    │   │                    # chatWithCohortAgent, etc.
    │   └── report.js
    ├── i18n/
    │   └── index.js         # loader dinámico de locales/*.json
    ├── router/
    │   └── index.js         # rutas: /, /cohort-setup, /cohort/:id,
    │                        #        /cohort/:id/run, /process/:projId,
    │                        #        /simulation/:id, /simulation/:id/start,
    │                        #        /report/:id, /interaction/:id
    ├── store/
    │   └── pendingUpload.js
    ├── views/               # páginas principales
    │   ├── Home.vue         # Landing · logo SVG enjambre · botón CABA
    │   ├── CohortSetupView.vue    # NEW Form cohort + historial
    │   ├── CohortResultView.vue   # NEW Stats + perfiles + chat + ontología
    │   ├── CohortRunView.vue      # NEW Enjambre OASIS en vivo
    │   ├── MainView.vue           # Step wizard Zep (con guard cohort→redirect)
    │   ├── Process.vue            # Legacy Zep flow
    │   ├── SimulationView.vue     # Legacy (con guard)
    │   ├── SimulationRunView.vue  # Legacy (con guard)
    │   ├── InteractionView.vue    # Chat via OASIS endpoint /interview
    │   └── ReportView.vue
    └── components/
        ├── GraphPanel.vue        # Grafo Zep
        ├── HistoryDatabase.vue   # Lista de sims del Home (con detect cohort)
        ├── LanguageSwitcher.vue
        ├── Step1GraphBuild.vue / Step2EnvSetup.vue / ...
        ├── CohortHistoryList.vue # NEW · ver/duplicar/borrar + dedup modal
        └── OntologyPanel.vue     # NEW · d3 force-directed + LLM/Zep toggle
```

### Guards de cohort

Para evitar que simulaciones cohort caigan en las vistas Zep originales
(que harían 404 contra `/api/graph/<project>`):

- `HistoryDatabase.isCohort(proj)` detecta por `entity_types`, `project_id`,
  `graph_id` → decide ruta al clickear una card.
- `MainView.initProject()` guard sincrónico: si `projectId` tiene prefix
  `caba-cohort-` redirige a `/cohort/<sim_id>` sin llamar a `/api/graph/`.
- `SimulationView.onMounted` + `SimulationRunView.loadSimulationData`:
  detectan entity_types y hacen `router.replace` al equivalente cohort.

---

## 6. Contratos API

### Endpoints nuevos (flujo cohort)

| Método | Path | Body/Query | Response |
|---|---|---|---|
| POST | `/api/simulation/prepare-from-cohort` | `{ simulation_requirement, cohort_config, force_new? }` | `{ simulation_id, status, profiles_count, already_exists, cohort_config }` |
| GET | `/api/simulation/cohort-history` | `?limit=50` | `{ items: [...], count }` |
| DELETE | `/api/simulation/cohort/<id>` | – | `{ deleted }` |
| POST | `/api/simulation/cohort/<id>/ontology/build` | `{ source: "llm"|"zep", force: bool }` | `{ entities, relationships, themes, stats, source }` |
| GET | `/api/simulation/cohort/<id>/ontology` | – | `{ llm: …, zep: … }` |
| POST | `/api/simulation/cohort/<id>/chat` | `{ agent_id, message, history? }` | `{ reply, agent_name }` |

### Endpoints reutilizados del core MiroFish

- `POST /api/simulation/create` — create simulation (requiere project)
- `POST /api/simulation/prepare` — flujo Zep tradicional
- `GET /api/simulation/<id>` — estado
- `GET /api/simulation/<id>/profiles` — perfiles
- `GET /api/simulation/<id>/config` — config OASIS
- `POST /api/simulation/start` — disparar OASIS
- `POST /api/simulation/stop` — parar
- `GET /api/simulation/<id>/run-status` — progreso en vivo
- `GET /api/simulation/<id>/actions` — feed acciones
- `GET /api/simulation/<id>/posts` — feed posts
- `GET /api/simulation/<id>/agent-stats` — ranking actividad
- `POST /api/simulation/interview` — chat vía OASIS (requiere env alive)

### Conventions

- Todas responden `{ success: bool, data: any, error?: string }`
- Interceptor Axios devuelve `response.data` directo (NO el objeto Axios)
- Errores 4xx/5xx rechazan la Promise con `new Error(error)`

---

## 7. Modelo de datos (archivos)

### 7.1 `state.json` (generado por SimulationManager)

```json
{
  "simulation_id": "sim_abc123",
  "project_id": "caba-cohort-20260419-141039",
  "graph_id": "caba-cohort-no-zep",
  "status": "ready|preparing|running|completed|failed",
  "entities_count": 15,
  "profiles_count": 15,
  "entity_types": ["caba_electoral_cohort_2023"],
  "config_generated": true,
  "created_at": "2026-04-19T14:10:39",
  "updated_at": "2026-04-19T14:10:45"
}
```

### 7.2 `cohort_meta.json` (nuevo, específico de cohort)

```json
{
  "source": "caba_electoral_cohort_2023",
  "cohort_hash": "82074ff353f29da1",
  "simulation_requirement": "El Gobierno anuncia ...",
  "cohort_config": {
    "n": 15,
    "comuna": [4, 8, 9],
    "edad_min": 18,
    "seed": 2026,
    "use_ecological_inference": true
  },
  "created_at": "2026-04-19T14:10:39",
  "profiles_count": 15
}
```

El `cohort_hash` es SHA-256 de `(requirement_normalizado, cohort_config_ordenado)`
truncado a 16 chars. Permite dedup sin falsos positivos.

### 7.3 `reddit_profiles.json` (formato OASIS)

Array de objetos con: `user_id, username, name, bio, persona, karma,
age, gender, mbti, country, profession, interested_topics`.

### 7.4 `simulation_config.json`

Dataclass `SimulationParameters`: time_config, agent_configs (N),
event_config (initial_posts con el artículo), twitter_config, reddit_config,
llm_model, llm_base_url, generation_reasoning.

### 7.5 `article_ontology_<source>.json`

```json
{
  "source": "llm|zep",
  "model": "gemini-2.5-flash",  // o zep_graph_id
  "entities": [
    {"id": "e1", "name": "Milei", "type": "persona", "role": "presidente"}
  ],
  "relationships": [
    {"from": "e1", "to": "e2", "label": "reporta a"}
  ],
  "themes": ["ajuste agotado", ...],
  "stats": {"entity_count": 14, "relationship_count": 12, "theme_count": 5}
}
```

---

## 8. Modelo probabilístico del sampler

Ver detalle en [`research/fase0/DOCUMENTACION.md`](research/fase0/DOCUMENTACION.md)
§5 (Sampler) y §8 (Ecological Inference).

### 8.1 Sin EI (baseline)

Asume independencia condicional dado (comuna, sexo, edad):

```
P(agente) = P(celda) · P(actividad|celda) · P(educación|celda) · P(voto|comuna)
```

Donde:
- `P(celda)` ∝ `poblacion_14plus` observada
- `P(actividad|celda)` y `P(educación|celda)` → marginales del Censo 2022
- `P(voto|comuna)` → % real de votos positivos 2023 (cargo JEF, solo nativos)

### 8.2 Con EI (Goodman ecological regression)

Mismo flujo hasta celda, actividad, educación. Pero el voto se refina:

```
P(voto=p | comuna, edu, edad) = baseline + 0.5 · (β_uni · [I_uni - share_uni_c]
                                                + β_65+ · [I_65+ - share_65+_c])
clamp a [0,1], renormalizar sobre los 4 parties
```

Coeficientes `β_p` estimados via OLS sobre 15 comunas con 2 predictores:
`share_universitario_c`, `share_65plus_c`. `share_female` dropeado por
falta de variación. Factor 0.5 atenúa extrapolación individual.

**Resultado**: spread JxC entre niveles educativos pasa de 6.4pp (sin EI)
a 28.5pp (con EI), preservando marginales comunales.

---

## 9. Integraciones externas

### Gemini 2.5 Flash (obligatoria)

- Endpoint OpenAI-compat: `https://generativelanguage.googleapis.com/v1beta/openai/`
- Usado para: generar personas (en el flujo Zep), chat con agentes,
  ontología LLM, reacciones en OASIS runtime, ReportAgent.
- Config crítica: `extra_body={"reasoning_effort": "none"}` para evitar
  que consuma tokens en thinking invisible.
- `response_format={"type": "json_object"}` para structured output.
- Free tier: 15 RPM, 1M tokens/día en `gemini-2.5-flash`.

### Zep Cloud (opcional, solo si se usa flujo Zep u ontología Zep)

- Endpoint oficial via SDK `zep-cloud==3.13.0`
- Usado para: GraphRAG del flujo clásico MiroFish, ontología alternativa
  del artículo en el flujo cohort.
- Si no está configurado: el flujo cohort funciona igual, solo el toggle
  "Zep" en el OntologyPanel fallará con mensaje claro.

### CAMEL-AI / OASIS (obligatoria para OASIS runtime)

- Packages: `camel-oasis==0.2.5`, `camel-ai==0.2.78`
- Subprocess spawneado por `SimulationRunner` al llamar `/start`
- Consume el `simulation_config.json` y genera acciones en
  `reddit_simulation.db` + `twitter_simulation.db` (SQLite)
- Usa LLM_API_KEY para cada agente (costo escala con N × rondas)

---

## 10. Decisiones arquitectónicas clave (ADRs)

### ADR-1: Flujo cohort como dispatch, no reemplazo

**Contexto**: Tenemos un sistema existente de MiroFish con 5-step wizard
+ Zep + OASIS. Agregar cohorte CABA podía ser un fork divergente o una
extensión aditiva.

**Decisión**: Extensión aditiva. Un parámetro `profile_source` en
`prepare_simulation` hace dispatch a `_prepare_from_caba_cohort` o flujo
Zep. Endpoints nuevos `/cohort/*` paralelos a los existentes.

**Consecuencias**:
- ✅ Cero regresión en flujo Zep
- ✅ Developers pueden elegir el flujo por caso de uso
- ⚠️ Frontend necesita guards para redirigir simulaciones cohort lejos de
  vistas Zep (que harían 404)

### ADR-2: Dedup por hash SHA-256 determinístico

**Contexto**: Con cohortes sintéticas rápidas, es muy fácil crear
duplicados (pegar mismo artículo, probar misma seed). Sin dedup se
acumula ruido.

**Decisión**: `sha256(json.dumps({req, cfg}, sort_keys=True))[:16]`.
Búsqueda lineal sobre `cohort_meta.json` al crear.

**Alternativas descartadas**:
- SQLite con índice → overhead para caso simple
- Tabla en memoria → se pierde al reiniciar

**Consecuencias**: O(N) búsqueda por hash; trivial para <1000 sims.
Al migrar: considerar índice separado.

### ADR-3: Ontología del artículo con toggle LLM/Zep

**Contexto**: El usuario quería ver un grafo de entidades del artículo
similar al que MiroFish genera con Zep. Zep tarda 30-120s, LLM tarda 5s.

**Decisión**: Dos endpoints internos, un endpoint externo con parámetro
`source`. Cada uno cachea su resultado en archivo separado
(`article_ontology_llm.json`, `article_ontology_zep.json`). El frontend
muestra un toggle para comparar ambos.

**Consecuencias**:
- ✅ LLM da feedback visual inmediato
- ✅ Zep queda disponible para casos que lo justifiquen
- ✅ Cache permite comparar ambos sin re-costo
- ⚠️ El formato normalizado (entities/relationships/themes) puede perder
  riqueza específica de Zep (memoria temporal)

### ADR-4: Chat directo con Gemini en lugar de `/interview` de OASIS

**Contexto**: El endpoint oficial `/api/simulation/interview` requiere
que OASIS esté corriendo en modo "wait-for-commands". Para cohortes que
no han corrido OASIS (o recién armadas) esto devuelve 400.

**Decisión**: Nuevo endpoint `/cohort/<id>/chat` que arma el system
prompt con la persona del perfil + artículo como contexto y llama
directamente a Gemini. No requiere OASIS.

**Consecuencias**:
- ✅ Chat funciona siempre, incluso antes de correr OASIS
- ✅ Más barato (1 LLM call por mensaje vs pipeline OASIS completo)
- ⚠️ No refleja cómo reaccionaría el agente si estuviera embebido en el
  feed de posts de otros (context social). Trade-off explícito.

### ADR-5: Datos del Censo copiados al repo

**Contexto**: `backend/app/services/caba_cohort/data/` contiene 15 MB
de CSV electoral + 700 KB de xlsx del Censo. Pueden incluirse en el repo
o descargarse al setup.

**Decisión**: Incluir en el repo.

**Razones**:
- Clone funciona "out of the box" sin scripts extra
- Los datos no cambian (Censo 2022 es definitivo, elecciones 2023 son
  resultado final)
- 16 MB es tolerable para git sin necesidad de LFS

**Consecuencia**: `.gitignore` tiene excepción explícita para
`backend/app/services/caba_cohort/data/`.

### ADR-6: Ecological Inference con atenuación 0.5

**Contexto**: Goodman OLS sobre 15 comunas produce coeficientes con
extrapolación agresiva cuando se aplican a individuos binarios
(I_uni=0 o 1) respecto a shares continuos (0.06-0.52).

**Decisión**: Multiplicar el shift ecológico por 0.5 antes de aplicarlo
al baseline comunal. Dropear `female` por falta de variación intercomunal.

**Alternativas descartadas**:
- MrP bayesiano → requiere microdata de encuesta individual (no la tenemos)
- Modelos complejos con más features → overfitting con N=15

**Consecuencias**: Preserva marginales comunales, da 4.5× más señal
individual que sin EI, pero el factor es arbitrario. Validado comparando
spread JxC por educación: 6.4pp → 28.5pp.

### ADR-7: Frontend en español, backend neutral

**Contexto**: El MiroFish original es chino. El fork es para Argentina.

**Decisión**: Crear `locales/es.json` (665 keys) como default del frontend
+ migración automática si hay `'zh'` en localStorage. Backend queda
multilingüe vía i18n server-side existente (`utils/locale.py`), usando el
header `Accept-Language` que el frontend manda.

**Consecuencias**: UX coherente en castellano rioplatense, sin tocar
código original del core MiroFish.

---

## 11. Seguridad y secrets

### Variables sensibles

Todas en `.env` (gitignored):
- `LLM_API_KEY` — Gemini vía OpenAI SDK
- `LLM_BASE_URL` — `https://generativelanguage.googleapis.com/v1beta/openai/`
- `LLM_MODEL_NAME` — `gemini-2.5-flash`
- `ZEP_API_KEY` — Zep Cloud (opcional para flujo cohort)
- `SECRET_KEY` — Flask session

### Amenazas y mitigaciones

| Amenaza | Mitigación actual | Pendiente |
|---|---|---|
| Keys en repo | `.gitignore` + documentación | Pre-commit hook con `trufflehog` |
| CORS abierto | `CORS(app, resources={r"/api/*": {"origins": "*"}})` | Restringir a origins específicos en prod |
| Sin auth | Todos los endpoints públicos | Agregar JWT middleware antes de prod |
| SQLi en SQLite | Parametrización via `cursor.execute(?)` | Auditar queries dinámicas |
| Prompt injection | Mensaje user va con `role: user`, no en system | Input validation + rate limiting |
| Artículo con PII | Usuario pega texto → se manda a LLM | Considerar redact antes de enviar |
| Consumo tokens | Cohortes grandes × rondas = $$ | Rate limit + cost caps por user/día |

### Políticas de datos

- **Datos sintéticos**: todos los perfiles generados son FICTICIOS. Los
  nombres son random (pool finito), no corresponden a personas reales.
- **Datos de censo y electoral**: agregados a nivel de comuna. No hay
  microdata individual. No hay PII de electores reales.
- **Artículos del usuario**: se guardan en `cohort_meta.json` y se envían
  al LLM. Usuario debe abstenerse de pegar PII.

---

## 12. Deploy y operación

### Desarrollo local

```bash
# Primera vez
cp .env.example .env   # completar LLM_API_KEY, opcional ZEP_API_KEY
npm run setup:all      # root + frontend + backend deps

# Correr
npm run dev            # concurrently: backend :5001, frontend :3000
```

Frontend en `http://localhost:3000/`, backend en `http://localhost:5001/`.
Proxy de Vite redirige `/api/*` al backend.

### Docker

`docker-compose.yml` existe desde MiroFish upstream. El flujo cohort
debería funcionar sin cambios (datos copiados + deps en pyproject).

### Producción (no implementado)

Consideraciones:
- `FLASK_DEBUG=false`
- CORS restrictivo
- Reverse proxy (Caddy/Nginx) sirviendo Vite build estático + proxy a Flask
- Secrets vía orquestador, no `.env` en disco
- Persistencia de `uploads/simulations/` en volumen montado
- Rate limiting por IP
- HTTPS obligatorio

---

## 13. Puntos de extensión

### Sampler

- **Rejection sampling previo** para respetar `n` al filtrar post-sample
  (hoy los filtros `sexo/actividad/educacion` reducen la cohorte efectiva)
- **Ingresos estimados** cruzando con EPH INDEC
- **Otras provincias** — nuevos parsers para CSV + xlsx provinciales
- **Elecciones nacionales** — DINE tiene datos por provincia
- **Radio censal** — microdatos + shapefiles + join geoespacial
- **MrP real** si se consigue microdata legítima

### Ontología

- **Clustering de razones** en reacciones con embeddings
- **Multiclase emocional** (enojo/miedo/alegría) además de sentiment binario
- **Diff ontologías LLM vs Zep** visual para ver qué aporta cada uno
- **Ontología multi-documento** para feeds de varios artículos

### OASIS

- **Feedback loop**: después de N rondas, reextraer ontología del feed
  generado y compararla con la del artículo inicial
- **Interview batch** sobre la cohorte para encuestas agregadas
- **Export timeline** como video/gif del enjambre

### Modo electoral

Ver [`research/fase0/DOCUMENTACION.md`](research/fase0/DOCUMENTACION.md)
§9.1 — requisitos regulatorios AAIP + ADR necesarios para uso en campaña
política (audit trail, disclaimers, TTL, bloqueo de export masivo).

---

**Última revisión**: 2026-04-19 · Buccdess Sense v0.1-Preview sobre MiroFish v0.1
