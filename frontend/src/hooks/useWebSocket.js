import { useEffect, useRef, useCallback, useState } from 'react'

/**
 * useWebSocket — connects to /ws/sprint/{sprintId} and streams agent output.
 *
 * Returns:
 *   messages  — array of received message objects
 *   status    — 'connecting' | 'connected' | 'disconnected' | 'error'
 *   clear     — reset messages
 */
export function useSprintWebSocket(sprintId) {
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState('disconnected')
  const wsRef = useRef(null)
  const pingRef = useRef(null)

  const connect = useCallback(() => {
    if (!sprintId) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/sprint/${sprintId}`
    const ws = new WebSocket(url)
    wsRef.current = ws
    setStatus('connecting')

    ws.onopen = () => {
      setStatus('connected')
      // Client-side heartbeat
      pingRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 25000)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'pong' || msg.type === 'ping') return
        setMessages((prev) => [...prev, { ...msg, _ts: Date.now() }])
      } catch {
        // ignore parse errors
      }
    }

    ws.onerror = () => setStatus('error')

    ws.onclose = () => {
      setStatus('disconnected')
      clearInterval(pingRef.current)
    }
  }, [sprintId])

  const disconnect = useCallback(() => {
    clearInterval(pingRef.current)
    wsRef.current?.close()
  }, [])

  const clear = useCallback(() => setMessages([]), [])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return { messages, status, clear, connect, disconnect }
}

/**
 * useSprintPoller — polls sprint status every N seconds.
 */
export function useSprintPoller(projectId, sprintId, intervalMs = 3000) {
  const [sprintStatus, setSprintStatus] = useState(null)
  const timerRef = useRef(null)

  useEffect(() => {
    if (!projectId || !sprintId) return

    const poll = async () => {
      try {
        const res = await fetch(`/api/v1/projects/${projectId}/sprints/${sprintId}/status`)
        const data = await res.json()
        setSprintStatus(data)
        if (data.status === 'done') {
          clearInterval(timerRef.current)
        }
      } catch {
        // ignore
      }
    }

    poll()
    timerRef.current = setInterval(poll, intervalMs)
    return () => clearInterval(timerRef.current)
  }, [projectId, sprintId, intervalMs])

  return sprintStatus
}
