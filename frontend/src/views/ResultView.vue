<template>
  <section class="result-view">
    <h1>Task Results: {{ methodName }} on {{ datasetName }} Dataset (Task ID: {{ runId }})</h1>

    <div class="result-grid">
      <article class="graph-card">
        <div class="graph-canvas" :class="{ running: isRunning }">
          <svg v-if="vizNodes.length" class="graph-svg" viewBox="0 0 1000 700" preserveAspectRatio="xMidYMid meet">
            <line
              v-for="(edge, idx) in vizEdges"
              :key="`e-${idx}`"
              :x1="posMap[edge[0]]?.x || 0"
              :y1="posMap[edge[0]]?.y || 0"
              :x2="posMap[edge[1]]?.x || 0"
              :y2="posMap[edge[1]]?.y || 0"
              stroke="#95a9b8"
              stroke-opacity="0.45"
              stroke-width="2"
            />
            <circle
              v-for="node in vizNodes"
              :key="`n-${node.node}`"
              :cx="posMap[node.node]?.x || 0"
              :cy="posMap[node.node]?.y || 0"
              :fill="communityColor(node.community)"
              r="9"
              stroke="#ffffff"
              stroke-width="2"
            />
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
          <p><strong>Auto Refresh:</strong> {{ autoRefreshText }}</p>
          <p v-if="latestLog"><strong>Current Step:</strong> {{ latestLog }}</p>
          <p><strong>Created Time:</strong> {{ formatTime(run?.created_at_ts) }}</p>
          <p><strong>Started Time:</strong> {{ formatTime(run?.started_at_ts) }}</p>
          <p><strong>Finished Time:</strong> {{ formatTime(run?.finished_at_ts) }}</p>
          <p v-if="run?.error" class="msg"><strong>Error:</strong> {{ run.error }}</p>
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
          <button type="button" @click="showLogs = !showLogs">{{ showLogs ? 'Hide Execution Logs' : 'View Execution Logs' }}</button>
          <button type="button" :disabled="!assignmentRows.length" @click="downloadCommunityCsv">Download Community CSV</button>
          <button type="button" @click="downloadResult">Download Results</button>
        </div>
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

const assignmentRows = computed(() => run.value?.results?.community_assignment || [])
const vizNodes = computed(() => run.value?.results?.viz?.nodes || [])
const vizEdges = computed(() => run.value?.results?.viz?.edges || [])
const vizThreshold = 100
const nodeCount = computed(() => {
  const explicitCount = Number(run.value?.results?.node_count || 0)
  if (Number.isFinite(explicitCount) && explicitCount > 0) return explicitCount
  if (assignmentRows.value.length) return assignmentRows.value.length
  return vizNodes.value.length
})
const isVizDisabledForLargeGraph = computed(() => !vizNodes.value.length && nodeCount.value >= vizThreshold)

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
  const ringR = Math.min(280, 120 + communities.length * 20)

  communities.forEach((community, gi) => {
    const list = groups.get(community)
    const angle = (2 * Math.PI * gi) / Math.max(1, communities.length)
    const gx = centerX + ringR * Math.cos(angle)
    const gy = centerY + ringR * Math.sin(angle)
    const localR = Math.max(28, 14 + list.length * 1.8)

    list.forEach((node, ni) => {
      const a = (2 * Math.PI * ni) / Math.max(1, list.length)
      out[node.node] = {
        x: gx + localR * Math.cos(a),
        y: gy + localR * Math.sin(a)
      }
    })
  })

  return out
})

function communityColor(c) {
  const palette = ['#4a81bf', '#57b589', '#e0bf67', '#cf6157', '#8a9aaa', '#58a3d1', '#b57dd6', '#6bbf85', '#e59a4d']
  const idx = Math.abs(Number(c || 0)) % palette.length
  return palette[idx]
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
  if (['finished', 'failed'].includes(run.value.status) && timer) {
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
