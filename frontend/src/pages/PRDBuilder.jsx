import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getPRD, refinePRD, updatePRD, approvePRD } from '../api/client'
import StatusBadge from '../components/StatusBadge'

export default function PRDBuilder() {
  const { projectId } = useParams()
  const navigate = useNavigate()

  const [prd, setPrd] = useState(null)
  const [rawInput, setRawInput] = useState('')
  const [refining, setRefining] = useState(false)
  const [approving, setApproving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    getPRD(projectId).then(setPrd).catch(() => {})
  }, [projectId])

  const handleRefine = async () => {
    if (!rawInput.trim()) return
    setRefining(true)
    setError(null)
    try {
      const result = await refinePRD(projectId, rawInput)
      setPrd(result)
    } catch (e) {
      setError(e)
    } finally {
      setRefining(false)
    }
  }

  const handleApprove = async () => {
    setApproving(true)
    setError(null)
    try {
      await approvePRD(projectId, prd.id)
      navigate(`/projects/${projectId}/backlog`)
    } catch (e) {
      setError(e)
    } finally {
      setApproving(false)
    }
  }

  const sp = prd?.structured_prd

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">PRD Builder</h1>
          <p className="text-gray-400 mt-1">Describe what you want to build — the Orchestrator will structure it.</p>
        </div>
        {prd && <StatusBadge status={prd.status} />}
      </div>

      {/* Input */}
      {(!prd || prd.status === 'draft') && (
        <div className="card space-y-4">
          <h2 className="font-semibold">Describe Your Product</h2>
          <textarea
            className="input min-h-[160px]"
            placeholder="I want to build a login screen with email/password authentication, biometric unlock, and a forgot password flow..."
            value={rawInput}
            onChange={(e) => setRawInput(e.target.value)}
          />
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button onClick={handleRefine} disabled={refining || !rawInput.trim()} className="btn-primary">
            {refining ? '⏳ Orchestrator is structuring your PRD...' : '✨ Refine PRD'}
          </button>
        </div>
      )}

      {/* Structured PRD output */}
      {sp && (
        <div className="space-y-4">
          <div className="card">
            <h2 className="font-semibold mb-2">📋 Product Overview</h2>
            <p className="text-gray-300 text-sm">{sp.product_overview}</p>
          </div>

          {sp.goals?.length > 0 && (
            <div className="card">
              <h2 className="font-semibold mb-2">🎯 Goals</h2>
              <ul className="list-disc list-inside space-y-1 text-sm text-gray-300">
                {sp.goals.map((g, i) => <li key={i}>{g}</li>)}
              </ul>
            </div>
          )}

          {sp.features?.map((feature, fi) => (
            <div key={fi} className="card">
              <h2 className="font-semibold mb-3">🧩 {feature.name}</h2>
              <p className="text-sm text-gray-400 mb-3">{feature.description}</p>
              <div className="space-y-3">
                {feature.user_stories?.map((story, si) => (
                  <div key={si} className="bg-gray-800 rounded-lg p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono text-brand-400">{story.id}</span>
                      <span className="font-medium text-sm">{story.title}</span>
                    </div>
                    <p className="text-xs text-gray-400 mb-2">
                      As a <em>{story.as_a}</em>, I want to <em>{story.i_want}</em>, so that <em>{story.so_that}</em>
                    </p>
                    {story.acceptance_criteria?.length > 0 && (
                      <ul className="text-xs text-gray-300 space-y-0.5">
                        {story.acceptance_criteria.map((ac, ai) => (
                          <li key={ai} className="flex gap-1"><span className="text-green-500">✓</span>{ac}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}

          {sp.technical_constraints?.length > 0 && (
            <div className="card">
              <h2 className="font-semibold mb-2">⚠️ Technical Constraints</h2>
              <ul className="list-disc list-inside space-y-1 text-sm text-gray-300">
                {sp.technical_constraints.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}

          {prd.status === 'draft' && (
            <div className="flex gap-3">
              <button onClick={handleApprove} disabled={approving} className="btn-primary">
                {approving ? 'Approving...' : '✅ Approve PRD → Generate Backlog'}
              </button>
              <button onClick={() => { setPrd(null); setRawInput('') }} className="btn-ghost">
                Start Over
              </button>
            </div>
          )}

          {prd.status === 'approved' && (
            <div className="flex items-center gap-3">
              <StatusBadge status="approved" />
              <button onClick={() => navigate(`/projects/${projectId}/backlog`)} className="btn-primary">
                View Backlog →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
