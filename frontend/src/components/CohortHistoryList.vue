<template>
  <section class="cohort-history" v-if="items.length || loading">
    <div class="history-header">
      <h3>
        Cohortes anteriores
        <span class="history-count" v-if="items.length">({{ items.length }})</span>
      </h3>
      <button class="refresh-btn" @click="load" :disabled="loading" :title="'Refrescar'">
        <span v-if="loading">↻</span>
        <span v-else>⟳</span>
      </button>
    </div>

    <div v-if="loading" class="loading-state">Cargando historial...</div>

    <div v-else-if="items.length" class="history-grid">
      <article v-for="it in items" :key="it.simulation_id" class="history-card">
        <div class="card-top">
          <div class="card-meta">
            <span class="status-dot" :class="'status-' + it.status"></span>
            <span class="sim-id">{{ it.simulation_id }}</span>
            <span class="sep">·</span>
            <span class="created">{{ formatDate(it.created_at) }}</span>
          </div>
          <div class="card-profiles">
            <span class="profiles-num">{{ it.profiles_count }}</span>
            <span class="profiles-label">agentes</span>
          </div>
        </div>

        <div class="card-requirement">
          {{ truncate(it.simulation_requirement, 180) }}
        </div>

        <div class="card-filters">
          <span class="filter-tag">N={{ it.cohort_config?.n ?? '?' }}</span>
          <span class="filter-tag" v-if="it.cohort_config?.comuna?.length">
            Comunas: {{ it.cohort_config.comuna.join(', ') }}
          </span>
          <span class="filter-tag" v-else>Toda CABA</span>
          <span class="filter-tag">≥{{ it.cohort_config?.edad_min ?? 18 }}a</span>
          <span class="filter-tag" v-if="it.cohort_config?.use_ecological_inference">
            EI
          </span>
          <span class="filter-tag hash" :title="it.cohort_hash">
            #{{ it.cohort_hash?.slice(0, 8) }}
          </span>
        </div>

        <div class="card-actions">
          <button class="act-btn act-view" @click="view(it)">
            → Ver
          </button>
          <button class="act-btn act-dup" @click="duplicate(it)">
            ⟳ Duplicar
          </button>
          <button class="act-btn act-del" @click="confirmDelete(it)">
            🗑
          </button>
        </div>
      </article>
    </div>

    <!-- Confirmación delete -->
    <div v-if="toDelete" class="modal-backdrop" @click="toDelete = null">
      <div class="modal" @click.stop>
        <h3>Borrar simulación</h3>
        <p>
          ¿Borrar la cohorte <code>{{ toDelete.simulation_id }}</code> con
          {{ toDelete.profiles_count }} agentes? Esta acción no se puede deshacer.
        </p>
        <div class="modal-actions">
          <button class="btn-cancel" @click="toDelete = null">Cancelar</button>
          <button class="btn-danger" @click="performDelete">Borrar</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getCohortHistory, deleteCohortSimulation } from '../api/simulation'

const emit = defineEmits(['duplicate'])

const router = useRouter()
const items = ref([])
const loading = ref(false)
const toDelete = ref(null)

async function load() {
  loading.value = true
  try {
    const res = await getCohortHistory(50)
    if (res?.success) items.value = res.data?.items || []
  } catch (e) {
    console.error('getCohortHistory failed:', e)
  } finally {
    loading.value = false
  }
}

function formatDate(iso) {
  if (!iso) return '?'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })
      + ' ' + d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}

function truncate(s, n) {
  if (!s) return '(sin descripción)'
  return s.length > n ? s.slice(0, n) + '…' : s
}

function view(it) {
  router.push({ name: 'CohortResult', params: { simulationId: it.simulation_id } })
}

function duplicate(it) {
  emit('duplicate', {
    simulation_requirement: it.simulation_requirement,
    cohort_config: it.cohort_config,
  })
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function confirmDelete(it) {
  toDelete.value = it
}

async function performDelete() {
  if (!toDelete.value) return
  const id = toDelete.value.simulation_id
  try {
    await deleteCohortSimulation(id)
    items.value = items.value.filter(x => x.simulation_id !== id)
  } catch (e) {
    console.error('delete failed:', e)
  } finally {
    toDelete.value = null
  }
}

defineExpose({ reload: load })

onMounted(load)
</script>

<style scoped>
.cohort-history {
  background: #FFF;
  border: 1px solid #E0E0E0;
  padding: 24px;
  margin-bottom: 24px;
}
.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.history-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.history-count {
  color: #FF4500;
  font-weight: 400;
  margin-left: 4px;
}
.refresh-btn {
  background: transparent;
  border: 1px solid #DDD;
  width: 32px;
  height: 32px;
  cursor: pointer;
  font-size: 1rem;
  color: #666;
}
.refresh-btn:hover:not(:disabled) { border-color: #FF4500; color: #FF4500; }
.loading-state {
  padding: 20px;
  text-align: center;
  color: #888;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}
.history-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}
.history-card {
  background: #FAFAFA;
  border: 1px solid #E8E8E8;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color 0.15s;
}
.history-card:hover { border-color: #FF4500; }
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
}
.card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #777;
  flex-wrap: wrap;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.status-ready { background: #4ADE80; }
.status-preparing { background: #FCD34D; }
.status-failed { background: #F87171; }
.status-created, .status-running { background: #60A5FA; }
.sim-id { color: #444; font-weight: 600; }
.sep { color: #BBB; }
.card-profiles {
  text-align: right;
}
.profiles-num {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 1rem;
  color: #FF4500;
}
.profiles-label {
  font-size: 0.7rem;
  color: #888;
  margin-left: 3px;
}
.card-requirement {
  font-size: 0.85rem;
  line-height: 1.4;
  color: #333;
  min-height: 40px;
}
.card-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.filter-tag {
  background: #FFF;
  border: 1px solid #DDD;
  padding: 2px 8px;
  font-size: 0.7rem;
  font-family: 'JetBrains Mono', monospace;
  color: #555;
}
.filter-tag.hash { color: #FF4500; border-color: #FFD4C0; }
.card-actions {
  display: flex;
  gap: 6px;
  margin-top: auto;
}
.act-btn {
  padding: 6px 10px;
  border: 1px solid #DDD;
  background: #FFF;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 600;
  transition: all 0.15s;
}
.act-btn:hover { border-color: #FF4500; }
.act-view { color: #FF4500; flex: 1; }
.act-view:hover { background: #FF4500; color: #FFF; }
.act-dup { color: #333; flex: 1; }
.act-dup:hover { background: #333; color: #FFF; }
.act-del { color: #B91C1C; }
.act-del:hover { background: #B91C1C; color: #FFF; }

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 20px;
}
.modal {
  background: #FFF;
  padding: 28px;
  max-width: 480px;
  width: 100%;
}
.modal h3 { margin: 0 0 10px 0; }
.modal p { color: #555; line-height: 1.5; }
.modal code { background: #F0F0F0; padding: 2px 6px; font-family: 'JetBrains Mono', monospace; font-size: 0.85em; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.btn-cancel {
  background: transparent;
  border: 1px solid #DDD;
  padding: 10px 20px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}
.btn-danger {
  background: #B91C1C;
  color: #FFF;
  border: none;
  padding: 10px 20px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  font-weight: 700;
}
.btn-danger:hover { background: #991818; }
</style>
