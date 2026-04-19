# Fase 0 — Reconocimiento de datos (CABA Generales 2023)

Exploración inicial para validar si los datos públicos permiten construir cohortes
electorales realistas para alimentar simulaciones de MiroFish.

**Objetivo:** responder con evidencia (no a priori) si se puede joinear resultados
electorales a nivel mesa/circuito con datos socioeconómicos del Censo 2022, y obtener
perfiles demográficos que reflejen la realidad de CABA.

## Fuentes identificadas

| Fuente | Qué aporta | Granularidad | Formato | Estado |
|---|---|---|---|---|
| data.buenosaires.gob.ar | Generales 2023 CABA | Mesa | CSV | Descargado |
| INDEC Censo 2022 | Demográfico/socioeconómico | Radio censal / Comuna | XLSX | Pendiente |
| API DINE | Elecciones nacionales | Mesa | JSON via API | Pendiente (fallback) |
| INDEC EPH | Ingresos/educación | Aglomerado urbano | TXT/CSV | Pendiente (si hace falta) |

## Estructura

```
fase0/
├── data/            # CSVs crudos (gitignored)
│   ├── caba/        # data.buenosaires.gob.ar
│   ├── censo/       # INDEC Censo 2022
│   └── dine/        # API DINE (elecciones nacionales)
├── notebooks/       # Exploración Jupyter
├── pyproject.toml   # Env aislado (pandas, jupyter, requests)
└── README.md
```

## Setup

```bash
cd research/fase0
uv sync
uv run jupyter lab
```

## Descargas hechas

- `data/caba/generales_2023_caba.csv` (15 MB, 237435 filas)
  Escrutinio provisorio de Jefe de Gobierno, Legisladores y Junta Comunal.
  Columnas: seccion_id, seccion_nombre (Comuna), circuito_id, mesa_id, mesa_tipo,
  mesa_electores, cargo_nombre, agrupacion_nombre, votos_tipo, votos_cantidad
- `data/caba/establecimientos_2023.csv` (13 KB)

## Entregable de esta fase

Un notebook que responda:
1. ¿La granularidad alcanza para construir cohortes? (mesa/circuito/comuna)
2. ¿Se puede joinear con Censo 2022 sin ambigüedad geográfica?
3. ¿Qué variables demográficas quedan disponibles por zona?
4. GO/NO-GO para Fase 1 (construir sampler).
