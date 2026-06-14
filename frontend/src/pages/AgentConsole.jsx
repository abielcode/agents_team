import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { listAgentRuns, getSprintCosts } from '../api/client'
import { useSprintWebSocket } from '../hooks/useWebSocket'
import StreamingOutput from '../components/StreamingOutput'
import CostMeter from '../components/CostMeter'
import StatusBadge from '../components/StatusBadge'

const AGENTS = ['orchestrator', 'architect', 'coder', 'test_writer', 'verifier']

export default function AgentConsole() {
  const { projectId, sprintId } = useParams()
  const [activeAgent, setActiveAgent] = useState('coder')
  const [runs, setRuns] = useState([])
  const [costs, setCosts] = useState(null)

  const { messages, status, clear } = useSprintWebSocket(sprintId)

  useEffect(() => {
    listAgentRuns(projectId, sprintId).then(setRuns).catch(() => {})
    getSprintCosts(projectId, sprintId).then(setCosts).catch(() => {})
  }, [projectId, sprintId])

  // Refresh costs whenever a cost message arrives
  useEffect(() => {
    const hasCost = messages.some((m) => m.type === 'cost')
    if (hasCost) {
      getSprintCosts(projectId, sprintId).then(setCosts).catch(() => {})
    }
  }, [messages.length])

  // Filter messages by active agent tab
  const agentMessages = messages.filter(
    (m) => !m.agent || m.agent === activeAgent || m.type === 'phase' || m.type === 'status'
  )

  const wsColor = {
    connected: 'text-green-400',
    connecting: 'text-yellow-400',
    disconnected: 'text-gray-500',
    error: 'text-red-400',
  }[status]

  return (
    <div className="h-full flex gap-6">
      {/* Left: story list + cost */}
      <div className="w-64 shrink-0 space-y-4">
        <div>
          <h1 className="text-xl font-bold">Agent Console</h1>
          <div className={`text-xs mt-1 ${wsColor}`}>
            ● WebSocket {status}
          </div>
        </div>

        {costs && (
          <div className="card space-y-3">
            <h3 className="text-sm font-semibold">Sprint Cost</h3>
            <CostMeter claudeCost={costs.claude_cost_usd} />
            <div className="text-xs text-gray-500 space-y-1">
              {Object.entries(costs.by_agent_name || {}).map(([name, data]) => (
                <div key={name} className="flex justify-between">
                  <span>{name}</span>
                  <span className="font-mono">
                    {data.cost_usd > 0 ? `$${data.cost_usd.toFixed(4)}` : 'free'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent runs */}
        {runs.length > 0 && (
          <div className="card space-y-2">
            <h3 className="text-sm font-semibold">Agent Runs</h3>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {runs.slice(0, 20).map((run) => (
                <div key={run.id} className="text-xs flex items-center justify-between">
                  <span className="text-gray-400">{run.agent_name}</span>
                  <StatusBadge status={run.status} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Right: agent tabs + streaming output */}
      <div className="flex-1 flex flex-col min-w-0 space-y-4">
        {/* Agent tabs */}
        <div className="flex gap-1 border-b border-gray-800 pb-2">
          {AGENTS.map((agent) => {
            const agentMsgs = messages.filter((m) => m.agent === agent)
            const hasActivity = agentMsgs.length > 0
            return (
              <button
                key={agent}
                onClick={() => setActiveAgent(agent)}
                className={`px-3 py-1.5 rounded-t text-sm font-medium transition-colors relative ${
                  activeAgent === agent
                    ? 'bg-gray-800 text-white border border-gray-700 border-b-gray-800'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {agent}
                {hasActivity && (
                  <span className="ml-1 inline-block w-1.5 h-1.5 bg-brand-500 rounded-full align-middle" />
                )}
              </button>
            )
          })}
          <button onClick={clear} className="ml-auto text-xs text-gray-600 hover:text-gray-400 px-2">
            Clear
          </button>
        </div>

        {/* Streaming output */}
        <StreamingOutput messages={agentMessages} className="flex-1 max-h-none h-full" />
      </div>
    </div>
  )
}
