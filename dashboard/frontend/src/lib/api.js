const BASE = ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'API Error')
  }
  return res.json()
}

// Organization
export const getOrg = () => request('/api/org')
export const getOrgTree = () => request('/api/org/tree')

// Agents
export const getAgents = () => request('/api/agents')
export const getAgent = (id) => request(`/api/agents/${id}`)
export const updateAgentJD = (id, content) => request(`/api/agents/${id}/jd`, { method: 'PUT', body: JSON.stringify({ content }) })
export const updateAgentResume = (id, content) => request(`/api/agents/${id}/resume`, { method: 'PUT', body: JSON.stringify({ content }) })
export const updateAgentMemory = (id, content) => request(`/api/agents/${id}/memory`, { method: 'PUT', body: JSON.stringify({ content }) })
export const updateAgentRace = (id, content) => request(`/api/agents/${id}/race`, { method: 'PUT', body: JSON.stringify({ content }) })
export const createAgent = (data) => request('/api/agents', { method: 'POST', body: JSON.stringify(data) })
export const deleteAgent = (id) => request(`/api/agents/${id}`, { method: 'DELETE' })

// Departments
export const createDepartment = (data) => request('/api/departments', { method: 'POST', body: JSON.stringify(data) })
export const deleteDepartment = (name) => request(`/api/departments/${name}`, { method: 'DELETE' })

// Contracts
export const getContracts = (params = {}) => {
  const qs = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v != null))).toString()
  return request(`/api/contracts${qs ? '?' + qs : ''}`)
}
export const getContract = (id) => request(`/api/contracts/${id}`)
export const getContractChain = (id) => request(`/api/contracts/${id}/chain`)
export const createContract = (data) => request('/api/contracts', { method: 'POST', body: JSON.stringify(data) })

// Activate
export const activate = (instruction, priority = 'medium') => request('/api/activate', { method: 'POST', body: JSON.stringify({ instruction, priority }) })
export const getActivateStatus = () => request('/api/activate/status')

// Analytics
export const getTokenStats = (range = '7d', agent = null) => {
  const params = new URLSearchParams({ range })
  if (agent) params.set('agent', agent)
  return request(`/api/analytics/tokens?${params}`)
}
export const getPerformance = (department = null) => {
  const params = department ? `?department=${department}` : ''
  return request(`/api/analytics/performance${params}`)
}
export const getCostAnalysis = () => request('/api/analytics/cost')

// Settings
export const getTools = () => request('/api/settings/tools')
export const getModels = () => request('/api/settings/models')
export const getStateMachine = () => request('/api/settings/state-machine')
export const getContractFormat = () => request('/api/settings/contract-format')
