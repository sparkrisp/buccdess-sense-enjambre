<template>
  <div class="cohort-setup">
    <nav class="navbar">
      <div class="nav-brand" @click="goHome">BUCCDESS SENSE <span class="nav-sub">— Enjambre</span></div>
      <div class="nav-tag">🇦🇷 COHORTE ELECTORAL CABA 2023</div>
    </nav>

    <div class="content">
      <header class="header">
        <h1>Nueva simulación desde cohorte CABA</h1>
        <p class="subtitle">
          Genera agentes sintéticos con distribución demográfica y electoral <strong>real</strong>
          del electorado porteño (INDEC Censo 2022 + DINE Generales 2023).
          Sin Zep, sin documento, directo al enjambre.
        </p>
      </header>

      <!-- Historial de cohortes: ver / duplicar / borrar -->
      <CohortHistoryList ref="historyRef" @duplicate="applyDuplicate" />

      <form class="form" @submit.prevent="submit">

        <!-- Medida / artículo -->
        <section class="card">
          <div class="card-header">
            <span class="badge">01</span>
            <h2>La medida o evento a simular</h2>
          </div>
          <p class="help">
            Pegá un artículo, anuncio o describí el evento. Esto se inyecta como
            <code>initial_post</code> en la simulación y los agentes reaccionan.
          </p>
          <textarea
            v-model="form.simulation_requirement"
            class="textarea"
            rows="10"
            placeholder="Ej: El Gobierno anuncia eliminación de subsidios al transporte público. Los aumentos llegan al 350% en subte..."
            required
          ></textarea>
          <div class="help-row">
            <span class="counter">{{ form.simulation_requirement.length }} caracteres</span>
          </div>
        </section>

        <!-- Cohorte: filtros demográficos -->
        <section class="card">
          <div class="card-header">
            <span class="badge">02</span>
            <h2>Filtros demográficos de la cohorte</h2>
          </div>

          <div class="grid-2">
            <div class="field">
              <label>Cantidad de agentes (N)</label>
              <input
                type="number"
                v-model.number="form.n"
                min="5"
                max="5000"
                class="input"
              />
              <span class="help-inline">5 - 5.000. Default recomendado: 50.</span>
            </div>

            <div class="field">
              <label>Edad mínima</label>
              <input
                type="number"
                v-model.number="form.edad_min"
                min="14"
                max="90"
                class="input"
              />
              <span class="help-inline">Legal: 16. Común: 18.</span>
            </div>
          </div>

          <div class="field">
            <label>Comunas (sin selección = toda CABA)</label>
            <div class="comunas-grid">
              <label
                v-for="c in COMUNAS"
                :key="c.id"
                class="comuna-chip"
                :class="{ selected: form.comuna.includes(c.id) }"
              >
                <input
                  type="checkbox"
                  :value="c.id"
                  v-model="form.comuna"
                />
                <span class="comuna-num">C{{ c.id }}</span>
                <span class="comuna-name">{{ c.nombre }}</span>
              </label>
            </div>
            <div class="help-row">
              <button type="button" class="link-btn" @click="selectZone('sur')">Zona sur (4, 8, 9)</button>
              <button type="button" class="link-btn" @click="selectZone('norte')">Zona norte (2, 13, 14)</button>
              <button type="button" class="link-btn" @click="selectZone('centro')">Centro (1, 3, 5, 6)</button>
              <button type="button" class="link-btn" @click="selectZone('clear')">Limpiar</button>
            </div>
          </div>

          <div class="grid-2">
            <div class="field">
              <label>
                <input type="checkbox" v-model="form.use_ecological_inference" />
                Ecological Inference
              </label>
              <span class="help-inline">
                Ajuste por perfil individual (spread voto × educación 4× más fuerte).
              </span>
            </div>

            <div class="field">
              <label>Seed (opcional, reproducibilidad)</label>
              <input
                type="number"
                v-model.number="form.seed"
                class="input"
                placeholder="ej: 2026"
              />
            </div>
          </div>
        </section>

        <!-- Plataformas -->
        <section class="card">
          <div class="card-header">
            <span class="badge">03</span>
            <h2>Plataformas simuladas</h2>
          </div>
          <div class="checkbox-row">
            <label>
              <input type="checkbox" v-model="form.enable_reddit" />
              Reddit
            </label>
            <label>
              <input type="checkbox" v-model="form.enable_twitter" />
              Twitter/X
            </label>
          </div>
          <p class="help">
            OASIS simula posts, comentarios, likes y follows en la plataforma elegida.
            Al menos una debe estar activa.
          </p>
        </section>

        <!-- Resumen + submit -->
        <section class="summary">
          <div class="summary-text">
            <strong>Vas a samplear {{ form.n }} agentes</strong>
            {{ form.comuna.length ? `de ${form.comuna.length} comuna(s)` : 'de toda CABA' }}
            con edad ≥ {{ form.edad_min }}.
            EI: {{ form.use_ecological_inference ? 'ON' : 'OFF' }}.
          </div>
          <button
            type="submit"
            class="submit-btn"
            :disabled="!canSubmit || loading"
          >
            <span v-if="!loading">Crear simulación <span class="arrow">→</span></span>
            <span v-else>Sampleando cohorte...</span>
          </button>
        </section>

        <div v-if="error" class="error-box">
          <strong>Error:</strong> {{ error }}
        </div>
      </form>
    </div>

    <!-- Modal dedup: ya existe una cohorte con estos mismos parámetros -->
    <div v-if="dedupModal" class="modal-backdrop" @click="dedupModal = null">
      <div class="modal-dedup" @click.stop>
        <h3>Ya existe una cohorte con estos parámetros</h3>
        <p>
          Encontramos una simulación con el mismo artículo y filtros.
          ¿Querés ver la existente o forzar la creación de una nueva?
        </p>
        <div class="modal-info">
          <div><strong>ID existente:</strong> <code>{{ dedupModal.simulation_id }}</code></div>
          <div><strong>Agentes:</strong> {{ dedupModal.profiles_count }}</div>
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="dedupModal = null">Cancelar</button>
          <button class="btn-force" @click="forceNewSubmit">⟳ Forzar nueva</button>
          <button class="btn-view" @click="viewExisting">→ Ver la existente</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { prepareFromCohort } from '../api/simulation'
import CohortHistoryList from '../components/CohortHistoryList.vue'

const router = useRouter()
const historyRef = ref(null)
const dedupModal = ref(null)

const COMUNAS = [
  { id: 1, nombre: 'Retiro, San Nicolás' },
  { id: 2, nombre: 'Recoleta' },
  { id: 3, nombre: 'Balvanera, San Cristóbal' },
  { id: 4, nombre: 'La Boca, Barracas' },
  { id: 5, nombre: 'Almagro, Boedo' },
  { id: 6, nombre: 'Caballito' },
  { id: 7, nombre: 'Flores, Parque Chacabuco' },
  { id: 8, nombre: 'Villa Soldati, Lugano' },
  { id: 9, nombre: 'Mataderos, Liniers' },
  { id: 10, nombre: 'Floresta, Vélez Sarsfield' },
  { id: 11, nombre: 'Villa Devoto, V. del Parque' },
  { id: 12, nombre: 'Saavedra, V. Urquiza' },
  { id: 13, nombre: 'Belgrano, Núñez, Colegiales' },
  { id: 14, nombre: 'Palermo' },
  { id: 15, nombre: 'Chacarita, V. Crespo' },
]

const form = ref({
  simulation_requirement: '',
  n: 15,
  edad_min: 18,
  comuna: [],
  seed: 2026,
  use_ecological_inference: true,
  enable_reddit: true,
  enable_twitter: false,
})

const loading = ref(false)
const error = ref('')

const canSubmit = computed(() =>
  form.value.simulation_requirement.trim().length > 10
  && form.value.n >= 5
  && (form.value.enable_reddit || form.value.enable_twitter)
)

const zones = {
  sur: [4, 8, 9],
  norte: [2, 13, 14],
  centro: [1, 3, 5, 6],
  clear: [],
}

function selectZone(zone) {
  form.value.comuna = [...zones[zone]]
}

function goHome() {
  router.push('/')
}

function buildPayload(forceNew = false) {
  return {
    simulation_requirement: form.value.simulation_requirement,
    enable_reddit: form.value.enable_reddit,
    enable_twitter: form.value.enable_twitter,
    force_new: forceNew,
    cohort_config: {
      n: form.value.n,
      edad_min: form.value.edad_min,
      comuna: form.value.comuna.length ? form.value.comuna : null,
      seed: form.value.seed,
      use_ecological_inference: form.value.use_ecological_inference,
    },
  }
}

async function submit(forceNew = false) {
  if (!canSubmit.value || loading.value) return

  loading.value = true
  error.value = ''
  dedupModal.value = null

  try {
    const res = await prepareFromCohort(buildPayload(forceNew))
    if (res?.success && res.data) {
      // Si ya existía (dedup) y NO fuerzo, mostrar modal
      if (res.data.already_exists && !forceNew) {
        dedupModal.value = res.data
        return
      }
      const simId = res.data.simulation_id
      historyRef.value?.reload?.()
      router.push({ name: 'CohortResult', params: { simulationId: simId } })
    } else {
      error.value = res?.error || 'Respuesta sin datos'
    }
  } catch (e) {
    console.error('prepareFromCohort failed:', e)
    error.value = e?.response?.data?.error || e?.message || 'Error de red'
  } finally {
    loading.value = false
  }
}

function forceNewSubmit() {
  dedupModal.value = null
  submit(true)
}

function viewExisting() {
  if (!dedupModal.value) return
  const simId = dedupModal.value.simulation_id
  dedupModal.value = null
  router.push({ name: 'CohortResult', params: { simulationId: simId } })
}

function applyDuplicate(payload) {
  if (payload.simulation_requirement) {
    form.value.simulation_requirement = payload.simulation_requirement
  }
  const cfg = payload.cohort_config || {}
  if (typeof cfg.n === 'number') form.value.n = cfg.n
  if (typeof cfg.edad_min === 'number') form.value.edad_min = cfg.edad_min
  if (Array.isArray(cfg.comuna)) form.value.comuna = [...cfg.comuna]
  else if (cfg.comuna === null) form.value.comuna = []
  if (typeof cfg.seed === 'number') form.value.seed = cfg.seed
  if (typeof cfg.use_ecological_inference === 'boolean') {
    form.value.use_ecological_inference = cfg.use_ecological_inference
  }
}
</script>

<style scoped>
.cohort-setup {
  min-height: 100vh;
  background: #FAFAFA;
  font-family: 'Space Grotesk', system-ui, sans-serif;
  color: #111;
}
.navbar {
  height: 60px;
  background: #000;
  color: #FFF;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 40px;
}
.nav-brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.2rem;
  cursor: pointer;
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.nav-sub {
  font-weight: 400;
  font-size: 0.85rem;
  letter-spacing: 0.5px;
  color: #FF4500;
}
.nav-tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  color: #FF4500;
}
.content {
  max-width: 960px;
  margin: 0 auto;
  padding: 40px;
}
.header h1 {
  font-size: 2.4rem;
  margin: 0 0 12px 0;
}
.subtitle {
  color: #555;
  line-height: 1.6;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 24px;
  margin-top: 32px;
}
.card {
  background: #FFF;
  border: 1px solid #E0E0E0;
  padding: 28px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
}
.badge {
  background: #000;
  color: #FFF;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  padding: 2px 10px;
  font-size: 0.8rem;
}
.card-header h2 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 600;
}
.help {
  color: #666;
  font-size: 0.9rem;
  margin: 0 0 14px 0;
}
.help-inline {
  color: #888;
  font-size: 0.8rem;
  display: block;
  margin-top: 4px;
}
.help-row {
  display: flex;
  gap: 12px;
  margin-top: 10px;
  justify-content: flex-end;
  flex-wrap: wrap;
}
.counter {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #999;
}
.textarea {
  width: 100%;
  padding: 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
  line-height: 1.6;
  border: 1px solid #DDD;
  background: #FAFAFA;
  resize: vertical;
  outline: none;
  box-sizing: border-box;
}
.textarea:focus { border-color: #FF4500; }
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field label {
  font-weight: 500;
  font-size: 0.9rem;
}
.input {
  padding: 10px 14px;
  border: 1px solid #DDD;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
  background: #FFF;
  outline: none;
}
.input:focus { border-color: #FF4500; }
.comunas-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
  margin-top: 6px;
}
.comuna-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid #DDD;
  background: #FFF;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.15s;
}
.comuna-chip:hover { border-color: #999; }
.comuna-chip.selected {
  border-color: #FF4500;
  background: #FFF5F0;
}
.comuna-chip input { accent-color: #FF4500; }
.comuna-num {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #FF4500;
  min-width: 28px;
}
.comuna-name {
  color: #555;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.link-btn {
  background: none;
  border: none;
  color: #FF4500;
  cursor: pointer;
  font-size: 0.8rem;
  text-decoration: underline;
  font-family: 'JetBrains Mono', monospace;
}
.checkbox-row {
  display: flex;
  gap: 24px;
}
.checkbox-row label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}
.summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 24px;
  background: #111;
  color: #FFF;
}
.summary-text {
  font-size: 0.95rem;
  line-height: 1.5;
}
.submit-btn {
  background: #FF4500;
  color: #FFF;
  border: none;
  padding: 18px 32px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 1rem;
  cursor: pointer;
  transition: background 0.2s;
  letter-spacing: 0.5px;
  white-space: nowrap;
}
.submit-btn:hover:not(:disabled) { background: #FF6A33; }
.submit-btn:disabled {
  background: #666;
  color: #AAA;
  cursor: not-allowed;
}
.arrow { margin-left: 8px; }
.error-box {
  padding: 14px 20px;
  background: #FEE;
  border-left: 4px solid #C00;
  color: #900;
  font-size: 0.9rem;
}
code {
  background: #F0F0F0;
  padding: 1px 5px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85em;
}
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 20px;
}
.modal-dedup {
  background: #FFF;
  padding: 30px;
  max-width: 520px;
  width: 100%;
}
.modal-dedup h3 { margin: 0 0 12px 0; color: #FF4500; }
.modal-dedup p { line-height: 1.5; color: #444; }
.modal-info {
  background: #FAFAFA;
  padding: 12px;
  margin: 14px 0 20px 0;
  border-left: 3px solid #FF4500;
  font-size: 0.9rem;
}
.modal-info div { margin: 2px 0; }
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
.btn-cancel {
  background: transparent;
  border: 1px solid #DDD;
  padding: 10px 18px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}
.btn-force {
  background: #333;
  color: #FFF;
  border: none;
  padding: 10px 18px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}
.btn-force:hover { background: #000; }
.btn-view {
  background: #FF4500;
  color: #FFF;
  border: none;
  padding: 10px 18px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  font-weight: 700;
}
.btn-view:hover { background: #FF6A33; }
</style>
