import { getToken } from '../stores/auth'

const BASE_URL = 'http://127.0.0.1:8000'

async function request(path, options = {}, auth = false) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  }

  if (auth) {
    const token = getToken()
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
  }

  const resp = await fetch(`${BASE_URL}${path}`, { ...options, headers })
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    throw new Error(data.detail || `Request failed: ${resp.status}`)
  }
  return data
}

export const api = {
  getMethods: () => request('/public/methods'),
  getDatasets: () => request('/public/datasets'),
  getMetrics: () => request('/public/metrics'),
  register: (payload) => request('/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
  login: (payload) => request('/auth/login', { method: 'POST', body: JSON.stringify(payload) }),
  createRun: (payload) => request('/runs', { method: 'POST', body: JSON.stringify(payload) }, true),
  getRun: (id) => request(`/runs/${id}`, {}, true),
  getRunResults: (id) => request(`/runs/${id}/results`, {}, true),
  getMyRuns: () => request('/runs/me', {}, true),
  cancelRun: (id) => request(`/runs/${id}/cancel`, { method: 'POST' }, true),
  deleteRun: (id) => request(`/runs/${id}`, { method: 'DELETE' }, true),
  deleteRunsBatch: (runIds) => request('/runs/batch-delete', { method: 'POST', body: JSON.stringify({ run_ids: runIds }) }, true)
}
