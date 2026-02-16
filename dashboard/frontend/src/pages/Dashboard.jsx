import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { getOrgTree, getContracts, getTokenStats, getAgents } from '@/lib/api'
import { formatTokens, formatCost, cn, typeColors, priorityColors, formatTime } from '@/lib/utils'
import OrgTree from '@/components/org/OrgTree'
import SlidePanel from '@/components/layout/SlidePanel'
import AgentDetail from '@/components/org/AgentDetail'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { Coins, Users, FileCheck, RotateCcw } from 'lucide-react'

const fadeIn = { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.3 } }

export default function Dashboard() {
  const [orgTree, setOrgTree] = useState(null)
  const [contracts, setContracts] = useState([])
  const [tokenData, setTokenData] = useState(null)
  const [agents, setAgents] = useState([])
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [selectedContract, setSelectedContract] = useState(null)

  useEffect(() => {
    getOrgTree().then(setOrgTree)
    getContracts().then(setContracts)
    getTokenStats('7d').then(setTokenData)
    getAgents().then(setAgents)
  }, [])

  const activeContracts = contracts.filter((c) => c.status === 'pending' || c.status === 'executing')
  const completedToday = contracts.filter((c) => c.status === 'completed').length
  const pendingCount = contracts.filter((c) => c.status === 'pending').length
  const activeAgents = agents.filter((a) => a.status === 'busy').length
  const reworkContracts = contracts.filter((c) => c.type === 'revision')
  const reworkRate = contracts.length > 0 ? ((reworkContracts.length / contracts.length) * 100).toFixed(1) : 0

  // Build chart data
  const chartData = tokenData?.daily ? (() => {
    const byDay = {}
    tokenData.daily.forEach((d) => {
      if (!byDay[d.day]) byDay[d.day] = { day: d.day }
      byDay[d.day][d.agent_name] = (byDay[d.day][d.agent_name] || 0) + d.total
    })
    return Object.values(byDay).sort((a, b) => a.day.localeCompare(b.day))
  })() : []

  const agentNames = [...new Set(tokenData?.daily?.map((d) => d.agent_name) || [])]
  const agentColors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#8b5cf6', '#14b8a6']

  const stats = [
    { label: 'Token消耗', value: formatTokens(tokenData?.summary?.total_input_tokens + tokenData?.summary?.total_output_tokens || 0), sub: formatCost(tokenData?.summary?.total_cost_usd || 0), icon: Coins, color: 'text-accent-blue' },
    { label: '活跃Agent', value: `${activeAgents} / ${agents.length}`, sub: '在线', icon: Users, color: 'text-accent-green' },
    { label: '今日Contract', value: `${completedToday} / ${pendingCount}`, sub: '完成/待处理', icon: FileCheck, color: 'text-accent-orange' },
    { label: '返工率', value: `${reworkRate}%`, sub: `${reworkContracts.length}次返工`, icon: RotateCcw, color: 'text-accent-red' },
  ]

  return (
    <div className="p-6 space-y-6">
      <motion.h1 {...fadeIn} className="text-lg font-semibold">总览</motion.h1>

      <div className="grid grid-cols-3 gap-6" style={{ gridTemplateColumns: '2fr 1fr' }}>
        {/* Left column */}
        <div className="space-y-6">
          {/* Org tree mini */}
          <motion.div {...fadeIn} transition={{ delay: 0.05 }} className="glass-card p-4">
            <h2 className="text-sm font-medium mb-3 text-text-secondary">组织架构</h2>
            <div className="h-[280px]">
              {orgTree && (
                <OrgTree
                  data={orgTree}
                  mini
                  width={600}
                  height={280}
                  onNodeClick={(node) => setSelectedAgent(node.id)}
                />
              )}
            </div>
          </motion.div>

          {/* Active contracts */}
          <motion.div {...fadeIn} transition={{ delay: 0.1 }} className="glass-card p-4">
            <h2 className="text-sm font-medium mb-3 text-text-secondary">活跃任务流水线</h2>
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {activeContracts.map((c) => {
                const typeColor = typeColors[c.type] || typeColors.task
                const prioColor = priorityColors[c.priority] || priorityColors.medium
                return (
                  <button
                    key={c.id}
                    onClick={() => setSelectedContract(c)}
                    className="w-full flex items-center gap-3 p-2.5 rounded-lg hover:bg-[#1a1a1f] transition-colors text-left"
                  >
                    <span className="text-xs text-text-muted font-mono w-16 shrink-0">{c.id}</span>
                    <span className="text-xs text-text-secondary truncate flex-1">
                      {c.from_agent} → {c.to_agent}
                    </span>
                    <span className={cn('px-1.5 py-0.5 rounded text-[10px]', typeColor.bg, typeColor.text)}>
                      {c.type}
                    </span>
                    <span className={cn('px-1.5 py-0.5 rounded text-[10px]', prioColor.bg, prioColor.text)}>
                      {{ high: '高', medium: '中', low: '低' }[c.priority]}
                    </span>
                    <span className="text-[10px] text-text-muted w-16 text-right shrink-0">
                      {formatTime(c.created_at)}
                    </span>
                  </button>
                )
              })}
              {activeContracts.length === 0 && (
                <div className="text-xs text-text-muted text-center py-6">暂无活跃任务</div>
              )}
            </div>
          </motion.div>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* Stats */}
          {stats.map(({ label, value, sub, icon: Icon, color }, i) => (
            <motion.div
              key={label}
              {...fadeIn}
              transition={{ delay: 0.05 + i * 0.05 }}
              className="glass-card p-4"
            >
              <div className="flex items-center gap-3">
                <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center bg-[#1f1f23]', color)}>
                  <Icon size={18} />
                </div>
                <div>
                  <div className="text-xs text-text-muted">{label}</div>
                  <div className="text-lg font-semibold">{value}</div>
                  <div className="text-[10px] text-text-muted">{sub}</div>
                </div>
              </div>
            </motion.div>
          ))}

          {/* Token trend chart */}
          <motion.div {...fadeIn} transition={{ delay: 0.3 }} className="glass-card p-4">
            <h2 className="text-sm font-medium mb-3 text-text-secondary">Token消耗趋势（7天）</h2>
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f1f23" />
                  <XAxis dataKey="day" tick={{ fill: '#71717a', fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
                  <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickFormatter={formatTokens} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#141417', border: '1px solid #1f1f23', borderRadius: '8px', fontSize: '12px' }}
                    labelStyle={{ color: '#a1a1aa' }}
                  />
                  {agentNames.slice(0, 6).map((name, i) => (
                    <Area
                      key={name}
                      type="monotone"
                      dataKey={name}
                      stackId="1"
                      stroke={agentColors[i % agentColors.length]}
                      fill={agentColors[i % agentColors.length]}
                      fillOpacity={0.3}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Agent detail panel */}
      <SlidePanel
        open={!!selectedAgent}
        onClose={() => setSelectedAgent(null)}
        title="Agent 详情"
      >
        {selectedAgent && <AgentDetail agentId={selectedAgent} />}
      </SlidePanel>

      {/* Contract detail panel */}
      <SlidePanel
        open={!!selectedContract}
        onClose={() => setSelectedContract(null)}
        title="Contract 详情"
      >
        {selectedContract && (
          <div className="p-5 space-y-4">
            <div className="space-y-2">
              <div className="text-xs text-text-muted">ID</div>
              <div className="text-sm font-mono">{selectedContract.id}</div>
            </div>
            <div className="space-y-2">
              <div className="text-xs text-text-muted">目标</div>
              <div className="text-sm text-text-secondary">{selectedContract.objective}</div>
            </div>
            <div className="space-y-2">
              <div className="text-xs text-text-muted">Payload</div>
              <pre className="text-xs bg-[#0a0a0b] rounded-lg p-3 text-text-secondary overflow-x-auto">
                {JSON.stringify(selectedContract.payload, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </SlidePanel>
    </div>
  )
}
