import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getBacklog, updateStory, deleteStory, createSprint, listSprints } from '../api/client'
import StatusBadge from '../components/StatusBadge'

export default function ProductBacklog() {
  const { projectId } = useParams()
  const navigate = useNavigate()

  const [backlog, setBacklog] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(new Set())
  const [planning, setPlanning] = useState(false)
  const [expandedEpics, setExpandedEpics] = useState({})
  const [error, setError] = useState(null)

  const load = async () => {
    try {
      const data = await getBacklog(projectId)
      setBacklog(data)
      // Expand all epics by default
      const expanded = {}
      data.epics?.forEach((e) => { expanded[e.id] = true })
      setExpandedEpics(expanded)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [projectId])

  const toggleStory = (storyId) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(storyId) ? next.delete(storyId) : next.add(storyId)
      return next
    })
  }

  const handlePlanSprint = async () => {
    setPlanning(true)
    setError(null)
    try {
      const sprints = await listSprints(projectId)
      const nextNumber = (sprints.length || 0) + 1
      const storyRefs = [...selected].map((id) => {
        for (const epic of backlog.epics) {
          const s = epic.stories.find((s) => s.id === id)
          if (s) return s.story_ref
        }
        return null
      }).filter(Boolean)

      const sprint = await createSprint(projectId, {
        number: nextNumber,
        story_refs: storyRefs,
      })
      navigate(`/projects/${projectId}/sprints/${sprint.id}`)
    } catch (e) {
      setError(e)
    } finally {
      setPlanning(false)
    }
  }

  const totalPoints = backlog?.epics?.flatMap((e) => e.stories).reduce((acc, s) => acc + (s.story_points || 0), 0) || 0
  const selectedPoints = [...selected].reduce((acc, id) => {
    for (const epic of backlog?.epics || []) {
      const s = epic.stories.find((s) => s.id === id)
      if (s) return acc + (s.story_points || 0)
    }
    return acc
  }, 0)

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Product Backlog</h1>
          <p className="text-gray-400 mt-1">{totalPoints} total story points</p>
        </div>
        <div className="flex items-center gap-3">
          {selected.size > 0 && (
            <span className="text-sm text-gray-400">{selected.size} selected ({selectedPoints} pts)</span>
          )}
          <button
            onClick={handlePlanSprint}
            disabled={selected.size === 0 || planning}
            className="btn-primary"
          >
            {planning ? 'Creating Sprint...' : `🏃 Plan Sprint (${selected.size})`}
          </button>
        </div>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {loading && <p className="text-gray-500">Loading backlog...</p>}

      {backlog?.epics?.map((epic) => (
        <div key={epic.id} className="card">
          <button
            onClick={() => setExpandedEpics((p) => ({ ...p, [epic.id]: !p[epic.id] }))}
            className="w-full flex items-center justify-between text-left"
          >
            <div className="flex items-center gap-2">
              <span className="text-brand-400 font-mono text-xs">{epic.epic_ref}</span>
              <span className="font-semibold">{epic.name}</span>
              <span className="text-xs text-gray-500">({epic.stories?.length || 0} stories)</span>
            </div>
            <span className="text-gray-500 text-sm">{expandedEpics[epic.id] ? '▾' : '▸'}</span>
          </button>

          {expandedEpics[epic.id] && (
            <div className="mt-3 space-y-2">
              {epic.stories?.map((story) => (
                <div
                  key={story.id}
                  onClick={() => toggleStory(story.id)}
                  className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                    selected.has(story.id)
                      ? 'bg-brand-900 border border-brand-700'
                      : 'bg-gray-800 hover:bg-gray-750 border border-transparent'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(story.id)}
                    onChange={() => toggleStory(story.id)}
                    onClick={(e) => e.stopPropagation()}
                    className="mt-0.5 accent-brand-500"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs text-brand-400">{story.story_ref}</span>
                      <span className="font-medium text-sm">{story.title}</span>
                      <StatusBadge status={story.status} />
                    </div>
                    {story.description && (
                      <p className="text-xs text-gray-400 mt-1 line-clamp-2">{story.description}</p>
                    )}
                    {story.acceptance_criteria?.length > 0 && (
                      <div className="mt-2 space-y-0.5">
                        {story.acceptance_criteria.slice(0, 3).map((ac, i) => (
                          <div key={i} className="text-xs text-gray-500 flex gap-1">
                            <span className="text-green-600">✓</span>{ac}
                          </div>
                        ))}
                        {story.acceptance_criteria.length > 3 && (
                          <div className="text-xs text-gray-600">+{story.acceptance_criteria.length - 3} more...</div>
                        )}
                      </div>
                    )}
                    {story.depends_on?.length > 0 && (
                      <div className="mt-1 text-xs text-yellow-600">
                        depends on: {story.depends_on.join(', ')}
                      </div>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-sm font-bold text-gray-300">{story.story_points}pt</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
