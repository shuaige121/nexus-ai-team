import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { getContracts, getContractChain } from '@/lib/api'
import ContractBoard from '@/components/tasks/ContractBoard'
import TaskDAG from '@/components/tasks/TaskDAG'
import SlidePanel from '@/components/layout/SlidePanel'
import { cn, typeColors } from '@/lib/utils'
import { Search, Filter } from 'lucide-react'

export default function Tasks() {
  const [contracts, setContracts] = useState([])
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState(null)
  const [selectedContract, setSelectedContract] = useState(null)
  const [chain, setChain] = useState(null)
  const [showChain, setShowChain] = useState(false)

  useEffect(() => {
    getContracts().then(setContracts)
  }, [])

  const filtered = contracts.filter((c) => {
    if (search && !c.objective?.includes(search) && !c.id.includes(search) && !c.from_agent.includes(search) && !c.to_agent.includes(search)) return false
    if (typeFilter && c.type !== typeFilter) return false
    return true
  })

  const handleContractClick = async (contract) => {
    setSelectedContract(contract)
    try {
      const c = await getContractChain(contract.id)
      setChain(c)
    } catch {
      setChain(null)
    }
  }

  const types = ['task', 'report', 'revision', 'escalation']

  return (
    <div className="p-6 h-full flex flex-col">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between mb-4"
      >
        <h1 className="text-lg font-semibold">任务中心</h1>
        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="flex items-center gap-2 bg-[#141417] border border-[#1f1f23] rounded-lg px-3 py-1.5">
            <Search size={14} className="text-text-muted" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索..."
              className="bg-transparent text-sm text-text-primary placeholder-text-muted outline-none w-40"
            />
          </div>
          {/* Type filter */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setTypeFilter(null)}
              className={cn(
                'px-2.5 py-1.5 rounded-lg text-xs transition-colors',
                !typeFilter ? 'bg-[#1f1f23] text-text-primary' : 'text-text-muted hover:text-text-secondary'
              )}
            >
              全部
            </button>
            {types.map((t) => {
              const tc = typeColors[t]
              return (
                <button
                  key={t}
                  onClick={() => setTypeFilter(typeFilter === t ? null : t)}
                  className={cn(
                    'px-2.5 py-1.5 rounded-lg text-xs transition-colors',
                    typeFilter === t ? cn(tc.bg, tc.text) : 'text-text-muted hover:text-text-secondary'
                  )}
                >
                  {t}
                </button>
              )
            })}
          </div>
        </div>
      </motion.div>

      {/* Board */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="flex-1 min-h-0"
      >
        <ContractBoard contracts={filtered} onContractClick={handleContractClick} />
      </motion.div>

      {/* Contract detail panel */}
      <SlidePanel
        open={!!selectedContract}
        onClose={() => { setSelectedContract(null); setChain(null); setShowChain(false) }}
        title={`Contract ${selectedContract?.id || ''}`}
        width="w-[520px]"
      >
        {selectedContract && (
          <div className="p-5 space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-text-muted mb-1">类型</div>
                <div className={cn('inline-block px-2 py-0.5 rounded text-xs', typeColors[selectedContract.type]?.bg, typeColors[selectedContract.type]?.text)}>
                  {selectedContract.type}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-muted mb-1">优先级</div>
                <div className="text-sm">{selectedContract.priority}</div>
              </div>
              <div>
                <div className="text-xs text-text-muted mb-1">发送方</div>
                <div className="text-sm">{selectedContract.from_agent}</div>
              </div>
              <div>
                <div className="text-xs text-text-muted mb-1">接收方</div>
                <div className="text-sm">{selectedContract.to_agent}</div>
              </div>
            </div>

            <div>
              <div className="text-xs text-text-muted mb-1">目标</div>
              <div className="text-sm text-text-secondary">{selectedContract.objective}</div>
            </div>

            {/* DAG toggle */}
            <div>
              <button
                onClick={() => setShowChain(!showChain)}
                className="text-xs text-accent-blue hover:underline"
              >
                {showChain ? '收起任务血缘图' : '展开任务血缘图'}
              </button>
              <AnimatePresence>
                {showChain && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-3 overflow-hidden"
                  >
                    <TaskDAG chain={chain} />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Raw payload */}
            <div>
              <div className="text-xs text-text-muted mb-2">Payload</div>
              <pre className="text-xs bg-[#0a0a0b] rounded-lg p-3 text-text-secondary overflow-x-auto max-h-[200px]">
                {JSON.stringify(selectedContract.payload, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </SlidePanel>
    </div>
  )
}
