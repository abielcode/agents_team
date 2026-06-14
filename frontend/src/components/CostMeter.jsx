/**
 * CostMeter — shows Claude spend vs the hard-stop limit as a progress bar.
 */
export default function CostMeter({ claudeCost = 0, warnAt = 0.10, stopAt = 0.50 }) {
  const pct = Math.min((claudeCost / stopAt) * 100, 100)
  const color =
    claudeCost >= stopAt * 0.8 ? 'bg-red-500' :
    claudeCost >= warnAt ? 'bg-yellow-500' :
    'bg-green-500'

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-400">
        <span>Claude cost</span>
        <span className="font-mono">${claudeCost.toFixed(4)} / ${stopAt.toFixed(2)}</span>
      </div>
      <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
