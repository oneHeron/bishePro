<template>
  <section class="result-view">
    <h1>Task Results: {{ methodName }} on {{ datasetName }} Dataset (Task ID: {{ runId }})</h1>

    <div class="result-grid">
      <article class="graph-card">
        <div class="graph-canvas" :class="{ running: isRunning }">
          <svg v-if="canRenderViz" class="graph-svg" viewBox="0 0 1000 700" preserveAspectRatio="xMidYMid meet">
            <defs>
              <linearGradient id="graphBg" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stop-color="#f8fbff" />
                <stop offset="58%" stop-color="#eff5fb" />
                <stop offset="100%" stop-color="#e8f0f7" />
              </linearGradient>
              <filter id="nodeShadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow dx="0" dy="1.5" stdDeviation="1.8" flood-color="#274b68" flood-opacity="0.28" />
              </filter>
            </defs>
            <rect x="0" y="0" width="1000" height="700" fill="url(#graphBg)" />
            <g class="community-halo-layer">
              <circle
                v-for="bubble in communityBubbles"
                :key="`bubble-${bubble.community}`"
                :cx="bubble.x"
                :cy="bubble.y"
                :r="bubble.r"
                :fill="communityColorAlpha(bubble.community, 0.13)"
              />
            </g>
            <g class="edge-layer">
              <path
                v-for="(edge, idx) in edgeRenderList"
                :key="`e-${idx}`"
                :d="edge.d"
                fill="none"
                :stroke="edge.intra ? '#8da4b8' : '#6d859a'"
                :stroke-opacity="edge.intra ? 0.42 : 0.26"
                :stroke-width="edge.intra ? 1.9 : 1.5"
              />
            </g>
            <g class="node-layer">
              <g v-for="node in vizNodes" :key="`n-${node.node}`" filter="url(#nodeShadow)">
                <circle
                  :cx="posMap[node.node]?.x || 0"
                  :cy="posMap[node.node]?.y || 0"
                  :fill="communityColorAlpha(node.community, 0.18)"
                  r="12.5"
                />
                <circle
                  :cx="posMap[node.node]?.x || 0"
                  :cy="posMap[node.node]?.y || 0"
                  :fill="communityColor(node.community)"
                  r="9.6"
                  stroke="#f7fbff"
                  stroke-width="2.3"
                />
                <text
                  class="node-id-label"
                  :x="posMap[node.node]?.x || 0"
                  :y="posMap[node.node]?.y || 0"
                  text-anchor="middle"
                  dominant-baseline="middle"
                >
                  {{ node.node }}
                </text>
              </g>
            </g>
            <g class="community-label-layer">
              <text
                v-for="bubble in communityBubbles"
                :key="`label-${bubble.community}`"
                :x="bubble.x"
                :y="bubble.y - bubble.r - 8"
                text-anchor="middle"
              >
                C{{ bubble.community }}
              </text>
            </g>
          </svg>
          <div v-else-if="isVizDisabledForLargeGraph" class="empty-viz large-graph-empty">
            <div class="empty-viz-icon">◎</div>
            <h3>已自动切换为摘要视图</h3>
            <p>
              当前任务节点数为 <strong>{{ nodeCount }}</strong>，超过前端交互可视化阈值
              <strong>{{ vizThreshold }}</strong>。
            </p>
            <p class="hint">为保证页面流畅，已关闭拓扑绘制。你仍可查看指标、日志与社区划分结果。</p>
            <div class="empty-viz-meta">
              <span class="viz-pill">Nodes: {{ nodeCount }}</span>
              <span class="viz-pill">Threshold: {{ vizThreshold }}</span>
            </div>
            <div class="empty-viz-actions">
              <button type="button" :disabled="!assignmentRows.length" @click="downloadCommunityCsv">下载社区划分 CSV</button>
              <button type="button" @click="showLogs = !showLogs">{{ showLogs ? '收起执行日志' : '查看执行日志' }}</button>
            </div>
          </div>
          <div v-else class="hint empty-viz">暂无可视化数据。</div>
          <div v-if="isRunning" class="running-overlay">
            <span class="spinner" />
            <span>任务运行中，结果会自动刷新</span>
          </div>
        </div>
      </article>

      <div class="right-column">
        <article class="status-card">
          <div v-if="isRunning" class="running-banner">
            <span class="spinner" />
            <span>{{ run?.status === 'pending' ? '任务排队中' : '任务执行中' }}</span>
          </div>
          <p><strong>Task Status:</strong> <span :class="statusClass">{{ run?.status || '-' }}</span></p>
          <p><strong>Execution Time:</strong> {{ displayDuration }} seconds</p>
          <p><strong>Estimated Remaining:</strong> {{ estimatedRemainingText }}</p>
          <p><strong>Method:</strong> {{ methodName }}</p>
          <p><strong>Dataset:</strong> {{ datasetName }}</p>
          <p><strong>Runtime Device:</strong> {{ runtimeDeviceText }}</p>
          <p><strong>Auto Refresh:</strong> {{ autoRefreshText }}</p>
          <p v-if="latestLog"><strong>Current Step:</strong> {{ latestLog }}</p>
          <p><strong>Created Time:</strong> {{ formatTime(run?.created_at_ts) }}</p>
          <p><strong>Started Time:</strong> {{ formatTime(run?.started_at_ts) }}</p>
          <p><strong>Finished Time:</strong> {{ formatTime(run?.finished_at_ts) }}</p>
          <div v-if="runNotices.length" class="notice-box">
            <strong>Notice:</strong>
            <ul>
              <li v-for="(notice, idx) in runNotices" :key="`notice-${idx}`">{{ notice }}</li>
            </ul>
          </div>
          <p v-if="run?.error" class="msg"><strong>Error:</strong> {{ run.error }}</p>
          <div v-if="fullErrorDetail" class="error-detail-box">
            <button type="button" class="error-detail-toggle" @click="showErrorDetail = !showErrorDetail">
              {{ showErrorDetail ? 'Hide Error Detail' : 'Show Error Detail' }}
            </button>
            <pre v-if="showErrorDetail">{{ fullErrorDetail }}</pre>
          </div>
        </article>

        <article class="metrics-card">
          <table>
            <thead>
              <tr>
                <th>Evaluation Metrics</th>
                <th>Data</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in metricRows" :key="row.key">
                <td>{{ row.label }}</td>
                <td>{{ row.value }}</td>
              </tr>
              <tr v-if="!metricRows.length">
                <td v-if="isRunning" colspan="2">
                  <div class="metric-skeleton-list">
                    <div v-for="idx in 3" :key="idx" class="metric-skeleton" />
                  </div>
                </td>
                <td v-else colspan="2">No metrics yet.</td>
              </tr>
            </tbody>
          </table>
        </article>

        <div class="btn-row">
          <button
            v-if="isRunning"
            type="button"
            class="danger-btn"
            :disabled="canceling"
            @click="cancelCurrentRun"
          >
            {{ canceling ? 'Cancelling...' : 'Cancel Run' }}
          </button>
          <button type="button" @click="showLogs = !showLogs">{{ showLogs ? 'Hide Execution Logs' : 'View Execution Logs' }}</button>
          <button type="button" :disabled="!assignmentRows.length" @click="downloadCommunityCsv">Download Community CSV</button>
          <button type="button" @click="downloadResult">Download Results</button>
        </div>
        <p v-if="actionMsg" :class="actionMsgClass">{{ actionMsg }}</p>
      </div>
    </div>

    <article v-if="showLogs" class="logs-card">
      <h2>Execution Logs</h2>
      <ul>
        <li v-for="(log, idx) in run?.logs || []" :key="idx">{{ log }}</li>
      </ul>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'

const route = useRoute()
const runId = route.params.id
const run = ref(null)
const methods = ref([])
const datasets = ref([])
const showLogs = ref(false)
const showErrorDetail = ref(false)
const canceling = ref(false)
const actionMsg = ref('')
const nowTs = ref(Date.now())
const isRefreshing = ref(false)
const nextRefreshInMs = ref(1500)
const avgDurationByPair = ref({})
const pollIntervalMs = 1500
let timer = null
let clockTimer = null
let countdownTimer = null

const methodName = computed(() => methods.value.find((item) => item.key === run.value?.method_key)?.name || run.value?.method_key || '-')
const datasetName = computed(() => datasets.value.find((item) => item.key === run.value?.dataset_key)?.name || run.value?.dataset_key || '-')
const statusClass = computed(() => (run.value?.status === 'finished' ? 'ok' : run.value?.status === 'failed' ? 'msg' : 'hint'))
const isRunning = computed(() => ['pending', 'running'].includes(run.value?.status || ''))
const latestLog = computed(() => {
  const logs = run.value?.logs || []
  return logs.length ? logs[logs.length - 1] : ''
})
const runtimeDeviceText = computed(() => {
  const runtime = run.value?.results?.runtime
  if (runtime && typeof runtime === 'object') {
    const framework = String(runtime.framework || 'unknown')
    const actual = String(runtime.actual_device || 'cpu').toUpperCase()
    const requested = String(runtime.requested_device || 'cpu').toUpperCase()
    return `${actual} (requested ${requested}, ${framework})`
  }

  const logs = run.value?.logs || []
  for (let i = logs.length - 1; i >= 0; i -= 1) {
    const line = String(logs[i] || '')
    if (!line.startsWith('[runtime]')) continue
    const actualMatch = line.match(/actual=([^,]+)/)
    const reqMatch = line.match(/requested=([^,]+)/)
    const fwMatch = line.match(/framework=([^,]+)/)
    const actual = (actualMatch?.[1] || '-').trim().toUpperCase()
    const requested = (reqMatch?.[1] || '-').trim().toUpperCase()
    const framework = (fwMatch?.[1] || 'unknown').trim()
    return `${actual} (requested ${requested}, ${framework})`
  }
  return '-'
})
const displayDuration = computed(() => {
  if (!run.value) return '-'
  if (isRunning.value && run.value.started_at_ts) {
    return Math.max(0, (nowTs.value - Number(run.value.started_at_ts)) / 1000).toFixed(1)
  }
  if (typeof run.value.duration_sec === 'number') return run.value.duration_sec.toFixed(3)
  return '-'
})
const autoRefreshText = computed(() => {
  if (!isRunning.value) return 'stopped'
  const sec = Math.max(0, nextRefreshInMs.value / 1000).toFixed(1)
  return isRefreshing.value ? 'refreshing...' : `every 1.5s (next ${sec}s)`
})
const estimatedRemainingText = computed(() => {
  if (!run.value) return '-'
  const pairKey = `${run.value.method_key || ''}::${run.value.dataset_key || ''}`
  const stat = avgDurationByPair.value[pairKey]
  if (!stat || !Number.isFinite(stat.avg) || stat.avg <= 0) return 'insufficient history'
  if (!isRunning.value) return `0.0s (avg ${stat.avg.toFixed(1)}s, n=${stat.count})`

  const startedAt = Number(run.value.started_at_ts || 0)
  if (!startedAt) return `avg ${stat.avg.toFixed(1)}s (n=${stat.count})`
  const elapsed = Math.max(0, (nowTs.value - startedAt) / 1000)
  const remain = Math.max(0, stat.avg - elapsed)
  return `${remain.toFixed(1)}s (avg ${stat.avg.toFixed(1)}s, n=${stat.count})`
})

const metricRows = computed(() => {
  const metricMap = run.value?.metrics_result || run.value?.results?.metrics || {}
  return Object.entries(metricMap).map(([key, value]) => ({
    key,
    label: key.toUpperCase(),
    value: typeof value === 'number' ? value.toFixed(3) : String(value)
  }))
})
const runNotices = computed(() => {
  const notices = run.value?.results?.notices
  if (!Array.isArray(notices)) return []
  return notices.filter((item) => typeof item === 'string' && item.trim()).map((item) => item.trim())
})
const fullErrorDetail = computed(() => {
  const fromResults = run.value?.results?.error_detail
  if (typeof fromResults === 'string' && fromResults.trim()) return fromResults.trim()
  if (typeof run.value?.error === 'string' && run.value.error.trim()) return run.value.error.trim()
  return ''
})
const actionMsgClass = computed(() => (actionMsg.value.startsWith('已') ? 'ok' : 'msg'))

const assignmentRows = computed(() => run.value?.results?.community_assignment || [])
const rawVizNodes = computed(() => run.value?.results?.viz?.nodes || [])
const rawVizEdges = computed(() => run.value?.results?.viz?.edges || [])
const vizThreshold = 200
const nodeCount = computed(() => {
  const explicitCount = Number(run.value?.results?.node_count || 0)
  if (Number.isFinite(explicitCount) && explicitCount > 0) return explicitCount
  if (assignmentRows.value.length) return assignmentRows.value.length
  return rawVizNodes.value.length
})
const canRenderViz = computed(() => nodeCount.value <= vizThreshold && (assignmentRows.value.length > 0 || rawVizNodes.value.length > 0))
const vizNodes = computed(() => {
  if (!canRenderViz.value) return []
  return assignmentRows.value.length ? assignmentRows.value : rawVizNodes.value
})
const vizEdges = computed(() => (canRenderViz.value ? rawVizEdges.value : []))
const isVizDisabledForLargeGraph = computed(() => !canRenderViz.value && nodeCount.value > vizThreshold)

const posMap = computed(() => {
  const nodes = vizNodes.value
  if (!nodes.length) return {}

  const groups = new Map()
  for (const node of nodes) {
    const c = Number(node.community)
    if (!groups.has(c)) groups.set(c, [])
    groups.get(c).push(node)
  }

  const communities = [...groups.keys()].sort((a, b) => a - b)
  const out = {}
  const centerX = 500
  const centerY = 350
  const ringR = Math.min(245, 95 + communities.length * 24)
  const golden = Math.PI * (3 - Math.sqrt(5))

  communities.forEach((community, gi) => {
    const list = groups.get(community)
    const angle = golden * gi - Math.PI / 2
    const gx = centerX + ringR * 1.1 * Math.cos(angle)
    const gy = centerY + ringR * 0.82 * Math.sin(angle)
    const localR = Math.max(24, 10 + list.length * 2.25)

    list.forEach((node, ni) => {
      const t = (golden * (ni + 1)) % (2 * Math.PI)
      const spiral = localR * Math.sqrt((ni + 1) / (list.length + 0.8))
      const jitter = nodeHash(node.node) % 9
      out[node.node] = {
        x: gx + (spiral + jitter * 0.16) * Math.cos(t),
        y: gy + (spiral + jitter * 0.12) * Math.sin(t)
      }
    })
  })

  const points = Object.values(out)
  if (!points.length) return out

  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const p of points) {
    if (p.x < minX) minX = p.x
    if (p.y < minY) minY = p.y
    if (p.x > maxX) maxX = p.x
    if (p.y > maxY) maxY = p.y
  }

  const boxW = Math.max(1, maxX - minX)
  const boxH = Math.max(1, maxY - minY)
  const viewW = 1000
  const viewH = 700
  const pad = 70
  const scale = Math.min((viewW - pad * 2) / boxW, (viewH - pad * 2) / boxH)
  const fitScale = Math.max(1, Math.min(scale, 4))
  const offsetX = (viewW - boxW * fitScale) / 2 - minX * fitScale
  const offsetY = (viewH - boxH * fitScale) / 2 - minY * fitScale

  const fitted = {}
  for (const [node, p] of Object.entries(out)) {
    fitted[node] = {
      x: p.x * fitScale + offsetX,
      y: p.y * fitScale + offsetY
    }
  }
  return fitted
})

const communityBubbles = computed(() => {
  const nodes = vizNodes.value
  if (!nodes.length) return []
  const byCommunity = new Map()
  for (const node of nodes) {
    const c = Number(node.community)
    if (!byCommunity.has(c)) byCommunity.set(c, [])
    byCommunity.get(c).push(node)
  }
  const bubbles = []
  for (const [community, list] of byCommunity.entries()) {
    let sx = 0
    let sy = 0
    for (const item of list) {
      sx += posMap.value[item.node]?.x || 0
      sy += posMap.value[item.node]?.y || 0
    }
    const cx = sx / Math.max(1, list.length)
    const cy = sy / Math.max(1, list.length)
    let maxD = 16
    for (const item of list) {
      const px = posMap.value[item.node]?.x || cx
      const py = posMap.value[item.node]?.y || cy
      const d = Math.hypot(px - cx, py - cy)
      if (d > maxD) maxD = d
    }
    bubbles.push({ community, x: cx, y: cy, r: Math.min(98, maxD + 24) })
  }
  return bubbles
})

const edgeRenderList = computed(() => {
  const nodeCommunity = {}
  for (const node of vizNodes.value) nodeCommunity[node.node] = Number(node.community)
  return vizEdges.value
    .map((edge, idx) => {
      const [src, dst] = edge
      const p1 = posMap.value[src]
      const p2 = posMap.value[dst]
      if (!p1 || !p2) return null
      const mx = (p1.x + p2.x) / 2
      const my = (p1.y + p2.y) / 2
      const dx = p2.x - p1.x
      const dy = p2.y - p1.y
      const len = Math.hypot(dx, dy) || 1
      const nx = -dy / len
      const ny = dx / len
      const bendBase = ((idx % 5) - 2) * 3.6
      const bend = bendBase + ((nodeHash(`${src}|${dst}`) % 7) - 3)
      const cx = mx + nx * bend
      const cy = my + ny * bend
      return {
        intra: nodeCommunity[src] === nodeCommunity[dst],
        d: `M ${p1.x.toFixed(2)} ${p1.y.toFixed(2)} Q ${cx.toFixed(2)} ${cy.toFixed(2)} ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`
      }
    })
    .filter(Boolean)
})

function communityColor(c) {
  const palette = ['#4a81bf', '#57b589', '#e0bf67', '#cf6157', '#8a9aaa', '#58a3d1', '#b57dd6', '#6bbf85', '#e59a4d']
  const idx = Math.abs(Number(c || 0)) % palette.length
  return palette[idx]
}

function communityColorAlpha(c, alpha = 0.2) {
  const hex = communityColor(c).replace('#', '')
  const n = parseInt(hex, 16)
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function nodeHash(value) {
  const text = String(value || '')
  let h = 0
  for (let i = 0; i < text.length; i += 1) {
    h = (h * 33 + text.charCodeAt(i)) >>> 0
  }
  return h
}

function formatTime(ts) {
  if (!ts) return '-'
  const d = new Date(Number(ts))
  if (Number.isNaN(d.getTime())) return '-'
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`
}

async function load() {
  isRefreshing.value = true
  run.value = await api.getRun(runId)
  isRefreshing.value = false
  if (['finished', 'failed', 'cancelled'].includes(run.value.status) && timer) {
    clearInterval(timer)
    timer = null
    if (countdownTimer) {
      clearInterval(countdownTimer)
      countdownTimer = null
    }
  }
}

function downloadBlob(content, filename, type = 'application/json') {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function downloadResult() {
  if (!run.value) return
  downloadBlob(JSON.stringify(run.value, null, 2), `run-${runId}.json`)
}

async function downloadCommunityCsv() {
  if (!assignmentRows.value.length) return
  const lines = ['node,community']
  for (const row of assignmentRows.value) {
    lines.push(`${row.node},${row.community}`)
  }
  downloadBlob(lines.join('\n'), `run-${runId}-community.csv`, 'text/csv;charset=utf-8')
}

async function cancelCurrentRun() {
  if (!isRunning.value || canceling.value) return
  canceling.value = true
  actionMsg.value = ''
  try {
    await api.cancelRun(runId)
    actionMsg.value = '已提交取消请求，后台将终止该任务进程。'
    await load()
  } catch (err) {
    actionMsg.value = err.message || '取消失败'
  } finally {
    canceling.value = false
  }
}

onMounted(async () => {
  methods.value = await api.getMethods()
  datasets.value = await api.getDatasets()
  try {
    const history = await api.getMyRuns()
    const groups = {}
    for (const item of history || []) {
      if (item?.status !== 'finished') continue
      if (typeof item?.duration_sec !== 'number' || item.duration_sec <= 0) continue
      const key = `${item.method_key || ''}::${item.dataset_key || ''}`
      if (!groups[key]) groups[key] = { sum: 0, count: 0 }
      groups[key].sum += item.duration_sec
      groups[key].count += 1
    }
    const stats = {}
    for (const [key, value] of Object.entries(groups)) {
      if (!value.count) continue
      stats[key] = { avg: value.sum / value.count, count: value.count }
    }
    avgDurationByPair.value = stats
  } catch {
    avgDurationByPair.value = {}
  }
  await load()
  nowTs.value = Date.now()
  clockTimer = setInterval(() => {
    nowTs.value = Date.now()
  }, 1000)
  nextRefreshInMs.value = pollIntervalMs
  timer = setInterval(() => {
    nextRefreshInMs.value = pollIntervalMs
    load()
  }, pollIntervalMs)
  countdownTimer = setInterval(() => {
    nextRefreshInMs.value = Math.max(0, nextRefreshInMs.value - 100)
  }, 100)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (clockTimer) clearInterval(clockTimer)
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>
