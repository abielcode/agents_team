import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getAgentConfig, updateAgentConfig } from '../api/client'

const PROVIDERS = ['anthropic', 'ollama']
const ANTHROPIC_MODELS = ['claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-6']
const OLLAMA_MODELS = ['qwen2.5-coder:7b', 'qwen2.5-coder:14b', 'qwen2.5-coder:32b', 'codellama:13b']

export default function TeamConfig() {
  const { projectId } = useParams()
  const [config, setConfig] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    getAgentConfig(projectId).then(setConfig).catch(setError)
  }, [projectId])

  const updateAgent = (agentName, field, value) => {
    setConfig((prev) => ({
      ...prev,
      agent_configs: {
        ...prev.agent_configs,
        [agentName]: { ...prev.agent_configs[agentName], [field]: value },
      },
    }))
  }

  const updateCostGuard = (field, value) => {
    setConfig((prev) => ({
      ...prev,
      cost_guard: { ...prev.cost_guard, [field]: parseFloat(value) },
    }))
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await updateAgentConfig(projectId, {
        agent_configs: config.agent_configs,
        cost_guard: config.cost_guard,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      setError(e)
    } finally {
      setSaving(false)
    }
  }

  if (!config) return <p className="text-gray-500">Loading config...</p>

  const agents = config.agent_configs || {}
  const costGuard = config.cost_guard || {}

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Team Configuration</h1>
          <p className="text-gray-400 mt-1">Configure agent models, providers, and cost limits.</p>
        </div>
        <button onClick={handleSave} disabled={saving} className="btn-primary">
          {saving ? 'Saving...' : saved ? '✓ Saved' : 'Save Changes'}
        </button>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {/* Agent configs */}
      <div className="space-y-4">
        <h2 className="font-semibold text-gray-300">Agent Settings</h2>
        {Object.entries(agents).map(([name, cfg]) => (
          <div key={name} className="card space-y-3">
            <div className="flex items-center gap-2">
              <span className="font-semibold capitalize">{name.replace('_', ' ')}</span>
              <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">
                {cfg.provider}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="label">Provider</label>
                <select
                  className="input"
                  value={cfg.provider}
                  onChange={(e) => updateAgent(name, 'provider', e.target.value)}
                >
                  {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Model</label>
                <select
                  className="input"
                  value={cfg.model}
                  onChange={(e) => updateAgent(name, 'model', e.target.value)}
                >
                  {(cfg.provider === 'anthropic' ? ANTHROPIC_MODELS : OLLAMA_MODELS).map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Max Tokens: {cfg.max_tokens}</label>
                <input
                  type="range"
                  min="500"
                  max="8000"
                  step="500"
                  value={cfg.max_tokens}
                  onChange={(e) => updateAgent(name, 'max_tokens', parseInt(e.target.value))}
                  className="w-full accent-brand-500 mt-2"
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Cost guard */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-gray-300">Cost Guard</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Warn at (USD/sprint)</label>
            <input
              type="number"
              step="0.01"
              className="input"
              value={costGuard.warn_usd_per_sprint || 0.10}
              onChange={(e) => updateCostGuard('warn_usd_per_sprint', e.target.value)}
            />
          </div>
          <div>
            <label className="label">Hard stop at (USD/sprint)</label>
            <input
              type="number"
              step="0.01"
              className="input"
              value={costGuard.hard_stop_usd_per_sprint || 0.50}
              onChange={(e) => updateCostGuard('hard_stop_usd_per_sprint', e.target.value)}
            />
          </div>
          <div>
            <label className="label">Max Claude tokens/sprint</label>
            <input
              type="number"
              step="1000"
              className="input"
              value={costGuard.max_claude_tokens_per_sprint || 20000}
              onChange={(e) => updateCostGuard('max_claude_tokens_per_sprint', parseInt(e.target.value))}
            />
          </div>
          <div>
            <label className="label">Max Claude tokens/story</label>
            <input
              type="number"
              step="500"
              className="input"
              value={costGuard.max_claude_tokens_per_story || 3000}
              onChange={(e) => updateCostGuard('max_claude_tokens_per_story', parseInt(e.target.value))}
            />
          </div>
        </div>
        <p className="text-xs text-gray-500">
          Ollama agents (architect, coder, test writer, verifier) are always free.
          Claude is used only for orchestration (≈4 calls/sprint).
        </p>
      </div>
    </div>
  )
}
