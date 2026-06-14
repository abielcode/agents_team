import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (r) => r.data,
  (err) => Promise.reject(err.response?.data?.detail || err.message)
)

// ── Projects ──────────────────────────────────────────────
export const listProjects = () => api.get('/projects/')
export const createProject = (data) => api.post('/projects/', data)
export const pickFolder = () => api.post('/projects/pick-folder')
export const getProject = (id) => api.get(`/projects/${id}`)
export const updateProject = (id, data) => api.patch(`/projects/${id}`, data)
export const deleteProject = (id) => api.delete(`/projects/${id}`)

// ── PRD ───────────────────────────────────────────────────
export const getPRD = (projectId) => api.get(`/projects/${projectId}/prd/`)
export const refinePRD = (projectId, rawInput) =>
  api.post(`/projects/${projectId}/prd/refine`, { raw_input: rawInput })
export const updatePRD = (projectId, prdId, data) =>
  api.patch(`/projects/${projectId}/prd/${prdId}`, data)
export const approvePRD = (projectId, prdId) =>
  api.post(`/projects/${projectId}/prd/${prdId}/approve`)

// ── Backlog ───────────────────────────────────────────────
export const getBacklog = (projectId) => api.get(`/projects/${projectId}/backlog/`)
export const createStory = (projectId, data) =>
  api.post(`/projects/${projectId}/backlog/stories`, data)
export const updateStory = (projectId, storyId, data) =>
  api.patch(`/projects/${projectId}/backlog/stories/${storyId}`, data)
export const deleteStory = (projectId, storyId) =>
  api.delete(`/projects/${projectId}/backlog/stories/${storyId}`)

// ── Sprints ───────────────────────────────────────────────
export const listSprints = (projectId) => api.get(`/projects/${projectId}/sprints/`)
export const createSprint = (projectId, data) =>
  api.post(`/projects/${projectId}/sprints/`, data)
export const getSprint = (projectId, sprintId) =>
  api.get(`/projects/${projectId}/sprints/${sprintId}`)
export const runSprint = (projectId, sprintId, options = {}) =>
  api.post(`/projects/${projectId}/sprints/${sprintId}/run`, options)
export const getSprintStatus = (projectId, sprintId) =>
  api.get(`/projects/${projectId}/sprints/${sprintId}/status`)
export const approveSprintReview = (projectId, sprintId) =>
  api.post(`/projects/${projectId}/sprints/${sprintId}/approve-review`)
export const resetSprint = (projectId, sprintId) =>
  api.post(`/projects/${projectId}/sprints/${sprintId}/reset`)

// ── Agents ────────────────────────────────────────────────
export const getAgentConfig = (projectId) =>
  api.get(`/projects/${projectId}/agents/config`)
export const updateAgentConfig = (projectId, data) =>
  api.patch(`/projects/${projectId}/agents/config`, data)
export const listAgentRuns = (projectId, sprintId) =>
  api.get(`/projects/${projectId}/agents/runs`, { params: { sprint_id: sprintId } })

// ── Costs ─────────────────────────────────────────────────
export const getProjectCosts = (projectId) =>
  api.get(`/projects/${projectId}/costs/`)
export const getSprintCosts = (projectId, sprintId) =>
  api.get(`/projects/${projectId}/costs/sprints/${sprintId}`)
