const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = body.detail || ''
    } catch {
      detail = await res.text()
    }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.json()
}

export const api = {
  getProject: (id) => request(`/project/${id}`),
  createProject: (payload) => request('/project', { method: 'POST', body: JSON.stringify(payload) }),
  listProjects: () => request('/projects'),
  renameProject: (id, name) => request(`/project/${id}`, { method: 'PATCH', body: JSON.stringify({ name }) }),
  deleteProject: (id) => request(`/project/${id}`, { method: 'DELETE' }),

  createSession: (payload) => request('/session', { method: 'POST', body: JSON.stringify(payload) }),
  listSessions: (projectId) => request(`/sessions?project_id=${encodeURIComponent(projectId)}`),
  listMessages: (sessionId) => request(`/messages?session_id=${encodeURIComponent(sessionId)}`),
  renameSession: (id, name) => request(`/session/${id}`, { method: 'PATCH', body: JSON.stringify({ name }) }),
  deleteSession: (id) => request(`/session/${id}`, { method: 'DELETE' }),

  listSignals: (projectId) =>
    request(`/monitor/signals${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''}`),
  runMonitor: (payload) => request('/monitor/run', { method: 'POST', body: JSON.stringify(payload) }),

  getEvidence: (chainId) => request(`/evidence/${chainId}`),
  recentChains: (limit = 10) => request(`/evidence/recent?limit=${limit}`),
}
