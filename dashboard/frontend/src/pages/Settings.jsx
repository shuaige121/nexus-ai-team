import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { getTools, getModels, getStateMachine, getContractFormat } from '@/lib/api'
import {
  Search, Terminal, FileEdit, Folder, UserPlus, Building,
  UserMinus, Trash2, Link, Archive, Globe,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'

const settingsTabs = [
  { id: 'tools', label: '工具市场' },
  { id: 'models', label: '模型仓库' },
  { id: 'fsm', label: '状态机' },
  { id: 'format', label: 'Contract格式' },
]

const toolIcons = {
  search: Globe,
  terminal: Terminal,
  edit: FileEdit,
  folder: Folder,
  'user-plus': UserPlus,
  building: Building,
  'user-minus': UserMinus,
  trash: Trash2,
  link: Link,
  archive: Archive,
}

export default function Settings() {
  const [tab, setTab] = useState('tools')

  return (
    <div className="p-6 h-full flex flex-col">
      <motion.h1
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-lg font-semibold mb-4"
      >
        系统配置
      </motion.h1>

      <div className="flex gap-1 mb-6 bg-[#141417] border border-[#1f1f23] rounded-lg p-1 w-fit">
        {settingsTabs.map(({ id, label }) => (
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
        {tab === 'tools' && <ToolMarket />}
        {tab === 'models' && <ModelRepo />}
        {tab === 'fsm' && <StateMachineView />}
        {tab === 'format' && <ContractFormatView />}
      </motion.div>
    </div>
  )
}

function ToolMarket() {
  const [tools, setTools] = useState([])
  useEffect(() => { getTools().then(setTools) }, [])

  return (
    <div className="grid grid-cols-3 gap-4">
      {tools.map((tool) => {
        const Icon = toolIcons[tool.icon] || Terminal
        return (
          <div key={tool.name} className="glass-card p-4 space-y-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-[#1f1f23] flex items-center justify-center">
                <Icon size={18} className="text-accent-blue" />
              </div>
              <div>
                <div className="font-medium text-sm">{tool.name}</div>
                <div className="text-xs text-text-muted">{tool.description}</div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-xs text-text-muted mr-1">使用者:</span>
              {tool.agents.map((a) => (
                <span key={a} className="px-1.5 py-0.5 bg-[#1f1f23] rounded text-[10px] text-text-secondary">{a}</span>
              ))}
              {tool.agents.length === 0 && <span className="text-xs text-text-muted">无</span>}
            </div>
            <button className="w-full py-1.5 rounded-lg border border-[#1f1f23] text-xs text-text-muted hover:text-accent-blue hover:border-accent-blue/30 transition-colors">
              安装到Agent
            </button>
          </div>
        )
      })}
    </div>
  )
}

function ModelRepo() {
  const [models, setModels] = useState([])
  useEffect(() => { getModels().then(setModels) }, [])

  return (
    <div className="space-y-4">
      <div className="glass-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1f1f23]">
              <th className="px-4 py-3 text-left text-xs text-text-muted font-medium">模型</th>
              <th className="px-4 py-3 text-left text-xs text-text-muted font-medium">Provider</th>
              <th className="px-4 py-3 text-left text-xs text-text-muted font-medium">推理能力</th>
              <th className="px-4 py-3 text-left text-xs text-text-muted font-medium">速度</th>
              <th className="px-4 py-3 text-right text-xs text-text-muted font-medium">Input $/1K</th>
              <th className="px-4 py-3 text-right text-xs text-text-muted font-medium">Output $/1K</th>
              <th className="px-4 py-3 text-left text-xs text-text-muted font-medium">使用Agent</th>
            </tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.id} className="border-b border-[#1f1f23]/50 hover:bg-[#1a1a1f]">
                <td className="px-4 py-3">
                  <div className="font-medium">{m.name}</div>
                  <div className="text-xs text-text-muted font-mono">{m.id}</div>
                </td>
                <td className="px-4 py-3 text-text-secondary">{m.provider}</td>
                <td className="px-4 py-3">
                  <span className={cn('px-1.5 py-0.5 rounded text-xs',
                    m.reasoning === '极强' ? 'bg-yellow-500/20 text-yellow-400' :
                    m.reasoning === '强' ? 'bg-blue-500/20 text-blue-400' : 'bg-zinc-500/20 text-zinc-400'
                  )}>{m.reasoning}</span>
                </td>
                <td className="px-4 py-3 text-text-secondary">{m.speed}</td>
                <td className="px-4 py-3 text-right text-text-secondary">${m.cost_input}</td>
                <td className="px-4 py-3 text-right text-text-secondary">${m.cost_output}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {m.agents.map((a) => (
                      <span key={a} className="px-1.5 py-0.5 bg-[#1f1f23] rounded text-[10px] text-text-secondary">{a}</span>
                    ))}
                    {m.agents.length === 0 && <span className="text-xs text-text-muted">未使用</span>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function StateMachineView() {
  const [fsm, setFsm] = useState(null)
  useEffect(() => { getStateMachine().then(setFsm) }, [])

  const states = fsm?.states || []

  const roleColors = {
    worker: { bg: 'bg-zinc-500/20', text: 'text-zinc-400', border: 'border-zinc-500/30' },
    manager: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30' },
    qa: { bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500/30' },
    ceo: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30' },
  }

  return (
    <div className="space-y-6">
      <p className="text-xs text-text-muted">强制选择状态机：每个角色完成任务后必须从以下选项中选择，保证任务链不断裂。</p>
      <div className="grid grid-cols-2 gap-4">
        {states.map((state) => {
          const color = roleColors[state.role] || roleColors.worker
          return (
            <div key={state.role} className={cn('glass-card p-5 space-y-3 border', color.border)}>
              <div className="flex items-center gap-2">
                <span className={cn('px-2 py-0.5 rounded text-xs font-medium', color.bg, color.text)}>{state.role.toUpperCase()}</span>
                <span className="text-sm font-medium">{state.name}</span>
              </div>
              <div className="space-y-2">
                {state.choices.map((choice) => (
                  <div key={choice.id} className="flex items-center justify-between p-2 bg-[#0a0a0b] rounded-lg">
                    <div className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-accent-blue" />
                      <span className="text-sm">{choice.label}</span>
                    </div>
                    <span className="text-xs text-text-muted font-mono">→ {choice.next}</span>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ContractFormatView() {
  const [data, setData] = useState(null)
  const [selectedExample, setSelectedExample] = useState(null)
  useEffect(() => { getContractFormat().then(setData) }, [])

  return (
    <div className="space-y-6">
      {/* Template */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-medium mb-3">Contract 模板</h3>
        <pre className="text-xs bg-[#0a0a0b] rounded-lg p-4 text-text-secondary overflow-x-auto font-mono">
          {JSON.stringify(data?.template, null, 2)}
        </pre>
      </div>

      {/* Examples */}
      <div>
        <h3 className="text-sm font-medium mb-3">示例</h3>
        <div className="grid grid-cols-2 gap-4">
          {(data?.examples || []).map((ex) => (
            <button
              key={ex.type}
              onClick={() => setSelectedExample(selectedExample === ex.type ? null : ex.type)}
              className={cn('glass-card p-4 text-left transition-colors', selectedExample === ex.type && 'border-accent-blue/30')}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className={cn('px-1.5 py-0.5 rounded text-[10px]',
                  ex.type === 'task' ? 'bg-blue-500/20 text-blue-400' :
                  ex.type === 'report' ? 'bg-green-500/20 text-green-400' :
                  ex.type === 'revision' ? 'bg-orange-500/20 text-orange-400' : 'bg-red-500/20 text-red-400'
                )}>{ex.type}</span>
                <span className="text-sm">{ex.description}</span>
              </div>
              {selectedExample === ex.type && (
                <pre className="text-xs bg-[#0a0a0b] rounded-lg p-3 text-text-secondary overflow-x-auto font-mono mt-2">
                  {JSON.stringify(ex.example, null, 2)}
                </pre>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Manual contract creation */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-medium mb-3">手动创建 Contract（调试用）</h3>
        <ManualContractForm />
      </div>
    </div>
  )
}

function ManualContractForm() {
  const [form, setForm] = useState({ type: 'task', from_agent: '', to_agent: '', priority: 'medium', objective: '' })

  const handleSubmit = async () => {
    try {
      const res = await fetch('/api/contracts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) throw new Error('创建失败')
      await res.json()
      alert('Contract 创建成功')
    } catch (e) {
      alert('创建失败: ' + e.message)
    }
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <label className="text-xs text-text-muted mb-1 block">类型</label>
        <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none">
          {['task', 'report', 'revision', 'escalation', 'assistance'].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <div>
        <label className="text-xs text-text-muted mb-1 block">优先级</label>
        <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none">
          {['high', 'medium', 'low'].map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>
      <div>
        <label className="text-xs text-text-muted mb-1 block">发送方</label>
        <input value={form.from_agent} onChange={(e) => setForm({ ...form, from_agent: e.target.value })} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none" placeholder="ceo" />
      </div>
      <div>
        <label className="text-xs text-text-muted mb-1 block">接收方</label>
        <input value={form.to_agent} onChange={(e) => setForm({ ...form, to_agent: e.target.value })} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none" placeholder="eng_director" />
      </div>
      <div className="col-span-2">
        <label className="text-xs text-text-muted mb-1 block">目标</label>
        <input value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none" placeholder="任务目标描述" />
      </div>
      <div className="col-span-2">
        <button onClick={handleSubmit} className="px-4 py-2 bg-accent-blue text-white rounded-lg text-sm hover:bg-accent-blue/80">
          创建Contract
        </button>
      </div>
    </div>
  )
}
