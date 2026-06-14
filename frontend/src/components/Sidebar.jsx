import { NavLink, useParams } from 'react-router-dom'
import { useStore } from '../store'
import clsx from 'clsx'

const NAV = [
  { to: '/projects',                         label: '🏠 Projects',      always: true },
  { to: (id) => `/projects/${id}/prd`,       label: '📄 PRD Builder' },
  { to: (id) => `/projects/${id}/backlog`,   label: '📋 Backlog' },
  { to: (id) => `/projects/${id}/sprints/1`, label: '🏃 Sprint Board' },
  { to: (id) => `/projects/${id}/sprints/1/console`, label: '🤖 Agent Console' },
  { to: (id) => `/projects/${id}/config`,    label: '⚙️ Team Config' },
]

export default function Sidebar() {
  const { projectId, sprintId } = useParams()
  const activeProjectId = projectId || useStore((s) => s.activeProjectId)

  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col py-6 px-3 shrink-0">
      <div className="mb-8 px-2">
        <h1 className="text-lg font-bold text-brand-400">Agents Team</h1>
        <p className="text-xs text-gray-500 mt-0.5">AI Dev Pipeline</p>
      </div>

      <nav className="flex flex-col gap-1">
        {NAV.map(({ to, label, always }) => {
          const href = always ? to : (activeProjectId ? to(activeProjectId) : null)
          if (!href) return (
            <div
              key={label}
              className="px-3 py-2 rounded-lg text-sm text-gray-600 cursor-not-allowed"
            >
              {label}
            </div>
          )
          return (
            <NavLink
              key={label}
              to={href}
              className={({ isActive }) =>
                clsx(
                  'px-3 py-2 rounded-lg text-sm transition-colors',
                  isActive
                    ? 'bg-brand-600 text-white font-medium'
                    : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
                )
              }
            >
              {label}
            </NavLink>
          )
        })}
      </nav>

      <div className="mt-auto px-2 text-xs text-gray-600">
        {activeProjectId ? `Project #${activeProjectId}` : 'No project selected'}
      </div>
    </aside>
  )
}
