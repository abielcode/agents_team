import { useEffect, useRef } from 'react'
import clsx from 'clsx'

/**
 * StreamingOutput — renders live agent token stream.
 * Auto-scrolls to bottom as tokens arrive.
 */
export default function StreamingOutput({ messages = [], className }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  // Build display lines from messages
  const lines = messages.map((msg, i) => {
    if (msg.type === 'phase') {
      return (
        <div key={i} className="text-brand-400 font-bold mt-2">
          {'─'.repeat(50)}
          {'\n'}  PHASE: {msg.phase}{msg.story_id ? ` [${msg.story_id}]` : ''}
          {'\n'}{'─'.repeat(50)}
        </div>
      )
    }
    if (msg.type === 'token') {
      return <span key={i} className="text-green-400">{msg.delta}</span>
    }
    if (msg.type === 'status') {
      const color = msg.status === 'done' ? 'text-green-400' : 'text-red-400'
      return (
        <div key={i} className={`mt-1 font-bold ${color}`}>
          {msg.status === 'done' ? '✅' : '🚩'} {msg.story_id} — {msg.status}
        </div>
      )
    }
    if (msg.type === 'cost') {
      return (
        <div key={i} className="text-yellow-500 text-xs mt-1">
          💰 {msg.agent}: {msg.tokens_in}in / {msg.tokens_out}out — ${(msg.cost_usd || 0).toFixed(6)}
        </div>
      )
    }
    if (msg.type === 'error') {
      return <div key={i} className="text-red-400 mt-1">⚠ {msg.message}</div>
    }
    return null
  })

  return (
    <div className={clsx('stream-output', className)}>
      {lines.length === 0 ? (
        <span className="text-gray-600">Waiting for agent output...</span>
      ) : lines}
      <div ref={bottomRef} />
    </div>
  )
}
