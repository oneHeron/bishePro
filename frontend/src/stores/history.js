const RUN_HISTORY_KEY = 'community_platform_run_history'

function normalizeRecord(entry) {
  if (!entry) return null
  if (typeof entry === 'string') {
    return { run_id: entry, created_at_ts: Date.now() }
  }
  if (!entry.run_id) return null
  return {
    run_id: entry.run_id,
    created_at_ts: Number(entry.created_at_ts) || Date.now()
  }
}

export function pushRunId(runId, createdAtTs = Date.now()) {
  const items = getRunHistory()
  const exists = items.some((item) => item.run_id === runId)
  if (!exists) {
    items.unshift({ run_id: runId, created_at_ts: createdAtTs })
    localStorage.setItem(RUN_HISTORY_KEY, JSON.stringify(items.slice(0, 50)))
  }
}

export function getRunHistory() {
  try {
    const raw = localStorage.getItem(RUN_HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.map(normalizeRecord).filter(Boolean)
  } catch {
    return []
  }
}

export function clearRunHistory() {
  localStorage.removeItem(RUN_HISTORY_KEY)
}
