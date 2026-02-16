import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { cn, formatTokens, formatCost } from '@/lib/utils'
import { getTokenStats, getPerformance, getCostAnalysis, getOrg } from '@/lib/api'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from 'recharts'
import { TrendingUp, DollarSign, Zap, ArrowDownRight, Activity } from 'lucide-react'

const analyticsTabs = [
  { id: 'tokens', label: 'Token消耗' },
  { id: 'performance', label: '绩效' },
  { id: 'cost', label: '成本优化' },
]

const rangeOptions = [
  { value: '1d', label: '今天' },
  { value: '7d', label: '7天' },
  { value: '30d', label: '30天' },
]

const agentColors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#8b5cf6', '#14b8a6']

export default function Analytics() {
  const [tab, setTab] = useState('tokens')

  return (
    <div className="p-6 h-full flex flex-col">
      <motion.h1
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-lg font-semibold mb-4"
      >
        数据分析
      </motion.h1>

      <div className="flex gap-1 mb-6 bg-[#141417] border border-[#1f1f23] rounded-lg p-1 w-fit">
        {analyticsTabs.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cn(
              'px-3 py-1.5 rounded-md text-xs transition-colors',
              tab === id ? 'bg-[#1f1f23] text-text-primary' : 'text-text-muted hover:text-text-secondary'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <motion.div key={tab} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex-1 min-h-0 overflow-y-auto">
        {tab === 'tokens' && <TokenTab />}
        {tab === 'performance' && <PerformanceTab />}
        {tab === 'cost' && <CostTab />}
      </motion.div>
    </div>
  )
}

function TokenTab() {
  const [range, setRange] = useState('7d')
  const [data, setData] = useState(null)

  useEffect(() => { getTokenStats(range).then(setData) }, [range])

  const chartData = data?.daily ? (() => {
    const byDay = {}
    data.daily.forEach((d) => {
      if (!byDay[d.day]) byDay[d.day] = { day: d.day }
      byDay[d.day][d.agent_name] = (byDay[d.day][d.agent_name] || 0) + d.total
    })
    return Object.values(byDay).sort((a, b) => a.day.localeCompare(b.day))
  })() : []

  const agentNames = [...new Set(data?.daily?.map((d) => d.agent_name) || [])]

  // Per-agent table
  const agentTable = (() => {
    if (!data?.daily) return []
    const map = {}
    data.daily.forEach((d) => {
      if (!map[d.agent_name]) map[d.agent_name] = { agent: d.agent_name, model: d.model, tokens: 0, cost: 0, calls: 0 }
      map[d.agent_name].tokens += d.total
      map[d.agent_name].cost += d.cost
      map[d.agent_name].calls += d.calls
    })
    return Object.values(map).sort((a, b) => b.tokens - a.tokens)
  })()

  const summary = data?.summary || {}

  return (
    <div className="space-y-6">
      {/* Range selector */}
      <div className="flex gap-1 bg-[#141417] border border-[#1f1f23] rounded-lg p-1 w-fit">
        {rangeOptions.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => setRange(value)}
            className={cn('px-3 py-1 rounded-md text-xs', range === value ? 'bg-[#1f1f23] text-text-primary' : 'text-text-muted')}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-medium mb-4 text-text-secondary">Token消耗趋势</h3>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f1f23" />
              <XAxis dataKey="day" tick={{ fill: '#71717a', fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickFormatter={formatTokens} />
              <Tooltip contentStyle={{ backgroundColor: '#141417', border: '1px solid #1f1f23', borderRadius: '8px', fontSize: '11px' }} />
              {agentNames.map((name, i) => (
                <Area key={name} type="monotone" dataKey={name} stackId="1" stroke={agentColors[i % agentColors.length]} fill={agentColors[i % agentColors.length]} fillOpacity={0.3} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Input Tokens', value: formatTokens(summary.total_input_tokens || 0), icon: TrendingUp },
          { label: 'Output Tokens', value: formatTokens(summary.total_output_tokens || 0), icon: Activity },
          { label: '总成本', value: formatCost(summary.total_cost_usd || 0), icon: DollarSign },
          { label: '单次最高', value: formatCost(summary.max_single_cost || 0), icon: Zap },
        ].map(({ label, value, icon: Icon }) => (
          <div key={label} className="glass-card p-4">
            <div className="flex items-center gap-2 mb-1">
              <Icon size={14} className="text-text-muted" />
              <span className="text-xs text-text-muted">{label}</span>
            </div>
            <div className="text-lg font-semibold">{value}</div>
          </div>
        ))}
      </div>

      {/* Agent table */}
      <div className="glass-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1f1f23]">
              <th className="px-4 py-3 text-left text-xs text-text-muted font-medium">Agent</th>
              <th className="px-4 py-3 text-left text-xs text-text-muted font-medium">模型</th>
              <th className="px-4 py-3 text-right text-xs text-text-muted font-medium">总Token</th>
              <th className="px-4 py-3 text-right text-xs text-text-muted font-medium">总成本</th>
              <th className="px-4 py-3 text-right text-xs text-text-muted font-medium">调用次数</th>
              <th className="px-4 py-3 text-right text-xs text-text-muted font-medium">平均Token/次</th>
            </tr>
          </thead>
          <tbody>
            {agentTable.map((a) => (
              <tr key={a.agent} className="border-b border-[#1f1f23]/50 hover:bg-[#1a1a1f]">
                <td className="px-4 py-3 font-medium">{a.agent}</td>
                <td className="px-4 py-3 text-text-secondary text-xs">{a.model?.split('-').slice(1, 2).join('')}</td>
                <td className="px-4 py-3 text-right text-text-secondary">{formatTokens(a.tokens)}</td>
                <td className="px-4 py-3 text-right text-text-secondary">{formatCost(a.cost)}</td>
                <td className="px-4 py-3 text-right text-text-secondary">{a.calls}</td>
                <td className="px-4 py-3 text-right text-text-secondary">{formatTokens(Math.round(a.tokens / Math.max(a.calls, 1)))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function PerformanceTab() {
  const [data, setData] = useState(null)
  const [department, setDepartment] = useState(null)
  const [org, setOrg] = useState(null)

  useEffect(() => { getPerformance(department).then(setData); getOrg().then(setOrg) }, [department])

  const agents = data?.agents || []
  const reworkRanking = data?.rework_ranking || []
  const departments = org?.departments || []

  return (
    <div className="space-y-6">
      {/* Department filter */}
      <div className="flex gap-2">
        <button onClick={() => setDepartment(null)} className={cn('px-3 py-1.5 rounded-lg text-xs border', !department ? 'bg-[#1f1f23] border-[#2a2a30] text-text-primary' : 'border-[#1f1f23] text-text-muted')}>
          全部
        </button>
        {departments.map((d) => (
          <button key={d.name} onClick={() => setDepartment(d.name)} className={cn('px-3 py-1.5 rounded-lg text-xs border', department === d.name ? 'bg-[#1f1f23] border-[#2a2a30] text-text-primary' : 'border-[#1f1f23] text-text-muted')}>
            {d.display_name}
          </button>
        ))}
      </div>

      {/* Performance cards */}
      <div className="grid grid-cols-3 gap-4">
        {agents.map((a) => (
          <div key={a.agent_name} className="glass-card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium text-sm">{a.display_name}</div>
                <div className="text-xs text-text-muted">{a.model}</div>
              </div>
              {/* Score ring */}
              <div className="relative w-12 h-12">
                <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                  <circle cx="18" cy="18" r="15.9" fill="none" stroke="#1f1f23" strokeWidth="3" />
                  <circle cx="18" cy="18" r="15.9" fill="none" stroke={a.score >= 80 ? '#22c55e' : a.score >= 60 ? '#f59e0b' : '#ef4444'} strokeWidth="3" strokeDasharray={`${a.score} ${100 - a.score}`} strokeLinecap="round" />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-xs font-bold">{a.score}</span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-text-muted">完成率</span>
                <div className="font-medium">{(a.completion_rate * 100).toFixed(0)}%</div>
              </div>
              <div>
                <span className="text-text-muted">返工率</span>
                <div className="font-medium text-accent-orange">{(a.rework_rate * 100).toFixed(0)}%</div>
              </div>
              <div>
                <span className="text-text-muted">质检通过率</span>
                <div className="font-medium">{(a.qa_rate * 100).toFixed(0)}%</div>
              </div>
              <div>
                <span className="text-text-muted">平均处理时间</span>
                <div className="font-medium">{a.avg_time_minutes}分钟</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Rework ranking */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-medium mb-4 text-text-secondary">返工率排行</h3>
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={reworkRanking} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#1f1f23" />
              <XAxis type="number" tick={{ fill: '#71717a', fontSize: 10 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
              <YAxis type="category" dataKey="display_name" tick={{ fill: '#a1a1aa', fontSize: 11 }} width={100} />
              <Tooltip contentStyle={{ backgroundColor: '#141417', border: '1px solid #1f1f23', borderRadius: '8px', fontSize: '11px' }} formatter={(v) => `${(v * 100).toFixed(1)}%`} />
              <Bar dataKey="rework_rate" radius={[0, 4, 4, 0]}>
                {reworkRanking.map((_, i) => (
                  <Cell key={i} fill={i === 0 ? '#ef4444' : i === 1 ? '#f59e0b' : '#3b82f6'} fillOpacity={0.7} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

function CostTab() {
  const [data, setData] = useState(null)

  useEffect(() => { getCostAnalysis().then(setData) }, [])

  const suggestions = data?.suggestions || []

  return (
    <div className="space-y-6">
      <div className="glass-card p-5">
        <div className="flex items-center gap-3 mb-1">
          <ArrowDownRight size={18} className="text-accent-green" />
          <span className="text-sm font-medium">预计月节省</span>
        </div>
        <div className="text-2xl font-bold text-accent-green">{formatCost(data?.total_estimated_monthly_savings || 0)}</div>
      </div>

      <div className="space-y-4">
        {suggestions.map((s, i) => (
          <div key={i} className="glass-card p-5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-medium text-sm">{s.agent}</span>
              <span className="text-sm text-accent-green font-medium">节省 {formatCost(s.estimated_monthly_savings)}/月</span>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="px-2 py-1 rounded bg-accent-red/10 text-accent-red">当前: {s.current_model} (${s.current_cost_per_1k}/1k)</span>
              <span>→</span>
              <span className="px-2 py-1 rounded bg-accent-green/10 text-accent-green">建议: {s.suggested_model} (${s.suggested_cost_per_1k}/1k)</span>
            </div>
            <p className="text-xs text-text-muted">{s.reason}</p>
            <button className="text-xs text-accent-blue hover:underline">一键换人</button>
          </div>
        ))}
      </div>
    </div>
  )
}
