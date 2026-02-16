import { cn, typeColors, priorityColors, formatTime } from '@/lib/utils'

export default function ContractCard({ contract, onClick }) {
  const typeColor = typeColors[contract.type] || typeColors.task
  const prioColor = priorityColors[contract.priority] || priorityColors.medium
  const prioLabel = { high: '高', medium: '中', low: '低' }[contract.priority] || contract.priority

  return (
    <button
      onClick={() => onClick?.(contract)}
      className="glass-card p-3.5 text-left w-full"
    >
      <div className="flex items-center gap-2 mb-2">
        <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium', typeColor.bg, typeColor.text)}>
          {contract.type}
        </span>
        <span className="text-xs text-text-muted truncate">
          {contract.from_agent} → {contract.to_agent}
        </span>
      </div>
      <p className="text-sm text-text-secondary line-clamp-2 mb-3">
        {contract.objective?.slice(0, 60) || '无描述'}
      </p>
      <div className="flex items-center justify-between">
        <span className={cn('px-1.5 py-0.5 rounded text-[10px]', prioColor.bg, prioColor.text)}>
          {prioLabel}
        </span>
        <span className="text-[10px] text-text-muted">
          {formatTime(contract.created_at)}
        </span>
      </div>
    </button>
  )
}
