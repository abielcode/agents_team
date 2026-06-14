import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getSprint, getSprintCosts, approveSprintReview, createSprint } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import CostMeter from '../components/CostMeter'

export default function SprintReview() {
  const { projectId, sprintId } = useParams()
  const navigate = useNavigate()

  const [sprint, setSprint] = useState(null)
  const [costs, setCosts] = useState(null)
  const [approving, setApproving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    getSprint(projectId, sprintId).then(setSprint).catch(setError)
    getSprintCosts(projectId, sprintId).then(setCosts).catch(() => {})
  }, [projectId, sprintId])

  const handleApproveNext = async () => {
    setApproving(true)
    setError(null)
    try {
      await approveSprintReview(projectId, sprintId)
      const nextNumber = (sprint.number || 1) + 1
      const proposal = sprint.review_dict?.next_sprint_proposal
      const newSprint = await createSprint(projectId, {
        number: nextNumber,
        story_refs: proposal?.stories || [],
      })
      navigate(`/projects/${projectId}/sprints/${newSprint.id}`)
    } catch (e) {
      setError(e)
    } finally {
      setApproving(false)
    }
  }

  const review = sprint?.review_dict
  const allFiles = [
    ...(review?.files_created || []),
    ...(review?.files_modified || []),
  ]

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Sprint {sprint?.number} Review</h1>
          <p className="text-gray-400 mt-1">Review results and approve next sprint.</p>
        </div>
        {sprint && <StatusBadge status={sprint.status} />}
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {review && (
        <>
          {/* Summary */}
          <div className="card">
            <h2 className="font-semibold mb-2">📝 Summary</h2>
            <p className="text-gray-300 text-sm">{review.summary}</p>
          </div>

          {/* Stories */}
          <div className="grid grid-cols-2 gap-4">
            <div className="card">
              <h2 className="font-semibold mb-3 text-green-400">
                ✅ Completed ({review.completed?.length || 0})
              </h2>
              <div className="space-y-1">
                {review.completed?.map((id) => (
                  <div key={id} className="flex items-center gap-2 text-sm">
                    <span className="font-mono text-brand-400">{id}</span>
                    <StatusBadge status="done" />
                  </div>
                ))}
                {!review.completed?.length && (
                  <p className="text-gray-600 text-sm">None</p>
                )}
              </div>
            </div>
            <div className="card">
              <h2 className="font-semibold mb-3 text-red-400">
                🚩 Flagged ({review.flagged?.length || 0})
              </h2>
              <div className="space-y-2">
                {review.flagged?.map((item) => (
                  <div key={item.id} className="text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-brand-400">{item.id}</span>
                      <StatusBadge status="flagged" />
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{item.reason}</p>
                  </div>
                ))}
                {!review.flagged?.length && (
                  <p className="text-gray-600 text-sm">None 🎉</p>
                )}
              </div>
            </div>
          </div>

          {/* Files */}
          {allFiles.length > 0 && (
            <div className="card">
              <h2 className="font-semibold mb-3">📁 Files Changed ({allFiles.length})</h2>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 max-h-48 overflow-y-auto">
                {(review.files_created || []).map((f) => (
                  <div key={f} className="flex items-center gap-1 text-xs font-mono">
                    <span className="text-green-500">+</span>
                    <span className="text-gray-300 truncate">{f}</span>
                  </div>
                ))}
                {(review.files_modified || []).map((f) => (
                  <div key={f} className="flex items-center gap-1 text-xs font-mono">
                    <span className="text-yellow-500">~</span>
                    <span className="text-gray-300 truncate">{f}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Cost */}
          {costs && (
            <div className="card space-y-4">
              <h2 className="font-semibold">💰 Cost Summary</h2>
              <CostMeter claudeCost={costs.claude_cost_usd} />
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <div className="text-gray-500 text-xs">Total cost</div>
                  <div className="font-mono font-bold">${costs.total_cost_usd?.toFixed(4)}</div>
                </div>
                <div>
                  <div className="text-gray-500 text-xs">Claude tokens</div>
                  <div className="font-mono">{costs.claude_tokens?.input}↑ {costs.claude_tokens?.output}↓</div>
                </div>
                <div>
                  <div className="text-gray-500 text-xs">Agent runs</div>
                  <div className="font-mono">{costs.total_runs}</div>
                </div>
              </div>
            </div>
          )}

          {/* Next sprint proposal */}
          {review.next_sprint_proposal && (
            <div className="card border-brand-700">
              <h2 className="font-semibold mb-3">🚀 Proposed Sprint {review.next_sprint_proposal.sprint}</h2>
              <p className="text-sm text-gray-400 mb-3">{review.next_sprint_proposal.rationale}</p>
              <div className="flex flex-wrap gap-2 mb-4">
                {review.next_sprint_proposal.stories?.map((id) => (
                  <span key={id} className="font-mono text-xs bg-gray-800 text-brand-400 px-2 py-1 rounded">
                    {id}
                  </span>
                ))}
              </div>
              <div className="flex gap-3">
                <button onClick={handleApproveNext} disabled={approving} className="btn-primary">
                  {approving ? 'Creating Sprint...' : '✅ Approve & Start Sprint ' + review.next_sprint_proposal.sprint}
                </button>
                <button
                  onClick={() => navigate(`/projects/${projectId}/backlog`)}
                  className="btn-ghost"
                >
                  Edit Backlog First
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {!review && sprint && (
        <div className="card text-gray-500 text-sm">
          Sprint review not yet generated. Run the sprint to completion first.
        </div>
      )}
    </div>
  )
}
