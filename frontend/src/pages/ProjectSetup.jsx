import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listProjects, createProject, deleteProject, pickFolder } from '../api/client'
import { useStore } from '../store'

const PLATFORM_ICONS = { ios: '🍎', android: '🤖', django: '🐍' }

export default function ProjectSetup() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState(null)
  const [creating, setCreating] = useState(false)
  const [picking, setPicking] = useState(false)
  const [form, setForm] = useState({ name: '', platform: 'ios', project_path: '', context: '' })
  const [error, setError] = useState(null)
  const navigate = useNavigate()
  const setActiveProject = useStore((s) => s.setActiveProject)

  const load = async () => {
    try {
      const data = await listProjects()
      setProjects(data)
      setMode(data.length > 0 ? 'existing' : 'new')
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handlePickFolder = async () => {
    setPicking(true)
    try {
      const result = await pickFolder()
      if (!result.cancelled && result.path) {
        setForm((prev) => ({ ...prev, project_path: result.path }))
        // Auto-fill project name from folder name if still empty
        if (!form.name) {
          const folderName = result.path.split('/').pop()
          setForm((prev) => ({ ...prev, project_path: result.path, name: folderName }))
        }
      }
    } catch (e) {
      setError(`Folder picker failed: ${e}`)
    } finally {
      setPicking(false)
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setCreating(true)
    setError(null)
    try {
      const project = await createProject(form)
      setActiveProject(project.id)
      navigate(`/projects/${project.id}/prd`)
    } catch (e) {
      setError(String(e))
    } finally {
      setCreating(false)
    }
  }

  const handleSelect = (project) => {
    setActiveProject(project.id)
    navigate(`/projects/${project.id}/prd`)
  }

  const handleDelete = async (id, e) => {
    e.stopPropagation()
    if (!confirm('Delete this project and all its data?')) return
    await deleteProject(id)
    load()
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8 pt-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold">Agents Team</h1>
        <p className="text-gray-400 mt-2">AI-powered development pipeline</p>
      </div>

      {/* Mode toggle */}
      {!loading && (
        <div className="flex gap-3 justify-center">
          <button
            onClick={() => setMode('new')}
            className={`px-6 py-3 rounded-xl font-medium text-sm transition-all ${
              mode === 'new'
                ? 'bg-brand-600 text-white shadow-lg shadow-brand-900'
                : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
            }`}
          >
            ✨ New Project
          </button>
          <button
            onClick={() => setMode('existing')}
            disabled={projects.length === 0}
            className={`px-6 py-3 rounded-xl font-medium text-sm transition-all ${
              mode === 'existing'
                ? 'bg-brand-600 text-white shadow-lg shadow-brand-900'
                : projects.length === 0
                ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
                : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
            }`}
          >
            📂 Use Existing {projects.length > 0 && `(${projects.length})`}
          </button>
        </div>
      )}

      {loading && (
        <div className="text-center text-gray-500 py-12">Loading...</div>
      )}

      {/* ── NEW PROJECT FORM ─────────────────────── */}
      {mode === 'new' && (
        <div className="card space-y-4">
          <h2 className="font-semibold text-lg">Create New Project</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Project Name</label>
                <input
                  className="input"
                  placeholder="My iOS App"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="label">Platform</label>
                <select
                  className="input"
                  value={form.platform}
                  onChange={(e) => setForm({ ...form, platform: e.target.value })}
                >
                  <option value="ios">🍎 iOS</option>
                  <option value="android">🤖 Android</option>
                  <option value="django">🐍 Django</option>
                </select>
              </div>
            </div>

            {/* Project path with folder picker */}
            <div>
              <label className="label">Project Path</label>
              <div className="flex gap-2">
                <input
                  className="input"
                  placeholder="~/path/to/your/project"
                  value={form.project_path}
                  onChange={(e) => setForm({ ...form, project_path: e.target.value })}
                  required
                />
                <button
                  type="button"
                  onClick={handlePickFolder}
                  disabled={picking}
                  title="Open folder picker"
                  className="shrink-0 flex items-center gap-1.5 px-3 py-2 bg-gray-700 hover:bg-gray-600 border border-gray-600 hover:border-gray-500 text-gray-300 hover:text-white rounded-lg transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {picking ? (
                    <span className="animate-pulse">...</span>
                  ) : (
                    <>
                      <span>📁</span>
                      <span>Browse</span>
                    </>
                  )}
                </button>
              </div>
              {form.project_path && (
                <p className="text-xs text-gray-600 mt-1 truncate">{form.project_path}</p>
              )}
            </div>

            <div>
              <label className="label">
                Existing Codebase Context{' '}
                <span className="text-gray-600 font-normal">(optional)</span>
              </label>
              <textarea
                className="input min-h-[80px]"
                placeholder="Brief description of existing code, architecture patterns, conventions to follow..."
                value={form.context}
                onChange={(e) => setForm({ ...form, context: e.target.value })}
              />
            </div>

            {error && <p className="text-red-400 text-sm">{error}</p>}
            <button type="submit" className="btn-primary w-full" disabled={creating}>
              {creating ? '⏳ Creating...' : '+ Create Project'}
            </button>
          </form>
        </div>
      )}

      {/* ── EXISTING PROJECTS ────────────────────── */}
      {mode === 'existing' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-lg">Your Projects</h2>
            <button
              onClick={() => setMode('new')}
              className="text-sm text-brand-400 hover:text-brand-300"
            >
              + New Project
            </button>
          </div>

          {projects.map((p) => (
            <div
              key={p.id}
              onClick={() => handleSelect(p)}
              className="card flex items-center gap-4 cursor-pointer hover:border-brand-600 transition-all hover:shadow-lg group"
            >
              <div className="text-3xl">{PLATFORM_ICONS[p.platform] || '📦'}</div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold group-hover:text-brand-300 transition-colors">
                  {p.name}
                </div>
                <div className="text-sm text-gray-500 truncate mt-0.5">{p.project_path}</div>
                <div className="text-xs text-gray-600 mt-1">
                  Created {new Date(p.created_at).toLocaleDateString()}
                </div>
              </div>
              <div className="flex flex-col items-end gap-2 shrink-0">
                <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">
                  {p.platform}
                </span>
                <button
                  onClick={(e) => handleDelete(p.id, e)}
                  className="text-gray-700 hover:text-red-400 text-xs transition-colors"
                >
                  Delete
                </button>
              </div>
              <div className="text-gray-600 group-hover:text-brand-400 transition-colors">→</div>
            </div>
          ))}

          {error && <p className="text-red-400 text-sm">{error}</p>}
        </div>
      )}
    </div>
  )
}
