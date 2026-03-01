<template>
  <section class="history-view card">
    <h1>Run History</h1>
    <p class="hint">历史记录按时间展示（YYYY-MM-DD HH:mm:ss），越新越靠前。</p>
    <div v-if="!token" class="login-tip">
      <strong>尚未登录。</strong>
      登录后可查看你的运行历史、状态和耗时。
      <RouterLink class="login-tip-link" :to="{ path: '/auth', query: { redirect: '/history' } }">立即登录</RouterLink>
    </div>
    <div class="history-actions">
      <label class="history-select-all">
        <input v-model="selectAll" type="checkbox" :disabled="!rows.length || !token" />
        全选
      </label>
      <button type="button" :disabled="!selectedIds.length || deleting || !token" @click="deleteSelected">
        批量删除 ({{ selectedIds.length }})
      </button>
      <button type="button" :disabled="deleting || !token" @click="reloadRows">刷新</button>
      <span class="hint">{{ opMsg }}</span>
    </div>

    <table>
      <thead>
        <tr>
          <th style="width: 44px;"></th>
          <th>Timestamp</th>
          <th>显示ID</th>
          <th>进度</th>
          <th>Method</th>
          <th>Dataset</th>
          <th>Status</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in rows" :key="item.run_id">
          <td><input v-model="selectedIds" type="checkbox" :value="item.run_id" /></td>
          <td>{{ formatTime(item.created_at_ts) }}</td>
          <td>
            <RouterLink :to="`/result/${item.run_id}`" :title="item.run_id">{{ displayRunId(item.run_id) }}</RouterLink>
            <button class="copy-btn" type="button" @click="copyRawId(item.run_id)">复制</button>
          </td>
          <td>
            <div class="run-progress-cell">
              <span class="status-pill" :class="statusPillClass(item.status)">{{ statusLabel(item.status) }}</span>
              <span class="hint">{{ progressText(item) }}</span>
            </div>
          </td>
          <td>{{ item.method_key || '-' }}</td>
          <td>{{ item.dataset_key || '-' }}</td>
          <td>{{ item.status || '-' }}</td>
          <td>
            <button class="copy-btn" type="button" :disabled="deleting || !token" @click="deleteOne(item.run_id)">删除</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td colspan="8">暂无历史记录</td>
        </tr>
      </tbody>
    </table>
  </section>

  <div v-if="confirmVisible" class="confirm-mask" @click.self="closeConfirm(false)">
    <div class="confirm-dialog" role="dialog" aria-modal="true" aria-label="删除确认">
      <p class="confirm-message">{{ confirmMessage }}</p>
      <div class="confirm-actions">
        <button class="confirm-btn primary" type="button" @click="closeConfirm(true)">确定</button>
        <button class="confirm-btn" type="button" @click="closeConfirm(false)">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api/client'
import { getToken } from '../stores/auth'

const rows = ref([])
const selectedIds = ref([])
const deleting = ref(false)
const opMsg = ref('')
const token = ref('')
const nowTs = ref(Date.now())
const confirmVisible = ref(false)
const confirmMessage = ref('')
let confirmResolver = null
let pollTimer = null
let clockTimer = null

const selectAll = computed({
  get() {
    return rows.value.length > 0 && selectedIds.value.length === rows.value.length
  },
  set(checked) {
    selectedIds.value = checked ? rows.value.map((item) => item.run_id) : []
  }
})

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

function displayRunId(runId) {
  if (!runId) return '-'
  const m = String(runId).match(/^r(\d{8})-(\d{6})-([0-9a-zA-Z]+)$/)
  if (!m) return runId.slice(0, 12)
  const date = m[1]
  const time = m[2]
  const suffix = m[3].slice(0, 4)
  return `${date} ${time} #${suffix}`
}

function statusLabel(status) {
  if (status === 'pending') return '排队中'
  if (status === 'running') return '运行中'
  if (status === 'finished') return '已完成'
  if (status === 'failed') return '运行失败'
  if (status === 'cancelled') return '已取消'
  return '未知'
}

function statusPillClass(status) {
  if (status === 'finished') return 'is-finished'
  if (status === 'failed') return 'is-failed'
  if (status === 'cancelled') return 'is-cancelled'
  if (status === 'running') return 'is-running'
  return 'is-pending'
}

function formatSeconds(sec) {
  if (!Number.isFinite(sec) || sec < 0) return '-'
  if (sec < 60) return `${sec.toFixed(1)}s`
  const min = Math.floor(sec / 60)
  const rest = sec % 60
  return `${min}m ${rest.toFixed(1)}s`
}

function runDurationSec(item) {
  if (typeof item?.duration_sec === 'number' && item.duration_sec >= 0) return item.duration_sec
  const startedAt = Number(item?.started_at_ts || 0)
  const finishedAt = Number(item?.finished_at_ts || 0)
  if (!startedAt || !finishedAt || finishedAt < startedAt) return null
  return (finishedAt - startedAt) / 1000
}

function progressText(item) {
  if (!item) return '-'
  const status = item.status
  if (status === 'finished' || status === 'failed' || status === 'cancelled') {
    const duration = runDurationSec(item)
    return duration === null ? (status === 'cancelled' ? '已取消' : '已结束') : `总耗时 ${formatSeconds(duration)}`
  }

  const baseTs = status === 'running' ? Number(item.started_at_ts || item.created_at_ts || 0) : Number(item.created_at_ts || 0)
  if (!baseTs) return status === 'running' ? '运行中' : '等待中'
  const elapsed = Math.max(0, (nowTs.value - baseTs) / 1000)
  return status === 'running' ? `已运行 ${formatSeconds(elapsed)}` : `已等待 ${formatSeconds(elapsed)}`
}

function openConfirm(message) {
  confirmMessage.value = message
  confirmVisible.value = true
  return new Promise((resolve) => {
    confirmResolver = resolve
  })
}

function closeConfirm(confirmed) {
  confirmVisible.value = false
  if (confirmResolver) {
    confirmResolver(Boolean(confirmed))
    confirmResolver = null
  }
}

function onKeydown(e) {
  if (!confirmVisible.value) return
  if (e.key === 'Escape') closeConfirm(false)
}

async function copyRawId(runId) {
  try {
    await navigator.clipboard.writeText(runId)
  } catch {
    // Ignore clipboard failure in restricted contexts.
  }
}

async function reloadRows() {
  token.value = getToken()
  selectedIds.value = []
  opMsg.value = ''
  if (!token.value) {
    rows.value = []
    opMsg.value = '请先登录后查看运行历史'
    return
  }

  try {
    const serverRuns = await api.getMyRuns()
    rows.value = serverRuns.sort((a, b) => (b.created_at_ts || 0) - (a.created_at_ts || 0))
  } catch (err) {
    rows.value = []
    opMsg.value = err.message || '后端不可用，无法获取历史记录'
  }
}

async function deleteOne(runId) {
  if (!token.value) return
  const confirmed = await openConfirm('确认删除这条历史记录？')
  if (!confirmed) return
  deleting.value = true
  opMsg.value = ''
  try {
    const result = await api.deleteRun(runId)
    if (result.deleted > 0) {
      rows.value = rows.value.filter((item) => item.run_id !== runId)
      selectedIds.value = selectedIds.value.filter((id) => id !== runId)
      opMsg.value = '删除成功'
    } else if ((result.blocked_running || []).length) {
      opMsg.value = '运行中/排队中的任务不能删除'
    } else {
      opMsg.value = '记录不存在或已删除'
    }
  } catch (err) {
    opMsg.value = err.message || '删除失败'
  } finally {
    deleting.value = false
  }
}

async function deleteSelected() {
  if (!token.value || !selectedIds.value.length) return
  const confirmed = await openConfirm(`确认批量删除 ${selectedIds.value.length} 条历史记录？`)
  if (!confirmed) return
  deleting.value = true
  opMsg.value = ''
  try {
    const ids = [...selectedIds.value]
    const result = await api.deleteRunsBatch(ids)
    rows.value = rows.value.filter((item) => !ids.includes(item.run_id))
    selectedIds.value = []
    const blocked = (result.blocked_running || []).length
    const notFound = (result.not_found || []).length
    opMsg.value = `已删除 ${result.deleted} 条` + (blocked ? `，${blocked} 条运行中未删` : '') + (notFound ? `，${notFound} 条不存在` : '')
    if (blocked) {
      await reloadRows()
    }
  } catch (err) {
    opMsg.value = err.message || '批量删除失败'
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  token.value = getToken()
  await reloadRows()
  pollTimer = setInterval(() => {
    if (!token.value) return
    reloadRows()
  }, 5000)
  clockTimer = setInterval(() => {
    nowTs.value = Date.now()
    token.value = getToken()
  }, 1000)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  if (pollTimer) clearInterval(pollTimer)
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<style scoped>
.confirm-mask {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(11, 18, 28, 0.45);
  padding: 24px;
}

.confirm-dialog {
  width: min(420px, calc(100vw - 48px));
  border-radius: 14px;
  background: #ffffff;
  padding: 20px;
  box-shadow: 0 18px 42px rgba(11, 18, 28, 0.24);
}

.confirm-message {
  margin: 0;
  color: #0b243c;
  font-size: 16px;
  line-height: 1.5;
}

.confirm-actions {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.confirm-btn {
  min-width: 72px;
  border: 1px solid #9ddde5;
  border-radius: 999px;
  padding: 8px 16px;
  cursor: pointer;
  background: #a7ecf4;
  color: #0c4c5e;
}

.confirm-btn.primary {
  border-color: #0a7f99;
  background: #0a7f99;
  color: #ffffff;
}
</style>
