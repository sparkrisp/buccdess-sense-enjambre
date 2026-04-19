<template>
  <section class="ontology-panel">
    <div class="panel-header">
      <h2>Grafo del artículo</h2>
      <div class="header-controls">
        <div class="source-toggle">
          <button
            v-for="s in ['llm', 'zep']"
            :key="s"
            class="toggle-btn"
            :class="{ active: source === s }"
            @click="source = s"
          >
            {{ s === 'llm' ? 'LLM (Gemini)' : 'Zep Cloud' }}
          </button>
        </div>
        <button
          class="build-btn"
          @click="build"
          :disabled="building"
        >
          {{ buildLabel }}
        </button>
      </div>
    </div>

    <div v-if="error" class="error-line">{{ error }}</div>

    <div v-if="building" class="building-state">
      <div class="spinner"></div>
      <div>
        {{ source === 'llm'
          ? 'Extrayendo entidades y relaciones con Gemini...'
          : 'Zep procesando el artículo (puede tardar 30-120 segundos)...' }}
      </div>
    </div>

    <div v-else-if="!current" class="empty-state">
      Elegí una fuente y hacé click en <strong>Generar</strong>.
      <ul class="sources-help">
        <li><strong>LLM</strong>: una llamada a Gemini con structured output. Rápido (~5s), gratis con free tier.</li>
        <li><strong>Zep Cloud</strong>: GraphRAG completo con memoria temporal. Más rico pero toma ~1min y consume cuota Zep.</li>
      </ul>
    </div>

    <div v-else class="graph-layout">
      <div class="graph-viz">
        <div class="graph-meta">
          <span class="stat-pill">{{ current.stats.entity_count }} entidades</span>
          <span class="stat-pill">{{ current.stats.relationship_count }} relaciones</span>
          <span class="stat-pill" v-if="current.stats.theme_count">{{ current.stats.theme_count }} temas</span>
          <span class="stat-pill source">fuente: {{ current.source }}</span>
          <div class="zoom-controls">
            <button class="zoom-btn" @click="zoomBy(1.25)" title="Acercar">＋</button>
            <button class="zoom-btn" @click="zoomBy(0.8)" title="Alejar">−</button>
            <button class="zoom-btn" @click="resetView" title="Centrar">⊙</button>
          </div>
        </div>
        <div class="graph-hint">
          Rueda del mouse = zoom · arrastrar fondo = pan · arrastrar nodo = mover · doble click = reset
        </div>
        <svg ref="svgEl" :viewBox="`0 0 ${width} ${height}`" class="graph-svg"></svg>
      </div>

      <aside class="graph-sidebar">
        <div v-if="current.themes?.length" class="themes-block">
          <h3>Temas</h3>
          <ul>
            <li v-for="t in current.themes" :key="t">{{ t }}</li>
          </ul>
        </div>
        <div class="legend">
          <h3>Tipos de nodo</h3>
          <div v-for="(color, type) in typeColors" :key="type" class="legend-row">
            <span class="legend-dot" :style="{ background: color }"></span>
            <span>{{ type }}</span>
          </div>
        </div>
        <div class="entities-list">
          <h3>Entidades</h3>
          <div v-for="e in current.entities" :key="e.id" class="entity-row">
            <span class="entity-name">{{ e.name }}</span>
            <span class="entity-type" :style="{ color: typeColors[e.type] || '#888' }">
              {{ e.type }}
            </span>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import * as d3 from 'd3'
import { buildCohortOntology, getCohortOntology } from '../api/simulation'

const props = defineProps({
  simulationId: { type: String, required: true },
})

const source = ref('llm')
const ontologies = ref({ llm: null, zep: null })
const building = ref(false)
const error = ref('')
const svgEl = ref(null)
let zoomBehavior = null  // d3.zoom instance, para usar desde los botones

const width = 700
const height = 440

const typeColors = {
  persona: '#3B82F6',
  institucion: '#FF4500',
  grupo: '#8B5CF6',
  concepto: '#10B981',
  evento: '#EF4444',
  entity: '#666',
}

const current = computed(() => ontologies.value[source.value])

const buildLabel = computed(() => {
  if (building.value) return 'Generando...'
  return current.value ? 'Regenerar' : 'Generar'
})

async function loadCached() {
  try {
    const res = await getCohortOntology(props.simulationId)
    if (res?.success) ontologies.value = res.data || { llm: null, zep: null }
  } catch (e) { /* silencioso */ }
}

async function build() {
  building.value = true
  error.value = ''
  try {
    const res = await buildCohortOntology(props.simulationId, source.value, true)
    if (res?.success && res.data) {
      ontologies.value = { ...ontologies.value, [source.value]: res.data }
    } else {
      error.value = res?.error || 'Error desconocido'
    }
  } catch (e) {
    console.error('buildCohortOntology failed:', e)
    error.value = e?.response?.data?.error || e?.message || 'Error de red'
  } finally {
    building.value = false
  }
}

function renderGraph() {
  if (!current.value || !svgEl.value) return
  const svg = d3.select(svgEl.value)
  svg.selectAll('*').remove()

  const entities = current.value.entities || []
  const relationships = current.value.relationships || []

  if (!entities.length) return

  // Preparar nodos y links
  const nodes = entities.map(e => ({ ...e }))
  const links = relationships.map(r => ({
    source: r.from,
    target: r.to,
    label: r.label,
  }))

  const defs = svg.append('defs')
  defs.append('marker')
    .attr('id', 'arrow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 20)
    .attr('refY', 0)
    .attr('markerWidth', 5)
    .attr('markerHeight', 5)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#888')

  // Capa transformable por el zoom (todo el contenido visible va dentro)
  const zoomLayer = svg.append('g').attr('class', 'zoom-layer')

  // Fondo transparente que captura eventos de pan cuando no hay nodo
  zoomLayer.append('rect')
    .attr('x', -2000).attr('y', -2000)
    .attr('width', 4000).attr('height', 4000)
    .attr('fill', 'transparent')
    .attr('pointer-events', 'all')

  // Configurar zoom + pan en el SVG
  zoomBehavior = d3.zoom()
    .scaleExtent([0.2, 5])
    .filter((event) => {
      // Permitir zoom con wheel siempre; pan solo si no es click sobre nodo
      if (event.type === 'wheel') return true
      return !event.target.closest('.graph-node')
    })
    .on('zoom', (event) => {
      zoomLayer.attr('transform', event.transform)
    })

  svg.call(zoomBehavior)
    .on('dblclick.zoom', () => {
      svg.transition().duration(400).call(zoomBehavior.transform, d3.zoomIdentity)
    })

  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(110))
    .force('charge', d3.forceManyBody().strength(-280))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(32))

  const linkG = zoomLayer.append('g')
  const link = linkG.selectAll('g').data(links).enter().append('g')
  link.append('line')
    .attr('stroke', '#AAA')
    .attr('stroke-width', 1.2)
    .attr('marker-end', 'url(#arrow)')
  link.append('text')
    .attr('fill', '#666')
    .attr('font-size', '9px')
    .attr('font-family', 'JetBrains Mono, monospace')
    .attr('text-anchor', 'middle')
    .text(d => d.label?.slice(0, 28) || '')

  const node = zoomLayer.append('g').selectAll('g')
    .data(nodes).enter().append('g')
    .attr('class', 'graph-node')
    .style('cursor', 'grab')
    .call(d3.drag()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on('drag', (event, d) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null
        d.fy = null
      }))

  node.append('circle')
    .attr('r', 18)
    .attr('fill', d => typeColors[d.type] || '#666')
    .attr('stroke', '#FFF')
    .attr('stroke-width', 2)

  node.append('text')
    .text(d => d.name.length > 14 ? d.name.slice(0, 12) + '…' : d.name)
    .attr('text-anchor', 'middle')
    .attr('dy', 32)
    .attr('font-size', '11px')
    .attr('font-family', 'Space Grotesk, sans-serif')
    .attr('fill', '#222')
    .style('pointer-events', 'none')

  node.append('title')
    .text(d => `${d.name}\n${d.type}\n${d.role || ''}`)

  simulation.on('tick', () => {
    link.select('line')
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)
    link.select('text')
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2)
    node.attr('transform', d => `translate(${d.x}, ${d.y})`)
  })
}

watch(current, async () => {
  await nextTick()
  renderGraph()
})

function zoomBy(factor) {
  if (!svgEl.value || !zoomBehavior) return
  d3.select(svgEl.value).transition().duration(250).call(zoomBehavior.scaleBy, factor)
}

function resetView() {
  if (!svgEl.value || !zoomBehavior) return
  d3.select(svgEl.value).transition().duration(400).call(zoomBehavior.transform, d3.zoomIdentity)
}

onMounted(async () => {
  await loadCached()
  await nextTick()
  renderGraph()
})
</script>

<style scoped>
.ontology-panel {
  background: #FFF;
  border: 1px solid #E0E0E0;
  padding: 24px;
  margin-bottom: 24px;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}
.panel-header h2 {
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.header-controls {
  display: flex;
  gap: 10px;
  align-items: center;
}
.source-toggle {
  display: flex;
  border: 1px solid #DDD;
}
.toggle-btn {
  background: #FFF;
  border: none;
  padding: 8px 14px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.82rem;
  color: #666;
  border-right: 1px solid #DDD;
}
.toggle-btn:last-child { border-right: none; }
.toggle-btn:hover { background: #F5F5F5; }
.toggle-btn.active {
  background: #FF4500;
  color: #FFF;
  font-weight: 700;
}
.build-btn {
  background: #000;
  color: #FFF;
  border: none;
  padding: 8px 18px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
}
.build-btn:hover:not(:disabled) { background: #FF4500; }
.build-btn:disabled { background: #888; cursor: not-allowed; }

.error-line {
  padding: 10px;
  background: #FEE;
  color: #900;
  font-size: 0.85rem;
  margin-bottom: 12px;
}
.empty-state {
  padding: 30px;
  background: #FAFAFA;
  color: #555;
  font-size: 0.9rem;
  line-height: 1.6;
}
.sources-help {
  margin-top: 10px;
  padding-left: 20px;
}
.sources-help li { margin: 6px 0; }

.building-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 40px;
  color: #555;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
}
.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #EEE;
  border-top-color: #FF4500;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.graph-layout {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 20px;
}
@media (max-width: 900px) {
  .graph-layout { grid-template-columns: 1fr; }
}

.graph-viz { display: flex; flex-direction: column; gap: 6px; }
.graph-meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.zoom-controls {
  margin-left: auto;
  display: flex;
  gap: 4px;
}
.zoom-btn {
  width: 28px;
  height: 28px;
  background: #FFF;
  border: 1px solid #DDD;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 1rem;
  color: #333;
  line-height: 1;
  padding: 0;
}
.zoom-btn:hover { border-color: #FF4500; color: #FF4500; }
.graph-hint {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem;
  color: #999;
  padding: 0 2px;
}
.stat-pill {
  background: #F0F0F0;
  padding: 3px 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #555;
}
.stat-pill.source { color: #FF4500; font-weight: 700; }

.graph-svg {
  width: 100%;
  height: 440px;
  background: #FAFAFA;
  border: 1px solid #EEE;
  cursor: grab;
  touch-action: none;
}
.graph-svg:active { cursor: grabbing; }

.graph-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 500px;
  overflow-y: auto;
  padding-right: 6px;
}
.graph-sidebar h3 {
  margin: 0 0 8px 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #FF4500;
}
.themes-block ul {
  margin: 0;
  padding-left: 16px;
  font-size: 0.88rem;
  line-height: 1.6;
}
.legend-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.82rem;
  margin: 3px 0;
  text-transform: capitalize;
}
.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}
.entities-list { margin-top: 4px; }
.entity-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 4px 6px;
  font-size: 0.82rem;
  border-bottom: 1px solid #F0F0F0;
}
.entity-name {
  color: #222;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.entity-type {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  text-transform: capitalize;
  white-space: nowrap;
}
</style>
