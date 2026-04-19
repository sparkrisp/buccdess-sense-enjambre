<template>
  <div class="cohort-run">
    <nav class="navbar">
      <div class="nav-brand" @click="$router.push('/')">
        BUCCDESS SENSE <span class="nav-sub">— Enjambre</span>
      </div>
      <div class="nav-right">
        <button class="btn-back" @click="goToResult">← Volver a cohorte</button>
        <button v-if="isRunning" class="btn-stop" @click="stopSim" :disabled="stopping">
          {{ stopping ? 'Parando...' : '⏹ Parar simulación' }}
        </button>
      </div>
    </nav>

    <div class="content">
      <!-- Barra de progreso + stats -->
      <section class="header-stats">
        <div class="stat-block">
          <div class="stat-label">Estado</div>
          <div class="stat-value" :class="'status-' + (status?.runner_status || 'idle')">
            {{ statusLabel }}
          </div>
        </div>
        <div class="stat-block">
          <div class="stat-label">Ronda</div>
          <div class="stat-value">{{ status?.current_round ?? 0 }}/{{ status?.total_rounds ?? '?' }}</div>
        </div>
        <div class="stat-block">
          <div class="stat-label">Acciones totales</div>
          <div class="stat-value counter">{{ status?.total_actions_count ?? 0 }}</div>
        </div>
        <div class="stat-block">
          <div class="stat-label">Reddit</div>
          <div class="stat-value mini">
            <span class="platform-dot" :class="{ active: status?.reddit_running }"></span>
            {{ status?.reddit_actions_count ?? 0 }} acciones · ronda {{ status?.reddit_current_round ?? 0 }}
          </div>
        </div>
        <div class="stat-block">
          <div class="stat-label">Twitter/X</div>
          <div class="stat-value mini">
            <span class="platform-dot" :class="{ active: status?.twitter_running }"></span>
            {{ status?.twitter_actions_count ?? 0 }} acciones · ronda {{ status?.twitter_current_round ?? 0 }}
          </div>
        </div>
      </section>

      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: (status?.progress_percent ?? 0) + '%' }"></div>
      </div>
      <div class="progress-text">
        {{ Math.round(status?.progress_percent ?? 0) }}% ·
        {{ lastUpdate ? `Actualizado hace ${secondsAgo}s` : 'Esperando primera actualización...' }}
      </div>

      <!-- Contenido principal: split feed + stats -->
      <div class="main-split">
        <!-- Feed de acciones -->
        <section class="feed-panel">
          <h2>Enjambre — feed en tiempo real</h2>
          <div v-if="!actions.length && !loadingActions" class="feed-empty">
            Esperando acciones de los agentes…
          </div>
          <div class="feed-list">
            <article
              v-for="a in actions"
              :key="a.id || (a.round_num + '-' + a.agent_id + '-' + a.timestamp)"
              class="feed-item"
              :class="'platform-' + (a.platform || 'unknown')"
            >
              <div class="feed-head">
                <span class="feed-platform">{{ platformIcon(a.platform) }} {{ a.platform }}</span>
                <span class="feed-round">R{{ a.round_num }}</span>
                <span class="feed-action">{{ a.action_type }}</span>
                <span class="feed-agent" v-if="a.agent_name">
                  {{ a.agent_name }}
                  <span v-if="a.agent_meta" class="feed-agent-meta">({{ a.agent_meta }})</span>
                </span>
              </div>
              <div class="feed-content" v-if="a.action_args?.content">
                {{ decodeText(a.action_args.content).slice(0, 400) }}
                <span v-if="decodeText(a.action_args.content).length > 400">…</span>
              </div>
              <div class="feed-content target" v-else-if="a.action_args?.post_id || a.action_args?.target_id">
                → sobre {{ a.action_args.post_id || a.action_args.target_id }}
              </div>
            </article>
          </div>
        </section>

        <!-- Panel lateral: stats -->
        <aside class="stats-panel">
          <h2>Actividad por agente</h2>
          <div v-if="!agentStats.length" class="stats-empty">
            Cargando...
          </div>
          <div v-else class="agents-rank">
            <div v-for="(a, i) in agentStats.slice(0, 20)" :key="a.agent_id" class="agent-row">
              <span class="rank">{{ i + 1 }}</span>
              <span class="agent-name" :title="a.agent_name">{{ a.agent_name }}</span>
              <span class="agent-count">{{ a.action_count }}</span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getRunStatus,
  getSimulationActions,
  getAgentStats,
  getSimulationProfiles,
  stopSimulation,
} from '../api/simulation'

const route = useRoute()
const router = useRouter()

const simulationId = route.params.simulationId
const status = ref(null)
const actions = ref([])
const agentStats = ref([])
const profiles = ref([])
const lastUpdate = ref(null)
const loadingActions = ref(true)
const stopping = ref(false)
const now = ref(Date.now())

let pollHandle = null
let tickHandle = null

const isRunning = computed(() =>
  status.value?.runner_status === 'running'
  || status.value?.reddit_running
  || status.value?.twitter_running
)

const statusLabel = computed(() => {
  const s = status.value?.runner_status
  if (s === 'running') return '● Corriendo'
  if (s === 'completed') return '✓ Completada'
  if (s === 'stopped') return '■ Parada'
  if (s === 'failed') return '✗ Falló'
  return '? ' + (s || 'idle')
})

const secondsAgo = computed(() => {
  if (!lastUpdate.value) return 0
  return Math.max(0, Math.round((now.value - lastUpdate.value) / 1000))
})

const profileMap = computed(() => {
  const m = new Map()
  for (const p of profiles.value) {
    m.set(p.user_id, p)
  }
  return m
})

function platformIcon(p) {
  if (p === 'reddit') return '🔶'
  if (p === 'twitter') return '🐦'
  return '●'
}

// El backend de OASIS escribe en utf-8 pero algunos strings vienen con
// doble-encoding (utf-8 interpretado como latin-1). Detectamos y arreglamos.
function decodeText(t) {
  if (!t) return ''
  // Si no hay caracteres raros, devolver como está
  if (!/[\u00c0-\u00ff][\u00a0-\u00bf]/.test(t)) return t
  try {
    const bytes = new Uint8Array([...t].map(c => c.charCodeAt(0) & 0xff))
    return new TextDecoder('utf-8').decode(bytes)
  } catch {
    return t
  }
}

function enrichAction(a) {
  const p = profileMap.value.get(a.agent_id)
  if (p) {
    a.agent_name = p.name
    const comuna = (p.persona || '').match(/Comuna (\d+)/)?.[1]
    a.agent_meta = [comuna ? 'C' + comuna : null, p.age + 'a'].filter(Boolean).join(', ')
  } else if (a.agent_id !== undefined && a.agent_id !== null) {
    a.agent_name = 'agent_' + a.agent_id
  }
  return a
}

async function loadProfiles() {
  try {
    const res = await getSimulationProfiles(simulationId, 'reddit')
    if (res?.success) profiles.value = res.data?.profiles || []
  } catch (e) { console.warn('loadProfiles failed', e) }
}

async function pollStatus() {
  try {
    const res = await getRunStatus(simulationId)
    if (res?.success) {
      status.value = res.data
      lastUpdate.value = Date.now()
    }
  } catch (e) { console.warn('pollStatus failed', e) }
}

async function pollActions() {
  try {
    const res = await getSimulationActions(simulationId, { limit: 50 })
    if (res?.success) {
      const list = res.data?.actions || res.data || []
      actions.value = list.map(enrichAction)
      loadingActions.value = false
    }
  } catch (e) { console.warn('pollActions failed', e) }
}

async function pollAgentStats() {
  try {
    const res = await getAgentStats(simulationId)
    if (res?.success) {
      const raw = res.data?.agent_stats || res.data?.stats || res.data || []
      agentStats.value = Array.isArray(raw) ? [...raw].sort((a, b) =>
        (b.action_count || 0) - (a.action_count || 0)
      ) : []
    }
  } catch (e) { console.warn('pollAgentStats failed', e) }
}

async function tick() {
  await Promise.all([pollStatus(), pollActions(), pollAgentStats()])
}

async function stopSim() {
  stopping.value = true
  try {
    await stopSimulation({ simulation_id: simulationId })
    await tick()
  } catch (e) {
    console.error('stop failed', e)
  } finally {
    stopping.value = false
  }
}

function goToResult() {
  router.push({ name: 'CohortResult', params: { simulationId } })
}

onMounted(async () => {
  await loadProfiles()
  await tick()
  pollHandle = setInterval(tick, 3000)
  tickHandle = setInterval(() => { now.value = Date.now() }, 1000)
})

onUnmounted(() => {
  if (pollHandle) clearInterval(pollHandle)
  if (tickHandle) clearInterval(tickHandle)
})
</script>

<style scoped>
.cohort-run {
  min-height: 100vh;
  background: #0B0B0B;
  color: #E5E5E5;
  font-family: 'Space Grotesk', system-ui, sans-serif;
}
.navbar {
  height: 60px;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 40px;
  border-bottom: 1px solid #222;
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
  color: #FFF;
}
.nav-sub { color: #FF4500; font-weight: 400; font-size: 0.85rem; }
.nav-right { display: flex; gap: 12px; }
.btn-back, .btn-stop {
  background: transparent;
  color: #FFF;
  border: 1px solid #444;
  padding: 6px 14px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}
.btn-back:hover { background: #333; }
.btn-stop { border-color: #B91C1C; color: #F87171; }
.btn-stop:hover:not(:disabled) { background: #B91C1C; color: #FFF; }

.content { max-width: 1400px; margin: 0 auto; padding: 30px 40px; }

.header-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.stat-block {
  background: #141414;
  border: 1px solid #222;
  padding: 14px 18px;
}
.stat-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  color: #888;
  margin-bottom: 6px;
}
.stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.3rem;
  font-weight: 700;
  color: #FFF;
}
.stat-value.mini { font-size: 0.85rem; font-weight: 500; color: #CCC; }
.stat-value.counter { color: #FF4500; }
.status-running { color: #4ADE80; }
.status-completed { color: #60A5FA; }
.status-stopped { color: #888; }
.status-failed { color: #F87171; }
.platform-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #555;
  margin-right: 6px;
}
.platform-dot.active {
  background: #4ADE80;
  box-shadow: 0 0 8px #4ADE80;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.progress-bar {
  height: 6px;
  background: #1A1A1A;
  border: 1px solid #222;
  overflow: hidden;
  margin-bottom: 6px;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #FF4500, #FF6A33);
  transition: width 0.4s ease;
}
.progress-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #888;
  margin-bottom: 24px;
}

.main-split {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 20px;
}
@media (max-width: 1024px) {
  .main-split { grid-template-columns: 1fr; }
}

.feed-panel, .stats-panel {
  background: #141414;
  border: 1px solid #222;
  padding: 20px;
}
.feed-panel h2, .stats-panel h2 {
  margin: 0 0 16px 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  color: #FF4500;
}

.feed-empty, .stats-empty {
  padding: 40px;
  text-align: center;
  color: #666;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}
.feed-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 65vh;
  overflow-y: auto;
}
.feed-item {
  background: #0B0B0B;
  border-left: 3px solid #444;
  padding: 10px 14px;
}
.feed-item.platform-reddit { border-left-color: #FF4500; }
.feed-item.platform-twitter { border-left-color: #1DA1F2; }
.feed-head {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: #888;
  margin-bottom: 6px;
}
.feed-platform { color: #CCC; font-weight: 700; }
.feed-round {
  background: #222;
  padding: 1px 6px;
  color: #FF4500;
}
.feed-action {
  background: #1A1A1A;
  padding: 1px 6px;
  color: #4ADE80;
  text-transform: uppercase;
}
.feed-agent { color: #E5E5E5; font-weight: 600; }
.feed-agent-meta { color: #888; font-weight: 400; margin-left: 3px; }
.feed-content {
  font-size: 0.88rem;
  line-height: 1.5;
  color: #D5D5D5;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.feed-content.target { font-style: italic; color: #888; font-size: 0.82rem; }

.agents-rank {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 65vh;
  overflow-y: auto;
}
.agent-row {
  display: grid;
  grid-template-columns: 28px 1fr 50px;
  gap: 8px;
  padding: 6px 8px;
  font-size: 0.82rem;
  background: #0B0B0B;
  align-items: center;
}
.rank {
  font-family: 'JetBrains Mono', monospace;
  color: #FF4500;
  font-weight: 700;
  text-align: right;
}
.agent-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #E5E5E5;
}
.agent-count {
  font-family: 'JetBrains Mono', monospace;
  color: #4ADE80;
  font-weight: 700;
  text-align: right;
}
</style>
