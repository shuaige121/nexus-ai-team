import { cn, typeColors, statusIcons } from '@/lib/utils'
import { motion } from 'framer-motion'

function DAGNode({ node, depth = 0 }) {
  const typeColor = typeColors[node.type] || typeColors.task
  const statusIcon = statusIcons[node.status] || '🔵'

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: depth * 0.15 }}
    >
      <div className="flex items-start gap-3">
        {depth > 0 && (
          <div className="flex flex-col items-center pt-3">
            <div className="w-px h-4 bg-[#1f1f23]" />
            <div className="w-2 h-2 rounded-full bg-[#2a2a30]" />
            <div className="w-px h-4 bg-[#1f1f23]" />
          </div>
        )}
        <div className={cn('glass-card p-3 flex-1', depth === 0 && 'border-accent-blue/30')}>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-base">{statusIcon}</span>
            <span className={cn('px-1.5 py-0.5 rounded text-[10px]', typeColor.bg, typeColor.text)}>
              {node.type}
            </span>
            <span className="text-xs text-text-muted">{node.id}</span>
          </div>
          <div className="text-sm text-text-secondary mb-1">
            {node.from_agent} → {node.to_agent}
          </div>
          <div className="text-xs text-text-muted">{node.objective}</div>
        </div>
      </div>

      {node.children && node.children.length > 0 && (
        <div className="ml-8 mt-1 space-y-1">
          {node.children.map((child) => (
            <DAGNode key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </motion.div>
  )
}

export default function TaskDAG({ chain }) {
  if (!chain || !chain.id) {
    return <div className="text-sm text-text-muted text-center py-8">无任务链数据</div>
  }
  return (
    <div className="space-y-2">
      <DAGNode node={chain} />
    </div>
  )
}
