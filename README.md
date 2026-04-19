# Buccdess Sense — Enjambre

> Simulación de opinión pública con agentes sintéticos cuya distribución
> demográfica y electoral refleja la realidad del electorado argentino.

[![Fork of MiroFish](https://img.shields.io/badge/fork%20of-666ghj/MiroFish-blue?style=flat-square)](https://github.com/666ghj/MiroFish)
[![License AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-green?style=flat-square)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org/)
[![Vue 3](https://img.shields.io/badge/vue-3.x-42b883?style=flat-square)](https://vuejs.org/)

Extensión de [MiroFish](https://github.com/666ghj/MiroFish) que agrega un
pipeline alternativo para generar cohortes de agentes LLM con **distribución
demográfica y preferencia electoral real** (INDEC Censo 2022 + DINE
Generales 2023). Caso de uso inicial: CABA.

- Pegás un artículo/medida
- Elegís N agentes con filtros (comunas, edad, educación)
- Se samplean con **Ecological Inference Goodman** sobre datos reales
- Chateás con cada agente, visualizás el grafo del artículo, corrés OASIS
  y ves el enjambre interactuar

---

## Quickstart

### Prerequisitos

| Tool | Versión | Chequear |
|---|---|---|
| Node.js | 18+ | `node -v` |
| Python | ≥3.11, ≤3.12 | `python --version` |
| uv | Latest | `uv --version` |

### Setup

```bash
git clone <URL_DE_ESTE_REPO>
cd Buccdess-Sense-Enjambre

# 1. Variables de entorno
cp .env.example .env
# Editar .env y completar LLM_API_KEY (Gemini free tier:
# https://aistudio.google.com/apikey)
# ZEP_API_KEY es opcional (solo si querés usar el grafo Zep del artículo)

# 2. Dependencias (root + frontend + backend)
npm run setup:all

# 3. Correr
npm run dev
```

- Frontend: `http://localhost:3000/`
- Backend: `http://localhost:5001/`

### Variables mínimas en `.env`

```env
LLM_API_KEY=<tu_key_de_google_aistudio>
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL_NAME=gemini-2.5-flash

ZEP_API_KEY=<opcional, para flujo Zep>
```

---

## Workflow (flujo cohort CABA)

```
┌───────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 1. Pegás el   │→  │ 2. Sampleás  │→  │ 3. Chateás   │→  │ 4. Corrés    │
│    artículo + │   │    N agentes │   │    con cada  │   │    OASIS:    │
│    filtros    │   │    con EI    │   │    agente /  │   │    enjambre  │
│    demográf.  │   │              │   │    ves grafo │   │    en vivo   │
└───────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
```

1. En la landing, click en **🇦🇷 CABA cohort** (navbar arriba-derecha)
2. **Formulario de cohorte**: artículo/URL + comunas + N + EI
3. **Vista de resultados**: stats demográficos + grafo del artículo
   (LLM o Zep) + 15/50/N cards de agentes
4. Click en **💬 Entrevistar** → modal con chat directo al agente
5. Click en **🐟 Correr simulación OASIS** → enjambre paralelo Reddit+Twitter

---

## Documentación

- [`ARQUITECTURA.md`](./ARQUITECTURA.md) — diseño técnico completo:
  componentes, flujos, endpoints, ADRs, seguridad, extensión.
- [`research/fase0/DOCUMENTACION.md`](./research/fase0/DOCUMENTACION.md)
  — pipeline completo del módulo cohort: fases 0/1/2/B/C, sampler,
  Ecological Inference, validaciones, costos, limitaciones, ética.
- [`MIROFISH_UPSTREAM.md`](./MIROFISH_UPSTREAM.md) — README original de
  MiroFish (preservado por atribución).

---

## Datos usados

**Electoral** (`data.buenosaires.gob.ar`):
- `generales_2023_caba.csv` — 237k filas a nivel **mesa** (15 comunas,
  167 circuitos, 8770 mesas, 4 agrupaciones, cargos JEF/LEG/COM)

**Censo INDEC 2022** (`censo.gob.ar`):
- `actividad_economica_c2` — ocupada/desocupada/inactiva por comuna × sexo × edad
- `educacion_c3` — máximo nivel alcanzado por comuna × sexo × edad

Ambos son **datos públicos agregados**, sin PII. Ver
[§7 del documento del módulo](./research/fase0/DOCUMENTACION.md#4-fase-0--reconocimiento-de-datos).

---

## Features (vs MiroFish upstream)

Lo que agrega este fork:

- 🇦🇷 **Sampler demográfico-electoral CABA** con Ecological Inference
- 📄 **Grafo del artículo** con toggle LLM (Gemini) / Zep Cloud +
  visualización d3.js force-directed interactiva (zoom, pan, drag)
- 💬 **Chat directo con agentes** sin necesidad de OASIS corriendo
- 🗂 **Historial de cohortes** con deduplicación por hash SHA-256
- 🎯 **Run view cohort** con feed de acciones en vivo + ranking por agente
- 🌐 **Idioma español rioplatense** por defecto (migración automática
  desde zh/en guardado previo)
- 🇦🇷 **Rebrand visual** (logo SVG de enjambre, tipografía, paleta)

No toca el flujo original de MiroFish (Zep + documento + ontología + 5-step
wizard + ReportAgent). Ambos conviven.

---

## Stack

**Backend**: Flask 3 · Python 3.11 · uv · OpenAI SDK (Gemini 2.5 Flash
compatible) · camel-oasis · camel-ai · Zep Cloud SDK (opcional) ·
pandas · openpyxl · numpy · pydantic

**Frontend**: Vue 3 · Vite 7 · vue-router · vue-i18n · axios · d3.js

**Persistencia**: archivos en `backend/uploads/simulations/<id>/` +
SQLite por simulación OASIS.

---

## Estado

**Versión**: v0.1-Preview (fork sobre MiroFish v0.1)

**Fases implementadas** (ver
[DOCUMENTACION.md](./research/fase0/DOCUMENTACION.md)):
- ✅ Fase 0 — Reconocimiento de datos
- ✅ Fase 1 — Sampler con validación 10k agentes
- ✅ Fase 2 — Integración al backend (endpoint + módulo productivo)
- ✅ Fase B — Demo de slicings con 4 escenarios reales
- ✅ Fase C — Ecological Inference Goodman
- ✅ Uso end-to-end con artículo real (La Nación) + LLM reactions
- ✅ UI completa: setup / result / run / chat / ontología / historial

**Planificado** (ver §10 de DOCUMENTACION):
- ⏳ Fase D — modo electoral (audit trail, disclaimers, TTL, compliance
  AAIP Argentina)
- ⏳ Extensión geográfica (Provincia de Buenos Aires, nacionales)
- ⏳ Microdata + MrP real (si se consigue fuente legítima)

---

## Agradecimientos

- **MiroFish** (666ghj/MiroFish) — motor base de simulación multi-agente
  sobre OASIS/CAMEL-AI. Mantenido por Shanda Group.
- **CAMEL-AI team** — OASIS (Open Agent Social Interaction Simulations).
- **INDEC** y **DINE** — por publicar los datos en formato abierto.

---

## Licencia

AGPL-3.0 — igual que el upstream MiroFish.
