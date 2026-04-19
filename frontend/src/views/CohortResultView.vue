<template>
  <div class="cohort-result">
    <nav class="navbar">
      <div class="nav-brand" @click="$router.push('/')">
        BUCCDESS SENSE <span class="nav-sub">— Enjambre</span>
      </div>
      <div class="nav-right">
        <button class="nav-btn-secondary" @click="$router.push('/cohort-setup')">
          ← Nueva cohorte
        </button>
      </div>
    </nav>

    <div class="content" v-if="!loading && profiles.length">
      <!-- Header con stats -->
      <header class="header">
        <div class="header-top">
          <h1>Cohorte electoral CABA · {{ profiles.length }} agentes</h1>
          <div class="sim-id">{{ simulationId }}</div>
        </div>
        <p class="subtitle" v-if="simulationRequirement">
          <span class="subtitle-label">Medida:</span> {{ simulationRequirement }}
        </p>
      </header>

      <!-- Grafo del artículo (LLM / Zep toggle) -->
      <OntologyPanel :simulation-id="simulationId" />

      <!-- Análisis agregado -->
      <section class="stats-grid">
        <div class="stat-card">
          <div class="stat-title">Distribución de voto 2023</div>
          <div class="bar-chart">
            <div v-for="(v, p) in votoDist" :key="p" class="bar-row">
              <span class="bar-label">{{ p }}</span>
              <div class="bar-track">
                <div class="bar-fill" :class="'party-' + p" :style="{ width: v + '%' }"></div>
              </div>
              <span class="bar-value">{{ v }}%</span>
            </div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-title">Nivel educativo</div>
          <div class="bar-chart">
            <div v-for="(v, e) in eduDist" :key="e" class="bar-row">
              <span class="bar-label">{{ labelEdu(e) }}</span>
              <div class="bar-track">
                <div class="bar-fill edu-bar" :style="{ width: v + '%' }"></div>
              </div>
              <span class="bar-value">{{ v }}%</span>
            </div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-title">Condición de actividad</div>
          <div class="bar-chart">
            <div v-for="(v, a) in actDist" :key="a" class="bar-row">
              <span class="bar-label">{{ labelAct(a) }}</span>
              <div class="bar-track">
                <div class="bar-fill act-bar" :style="{ width: v + '%' }"></div>
              </div>
              <span class="bar-value">{{ v }}%</span>
            </div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-title">Distribución por comuna</div>
          <div class="comuna-grid">
            <div v-for="(count, c) in comunaDist" :key="c" class="comuna-tile" :title="'Comuna ' + c + ': ' + count + ' agentes'">
              <div class="comuna-num">C{{ c }}</div>
              <div class="comuna-count">{{ count }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- Listado de agentes -->
      <section class="agents-section">
        <div class="agents-header">
          <h2>Agentes sampleados</h2>
          <div class="filter-row">
            <select v-model="filterVoto" class="filter-sel">
              <option value="">Todos los votos</option>
              <option v-for="p in parties" :key="p" :value="p">{{ p }}</option>
            </select>
            <select v-model="filterComuna" class="filter-sel">
              <option value="">Todas las comunas</option>
              <option v-for="c in comunas" :key="c" :value="c">Comuna {{ c }}</option>
            </select>
            <span class="filter-count">{{ filteredProfiles.length }} de {{ profiles.length }}</span>
          </div>
        </div>

        <div class="agents-list">
          <article
            v-for="p in filteredProfiles"
            :key="p.user_id"
            class="agent-card"
          >
            <div class="agent-head">
              <div class="agent-main">
                <div class="agent-name">{{ p.name }}</div>
                <div class="agent-meta">
                  {{ p.age }}a · {{ labelGender(p.gender) }} · @{{ p.username }}
                </div>
              </div>
              <div class="agent-badges">
                <span class="badge" :class="'party-badge-' + getVoto(p)">{{ getVoto(p) }}</span>
              </div>
            </div>
            <div class="agent-bio">{{ p.bio }}</div>
            <div class="agent-topics">
              <span v-for="t in p.interested_topics?.slice(0, 5)" :key="t" class="topic-chip">
                {{ t }}
              </span>
            </div>
            <div class="agent-actions">
              <button class="btn-chat" @click="openChat(p)">
                💬 Entrevistar
              </button>
              <button class="btn-detail" @click="selectProfile(p)">
                Ver perfil completo
              </button>
            </div>
          </article>
        </div>
      </section>

      <!-- CTA simulación OASIS -->
      <section class="cta-section">
        <h3>¿Querés ver el enjambre interactuando?</h3>
        <p>
          Disparar la simulación OASIS: los agentes van a postear, comentar y reaccionarse
          entre ellos durante <strong>{{ totalHours }} horas simuladas</strong>.
          Esto llama al LLM por cada acción de cada agente (puede tardar).
        </p>
        <button class="btn-oasis" @click="startOasis" :disabled="oasisStarting">
          {{ oasisStarting ? 'Disparando...' : '🐟 Correr simulación OASIS →' }}
        </button>
        <div v-if="oasisMsg" class="oasis-msg" :class="{ error: oasisError }">{{ oasisMsg }}</div>
      </section>
    </div>

    <!-- Modal de detalle -->
    <div v-if="selectedProfile" class="modal-backdrop" @click="closeProfile">
      <div class="modal modal-wide" @click.stop>
        <button class="modal-close" @click="closeProfile">×</button>
        <h2>{{ selectedProfile.name }}</h2>
        <div class="profile-grid">
          <div><strong>Edad:</strong> {{ selectedProfile.age }} años</div>
          <div><strong>Género:</strong> {{ labelGender(selectedProfile.gender) }}</div>
          <div><strong>MBTI:</strong> {{ selectedProfile.mbti }}</div>
          <div><strong>Profesión:</strong> {{ selectedProfile.profession }}</div>
          <div><strong>Karma:</strong> {{ selectedProfile.karma }}</div>
          <div><strong>Voto 2023:</strong> {{ getVoto(selectedProfile) }}</div>
        </div>

        <div class="modal-tabs">
          <button :class="{ active: tab === 'info' }" @click="tab = 'info'">📄 Perfil</button>
          <button :class="{ active: tab === 'chat' }" @click="tab = 'chat'">💬 Entrevista</button>
        </div>

        <div v-if="tab === 'info'" class="tab-content">
          <h3>Bio</h3>
          <p>{{ selectedProfile.bio }}</p>
          <h3>Persona (system prompt del LLM)</h3>
          <p class="persona-text">{{ selectedProfile.persona }}</p>
          <h3>Intereses</h3>
          <div class="agent-topics">
            <span v-for="t in selectedProfile.interested_topics" :key="t" class="topic-chip">{{ t }}</span>
          </div>
        </div>

        <div v-else class="tab-content chat-pane">
          <div class="chat-history" ref="chatHistoryEl">
            <div v-if="!chatMessages.length" class="chat-empty">
              Hacele una pregunta al agente. Por ejemplo: "¿Qué opinás del tarifazo?" o
              "¿Viste las noticias de hoy? ¿Qué pensás?"
            </div>
            <div
              v-for="(m, i) in chatMessages"
              :key="i"
              class="chat-msg"
              :class="'chat-' + m.role"
            >
              <div class="chat-bubble">{{ m.content }}</div>
            </div>
            <div v-if="chatLoading" class="chat-msg chat-assistant">
              <div class="chat-bubble typing">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
          <form class="chat-input-row" @submit.prevent="sendChat">
            <input
              v-model="chatInput"
              class="chat-input"
              :placeholder="`Preguntale a ${selectedProfile.name}...`"
              :disabled="chatLoading"
              @keydown.enter.exact="sendChat"
            />
            <button type="submit" class="chat-send" :disabled="chatLoading || !chatInput.trim()">
              {{ chatLoading ? '...' : 'Enviar' }}
            </button>
          </form>
          <div v-if="chatError" class="chat-error">{{ chatError }}</div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">Cargando cohorte…</div>
    <div v-if="error" class="error-box">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getSimulation,
  getSimulationProfiles,
  getSimulationConfig,
  startSimulation,
  chatWithCohortAgent,
} from '../api/simulation'
import OntologyPanel from '../components/OntologyPanel.vue'

import { nextTick } from 'vue'

const route = useRoute()
const router = useRouter()

const simulationId = route.params.simulationId
const profiles = ref([])
const simulationRequirement = ref('')
const totalHours = ref(72)
const loading = ref(true)
const error = ref('')
const selectedProfile = ref(null)

const filterVoto = ref('')
const filterComuna = ref('')

const oasisStarting = ref(false)
const oasisMsg = ref('')
const oasisError = ref(false)

const parties = ['UxP', 'JxC', 'LLA', 'FIT']

function getVoto(p) {
  const topics = p.interested_topics || []
  if (topics.includes('Milei')) return 'LLA'
  if (topics.includes('Bullrich')) return 'JxC'
  if (topics.includes('Massa')) return 'UxP'
  if (topics.includes('Bregman')) return 'FIT'
  return '?'
}

function labelGender(g) {
  return g === 'female' ? 'mujer' : g === 'male' ? 'varón' : 'otro'
}

function labelEdu(e) {
  return {
    ninguno: 'sin instrucción',
    primario: 'primario',
    secundario: 'secundario',
    terciario: 'terciario',
    universitario: 'universitario',
  }[e] || e
}

function labelAct(a) {
  return { ocupada: 'ocupado', desocupada: 'desocupado', inactiva: 'inactivo' }[a] || a
}

const comunas = computed(() => {
  const comunasSet = new Set()
  profiles.value.forEach(p => {
    const m = p.persona?.match(/Comuna (\d+)/)
    if (m) comunasSet.add(parseInt(m[1]))
  })
  return Array.from(comunasSet).sort((a, b) => a - b)
})

function getComuna(p) {
  const m = p.persona?.match(/Comuna (\d+)/)
  return m ? parseInt(m[1]) : null
}

function getEdu(p) {
  const bio = p.bio?.toLowerCase() || ''
  if (bio.includes('universitario')) return 'universitario'
  if (bio.includes('terciario')) return 'terciario'
  if (bio.includes('secundario')) return 'secundario'
  if (bio.includes('primario')) return 'primario'
  if (bio.includes('sin estudios')) return 'ninguno'
  return 'otro'
}

function getAct(p) {
  const bio = p.bio?.toLowerCase() || ''
  if (bio.includes('busca trabajo')) return 'desocupada'
  if (bio.includes('jubilado') || bio.includes('inactivo')) return 'inactiva'
  return 'ocupada'
}

const votoDist = computed(() => buildDist(profiles.value.map(getVoto)))
const eduDist = computed(() => buildDist(profiles.value.map(getEdu)))
const actDist = computed(() => buildDist(profiles.value.map(getAct)))

const comunaDist = computed(() => {
  const d = {}
  profiles.value.forEach(p => {
    const c = getComuna(p)
    if (c) d[c] = (d[c] || 0) + 1
  })
  return d
})

function buildDist(arr) {
  const counts = {}
  arr.forEach(v => { counts[v] = (counts[v] || 0) + 1 })
  const total = arr.length
  const dist = {}
  Object.entries(counts).forEach(([k, c]) => {
    dist[k] = total > 0 ? Math.round(c / total * 1000) / 10 : 0
  })
  return dist
}

const filteredProfiles = computed(() => {
  return profiles.value.filter(p => {
    if (filterVoto.value && getVoto(p) !== filterVoto.value) return false
    if (filterComuna.value && getComuna(p) !== parseInt(filterComuna.value)) return false
    return true
  })
})

function selectProfile(p) {
  selectedProfile.value = p
  tab.value = 'info'
  chatMessages.value = []
  chatError.value = ''
}

function closeProfile() {
  selectedProfile.value = null
  chatMessages.value = []
  chatInput.value = ''
  chatError.value = ''
}

function openChat(p) {
  selectedProfile.value = p
  tab.value = 'chat'
  chatMessages.value = []
  chatError.value = ''
}

// --- Chat state ---
const tab = ref('info')
const chatMessages = ref([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatError = ref('')
const chatHistoryEl = ref(null)

async function sendChat() {
  const text = chatInput.value.trim()
  if (!text || chatLoading.value || !selectedProfile.value) return
  chatError.value = ''
  chatMessages.value.push({ role: 'user', content: text })
  chatInput.value = ''
  chatLoading.value = true
  await nextTick()
  scrollChatBottom()

  try {
    const history = chatMessages.value.slice(0, -1).map(m => ({
      role: m.role, content: m.content
    }))
    const res = await chatWithCohortAgent(simulationId, {
      agent_id: selectedProfile.value.user_id,
      message: text,
      history,
    })
    if (res?.success && res.data?.reply) {
      chatMessages.value.push({ role: 'assistant', content: res.data.reply })
    } else {
      chatError.value = res?.error || 'Sin respuesta'
    }
  } catch (e) {
    chatError.value = e?.response?.data?.error || e?.message || 'Error de red'
  } finally {
    chatLoading.value = false
    await nextTick()
    scrollChatBottom()
  }
}

function scrollChatBottom() {
  if (chatHistoryEl.value) {
    chatHistoryEl.value.scrollTop = chatHistoryEl.value.scrollHeight
  }
}

async function startOasis() {
  oasisStarting.value = true
  oasisMsg.value = ''
  oasisError.value = false
  try {
    const res = await startSimulation({
      simulation_id: simulationId,
      platform: 'reddit',
    })
    if (res?.success) {
      oasisMsg.value = 'Simulación OASIS disparada. Redirigiendo...'
      setTimeout(() => {
        router.push({ name: 'CohortRun', params: { simulationId } })
      }, 1200)
    } else {
      oasisError.value = true
      oasisMsg.value = 'Error: ' + (res?.error || 'desconocido')
    }
  } catch (e) {
    oasisError.value = true
    oasisMsg.value = 'Error: ' + (e?.message || 'desconocido')
  } finally {
    oasisStarting.value = false
  }
}

onMounted(async () => {
  try {
    const [profRes, cfgRes] = await Promise.all([
      getSimulationProfiles(simulationId, 'reddit'),
      getSimulationConfig(simulationId),
    ])
    // El endpoint devuelve { success, data: { platform, count, profiles: [...] } }
    if (profRes?.success) {
      profiles.value = profRes.data?.profiles || []
    }
    if (cfgRes?.success) {
      simulationRequirement.value = cfgRes.data?.simulation_requirement || ''
      totalHours.value = cfgRes.data?.time_config?.total_simulation_hours || 72
    }
    if (!profiles.value.length) {
      error.value = 'No se encontraron perfiles para esta simulación.'
    }
  } catch (e) {
    error.value = e?.message || 'Error al cargar la cohorte'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.cohort-result {
  min-height: 100vh;
  background: #FAFAFA;
  color: #111;
  font-family: 'Space Grotesk', system-ui, sans-serif;
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
.nav-sub { color: #FF4500; font-weight: 400; font-size: 0.85rem; }
.nav-btn-secondary {
  background: transparent;
  color: #FFF;
  border: 1px solid #444;
  padding: 6px 14px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}
.nav-btn-secondary:hover { background: #FF4500; border-color: #FF4500; }
.content { max-width: 1280px; margin: 0 auto; padding: 40px; }

.header { margin-bottom: 32px; }
.header-top { display: flex; align-items: baseline; gap: 16px; justify-content: space-between; flex-wrap: wrap; }
.header h1 { margin: 0; font-size: 2rem; }
.sim-id { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #888; }
.subtitle { color: #444; line-height: 1.6; max-width: 960px; }
.subtitle-label { font-weight: 700; color: #FF4500; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-bottom: 40px; }
.stat-card { background: #FFF; border: 1px solid #E0E0E0; padding: 20px; }
.stat-title { font-weight: 600; margin-bottom: 14px; font-size: 0.95rem; color: #333; text-transform: uppercase; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; letter-spacing: 1px; }
.bar-chart { display: flex; flex-direction: column; gap: 10px; }
.bar-row { display: grid; grid-template-columns: 90px 1fr 50px; align-items: center; gap: 10px; font-size: 0.85rem; }
.bar-label { text-transform: capitalize; color: #555; }
.bar-track { height: 12px; background: #F0F0F0; border-radius: 2px; overflow: hidden; }
.bar-fill { height: 100%; background: #666; transition: width 0.4s; }
.bar-fill.party-UxP { background: #3B82F6; }
.bar-fill.party-JxC { background: #F59E0B; }
.bar-fill.party-LLA { background: #8B5CF6; }
.bar-fill.party-FIT { background: #EF4444; }
.bar-fill.edu-bar { background: #111; }
.bar-fill.act-bar { background: #FF4500; }
.bar-value { text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #333; }

.comuna-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }
.comuna-tile { background: #F5F5F5; padding: 10px; text-align: center; border: 1px solid #E0E0E0; }
.comuna-num { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.75rem; color: #FF4500; }
.comuna-count { font-size: 1.2rem; font-weight: 700; }

.agents-section { margin-bottom: 40px; }
.agents-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px; }
.agents-header h2 { margin: 0; }
.filter-row { display: flex; gap: 10px; align-items: center; }
.filter-sel { padding: 6px 10px; border: 1px solid #DDD; background: #FFF; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.filter-count { color: #888; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }

.agents-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }
.agent-card { background: #FFF; border: 1px solid #E0E0E0; padding: 20px; display: flex; flex-direction: column; gap: 12px; transition: border-color 0.15s; }
.agent-card:hover { border-color: #FF4500; }
.agent-head { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
.agent-name { font-weight: 700; font-size: 1.05rem; }
.agent-meta { font-size: 0.85rem; color: #666; margin-top: 2px; font-family: 'JetBrains Mono', monospace; }
.badge { padding: 3px 10px; font-size: 0.75rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; letter-spacing: 0.5px; }
.party-badge-UxP { background: #DBEAFE; color: #1E40AF; }
.party-badge-JxC { background: #FEF3C7; color: #92400E; }
.party-badge-LLA { background: #EDE9FE; color: #5B21B6; }
.party-badge-FIT { background: #FEE2E2; color: #991B1B; }
.agent-bio { font-size: 0.9rem; line-height: 1.5; color: #333; }
.agent-topics { display: flex; flex-wrap: wrap; gap: 4px; }
.topic-chip { font-size: 0.7rem; padding: 2px 8px; background: #F0F0F0; color: #555; border-radius: 10px; font-family: 'JetBrains Mono', monospace; }
.agent-actions { display: flex; gap: 8px; margin-top: auto; }
.btn-chat { background: #FF4500; color: #FFF; border: none; padding: 8px 14px; cursor: pointer; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 700; flex: 1; }
.btn-chat:hover { background: #FF6A33; }
.btn-detail { background: transparent; color: #333; border: 1px solid #DDD; padding: 8px 14px; cursor: pointer; font-size: 0.85rem; }
.btn-detail:hover { border-color: #333; }

.cta-section { background: #111; color: #FFF; padding: 40px; text-align: center; }
.cta-section h3 { margin: 0 0 10px 0; font-size: 1.4rem; }
.cta-section p { color: #BBB; max-width: 700px; margin: 0 auto 20px auto; line-height: 1.5; }
.btn-oasis { background: #FF4500; color: #FFF; border: none; padding: 18px 40px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 1rem; cursor: pointer; letter-spacing: 1px; }
.btn-oasis:hover:not(:disabled) { background: #FF6A33; }
.btn-oasis:disabled { background: #444; cursor: not-allowed; }
.oasis-msg { margin-top: 14px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #4ADE80; }
.oasis-msg.error { color: #F87171; }

.modal-backdrop { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 20px; }
.modal { background: #FFF; max-width: 720px; width: 100%; max-height: 90vh; overflow-y: auto; padding: 40px; position: relative; }
.modal-close { position: absolute; top: 10px; right: 15px; background: transparent; border: none; font-size: 2rem; cursor: pointer; color: #666; }
.modal h2 { margin-top: 0; }
.profile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 20px; font-size: 0.9rem; margin-bottom: 20px; padding: 15px; background: #F5F5F5; }
.persona-text { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; line-height: 1.6; background: #FAFAFA; padding: 15px; border-left: 3px solid #FF4500; }

.loading, .error-box { text-align: center; padding: 60px 20px; color: #666; font-family: 'JetBrains Mono', monospace; }
.error-box { color: #C00; background: #FEE; }

/* Modal wide + chat */
.modal.modal-wide { max-width: 820px; }
.modal-tabs { display: flex; gap: 6px; margin: 20px 0 14px 0; border-bottom: 1px solid #E5E5E5; }
.modal-tabs button {
  background: transparent;
  border: none;
  padding: 10px 18px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  color: #666;
  border-bottom: 3px solid transparent;
}
.modal-tabs button:hover { color: #FF4500; }
.modal-tabs button.active { color: #FF4500; border-bottom-color: #FF4500; font-weight: 700; }
.tab-content { min-height: 200px; }
.chat-pane { display: flex; flex-direction: column; gap: 12px; }
.chat-history {
  min-height: 300px;
  max-height: 400px;
  overflow-y: auto;
  padding: 14px;
  background: #FAFAFA;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.chat-empty { color: #888; font-size: 0.88rem; padding: 30px; text-align: center; line-height: 1.6; }
.chat-msg { display: flex; }
.chat-msg.chat-user { justify-content: flex-end; }
.chat-msg.chat-assistant { justify-content: flex-start; }
.chat-bubble {
  max-width: 75%;
  padding: 10px 14px;
  font-size: 0.9rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.chat-user .chat-bubble {
  background: #FF4500;
  color: #FFF;
  border-radius: 14px 14px 2px 14px;
}
.chat-assistant .chat-bubble {
  background: #FFF;
  color: #222;
  border: 1px solid #E5E5E5;
  border-radius: 14px 14px 14px 2px;
}
.chat-bubble.typing { display: flex; gap: 4px; padding: 14px; }
.chat-bubble.typing span {
  width: 6px; height: 6px; background: #888; border-radius: 50%;
  animation: typing 1.2s infinite ease-in-out;
}
.chat-bubble.typing span:nth-child(2) { animation-delay: 0.2s; }
.chat-bubble.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}
.chat-input-row {
  display: flex;
  gap: 8px;
}
.chat-input {
  flex: 1;
  padding: 12px 14px;
  border: 1px solid #DDD;
  font-family: 'Space Grotesk', system-ui, sans-serif;
  font-size: 0.95rem;
  outline: none;
}
.chat-input:focus { border-color: #FF4500; }
.chat-send {
  background: #FF4500;
  color: #FFF;
  border: none;
  padding: 12px 22px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 0.85rem;
}
.chat-send:hover:not(:disabled) { background: #FF6A33; }
.chat-send:disabled { background: #888; cursor: not-allowed; }
.chat-error {
  padding: 8px 12px;
  background: #FEE;
  color: #900;
  font-size: 0.85rem;
}
</style>
