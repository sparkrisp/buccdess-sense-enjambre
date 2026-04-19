# MiroFish — Extensión Electoral CABA

Documentación comprehensiva del módulo de cohortes electorales CABA integrado a MiroFish.

**Autores:** arielrm@gmail.com + sesiones con Claude (sonnet/opus)
**Período:** 2026-04-18 / 2026-04-19
**Estado:** Fases 0–C completadas. Fase D planificada.

---

## Tabla de contenidos

1. [Visión general](#1-visión-general)
2. [Motivación y caso de uso](#2-motivación-y-caso-de-uso)
3. [Decisiones arquitectónicas clave](#3-decisiones-arquitectónicas-clave)
4. [Fase 0 — Reconocimiento de datos](#4-fase-0--reconocimiento-de-datos)
5. [Fase 1 — Sampler de cohortes](#5-fase-1--sampler-de-cohortes)
6. [Fase 2 — Integración al backend](#6-fase-2--integración-al-backend)
7. [Fase B — Demo de slicing](#7-fase-b--demo-de-slicing)
8. [Fase C — Ecological Inference](#8-fase-c--ecological-inference)
9. [Uso end-to-end: reacción a un artículo](#9-uso-end-to-end-reacción-a-un-artículo)
9b. [UI web integrada (Buccdess Sense)](#9b-ui-web-integrada-buccdess-sense)
10. [Fase D — Plan de extensión](#10-fase-d--plan-de-extensión)
11. [Features propuestas](#11-features-propuestas)
12. [Mejoras al módulo caba_cohort](#12-mejoras-al-módulo-caba_cohort)
13. [Mejoras a MiroFish en general y en particular](#13-mejoras-a-mirofish-en-general-y-en-particular)
14. [Limitaciones conocidas](#14-limitaciones-conocidas)
15. [Ética, legales y compliance](#15-ética-legales-y-compliance)
16. [Referencias y fuentes](#16-referencias-y-fuentes)
17. [Apéndice: estructura de archivos](#17-apéndice-estructura-de-archivos)
18. [Apéndice: configuración de entorno (.env)](#18-apéndice-configuración-de-entorno-env)

---

## 1. Visión general

Se extendió MiroFish (motor de predicción multi-agente basado en OASIS/CAMEL-AI)
con un pipeline alternativo para generar cohortes de agentes sintéticos con
distribución demográfica y electoral **real** de la Ciudad Autónoma de Buenos
Aires. La fuente primaria son datos públicos: INDEC Censo 2022 y DINE Generales
2023.

El flujo tradicional de MiroFish toma un documento semilla, construye un
GraphRAG en Zep Cloud, extrae entidades (personas, instituciones) y genera
perfiles via LLM. El nuevo flujo bypasea Zep y LLM para la etapa de perfiles:
samplea agentes desde distribuciones reales de la población porteña con
preferencia electoral asignada por datos DINE, exporta al formato OASIS y
corre la simulación.

Caso de uso principal: **simular cómo reacciona el electorado porteño ante
una medida o evento X**, desde una perspectiva de investigación / consultoría
/ producto propio. El modo campaña requiere salvaguardas adicionales (ver §14).

---

## 2. Motivación y caso de uso

### Caso de uso elegido

> "Simular cómo reacciona el electorado porteño ante una medida X"

Concreto: el usuario ingresa el texto de una medida (p. ej. "Se anuncia un
aumento del 40% en el boleto de subte"), elige un filtro demográfico
(p. ej. "500 vecinos de Comunas 2, 13 y 14") y MiroFish devuelve una
simulación donde 500 agentes con perfil porteño realista reaccionan en un
Reddit/Twitter virtual.

### Por qué NO usamos padrón electoral

El padrón electoral argentino contiene datos personales identificables (DNI,
nombre, domicilio). Está regulado por la **Ley 25.326 de Protección de Datos
Personales** y el Código Nacional Electoral:

- Se obtiene para administración electoral; usarlo para microtargeting o
  entrenamiento de IA viola el principio de finalidad (art. 4).
- Hay jurisprudencia incipiente en Argentina (y precedentes internacionales
  como Cambridge Analytica) que desincentiva fuertemente este camino.
- Académicamente está documentado el problema: ver Halabi et al. (UNLP) sobre
  padrones publicados online que comprometen la privacidad.

### Por qué SÍ usamos Censo + Electoral agregado

- **Censo 2022 (INDEC):** distribución demográfica por comuna. Público y
  pensado para análisis.
- **Generales 2023 (DINE / data.buenosaires.gob.ar):** resultados electorales
  por mesa. Público por transparencia electoral.
- **No hay riesgo de identificación individual**: trabajamos con
  distribuciones agregadas.

---

## 3. Decisiones arquitectónicas clave

### 3.1 Separación research/ vs backend/

- **`research/fase0/`**: código exploratorio, notebooks, datos crudos.
  Aislado via `uv`, gitignored el directorio data/.
- **`backend/app/services/caba_cohort/`**: módulo productivo con copias
  estables de los parsers + un adapter (`source.py`) que genera
  `OasisAgentProfile`.

**Razón:** separar experimentación de código productivo. Cuando el sampler
queda estable se promueve al backend (se hizo en Fase 2).

**Trade-off:** código duplicado (parsers en ambos lados). Minimizado con
`cp` y pruebas de smoke en ambos lados.

### 3.2 Nivel de agregación: comuna, no radio censal

CABA tiene:
- **15 comunas** (división política)
- ~**3.400 radios censales** (división estadística)
- **8.770 mesas electorales** en **167 circuitos**

Elegimos **comuna** para el MVP porque:
- El Censo publica tabulados por comuna directamente (sin procesar microdatos)
- El join electoral ↔ censo por comuna es trivial (15 puntos a unir)
- Perdemos granularidad espacial pero ganamos velocidad y claridad

Para mayor resolución (Fase D) habría que bajar microdatos del Censo (con
radio) y hacer join geoespacial con los circuitos electorales.

### 3.3 Modelo probabilístico MVP

Sampleamos en 4 pasos independientes condicional a la celda (comuna, sexo, edad):

1. `P(celda) ∝ población_14+`
2. `P(actividad | celda)` — marginal del Censo
3. `P(educación | celda)` — marginal del Censo
4. `P(voto | celda, edu, edad)` — con Ecological Inference (Fase C) o sin
   (solo `P(voto | comuna)` en Fase 1)

**Asume independencia** entre actividad y educación dado (celda). Es una
aproximación MVP; lo real es que están correlacionadas (universitarios se
ocupan más). Mejora posible en Fase D con `actividad_economica_c10_1.xlsx`
que cruza ambas (solo para ocupados).

### 3.4 Persona textual via templates, no LLM

Cada perfil tiene `bio` y `persona` generados por templates determinísticos
desde atributos (edad + barrio + educación + actividad + voto). OASIS
después los consume como system prompt del LLM que controla al agente.

**Razón:** determinístico, reproducible, sin costo de API. El usuario puede
re-correr con el mismo seed y obtener los mismos perfiles.

**Limitación:** todas las personas suenan similares. Mejorar con
enriquecimiento LLM opcional post-sample (Fase D).

---

## 4. Fase 0 — Reconocimiento de datos

**Objetivo:** responder con evidencia (no a priori) si los datos públicos
alcanzan para construir cohortes realistas.

### Qué se hizo

- Exploración de 4 fuentes: API DINE, dataset DINE en datos.gob.ar,
  data.buenosaires.gob.ar, INDEC Censo 2022.
- Descarga de:
  - `generales_2023_caba.csv` (15 MB, 237.434 filas a nivel mesa)
  - 100+ tabulados xlsx del Censo 2022 CABA por comuna
- Inspección de schemas, validación de granularidad.

### Hallazgos

- **Electoral:** 237k filas nivel mesa, 15 comunas × 167 circuitos × 8.770
  mesas, 3 cargos (JEF/LEG/COM), 4 agrupaciones (UxP/JxC/LLA/FIT), voto
  desagregado por tipo (positivo/blanco/nulo/impugnado/recurrido/comando),
  mesas separadas NATIVOS vs EXTRANJEROS.
- **Señal demográfica clarísima por comuna** antes de cualquier modelo:
  Recoleta 66% JxC vs Lugano 36% JxC, LLA 20% en Lugano vs 11% en Belgrano.
- **Censo:** estructura xlsx compleja (multi-header, celdas combinadas),
  una hoja por comuna ("Cuadro N.N.K"), encoding latin-1 en sheet names
  (cosmético).

### Pros

- Ambas fuentes son oficiales, públicas y sin restricciones de uso.
- Actualización periódica (electoral cada ciclo, Censo cada década).
- Cobertura demográfica muy rica.

### Contras / limitaciones

- Censo tabulado no incluye **ingresos** (eso está en la EPH INDEC).
- La granularidad electoral (mesa) es más fina que la demográfica (comuna).
- Formatos poco amigables (xlsx con multi-headers).
- Sitio `censo.gob.ar` tiene certificado SSL problemático en Windows
  (hay que usar `--insecure` con curl).

### Artefactos

- `research/fase0/data/caba/generales_2023_caba.csv`
- `research/fase0/data/censo/*.xlsx` (100+ archivos)
- `research/fase0/notebooks/01_*.py` a `06_*.py` — exploraciones

---

## 5. Fase 1 — Sampler de cohortes

### Qué se hizo

Implementación del pipeline completo de generación de perfiles sintéticos:

1. **`censo_parser.py`** — parsea los xlsx del INDEC (actividad y educación)
   a DataFrame tidy (`comuna × sexo × edad × N`).
2. **`electoral_parser.py`** — CSV electoral a DataFrame
   (`comuna × party × pct_votos`).
3. **`cohort_builder.py`** — `CohortBuilder.sample(n, filtros, seed)`.
4. **`oasis_adapter.py`** — convierte `Perfil` a `OasisProfileDict` con
   bio/persona en texto natural rioplatense.

### Validación

10.000 agentes sampleados con seed=42:
- Distribución por comuna vs real: **max diff 0.38%** (<3% tolerancia).
- Voto global CABA vs real: **max diff 1.20pp**.
- RMSE voto por comuna: **1.05-1.51pp**.
- Crosstabs demográficos plausibles: Recoleta 49% universitarios, Lugano 5.5%.

### Pros

- **Determinístico y reproducible** (seed).
- **Rápido**: 10k agentes en ~5 segundos, sin LLM.
- **Interpretable**: cada perfil tiene trazabilidad a su celda demográfica.
- **Extensible**: agregar un nuevo atributo = agregar un parser + una columna.

### Contras

- Asume **independencia condicional** entre actividad y educación dado la
  celda. Irreal: universitarios se ocupan más que sin instrucción.
- Voto solo condicional a comuna (Fase 1 sin EI) → subestima la correlación
  educación↔voto. Mitigado en Fase C.
- Personas generadas por template son narrativamente planas.
- Solo CABA. Otras provincias requieren nuevos parsers + nuevos datos.

### Mejoras propuestas

- [ ] **Cross-tabs del Censo** (Fase C+): usar `actividad_economica_c10_1` que
  cruza educación × ocupación para modelar P(ocup | edu, comuna).
- [ ] **Enriquecimiento LLM opcional** post-sample: reescribir las personas
  con un LLM para darles variedad narrativa (con cache para reproducibilidad).
- [ ] **Ingresos estimados** vía EPH INDEC por ocupación + educación.
- [ ] **Barrios** más granulares (radio censal) si se hace el join geoespacial.

---

## 6. Fase 2 — Integración al backend

### Qué se hizo

- Módulo productivo **`backend/app/services/caba_cohort/`** con copias
  estables de los parsers + `source.py` adapter.
- **Dispatch en `SimulationManager.prepare_simulation()`**: nuevo parámetro
  `profile_source="caba_cohort_2023"` que bypasea Zep y el
  `SimulationConfigGenerator` (LLM). Flujo Zep intacto.
- Método nuevo `_prepare_from_caba_cohort()` paralelo al flujo tradicional.
- **Endpoint HTTP**: `POST /api/simulation/prepare-from-cohort`.
- Deps agregadas a `backend/pyproject.toml`: openpyxl, numpy, pandas.

### Validación

Smoke tests pasaron:
- `SimulationManager.prepare_simulation(profile_source="caba_cohort_2023", ...)`: OK
- HTTP `POST /prepare-from-cohort`: 200 OK, 100 agentes persistidos en
  `uploads/simulations/{sim_id}/reddit_profiles.json` + `.csv` + `.config`
- Archivos en formato **OASIS-compatible validado** contra schema de
  `oasis_profile_generator._save_reddit_json`.

### Pros

- **Cambio aditivo, no invasivo**: flujo Zep sigue funcionando exactamente
  igual. Si el backend no recibe `profile_source`, usa Zep por default.
- **Zero LLM**: el flujo cohort no requiere `LLM_API_KEY` para la etapa de
  perfiles (sí para la simulación posterior de OASIS).
- **Zero Zep**: no requiere `ZEP_API_KEY` para cohortes.
- **Sync fast**: cohortes de 500 en <5 segundos, no hace falta TaskManager
  async como el flujo Zep.

### Contras

- **Datos copiados al backend** (~15 MB). Ocupan espacio y requieren
  sincronización manual con `research/fase0/data/`. Aceptable por ahora,
  pero para producción conviene externalizar (Fase D).
- **Config default sin LLM**: la `simulation_config.json` se genera con
  valores razonables pero no está "tuneada" al contenido de la medida
  simulada. El usuario puede editarla manualmente o aceptar el default.
- **Frontend no modificado**: el endpoint nuevo existe pero la UI actual
  sigue yendo a `/prepare`. Requiere cambio de UX para exponerlo.

### Mejoras propuestas

- [ ] **Externalizar datos**: mover los xlsx del backend a un bucket S3/MinIO
  o a un volumen Docker montado (evitar duplicar 15 MB en el repo).
- [ ] **Config generator lite**: una versión del `SimulationConfigGenerator`
  que use LLM opcional para tunear el config al contenido de la medida,
  pero con defaults seguros si no hay API key.
- [ ] **Frontend**: pantalla nueva "Simulación desde cohorte" con form para
  elegir comuna/edad/sexo/educación y disparar `POST /prepare-from-cohort`.
- [ ] **Feature flag** en Config para habilitar/deshabilitar el flujo cohort
  por deploy (útil para gradual rollout).

### Arquitectura

```
POST /api/simulation/prepare-from-cohort
       ↓
SimulationManager.prepare_simulation(profile_source="caba_cohort_2023")
       ↓
_prepare_from_caba_cohort()
       ↓
CabaCohortSource.generate_profiles(CohortConfig)
       ↓
CohortBuilder.sample() → List[Perfil]
       ↓
perfil_to_oasis() → List[OasisAgentProfile]
       ↓
_save_reddit_json + _save_twitter_csv (reutilizados de OasisProfileGenerator)
       ↓
simulation_config.json (default, sin LLM)
       ↓
state.status = "ready"  → OASIS puede ejecutar
```

---

## 7. Fase B — Demo de slicing

### Qué se hizo

Notebook con 4 escenarios reales mostrando el poder del sampler con queries
variadas:

1. **Empleo joven zona sur** — 500 agentes de Comunas 8+9, 18-35 años.
2. **Seguridad para universitarios norte** — 300 solicitados, 136 efectivos
   (filtro `educacion="universitario"` post-sample), Comunas 2+13+14.
3. **Reforma previsional** — 400 agentes 60+ años toda CABA.
4. **Mujeres desocupadas 25-55** — 200 solicitados, **solo 13 efectivos**
   (filtros muy restrictivos).

### Valor demostrado

Cada cohorte produce una distribución coherente con la realidad y con
perfiles individuales plausibles. Ejemplos:
- Cohorte #1 (jóvenes sur): JxC 40%, UxP 38%, **LLA 18%** (vs 13% global),
  desocupación 12.8% (vs 4% global).
- Cohorte #2 (universitarios norte): JxC 60%, **universitarios 100%**,
  edades dispersas, aparecen perfiles disidentes (universitario que votó UxP).

### Limitación descubierta (importante)

**Los filtros post-sample reducen la cohorte efectiva.** En el escenario 4
de 200 pedidas quedaron 13. Para slicings muy restrictivos se necesita
`n` mucho más grande.

### Mejoras propuestas

- [ ] **Rejection sampling previo** para los filtros sexo/actividad/educacion:
  filtrar el universo demográfico antes del `rng.choice`, así `n` solicitado
  se respeta siempre.
- [ ] **Validar factibilidad** del filtro antes de samplear: si el universo
  filtrado es muy chico, avisar al usuario "solo hay 5.000 mujeres
  desocupadas 25-55 en CABA, pedir >200 podría sesgar".
- [ ] **Recomendador de slicing**: dada una pregunta natural
  ("jubilados no oficialistas"), sugerir los filtros apropiados.

---

## 8. Fase C — Ecological Inference

### Qué es y qué no es

**No es MrP clásico.** MrP (Multilevel Regression with Poststratification)
requiere microdata de encuesta individual (gente con sus atributos + su
voto declarado). No la tenemos y no podemos legalmente obtenerla del padrón.

**Es Ecological Inference (Goodman 1953).** Se ajusta una regresión ecológica
por party en las 15 comunas:

```
pct_voto_party_c = α_p + β_p_uni * share_uni_c + β_p_65plus * share_65plus_c
```

Los coeficientes `β` aproximan el **efecto ecológico marginal** de la
proporción de cada grupo sobre el voto, observado entre comunas.

### Qué se ajustó (resultados)

```
R^2 por party (ajuste sobre 15 comunas):
  UxP: 0.76    JxC: 0.91    LLA: 0.82    FIT: 0.72

Coeficientes:
party  interc    uni   65plus
UxP     0.461  -0.378  -0.114
JxC     0.251  +0.544  +0.426
LLA     0.238  -0.111  -0.354
FIT     0.051  -0.056  +0.041
```

**Interpretación:** un punto más de % universitarios en una comuna se asocia
con +0.54pp JxC, -0.38pp UxP, -0.11pp LLA. Coherente con patrones electorales
argentinos conocidos.

### Cómo se aplica al sampling

Para un individuo en comuna c:
- Baseline = `pct_voto_c` (observado).
- Shift = `0.5 × β_uni × (I_uni − share_uni_c) + 0.5 × β_65plus × (I_65+ − share_65+_c)`
- `P(voto) = max(0, baseline + shift)`, luego renormalizado.

**Factor de atenuación 0.5**: los coeficientes se ajustan sobre comunas
cuyos shares varían en rango acotado (share_uni de 0.06 a 0.52), extrapolar
a individuos (I=0 o 1) amplifica en exceso. El factor 0.5 deja pasar la
señal sin destruir el baseline comunal.

### Validación comparativa (20.000 agentes)

| Métrica | Sin EI | Con EI |
|---|---|---|
| Max diff voto global | 0.14pp | 0.32pp |
| RMSE JxC por comuna | 1.09pp | 1.14pp |
| Spread JxC entre niveles edu | **6.4pp** | **28.5pp** |
| JxC en 65+ vs <65 | ~51% / ~50% | **65.9% / 46.5%** |
| Universitarios Recoleta JxC | 68.7% | 78.1% |

### Pros

- **Señal individual 4.5x más fuerte** (spread educación × voto).
- Diferenciación etaria marcada (65+ vs <65: 19pp de diferencia en JxC).
- Sin nuevas dependencias de software (solo numpy).
- **Honesto sobre qué hace**: no promete más que lo que es.

### Contras

- 15 comunas son **pocas observaciones**: los coeficientes son ruidosos.
- **Ecological fallacy** sigue siendo un riesgo: la inferencia sobre
  individuos desde datos agregados puede errarle si hay heterogeneidad
  dentro de comuna.
- Confundidos obvios (edu alta = ingreso alto en CABA) no se separan.
- `female` no aporta señal estimable (shares entre 0.53-0.57, sin variación)
  y fue dropeado — implica que el sampler **no diferencia voto por género**.
- El factor de atenuación 0.5 es arbitrario (no viene de la teoría).

### Mejoras propuestas

- [ ] **Encuestas como supervisión externa**: aunque no tenemos microdata,
  las encuestadoras publican cross-tabs agregados (voto × edu × edad). Se
  pueden usar para calibrar los coeficientes.
- [ ] **Modelo jerárquico bayesiano** (PyMC) que admita priors sobre los
  efectos y produzca intervalos de credibilidad, no solo puntos. Requiere
  nueva dep `pymc`.
- [ ] **Agregar Provincia de Buenos Aires** al ajuste (135 municipios + más
  datapoints) para estabilizar los betas.
- [ ] **Validación por elección histórica**: re-entrenar con PASO 2021,
  predecir Generales 2021, comparar vs real. Si tracks → modelo generaliza.
- [ ] **Factor de atenuación adaptivo** basado en R^2 del fit o variance de
  los coeficientes.

---

## 9. Uso end-to-end: reacción a un artículo

Pipeline completo puesto en producción local: de URL/texto → cohorte →
LLM → reacción individual + análisis agregado.

### 9.1 Arquitectura del flujo de reacción

```
URL o texto del artículo
        │
        ▼
[trafilatura: fetch + extract] (solo si URL)
        │
        ▼
[CohortBuilder.sample()] → N perfiles con EI
        │
        ▼
[perfiles_to_oasis] → personas textuales rioplatenses
        │
        ▼
[Gemini 2.5 Flash via OpenAI SDK] (una llamada por agente)
    response_format=json_object
    {"tweet": "...", "sentiment": "a_favor|en_contra|neutro|ambiguo",
     "razon_principal": "..."}
        │
        ▼
[Agregación] → sentiment × voto, sentiment × educación, JSON export
```

### 9.2 Cómo se corre

Script: `research/fase0/notebooks/12_reaccion_articulo.py`

```bash
cd research/fase0

# Con URL de artículo real
uv run python notebooks/12_reaccion_articulo.py --url https://www.lanacion.com.ar/...

# Con archivo local de texto
uv run python notebooks/12_reaccion_articulo.py --file mi_articulo.txt --n 50

# Con texto directo
uv run python notebooks/12_reaccion_articulo.py --text "..." --comuna 2 13 14

# Demo por default (tarifazo ficticio)
uv run python notebooks/12_reaccion_articulo.py --n 10

# Filtros combinados
uv run python notebooks/12_reaccion_articulo.py \
    --url <url> \
    --n 50 \
    --comuna 8 9 \
    --edad-min 25 \
    --seed 2026
```

### 9.3 Qué devuelve

- **Reacción individual** por agente con:
  - `tweet`: 1-3 oraciones en rioplatense
  - `sentiment`: a_favor / en_contra / neutro / ambiguo
  - `razon_principal`: resumen corto de la razón
- **Análisis agregado**:
  - Distribución global de sentiment
  - Sentiment por voto 2023 (UxP / JxC / LLA / FIT)
  - Sentiment por nivel educativo
- **Export JSON** a `data/exports/reacciones/reaccion_<seed>_n<N>.json`
  con artículo + cohorte + todas las reacciones.

### 9.4 Caso probado (demo default)

Artículo: *"El Gobierno anuncia eliminación de subsidios al transporte,
aumento 350% subte, 200-400% colectivos..."* (ficticio).

Cohorte: 10 agentes CABA, edad_min=18, seed=2026, con EI.

Resultado: **100% en_contra**. Incluso el único votante LLA se quejó del
monto: *"¡Qué barbaridad! Otro golpe al bolsillo de los que laburamos.
Dicen que es para la clase media pero al final nos afecta a todos"*.
Eso es coherente: un aumento del 350% es brutal incluso para libertarios
consecuentes.

**Rasgos de calidad observados:**
- Registro rioplatense natural ("che", "laburamos", "los platos rotos",
  "tarifazo", "viejo está en bolas").
- Mención al contexto del artículo (el ministro, la "clase media porteña"
  como justificación).
- Anclaje demográfico: jubilados mencionan la jubilación, trabajadores
  mencionan el bolsillo.
- Voz diferenciada por perfil (ni todos los mensajes son iguales).

### 9.5 Configuración LLM crítica

- **Modelo:** `gemini-2.5-flash` vía endpoint
  `https://generativelanguage.googleapis.com/v1beta/openai/`.
- **max_tokens=800** (Gemini 2.5 consume tokens en "thinking" invisible,
  <300 no alcanzan).
- **`extra_body={"reasoning_effort": "none"}`** para minimizar thinking y
  dejar presupuesto para la respuesta.
- **`response_format={"type": "json_object"}`** para structured output
  (Gemini lo soporta).
- **`temperature=0.85`** para variedad sin perder coherencia.

### 9.6 Costos estimados (Gemini 2.5 Flash)

Por llamada (persona ~400 tokens, artículo ~1000 tokens, respuesta ~150 tokens):
- Input: ~1400 tokens × USD 0.075 / 1M = ~0.0001 USD
- Output: ~150 tokens × USD 0.30 / 1M = ~0.00005 USD
- **Total por agente: ~0.00015 USD**

Cohortes de referencia:
- N=50: ~0.008 USD
- N=500: ~0.08 USD
- N=5000: ~0.80 USD

Considerando que cada llamada tarda 2-5 segundos con Gemini Flash y sin
paralelización, 500 agentes son ~15-40 minutos.

### 9.7 Pros

- **Velocidad**: reacciones de 500 agentes en <1 hora por <1 USD.
- **Reproducibilidad**: mismo seed = mismos agentes.
- **Auditable**: el JSON exportado tiene TODO (cohorte + reacciones + meta).
- **Cero dependencia de Zep ni de un documento semilla preprocesado**.
- **URL handling**: trafilatura extrae el contenido principal sin
  publicidad ni navegación.
- **Voz diferenciada**: los LLA libertarios no dicen lo mismo que los
  UxP ni los universitarios del norte ni los jubilados de Lugano.

### 9.8 Contras

- **Sin interacción entre agentes**: cada uno reacciona al artículo, pero
  no se ven entre sí, no se contagian, no hay echo chambers.
  Para eso está OASIS (Fase D opcional).
- **Una sola reacción por agente**: no hay seguimiento temporal (cómo
  cambia la opinión con más info, o con tiempo).
- **Prompt fijo**: el template "reaccionás posteando en X" se puede
  refinar (ej. separar "cómo te sentís" de "qué harías").
- **Sentiment categorías rígidas**: 4 buckets. Mejor sería score
  continuo (-1 a +1) con 4 clasificaciones.
- **No registra emoción específica** (enojo vs decepción vs miedo).
  Agregar clasificación emocional multiclase.

### 9.9 Mejoras propuestas al flujo de reacción

- [ ] **Paralelización de llamadas LLM** (async / ThreadPool): con 5
  workers paralelos, N=500 baja de 20 min a ~4 min.
- [ ] **Cache determinístico** por (persona_hash, articulo_hash, seed).
  Re-correr mismo input no re-llama al LLM.
- [ ] **Clasificación emocional** además de sentiment (enojo / sorpresa /
  miedo / neutral / alegría).
- [ ] **Extracción de hashtags/keywords** de los tweets para word-cloud.
- [ ] **Clustering de `razon_principal`** con embeddings para encontrar
  los argumentos mayoritarios.
- [ ] **Segunda ronda de razonamiento**: mostrar al agente los 5 tweets
  más populares de su comuna y pedirle que actualice.
- [ ] **Comparación A/B**: correr dos versiones del mismo artículo
  (ej. título alarmista vs neutro) y comparar sentiment.
- [ ] **Multi-artículo**: feed de 5 artículos de la semana para ver qué
  tema mueve más la aguja.

---

## 9b. UI web integrada (Buccdess Sense)

El sampler y todos los flujos descritos arriba se exponen a través de
una UI Vue 3 que reemplaza y extiende la original de MiroFish. Para el
diseño técnico completo ver [`ARQUITECTURA.md`](../../ARQUITECTURA.md).

### 9b.1 Views agregadas

| View | Ruta | Rol |
|---|---|---|
| `CohortSetupView.vue` | `/cohort-setup` | Formulario completo: artículo, filtros (comunas multi-select con zonas preset: sur/norte/centro), N, edad, seed, toggle EI. Arriba incluye `CohortHistoryList`. |
| `CohortResultView.vue` | `/cohort/:simulationId` | Stats agregados (voto/edu/actividad/comunas), grafo del artículo (`OntologyPanel`), cards de agentes con filtros voto/comuna, modal de perfil con tabs **Perfil** e **Entrevista** (chat). Botón "Correr simulación OASIS". |
| `CohortRunView.vue` | `/cohort/:simulationId/run` | Dashboard oscuro con feed en vivo (polling 3s) de acciones OASIS por plataforma, progress bar, ranking de agentes, botón parar. |

### 9b.2 Componentes nuevos

- **`CohortHistoryList.vue`** — lista las cohortes guardadas con metadata
  (N, filtros, hash, snippet). Acciones: Ver, Duplicar (precarga form),
  Borrar (modal confirmación).
- **`OntologyPanel.vue`** — visualización d3.js force-directed del grafo
  extraído del artículo. Toggle **LLM (Gemini)** vs **Zep Cloud**. Cada
  uno cacheado en `article_ontology_<source>.json`. Incluye zoom (wheel),
  pan (drag del fondo), reset (doble click), botones `＋ − ⊙`, drag de
  nodos, panel lateral con temas + legenda + entidades.

### 9b.3 Chat con agentes (vía API, no vía OASIS)

Endpoint **`POST /api/simulation/cohort/<id>/chat`**. No requiere que
OASIS esté corriendo. Pasos:

1. Carga el perfil del `agent_id` de `reddit_profiles.json`
2. Resuelve el artículo del `cohort_meta.json` (fallback a `simulation_config.json`)
3. System prompt = `persona` + instrucción rioplatense + artículo (contexto)
4. Envía `history` previa + mensaje al LLM (Gemini 2.5 Flash)
5. Devuelve reply + agent_name

UI: modal de perfil con tabs, burbujas estilo iMessage, indicador typing,
Enter envía.

**Trade-off vs `/interview` de OASIS**: este chat es 1:1 con el LLM,
NO refleja el context social del feed simulado. Para preguntas de opinión
individual: excelente. Para entrevistar post-simulación con contexto del
enjambre: seguir usando `/interview` con OASIS alive.

### 9b.4 Historial con dedup por hash

Al crear una cohorte, el backend computa:

```
cohort_hash = sha256(json_dump({"req": req, "cfg": sorted_cfg}))[:16]
```

Y busca entre todos los `cohort_meta.json` una coincidencia. Si existe
y `force_new != true`, devuelve la existente con `already_exists: true`.
Frontend muestra modal dedup con 3 opciones: Cancelar / Forzar nueva /
Ver la existente.

Endpoints:
- `GET /api/simulation/cohort-history` — lista todas las cohortes (ordenadas desc)
- `DELETE /api/simulation/cohort/<id>` — borra archivos + state

### 9b.5 Ontología del artículo (LLM + Zep)

Endpoint **`POST /api/simulation/cohort/<id>/ontology/build`** con
parámetro `source`:

- **`"llm"`** (~5s, gratis con Gemini free tier): 1 llamada a Gemini con
  structured JSON output. Máximo 20 entidades, 25 relaciones, 3-7 temas.
  Implementado en `backend/app/services/article_ontology.py`.
- **`"zep"`** (30-120s, consume cuota Zep): crea graph_id nuevo, chunkea
  el artículo (2000 chars / overlap 100), upload, espera procesamiento,
  trae nodes + edges. Normaliza al mismo schema que LLM. Implementado en
  `backend/app/services/zep_article_graph.py`.

Ambos resultados se guardan en archivos separados (`article_ontology_llm.json`,
`article_ontology_zep.json`) para poder comparar sin re-costo.

### 9b.6 Guards de redirección cohort → cohort views

Para evitar que una simulación cohort caiga en views Zep originales
(`/simulation/<id>` o `/process/<projId>`), se agregaron guards:

- `HistoryDatabase.isCohort(proj)` — detecta por `entity_types`, prefijo
  `caba-cohort-` en project_id, o `graph_id === 'caba-cohort-no-zep'`.
  Al clickear "Project" o "Simulation" en el modal del historial,
  redirige a `CohortResult` si detecta cohort.
- `MainView.initProject()` — guard sincrónico que detecta prefijo
  `caba-cohort-` en el projectId ANTES de hacer cualquier llamada a
  `/api/graph/<id>` que sería 404.
- `SimulationView.onMounted` + `SimulationRunView.loadSimulationData` —
  consultan `entity_types` y hacen `router.replace` al equivalente cohort.

### 9b.7 Rebrand / i18n

- `locales/es.json` nuevo (665 keys traducidas al rioplatense)
- Default locale cambiado a `'es'` con **migración automática** (si un
  usuario tiene `'zh'` guardado en localStorage de una sesión previa,
  se pasa solo a `'es'`)
- Todas las vistas con `<div class="nav-brand">MIROFISH</div>`
  reemplazadas por `BUCCDESS SENSE — Enjambre` (9 archivos)
- Logo JPEG de MiroFish en Home reemplazado por SVG inline: 7 nodos +
  5 satélites + aristas `stroke-orange opacity-0.25`, animación
  `swarm-pulse` de 6s.
- `index.html`: `title`, `meta description`, `lang="es"`.

### 9b.8 Costos operativos estimados

Con Gemini 2.5 Flash (free tier: 15 RPM, 1M tokens/día):

| Operación | Tokens aprox | Costo paid | Tiempo |
|---|---|---|---|
| Generar cohorte de 50 agentes | 0 (no usa LLM) | 0 USD | 3 s |
| Ontología LLM del artículo | ~2k in + 1k out | ~0.0005 USD | 5 s |
| Chat 1 mensaje con agente | ~1k in + 200 out | ~0.0002 USD | 2 s |
| OASIS 50 agentes × 10 rondas | ~200 LLM calls | ~0.03 USD | 5-15 min |
| OASIS 500 agentes × 72 rondas | ~5000 LLM calls | ~0.80 USD | 15-40 min |

---

## 10. Fase D — Plan de extensión

### 9.1 Modo electoral

Requisitos regulatorios y técnicos para usar MiroFish en campaña política:

- **Audit trail inmutable** (append-only log: quién, cuándo, qué medida,
  qué config, qué resultado).
- **Disclaimer obligatorio** en cada output: "Simulación, no encuesta real,
  datos públicos".
- **TTL corto** de simulaciones electorales + purga automática.
- **Bloqueo de export masivo** (nada de exportar 10k perfiles individuales).
- **Prohibición de texto persuasivo dirigido** (solo insights agregados).
- **Separación estricta** prod/staging.
- Referencia: guía AAIP 2019 sobre tratamiento de datos con fines electorales.

Implementación estimada: capa de policy enforcement en `simulation_manager`
+ middleware auth + nuevos endpoints específicos. ~400 líneas.

### 9.2 Extensión geográfica

**Provincia de Buenos Aires:** disponible. DINE publica por municipio (135),
Censo 2022 idem. Ventaja: mucho más datapoints para EI.

**Todas las provincias:** requiere normalizar schemas (cada provincia
publica distinto). Factible pero tedioso. ~1-2 semanas.

**Elecciones nacionales (presidenciales 2023):** la DINE publica todo
agregado por provincia. Se podría modelar Argentina completa con 24 puntos
demográficos (24 provincias).

### 9.3 Otras elecciones temporales

Legislativas 2025, PASO históricas, segunda vuelta 2023 — todos disponibles
en DINE. Permite series temporales por comuna.

### 9.4 Integración con encuestas

Algunas encuestadoras (Zuban Córdoba, Opinaia, CEOP) publican cross-tabs
agregados. Calibrar el modelo de EI contra esas tablas mejoraría la precisión
sin romper privacidad.

### 9.5 Radio censal (mayor resolución)

Bajar microdatos del Censo 2022 con radio censal + shapefiles de circuitos
electorales + join geoespacial = cohortes con resolución de ~200 m.
Permite estudios de barrios puntuales. Complejidad: media-alta.

### 9.6 Microdata de encuesta (MrP real)

Si se obtiene microdata legítima (ej. Latinobarómetro, encuestas propias
con consentimiento), se puede implementar MrP propiamente dicho: regresión
logística multinomial jerárquica con postestratificación sobre el Censo.
Ganancia esperada: señal individual mucho más precisa, sin atenuación
arbitraria.

### 9.7 OASIS mejorado

- **Memoria a largo plazo** por agente (usando Zep para la cohorte, no
  para generarla).
- **Redes sociales más ricas** (ahora los agentes no tienen "amigos" reales;
  se podría modelar homofilia por comuna).
- **Métricas de resultado**: sentiment shift, polarización, echo chambers.

---

## 11. Features propuestas

### Features al módulo caba_cohort (nuevas)

| Feature | Prioridad | Esfuerzo | Descripción |
|---|---|---|---|
| Rejection sampling previo | Alta | Chico | Filtrar universo antes de rng.choice, respeta `n` exacto. |
| Factor atenuación adaptivo | Media | Chico | Derivar del R^2 del fit EI, no hardcode. |
| Feature `sexo` recuperable | Alta | Medio | Conseguir variación intercomunal del share_female (ej. joinear con BA provincia) o usar encuestas. |
| Enriquecimiento LLM opcional | Media | Medio | Post-sample, reescribir personas con LLM para variedad narrativa. Cache por (perfil_hash). |
| Ingresos estimados | Media | Medio | Cross con EPH para estimar ingreso por (edu, ocup, edad). |
| Shapes geográficos | Baja | Alto | GeoJSON de comunas + join a nivel radio censal. |
| Validación histórica | Alta | Medio | Re-entrenar modelo con 2019/2021, predecir 2023, medir error. |
| Multi-cohort mix | Baja | Chico | Samplear 70% comuna 2 + 30% comuna 8 en una sola llamada. |
| Exportar a parquet | Baja | Chico | Además de JSON/CSV. |

### Features a MiroFish en general

| Feature | Beneficio |
|---|---|
| `profile_source` como registry abierto | Permite plug-and-play de otros samplers (ej. "usa_california_2022"). |
| Simulación A/B de medidas | Correr dos simulaciones paralelas con distinto `simulation_requirement` y misma cohorte, comparar reacciones. |
| Persistencia de cohortes reutilizables | Guardar una cohorte como preset reusable entre simulaciones. |
| Multi-tenancy | Proyectos aislados por usuario/cliente. |
| Logs estructurados de simulación | Export a JSON lines para análisis externo (Grafana, Datadog). |
| API versioning | `/api/v1/simulation/...` para romper contratos sin pegarle a clientes. |

### Features a MiroFish en particular (cambios al stack actual)

| Feature | Impacto |
|---|---|
| Reemplazar encoding ASCII de sheets xlsx INDEC | Cosmético en logs, -1 línea de reconfigure. |
| Opcional `use_llm_for_profiles=False` bypass | Ya existe en el flujo Zep; extender a todos. |
| `OasisAgentProfile.to_reddit_format` como método público | Es estático pero está marcado como privado; refactor chico. |
| Endpoint `/cohort/estimate-size` | Pre-estimar cuántos agentes da un filtro antes de samplear. |
| Worker pool para simulaciones paralelas | Actualmente `simulation_runner` corre uno a la vez. |

---

## 12. Mejoras al módulo caba_cohort

### Mejoras arquitecturales

- **Data pipeline reproducible**: un script `refresh_data.py` que baje
  automáticamente las últimas versiones de DINE y INDEC, haga checksums,
  avise si hay cambios relevantes. Permite actualizar el módulo sin
  intervención manual cada vez que INDEC republica.
- **Schema de entrada validado con Pydantic**: `CohortConfig` actual es un
  dataclass simple. Pydantic daría validación automática y docs en runtime.
- **Tests unitarios**: hoy hay smoke tests en `__main__`. Conviene pasarlos
  a pytest con fixtures reales del Censo + electoral.
- **Logging estructurado** (structlog/loguru) en lugar de `logger.info` con
  strings plano. Permite queryar por comuna, seed, etc.

### Mejoras en la calidad del modelo

- **Calibración con encuestas**: las encuestadoras publican cross-tabs
  agregados. Agregar un paso post-fit que empuje los coeficientes hacia
  direcciones consistentes con esas tablas (Bayesian update simple).
- **Validación por elección histórica**: entrenar con 2021, predecir 2023,
  medir error. Si no tracks bien, revisar.
- **Interacciones**: hoy el modelo EI asume efectos aditivos (uni + 65plus).
  Podría haber interacciones (universitarios mayores votan distinto que
  universitarios jóvenes). Agregar término cruzado.
- **Regularización**: con 15 obs, ridge regression (no OLS pura) evitaría
  coeficientes inflados.

### Mejoras de UX

- **CLI** `python -m caba_cohort sample --n 500 --comuna 8 --seed 42
  --out cohorte.json`.
- **Modo "preview"**: antes de samplear, mostrar qué agentes va a generar
  (distribución esperada).
- **Exports enriquecidos**: SVG con el mapa de CABA coloreado por dónde
  caen los agentes, markdown report con ejemplos.

---

## 13. Mejoras a MiroFish en general y en particular

### General (aplican a cualquier deploy de MiroFish)

- **Multi-tenancy real**: cada proyecto debe estar aislado. Hoy
  `SIMULATION_DATA_DIR` es global — en un SaaS eso rompe privacidad.
- **Observabilidad**: agregar métricas Prometheus (cantidad de simulaciones
  activas, tiempos de preparación, uso LLM tokens). Hoy solo hay logs.
- **Rate limiting** y billing: una simulación de 1000 agentes con LLM
  cuesta USD 2-10 en tokens. Sin límites, un usuario puede quemar presupuesto.
- **Idiomas**: el backend está muy chinocentrado (comentarios, nombres,
  defaults como `country="中国"`). Para uso en Latinoamérica conviene
  internacionalizar el default (ya hay `utils/locale.py` iniciado).
- **Docs de API OpenAPI**: hoy los endpoints están documentados en
  docstrings. Generar `openapi.json` permite auto-gen de clientes.
- **Testing**: el repo no parece tener suite de tests extensiva. Un flujo
  tan complejo (multi-agente, LLM, Zep) necesita tests de integración.
- **Health checks detallados**: `/health` devuelve status. Agregar
  `/health/deps` que testee LLM, Zep, disco.

### Particular (MiroFish tal como está hoy)

- **`OasisProfileGenerator` tiene lógica muy acoplada**: parsea xlsx,
  llama a LLM, parse JSON truncado, retry, fallback. Separar
  responsabilidades (parser, client, fallback) facilitaría testing.
- **Carpeta `uploads/simulations/`** crece sin control. Agregar cleanup
  policy (borrar simulaciones >30 días).
- **Scripts de OASIS en `backend/scripts/`** — duplicados, uno por plataforma.
  Unificar en uno solo con flag `--platform`.
- **`SimulationConfigGenerator`** usa LLM para TODO el config. Hay partes
  (time_config, platform_config) que no necesitan LLM. Separar el LLM
  solo para agent_configs.
- **Comentarios en chino** dificultan onboarding de devs fuera del equipo
  original. Traducir los core (al menos docstrings de funciones públicas).
- **Dependencias pesadas**: `camel-oasis` + `camel-ai` traen muchos packages.
  Revisar si se puede aliviar.
- **Mal encoding en xlsx sheet names**: los nombres vienen como
  "Car�tula" por latin-1 / utf-8 double-encoding. `read_excel` con
  `engine="openpyxl"` resuelve, pero el código actual no lo normaliza.
- **Re-creación de clients**: `ZepClient`, `OpenAI` se instancian en cada
  request. Cache singleton mejora performance.

---

## 14. Limitaciones conocidas

### Del sampler

- Solo CABA. No funciona para otras provincias (todavía).
- 15 comunas = poca variación para algunos predictores (`female`).
- Asume independencia condicional actividad × educación.
- No modela ingresos (requiere EPH).
- Personas son textualmente similares entre sí (templates).

### Del modelo ecológico (Fase C)

- R² aparente alto, pero con 15 obs puede haber overfitting.
- Factor de atenuación arbitrario (0.5).
- No captura efecto puro de género.
- Confundidos estructurales (edu ↔ ingreso) no se separan.

### De la integración

- Datos xlsx + CSV copiados al backend (15 MB).
- Config de simulación por default, no tuneado al contenido de la medida.
- Frontend de MiroFish no tiene aún UI para disparar el endpoint cohort.

### Del pipeline OASIS completo (corriente aguas abajo)

- Para correr la simulación hace falta `LLM_API_KEY`.
- OASIS itera sincrónicamente: 500 agentes × 72 rondas tarda horas.
- Modelo de agentes de OASIS tiene supuestos fuertes (ver CAMEL-AI docs).

---

## 15. Ética, legales y compliance

### Marco legal argentino aplicable

- **Ley 25.326** — Protección de Datos Personales. Aplica solo si tratáramos
  datos personales identificables. Como usamos agregados, no aplica
  directamente — pero las simulaciones podrían asemejar a perfiles reales.
- **Código Nacional Electoral** (art. 25, 30) — regula el padrón.
- **Ley de Servicios de Comunicación Audiovisual** — aplica si los
  outputs se difunden.
- **Resolución AAIP 2019** sobre datos con fines electorales — guía específica.

### Consideraciones éticas

| Escenario | Riesgo | Mitigación |
|---|---|---|
| Investigación académica | Bajo | Publicar metodología, datos abiertos, código abierto. |
| Consultoría (empresa cliente) | Medio | Contratos con alcance claro, disclaimers en reportes. |
| Producto propio (SaaS) | Medio | ToS, AUP, auditoría interna, logging de uso. |
| Asesoría en campaña política | **Alto** | Implementar "modo electoral" (ver §9.1). Considerar negarse. |
| Microtargeting persuasivo | **Muy alto** | No implementar. Ver §3 del Código de Ética APA. |

### Recomendaciones de uso responsable

1. **Disclaimer visible**: todo output debería decir "simulación basada en
   datos públicos, no es encuesta".
2. **Trazabilidad**: dejar ruta clara de qué datos, qué versión, qué seed.
3. **Reproducibilidad**: publicar metodología para que terceros puedan
   replicar.
4. **No individualizar**: nunca atribuir opinión a "una persona real".
5. **Revisión ética**: para uso en campaña, solicitar revisión externa
   (abogado, académico).

---

## 16. Referencias y fuentes

### Datos usados

- [DINE — Dirección Nacional Electoral](https://www.argentina.gob.ar/dine)
- [API DINE resultados electorales](https://resultados-electorales.argentina.apidocs.ar/)
- [Portal Datos Abiertos CABA](https://data.buenosaires.gob.ar/)
- [INDEC — Censo Nacional 2022](https://censo.gob.ar/)
- [INDEC — EPH microdatos](https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-31-58)
- [RENAPER — Estructura de población](https://datos.gob.ar/dataset/renaper-estructura-poblacion-argentina)

### Herramientas y stack

- **MiroFish** — motor base, sobre OASIS
- **OASIS** — CAMEL-AI multi-agent social simulation
- **Zep Cloud** — memoria de grafos (flujo tradicional, no cohort)
- **Python 3.11 + uv** — entorno
- **pandas, numpy, openpyxl** — procesamiento

### Método Ecological Inference

- Goodman, L. A. (1953). "Ecological regressions and the behavior of
  individuals". American Sociological Review.
- King, G. (1997). "A Solution to the Ecological Inference Problem".
- Gelman, A., Hill, J. (2006). "Data Analysis Using Regression and
  Multilevel/Hierarchical Models" (referencia MrP).

### Marco ético/legal

- [Ley 25.326 texto actualizado](https://servicios.infoleg.gob.ar/infolegInternet/anexos/60000-64999/64790/texact.htm)
- [AAIP — Protección de datos personales](https://www.argentina.gob.ar/aaip/datospersonales)
- Halabi et al. (UNLP) — datos personales en padrones electorales.

---

## 17. Apéndice: estructura de archivos

```
MiroFish/
├── research/
│   └── fase0/
│       ├── pyproject.toml              # env uv aislado
│       ├── README.md
│       ├── DOCUMENTACION.md            # ESTE archivo
│       ├── sampler/
│       │   ├── __init__.py
│       │   ├── censo_parser.py         # xlsx INDEC -> DataFrame tidy
│       │   ├── electoral_parser.py     # CSV electoral -> votos por comuna
│       │   ├── cohort_builder.py       # CohortBuilder.sample()
│       │   ├── ecological_inference.py # Fase C: OLS por party
│       │   └── oasis_adapter.py        # Perfil -> OasisProfileDict
│       ├── notebooks/
│       │   ├── 01_exploracion_caba_2023.py
│       │   ├── 02_exploracion_censo_caba.py
│       │   ├── 03_join_voto_educacion.py
│       │   ├── 04_catalogo_cuadros.py
│       │   ├── 05_inspect_actividad_c2.py
│       │   ├── 06_inspect_educacion_c3.py
│       │   ├── 07_validacion_sampler.py       # 10k agents validation (Fase 1)
│       │   ├── 08_demo_end_to_end.py          # demo reddit/twitter JSON
│       │   ├── 09_demo_slicing.py             # 4 escenarios (Fase B)
│       │   ├── 10_validacion_fase_c.py        # EI vs baseline (Fase C)
│       │   ├── 11_demo_llm_reactions.py       # demo LLM con Gemini 2.5
│       │   └── 12_reaccion_articulo.py        # URL/texto -> reaccion cohorte
│       └── data/                              # gitignored
│           ├── caba/
│           │   ├── generales_2023_caba.csv
│           │   └── establecimientos_2023.csv
│           └── censo/
│               └── c2022_caba_*.xlsx  (100+ archivos)
└── backend/
    ├── pyproject.toml                   # +deps openpyxl, numpy, pandas
    └── app/
        ├── services/
        │   ├── simulation_manager.py   # +profile_source, +_prepare_from_caba_cohort
        │   └── caba_cohort/            # MODULO NUEVO
        │       ├── __init__.py
        │       ├── source.py           # CabaCohortSource + CohortConfig
        │       ├── censo_parser.py     # copia estable de research/
        │       ├── electoral_parser.py # idem
        │       ├── cohort_builder.py   # idem
        │       ├── ecological_inference.py  # idem (Fase C)
        │       └── data/
        │           ├── generales_2023_caba.csv
        │           ├── c2022_caba_actividad_economica_c2_1.xlsx
        │           └── c2022_caba_educacion_c3_1.xlsx
        └── api/
            └── simulation.py           # +endpoint /prepare-from-cohort
└── .env                                # gitignored: LLM_API_KEY Gemini
```

### Tamaños aproximados

| Archivo | Tamaño |
|---|---|
| `generales_2023_caba.csv` | 15 MB |
| Todos los xlsx Censo CABA | ~3 MB |
| Total `research/fase0/data/` | ~18 MB |
| Código `sampler/*.py` | ~30 KB |
| Código `backend/.../caba_cohort/*.py` | ~30 KB |
| Esta documentación | ~35 KB |

---

---

## 18. Apéndice: configuración de entorno (.env)

El archivo `.env` va en la **raíz del repo MiroFish** (NO en backend/).
Está en `.gitignore` — nunca commitear.

```env
# ============================================================
# LLM Config - Gemini via OpenAI-compatible endpoint
# ============================================================
LLM_API_KEY=<tu_key_de_google_aistudio>
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL_NAME=gemini-2.5-flash

# ============================================================
# Zep Cloud - no usado en flujo cohort, opcional
# ============================================================
ZEP_API_KEY=

# ============================================================
# Flask
# ============================================================
FLASK_DEBUG=True
SECRET_KEY=cambiar-en-prod
```

### Obtener una API key de Gemini

1. Ir a https://aistudio.google.com/apikey
2. Sign in con cuenta Google
3. "Create API key"
4. Pegar en `LLM_API_KEY`

Las API keys de Google AI Studio **son gratuitas** en tier básico (15 RPM,
1M tokens/día para Gemini 2.5 Flash). Suficiente para pruebas y demos
pequeños.

### Modelos disponibles (al 2026-04-19)

Endpoint `GET {LLM_BASE_URL}/models` con `Authorization: Bearer <key>`:
- `gemini-2.5-flash` — recomendado, balanceado
- `gemini-2.5-pro` — más inteligente, más caro
- `gemini-2.0-flash-001` — versión anterior estable
- `gemini-2.0-flash-lite` — más barato, menos capaz

⚠️ `gemini-2.0-flash` (sin sufijo) está deprecado para nuevos usuarios.

### Seguridad de la key

- **NO pegarla en chat, notebooks, repos públicos, tickets.**
- Si se compromete: rotar inmediatamente en
  https://aistudio.google.com/apikey (delete + create new).
- Para producción: usar variables de entorno del orquestador
  (Kubernetes Secret, AWS SM, etc), no `.env` en disco.

---

**Fin del documento.**

Para preguntas, issues, o propuestas de mejora: revisar engram (memoria
persistente) con topic_keys `project/mirofish-electoral-caba-fase*`.
