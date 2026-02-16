import { cn, levelColors } from '@/lib/utils'

export default function AgentCard({ agent, onClick }) {
  const color = levelColors[agent.level] || levelColors.worker

  return (
    <button
      onClick={() => onClick?.(agent)}
      className="glass-card p-4 text-left w-full"
    >
      <div className="flex items-center gap-3">
        <div className={cn(
          'w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold shrink-0',
          color.bg, color.text
        )}>
          {agent.display_name[0]}
        </div>
        <div className="min-w-0">
          <div className="text-sm font-medium truncate">{agent.display_name}</div>
          <div className="text-xs text-text-muted flex items-center gap-1.5">
            <span className={cn('px-1 py-0.5 rounded text-[10px]', color.bg, color.text)}>
              {agent.model_short}
            </span>
            <span>{agent.department}</span>
          </div>
        </div>
        <div className={cn(
          'ml-auto w-2 h-2 rounded-full shrink-0',
          agent.status === 'busy' ? 'bg-accent-green animate-pulse' : 'bg-text-muted'
        )} />
      </div>
    </button>
  )
}
