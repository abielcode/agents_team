import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getSprint, getBacklog, resetSprint } from '../api/client'
import { useSprintPoller } from '../hooks/useWebSocket'
import StatusBadge from '../components/StatusBadge'
import SprintRunModal from '../components/SprintRunModal'

const COLUMNS = ['backlog', 'in_sprint', 'done', 'flagged']
const COLUMN_LABELS = {
  backlog:   '📋 Backlog',
  in_sprint: '⚡ In Progress',
  done:      '✅ Done',
  flagged:   '🚩 Flagged',
}

export default function SprintBoard() {
  const { projectId, sprintId } = useParams()
  const navigate = useNavigate()

  const [sprint, setSprint] = useState(null)
  const [stories, setStories] = useState([])
  const [showRunModal, setShowRunModal] = useState(false)
  const [error, setError] = useState(null)

  const liveStatus = useSprintPoller(projectId, sprintId, 3000)

  useEffect(() => {
    getSprint(projectId, sprintId).then(setSprint).catch(setError)
    getBacklog(projectId).then((b) => {
      const all = b.epics?.flatMap((e) => e.stories) || []
      setStories(all.filter((s) => s.sprint_id === parseInt(sprintId)))
    }).catch(() => {})
  }, [projectId, sprintId])

  // Sync live status into sprint state
  useEffect(() => {
    if (!liveStatus) return
    setSprint((prev) => prev ? { ...prev, status: liveStatus.status } : prev)
    // Refresh stories when sprint completes
    if (liveStatus.status === 'done') {
      getBacklog(projectId).then((b) => {
        const all = b.epics?.flatMap((e) => e.stories) || []
        setStories(all.filter((s) => s.sprint_id === parseInt(sprintId)))
      }).catch(() => {})
    }
  }, [liveStatus])

  const grouped = COLUMNS.reduce((acc, col) => {
    acc[col] = stories.filter((s) => s.status === col)
    return acc
  }, {})

  const isActive = sprint?.status === 'active'
  const isDone = sprint?.status === 'done'

  const handleReset = async () => {
    if (!confirm('Reset this sprint back to planning? This will clear the review and reset story statuses.')) return
    try {
      await resetSprint(projectId, sprintId)
      getSprint(projectId, sprintId).then(setSprint)
      getBacklog(projectId).then((b) => {
        const all = b.epics?.flatMap((e) => e.stories) || []
        setStories(all.filter((s) => s.sprint_id === parseInt(sprintId)))
      })
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div className="space-y-6">
      {/* Run modal */}
      {showRunModal && (
        <SprintRunModal
          projectId={projectId}
          sprintId={sprintId}
          sprintNumber={sprint?.number}
          onClose={() => setShowRunModal(false)}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Sprint {sprint?.number} Board</h1>
          <p className="text-gray-400 mt-1 text-sm">
            {stories.length} stories &nbsp;·&nbsp;
            {stories.reduce((a, s) => a + (s.story_points || 0), 0)} points
          </p>
        </div>
        <div className="flex items-center gap-3">
          {sprint && <StatusBadge status={sprint.status} />}
          {!isActive && !isDone && (
            <button onClick={() => setShowRunModal(true)} className="btn-primary">
              ▶ Run Sprint
            </button>
          )}
          {isActive && (
            <button
              onClick={() => navigate(`/projects/${projectId}/sprints/${sprintId}/console`)}
              className="btn-primary"
            >
              🤖 Open Console
            </button>
          )}
          {!isActive && (
            <button
              onClick={handleReset}
              className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 hover:text-white text-sm font-medium transition-colors"
            >
              🔄 Reset Sprint
            </button>
          )}
          {isDone && (
            <button
              onClick={() => navigate(`/projects/${projectId}/sprints/${sprintId}/review`)}
              className="btn-primary"
            >
              📊 Sprint Review →
            </button>
          )}
        </div>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {/* Live progress bar */}
      {isActive && liveStatus && (
        <div className="card">
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-400">Sprint progress</span>
            <span className="font-mono text-gray-300">
              {liveStatus.stories?.done || 0} / {liveStatus.stories?.total || 0} done
            </span>
          </div>
          <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-500 rounded-full transition-all duration-500"
              style={{
                width: `${liveStatus.stories?.total
                  ? (liveStatus.stories.done / liveStatus.stories.total) * 100
                  : 0}%`
              }}
            />
          </div>
        </div>
      )}

      {/* Kanban board */}
      <div className="grid grid-cols-4 gap-4">
        {COLUMNS.map((col) => (
          <div key={col}>
            <div className="text-sm font-medium text-gray-400 mb-2 flex items-center justify-between">
              <span>{COLUMN_LABELS[col]}</span>
              <span className="text-gray-600">{grouped[col]?.length || 0}</span>
            </div>
            <div className="space-y-2 min-h-[200px]">
              {grouped[col]?.map((story) => (
                <StoryCard key={story.id} story={story} isActive={isActive} />
              ))}
              {grouped[col]?.length === 0 && (
                <div className="border border-dashed border-gray-800 rounded-lg h-20 flex items-center justify-center">
                  <span className="text-xs text-gray-700">empty</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function StoryCard({ story, isActive }) {
  return (
    <div className="card p-3 space-y-2">
      <div className="flex items-start justify-between gap-1">
        <span className="font-mono text-xs text-brand-400">{story.story_ref}</span>
        <StatusBadge status={story.status} />
      </div>
      <p className="text-sm font-medium leading-tight">{story.title}</p>
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>{story.story_points}pt</span>
        {story.status === 'flagged' && (
          <span className="text-red-400">needs review</span>
        )}
      </div>
    </div>
  )
}
