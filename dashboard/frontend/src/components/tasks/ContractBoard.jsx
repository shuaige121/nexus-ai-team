import { cn } from '@/lib/utils'
import ContractCard from './ContractCard'

const columns = [
  { key: 'pending', label: '待处理', color: 'text-accent-orange' },
  { key: 'executing', label: '执行中', color: 'text-accent-blue' },
  { key: 'completed', label: '已完成', color: 'text-accent-green' },
]

export default function ContractBoard({ contracts, onContractClick }) {
  return (
    <div className="grid grid-cols-3 gap-4 h-full">
      {columns.map(({ key, label, color }) => {
        const items = contracts.filter((c) => c.status === key)
        return (
          <div key={key} className="flex flex-col min-h-0">
            <div className="flex items-center gap-2 mb-3 px-1">
              <span className={cn('text-sm font-medium', color)}>{label}</span>
              <span className="text-xs text-text-muted bg-[#1f1f23] px-1.5 py-0.5 rounded-full">
                {items.length}
              </span>
            </div>
            <div className="flex-1 space-y-2.5 overflow-y-auto pr-1">
              {items.map((c) => (
                <ContractCard key={c.id} contract={c} onClick={onContractClick} />
              ))}
              {items.length === 0 && (
                <div className="text-xs text-text-muted text-center py-8">暂无任务</div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
