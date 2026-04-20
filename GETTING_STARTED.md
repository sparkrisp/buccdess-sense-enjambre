# Getting Started — Buccdess Sense · Enjambre

Guía paso a paso para clonar, configurar y correr el proyecto en local.
Si ya tenés todo instalado, ver el [quickstart del README](./README.md).

---

## Tabla de contenidos

1. [Prerequisitos de sistema](#1-prerequisitos-de-sistema)
2. [Instalación paso a paso](#2-instalación-paso-a-paso)
3. [Obtener las API keys](#3-obtener-las-api-keys)
4. [Primer run — ver el sistema funcionando](#4-primer-run--ver-el-sistema-funcionando)
5. [Uso básico end-to-end](#5-uso-básico-end-to-end)
6. [Troubleshooting común](#6-troubleshooting-común)
7. [Seguridad y rotación de keys](#7-seguridad-y-rotación-de-keys)
8. [Comandos git útiles (fork workflow)](#8-comandos-git-útiles-fork-workflow)
9. [Smoke tests rápidos](#9-smoke-tests-rápidos)

---

## 1. Prerequisitos de sistema

Antes de clonar verificá que tenés instalado:

| Tool | Versión mínima | Cómo chequear | Cómo instalar |
|---|---|---|---|
| **Git** | 2.30+ | `git --version` | [git-scm.com](https://git-scm.com/) |
| **Node.js** | 18+ | `node -v` | [nodejs.org](https://nodejs.org/) |
| **Python** | ≥3.11, ≤3.12 | `python --version` | [python.org](https://www.python.org/) |
| **uv** | 0.4+ | `uv --version` | `pip install uv` o [docs](https://docs.astral.sh/uv/getting-started/installation/) |

**Windows**: se probó con Git Bash + PowerShell. El proyecto usa paths
unix en los scripts bash; los comandos `npm run ...` andan igual en
Windows nativo.

**macOS / Linux**: funcionar todo directo.

---

## 2. Instalación paso a paso

### 2.1 Clonar el repo

```bash
git clone https://github.com/sparkrisp/buccdess-sense-enjambre.git
cd buccdess-sense-enjambre
```

### 2.2 Crear el archivo `.env`

El proyecto necesita API keys en un archivo `.env` en la raíz. Está
gitignored por seguridad.

Creá `.env` con este contenido (mirá §3 para obtener las keys):

```env
# --- LLM: Gemini via endpoint OpenAI-compatible ---
LLM_API_KEY=<tu_key_de_google_aistudio>
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL_NAME=gemini-2.5-flash

# --- Zep Cloud: OPCIONAL ---
# Solo si querés usar el toggle Zep en el grafo del artículo.
# Si lo dejás vacío, el resto del sistema funciona igual.
ZEP_API_KEY=

# --- Flask ---
FLASK_DEBUG=True
SECRET_KEY=cualquier-string-aleatorio

# --- OASIS ---
OASIS_DEFAULT_MAX_ROUNDS=10
```

⚠️ **Importante**: `ZEP_API_KEY=` vacío está bien — el backend tiene
validación que antes pedía ZEP obligatorio. La validación ahora acepta
string vacío o placeholder para el flujo cohort. Si el arranque falla
con "ZEP_API_KEY no configurada", poné `ZEP_API_KEY=placeholder-not-used`.

### 2.3 Instalar dependencias

Un solo comando instala todo (root + frontend + backend con `uv`):

```bash
npm run setup:all
```

Si falla, probar por pasos:

```bash
# Raíz (concurrently)
npm install

# Frontend (Vue 3 + Vite + d3)
cd frontend && npm install && cd ..

# Backend (Flask + openai + camel-ai + pandas + ...)
cd backend && uv sync && cd ..
```

**Tiempos esperados**:
- Frontend: 30-60 seg
- Backend: 2-5 min (camel-ai trae muchas deps)

### 2.4 Verificar que todo instaló bien

```bash
# Python
cd backend && uv run python -c "from app.services.caba_cohort import CabaCohortSource; print('OK cohort module')"
cd ..

# Node
cd frontend && npx vite --version && cd ..
```

Si ambos imprimen sin error → seguís al §4.

---

## 3. Obtener las API keys

### 3.1 Gemini (obligatorio)

**Free tier**: 15 requests/minuto, 1 millón tokens/día con `gemini-2.5-flash`.
Suficiente para testing extenso.

1. Ir a https://aistudio.google.com/apikey
2. Sign in con cuenta Google
3. Click **"Create API key"**
4. Copiar la key (empieza con `AIza...`)
5. Pegar en `.env` como `LLM_API_KEY=AIzaSy...`

### 3.2 Zep Cloud (opcional)

Solo si querés usar el toggle **Zep** en el panel de grafo del artículo.
Sin esto, el toggle LLM (Gemini) funciona normal.

1. Ir a https://www.getzep.com/
2. Sign up (free tier)
3. Dashboard → API Keys → Create
4. Pegar en `.env` como `ZEP_API_KEY=z_...`

---

## 4. Primer run — ver el sistema funcionando

### 4.1 Levantar backend + frontend

Desde la raíz del proyecto:

```bash
npm run dev
```

Eso levanta ambos procesos en paralelo (`concurrently`):
- Backend Flask en `http://localhost:5001`
- Frontend Vite en `http://localhost:3000`

Salida esperada en consola:
```
[backend]  * Running on http://127.0.0.1:5001
[backend]    MiroFish Backend 启动完成
[frontend] VITE v7.2.x  ready in 850 ms
[frontend] ➜  Local:   http://localhost:3000/
```

### 4.2 Abrir el navegador

https://localhost:3000 debería mostrar el landing de Buccdess Sense con:
- Navbar negra con **"BUCCDESS SENSE — Enjambre"**
- Hero con logo SVG animado del enjambre
- Botón naranja **🇦🇷 CABA cohort →** arriba-derecha

Si ves todo en chino, algo falló con la migración i18n — limpiá
localStorage del browser (DevTools → Application → Local Storage → click
derecho → Clear) y recargá.

### 4.3 Healthcheck backend

En otra terminal:

```bash
curl http://localhost:5001/health
# Respuesta esperada: {"service":"MiroFish Backend","status":"ok"}
```

---

## 5. Uso básico end-to-end

Te guiamos por un flujo completo: crear cohorte, chatear con un agente,
generar grafo del artículo.

### 5.1 Crear una cohorte

1. En `/` click **🇦🇷 CABA cohort →** (navbar)
2. Te lleva a `/cohort-setup`
3. Completar el formulario:
   - **Artículo**: pegá cualquier texto — por ej. un párrafo de noticia
     sobre política argentina
   - **N agentes**: `15` (default) para ver rápido
   - **Comunas**: click link **"Zona sur (4, 8, 9)"** para auto-seleccionar
   - **Edad mínima**: `18`
   - **Ecological Inference**: ✅ activado
   - **Plataformas**: Reddit ✅ (Twitter opcional)
4. Click **"Crear simulación →"**
5. Te redirige automáticamente a `/cohort/sim_<hash>`

**Tiempo esperado**: 3-5 segundos.

### 5.2 Explorar la cohorte

En la vista de resultado vas a ver:

- **Grafo del artículo** (vacío al principio)
- **Stats agregados**: distribución de voto, educación, actividad, comunas
- **Cards de 15 agentes**: cada uno con nombre, edad, barrio, voto 2023
- Botones **🐟 Correr simulación OASIS** abajo

### 5.3 Generar el grafo del artículo

En el panel "Grafo del artículo":
- Toggle **LLM (Gemini)** (default)
- Click **Generar** → ~5 segundos
- Aparece el grafo force-directed con nodos coloreados por tipo

Podés:
- **Scroll** para zoom
- **Arrastrar el fondo** para pan
- **Arrastrar nodos**
- **Doble click** para reset

Probá switchear a **Zep Cloud** y regenerar (si tenés ZEP_API_KEY).
Tarda 30-120 seg pero te da un grafo distinto con memoria temporal.

### 5.4 Chatear con un agente

1. Click en cualquier card de agente → se abre modal
2. Tab **💬 Entrevista**
3. Escribir una pregunta en rioplatense:
   - *"¿Qué pensás del artículo?"*
   - *"¿Cambió tu opinión sobre el gobierno?"*
   - *"Si fueras presidente, ¿qué harías?"*
4. Enter o click Enviar
5. El agente responde en ~2 seg con su voz (persona del sampler)

El chat NO requiere que OASIS esté corriendo. Usa el endpoint
`/cohort/<id>/chat` que llama directo a Gemini con la persona del agente.

### 5.5 Ver el enjambre (OASIS real)

Desde `/cohort/<id>` click **🐟 Correr simulación OASIS →**

Se lanza un subprocess con `camel-ai` que simula N rondas. Los agentes
postean, comentan, likean entre sí. Frontend muestra feed en vivo:

- Estado: "Corriendo" / ronda X/72 / acciones totales
- Barra de progreso
- Feed con cada acción: `[PLATFORM] R<round> [ACTION_TYPE] <agent>: <content>`
- Ranking por cantidad de acciones

**Tiempo esperado**:
- 15 agentes × 10 rondas: 3-8 minutos
- 500 agentes × 72 rondas: 15-40 minutos

**Costo** con Gemini Free Tier: 0 hasta llegar al límite de 1M tokens/día.
Con paid: ~0.03-0.80 USD según tamaño.

---

## 6. Troubleshooting común

### 6.1 "ZEP_API_KEY no configurada" al arrancar backend

Causa: `run.py` valida que `ZEP_API_KEY` no esté vacío.

Fix: en `.env` poner:
```env
ZEP_API_KEY=placeholder-not-used-for-cohort
```

### 6.2 "No module named 'openpyxl'" o similar en backend

Causa: `uv sync` no corrió o no instaló las deps del cohort.

Fix:
```bash
cd backend && uv sync
```

### 6.3 Frontend levanta pero se ve en chino

Causa: localStorage tiene `locale=zh` de una sesión previa.

Fix opción A (UI): selector de idioma en el nav.

Fix opción B (DevTools):
```js
// En la consola del browser
localStorage.setItem('locale', 'es')
location.reload()
```

### 6.4 "Request failed with status code 404" al crear simulación

Causa: intentó cargar una view Zep con una cohorte. Los guards deberían
redirigir automáticamente.

Fix:
```bash
# Hard reload del browser
Ctrl+Shift+R

# Si persiste, reiniciar Vite
# En la terminal del frontend: Ctrl+C
npm run frontend
```

### 6.5 Grafo del artículo: "cohort_meta.json no existe"

Causa: simulación creada antes del hash dedup.

Fix: automático desde abril 2026 — el endpoint cae al fallback de leer
del `simulation_config.json`. Si persiste, crear una simulación nueva.

### 6.6 OASIS no arranca: error camel-ai

Causa: probablemente falta una dep o el modelo Gemini no es compatible
con el tool-calling de camel-ai.

Diagnóstico:
```bash
cd backend
uv run python -c "import camel_ai; print(camel_ai.__version__)"
```

Si falla: `uv sync --reinstall`.

### 6.7 "Encoding" corrupto en el contenido del artículo dentro de OASIS

Causa: bug conocido de camel-ai con Gemini — guarda texto con
double-UTF8. Cosmético.

Fix: no hay fix inmediato. Las reacciones de los agentes siguen siendo
legibles. Ver issue en el repo.

### 6.8 Port 3000 o 5001 ocupados

Fix: matar los procesos anteriores:

```bash
# Windows
netstat -ano | findstr :3000
taskkill /PID <pid> /F

# macOS/Linux
lsof -i :3000
kill -9 <pid>
```

O cambiar el puerto:
- Backend: `FLASK_PORT=5002 npm run backend`
- Frontend: editar `frontend/vite.config.js` → `server.port`

---

## 7. Seguridad y rotación de keys

### 7.1 Cuándo rotar

**ALWAYS rotar** si:
- Pegaste la key en chat (Discord, Slack, Claude, Copilot, etc)
- La tipeaste en un notebook público (Jupyter, Colab)
- Commiteaste el `.env` por error (revisar con `git log -p .env`)
- Pasó más de 90 días (buena higiene)

### 7.2 Cómo rotar

**Gemini**:
1. https://aistudio.google.com/apikey
2. Icono borrar al lado de la key vieja → confirmar
3. **Create API key** → nueva
4. Actualizar `.env` local

**Zep**:
1. https://app.getzep.com/dashboard
2. Settings → API Keys
3. Revoke la vieja
4. Create new
5. Actualizar `.env` local

### 7.3 Verificar que el `.env` nunca se subió

```bash
git log --all --pretty=format: --name-only --diff-filter=A | grep "^\.env$"
# No debería devolver nada
```

Si aparece en el log, el repo fue comprometido y hay que limpiar history
con `git filter-branch` o BFG. Contactar al maintainer.

---

## 8. Comandos git útiles (fork workflow)

```bash
# Ver remotes configurados
git remote -v
# Esperado:
#   origin    https://github.com/sparkrisp/buccdess-sense-enjambre.git
#   upstream  https://github.com/666ghj/MiroFish.git

# Pushear cambios tuyos
git add <archivos>
git commit -m "feat: nueva feature"
git push

# Traer cambios del MiroFish upstream
git fetch upstream
git merge upstream/main         # o rebase si preferís history lineal
git push                         # actualiza tu fork

# Crear una branch feature
git checkout -b feat/modo-electoral
# trabajar, commitear, pushear:
git push -u origin feat/modo-electoral

# Abrir PR desde CLI
gh pr create --web
```

---

## 9. Smoke tests rápidos

### 9.1 Sampler standalone (sin frontend)

```bash
cd backend
uv run python -c "
from app.services.caba_cohort import CabaCohortSource, CohortConfig
src = CabaCohortSource()
profiles = src.generate_profiles(CohortConfig(n=5, seed=42, use_ecological_inference=True))
for p in profiles:
    print(f'{p.user_id}: {p.name}, {p.age}a, {p.gender} - {p.bio[:80]}')
"
```

Debería imprimir 5 perfiles con datos coherentes.

### 9.2 Endpoint cohorte via test client

```bash
cd backend
uv run python -c "
from app import create_app
c = create_app().test_client()
r = c.post('/api/simulation/prepare-from-cohort', json={
    'simulation_requirement': 'Test',
    'cohort_config': {'n': 3, 'seed': 42}
})
print(r.status_code, r.get_json().get('data', {}).get('simulation_id'))
"
```

Debería imprimir `200 sim_<hash>`.

### 9.3 Frontend build (verifica compilación Vue)

```bash
cd frontend
npm run build
```

Si compila sin error → está todo OK.

### 9.4 Notebooks de research

```bash
cd research/fase0
uv sync
uv run python notebooks/07_validacion_sampler.py
```

Valida el sampler contra datos reales (10k agentes). Debería terminar
con `>>> SAMPLER VALIDADO - GO para Fase 2 <<<`.

---

## Dónde ir a continuación

- [`README.md`](./README.md) — overview general, features, créditos
- [`ARQUITECTURA.md`](./ARQUITECTURA.md) — diseño técnico, endpoints, ADRs
- [`research/fase0/DOCUMENTACION.md`](./research/fase0/DOCUMENTACION.md) — pipeline del módulo cohort (1200+ líneas)
- [`MIROFISH_UPSTREAM.md`](./MIROFISH_UPSTREAM.md) — README original del upstream

¿Encontraste algo que no está documentado? Abrí un issue en
https://github.com/sparkrisp/buccdess-sense-enjambre/issues
