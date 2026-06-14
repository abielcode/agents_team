import clsx from 'clsx'

const COLORS = {
  done:       'bg-green-900 text-green-300 border-green-700',
  pass:       'bg-green-900 text-green-300 border-green-700',
  approved:   'bg-green-900 text-green-300 border-green-700',
  active:     'bg-blue-900 text-blue-300 border-blue-700',
  running:    'bg-blue-900 text-blue-300 border-blue-700',
  in_sprint:  'bg-blue-900 text-blue-300 border-blue-700',
  planning:   'bg-yellow-900 text-yellow-300 border-yellow-700',
  draft:      'bg-yellow-900 text-yellow-300 border-yellow-700',
  review:     'bg-purple-900 text-purple-300 border-purple-700',
  flagged:    'bg-red-900 text-red-300 border-red-700',
  fail:       'bg-red-900 text-red-300 border-red-700',
  blocked:    'bg-red-900 text-red-300 border-red-700',
  backlog:    'bg-gray-800 text-gray-400 border-gray-700',
  pending:    'bg-gray-800 text-gray-400 border-gray-700',
}

export default function StatusBadge({ status }) {
  return (
    <span className={clsx(
      'inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium capitalize',
      COLORS[status] || 'bg-gray-800 text-gray-400 border-gray-700'
    )}>
      {status?.replace('_', ' ')}
    </span>
  )
}
