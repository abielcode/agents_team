import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { runSprint } from '../api/client'
import clsx from 'clsx'

/**
 * SprintRunModal — shown when the user clicks "Run Sprint".
 * Collects run options then fires POST /sprints/{id}/run.
 * On success redirects to Agent Console for live output.
 */
export default function SprintRunModal({ projectId, sprintId, sprintNumber, onClose }) {
  const navigate = useNavigate()
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [options, setOptions] = useState({
    dry_run: false,
    git_safe: false,
    skip_scan: false,
    all_anthropic: false,
    task_description: '',
  })

  const toggle = (key) => setOptions((o) => ({ ...o, [key]: !o[key] }))

  const handleRun = async () => {
    setRunning(true)
    setError(null)
    try {
      await runSprint(projectId, sprintId, options)
      onClose()
      navigate(`/projects/${projectId}/sprints/${sprintId}/console`)
    } catch (e) {
      setError(String(e))
      setRunning(false)
    }
  }

  return (
    // Backdrop
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-lg shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold">Run Sprint {sprintNumber}</h2>
            <p className="text-gray-400 text-sm mt-0.5">Configure pipeline options before starting</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none">✕</button>
        </div>

        {/* Options */}
        <div className="space-y-3 mb-6">
          <Toggle
            active={options.dry_run}
            onToggle={() => toggle('dry_run')}
            label="Dry Run"
            description="LLM-only verification — no real build/lint/test tools. Use when you don't have Xcode set up."
            icon="🧪"
          />
          <Toggle
            active={options.all_anthropic}
            onToggle={() => toggle('all_anthropic')}
            label="All Anthropic"
            description="Route all agents through Claude Haiku. Use when Ollama is not running locally."
            icon="☁️"
          />
          <Toggle
            active={options.git_safe}
            onToggle={() => toggle('git_safe')}
            label="Git Safe Mode"
            description="Block pipeline if it would overwrite files with uncommitted changes. Warn only if off."
            icon="🛡️"
          />
          <Toggle
            active={options.skip_scan}
            onToggle={() => toggle('skip_scan')}
            label="Skip Codebase Scan"
            description="Skip automatic source scanning. Use when CODEBASE.md is already complete."
            icon="⚡"
          />
        </div>

        {/* Task description override */}
        <div className="mb-6">
          <label className="label">Task Description Override <span className="text-gray-600 font-normal">(optional)</span></label>
          <textarea
            className="input min-h-[72px] text-sm"
            placeholder="Leave empty to use the sprint plan. Or describe a new feature to generate a fresh PRD + backlog."
            value={options.task_description}
            onChange={(e) => setOptions((o) => ({ ...o, task_description: e.target.value }))}
          />
        </div>

        {/* Cost estimate */}
        <div className="bg-gray-800 rounded-lg p-3 mb-6 text-xs text-gray-400">
          <div className="font-medium text-gray-300 mb-1">💰 Estimated cost</div>
          {options.all_anthropic
            ? 'All agents on Claude Haiku — est. $0.10–0.40 per sprint'
            : 'Orchestrator on Claude Haiku, code agents on Ollama (free) — est. $0.02–0.08 per sprint'
          }
        </div>

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={handleRun}
            disabled={running}
            className="btn-primary flex-1"
          >
            {running ? '⏳ Starting pipeline...' : '▶ Run Sprint'}
          </button>
          <button onClick={onClose} className="btn-ghost">Cancel</button>
        </div>

        {/* WebSocket note */}
        <p className="text-xs text-gray-600 mt-3 text-center">
          After starting, you'll be redirected to the Agent Console for live streaming output.
        </p>
      </div>
    </div>
  )
}


function Toggle({ active, onToggle, label, description, icon }) {
  return (
    <button
      onClick={onToggle}
      className={clsx(
        'w-full flex items-start gap-3 p-3 rounded-xl border text-left transition-all',
        active
          ? 'bg-brand-900 border-brand-600'
          : 'bg-gray-800 border-gray-700 hover:border-gray-600'
      )}
    >
      <span className="text-xl mt-0.5 shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className={clsx('font-medium text-sm', active ? 'text-brand-300' : 'text-gray-200')}>
            {label}
          </span>
          {/* Toggle pill */}
          <div className={clsx(
            'w-9 h-5 rounded-full transition-colors shrink-0 relative',
            active ? 'bg-brand-500' : 'bg-gray-600'
          )}>
            <div className={clsx(
              'absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all',
              active ? 'left-4' : 'left-0.5'
            )} />
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-0.5 leading-snug">{description}</p>
      </div>
    </button>
  )
}
