import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { getAgents, getOrg, createAgent, createDepartment, deleteAgent } from '@/lib/api'
import { useToast } from '@/components/layout/Toast'
import { UserPlus, FileText, Smile, UserMinus, Search, Trash2, ArrowRight } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

const hrTabs = [
  { id: 'recruit', label: '招聘', icon: UserPlus },
  { id: 'jd', label: 'JD生成器', icon: FileText },
  { id: 'persona', label: '人格生成器', icon: Smile },
  { id: 'manage', label: '调岗/解雇', icon: UserMinus },
]

export default function HR() {
  const [tab, setTab] = useState('recruit')

  return (
    <div className="p-6 h-full flex flex-col">
      <motion.h1
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-lg font-semibold mb-4"
      >
        人事管理
      </motion.h1>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-[#141417] border border-[#1f1f23] rounded-lg p-1 w-fit">
        {hrTabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs transition-colors',
              tab === id ? 'bg-[#1f1f23] text-text-primary' : 'text-text-muted hover:text-text-secondary'
            )}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      <motion.div key={tab} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex-1 min-h-0">
        {tab === 'recruit' && <RecruitPanel />}
        {tab === 'jd' && <JDGenerator />}
        {tab === 'persona' && <PersonaGenerator />}
        {tab === 'manage' && <StaffManager />}
      </motion.div>
    </div>
  )
}

function RecruitPanel() {
  const [step, setStep] = useState(0)
  const [requirement, setRequirement] = useState('')
  const { addToast } = useToast()

  const steps = ['描述需求', 'AI规划方案', '审批确认', '创建执行', '完成']

  return (
    <div className="space-y-6">
      {/* Stepper */}
      <div className="flex items-center gap-2">
        {steps.map((s, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className={cn(
              'w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium',
              i <= step ? 'bg-accent-blue text-white' : 'bg-[#1f1f23] text-text-muted'
            )}>
              {i + 1}
            </div>
            <span className={cn('text-xs', i <= step ? 'text-text-primary' : 'text-text-muted')}>{s}</span>
            {i < steps.length - 1 && <ArrowRight size={12} className="text-text-muted mx-1" />}
          </div>
        ))}
      </div>

      {step === 0 && (
        <div className="glass-card p-6 space-y-4">
          <label className="text-sm text-text-secondary">描述你的需求</label>
          <textarea
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
            placeholder="例如：我需要一个能做市场调研的团队，包含一个主管和两名调研员"
            className="w-full h-32 bg-[#0a0a0b] border border-[#1f1f23] rounded-lg p-4 text-sm text-text-primary placeholder-text-muted outline-none focus:border-accent-blue/50 resize-none"
          />
          <button
            onClick={() => { if (requirement.trim()) { setStep(1); addToast('正在分析需求...', 'loading') } }}
            className="px-4 py-2 bg-accent-blue text-white rounded-lg text-sm hover:bg-accent-blue/80 transition-colors"
          >
            提交需求
          </button>
        </div>
      )}

      {step === 1 && (
        <div className="glass-card p-6 space-y-4">
          <h3 className="text-sm font-medium">AI规划方案</h3>
          <div className="bg-[#0a0a0b] rounded-lg p-4 text-sm text-text-secondary space-y-2">
            <p>根据您的需求，建议创建以下组织结构：</p>
            <div className="pl-4 border-l-2 border-accent-blue/30 space-y-1">
              <p>📁 <strong>调研部</strong> (research_team)</p>
              <p className="pl-4">👤 调研主管 - Claude Sonnet - Manager</p>
              <p className="pl-4">👤 高级调研员 - Claude Haiku - Worker</p>
              <p className="pl-4">👤 初级调研员 - Claude Haiku - Worker</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setStep(2)} className="px-4 py-2 bg-accent-blue text-white rounded-lg text-sm hover:bg-accent-blue/80">
              确认方案
            </button>
            <button onClick={() => setStep(0)} className="px-4 py-2 text-text-muted hover:text-text-primary rounded-lg text-sm">
              重新描述
            </button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="glass-card p-6 space-y-4">
          <h3 className="text-sm font-medium">审批确认</h3>
          <p className="text-xs text-text-muted">以下Agent将被创建，请确认</p>
          <div className="space-y-2">
            {['调研主管 (research_mgr)', '高级调研员 (senior_researcher)', '初级调研员 (junior_researcher)'].map((a, i) => (
              <div key={i} className="flex items-center gap-3 p-3 bg-[#0a0a0b] rounded-lg text-sm text-text-secondary">
                <span className="w-2 h-2 rounded-full bg-accent-green" />
                {a}
              </div>
            ))}
          </div>
          <button onClick={() => { setStep(3); addToast('正在创建Agent...', 'loading') ; setTimeout(() => { setStep(4); addToast('创建完成', 'success') }, 1500) }} className="px-4 py-2 bg-accent-green text-white rounded-lg text-sm hover:bg-accent-green/80">
            一键创建
          </button>
        </div>
      )}

      {step >= 3 && step < 4 && (
        <div className="glass-card p-6 text-center">
          <div className="animate-spin w-8 h-8 border-2 border-accent-blue border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-sm text-text-muted">正在创建Agent...</p>
        </div>
      )}

      {step === 4 && (
        <div className="glass-card p-6 text-center space-y-3">
          <div className="text-3xl">✅</div>
          <p className="text-sm font-medium">团队创建完成</p>
          <p className="text-xs text-text-muted">3个Agent已成功创建并加入组织架构</p>
          <button onClick={() => { setStep(0); setRequirement('') }} className="px-4 py-2 text-accent-blue text-sm hover:underline">
            继续招聘
          </button>
        </div>
      )}
    </div>
  )
}

function JDGenerator() {
  const [form, setForm] = useState({
    name: '', department: '', level: 'worker', reports_to: '', duties: [''], constraints: [''], tools: [],
  })
  const [agents, setAgents] = useState([])
  const [org, setOrg] = useState(null)

  useEffect(() => { getAgents().then(setAgents); getOrg().then(setOrg) }, [])

  const update = (key, val) => setForm((p) => ({ ...p, [key]: val }))
  const departments = org?.departments || []
  const availableTools = ['web_search', 'code_exec', 'canvas', 'file_manager']

  const addItem = (key) => update(key, [...form[key], ''])
  const updateItem = (key, i, val) => {
    const arr = [...form[key]]
    arr[i] = val
    update(key, arr)
  }

  const generatedJD = `# ${form.name || '岗位名称'}\n\n## 核心职责\n${form.duties.filter(Boolean).map((d) => `- ${d}`).join('\n') || '- 待定义'}\n\n## 边界约束\n${form.constraints.filter(Boolean).map((c) => `- ${c}`).join('\n') || '- 无'}\n\n## 可用工具\n${form.tools.map((t) => `- ${t}`).join('\n') || '- 无'}`

  return (
    <div className="grid grid-cols-2 gap-6 h-full">
      {/* Form */}
      <div className="space-y-4 overflow-y-auto pr-2">
        <div>
          <label className="text-xs text-text-muted mb-1 block">岗位名称</label>
          <input value={form.name} onChange={(e) => update('name', e.target.value)} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none focus:border-accent-blue/50" placeholder="如: 高级后端工程师" />
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">所属部门</label>
          <select value={form.department} onChange={(e) => update('department', e.target.value)} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none">
            <option value="">选择部门</option>
            {departments.map((d) => <option key={d.name} value={d.name}>{d.display_name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">级别</label>
          <select value={form.level} onChange={(e) => update('level', e.target.value)} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none">
            <option value="c-suite">C-suite</option>
            <option value="director">Director</option>
            <option value="manager">Manager</option>
            <option value="worker">Worker</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">汇报对象</label>
          <select value={form.reports_to} onChange={(e) => update('reports_to', e.target.value)} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none">
            <option value="">选择上级</option>
            {agents.map((a) => <option key={a.id} value={a.id}>{a.display_name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">核心职责</label>
          {form.duties.map((d, i) => (
            <input key={i} value={d} onChange={(e) => updateItem('duties', i, e.target.value)} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none mb-1.5" placeholder={`职责 ${i + 1}`} />
          ))}
          <button onClick={() => addItem('duties')} className="text-xs text-accent-blue hover:underline">+ 添加职责</button>
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">边界约束</label>
          {form.constraints.map((c, i) => (
            <input key={i} value={c} onChange={(e) => updateItem('constraints', i, e.target.value)} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none mb-1.5" placeholder={`约束 ${i + 1}`} />
          ))}
          <button onClick={() => addItem('constraints')} className="text-xs text-accent-blue hover:underline">+ 添加约束</button>
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">所需工具</label>
          <div className="flex flex-wrap gap-2">
            {availableTools.map((t) => (
              <button
                key={t}
                onClick={() => update('tools', form.tools.includes(t) ? form.tools.filter((x) => x !== t) : [...form.tools, t])}
                className={cn('px-2.5 py-1 rounded-lg text-xs border transition-colors', form.tools.includes(t) ? 'bg-accent-blue/20 text-accent-blue border-accent-blue/30' : 'border-[#1f1f23] text-text-muted hover:text-text-secondary')}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Preview */}
      <div className="glass-card p-5 overflow-y-auto">
        <h3 className="text-xs text-text-muted mb-3">实时预览</h3>
        <div className="prose prose-invert prose-sm max-w-none text-text-secondary [&_h1]:text-text-primary [&_h2]:text-text-primary [&_li]:text-text-secondary">
          <ReactMarkdown>{generatedJD}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}

function PersonaGenerator() {
  const [agentId, setAgentId] = useState('')
  const [model, setModel] = useState('claude-haiku-3-5-20241022')
  const [personality, setPersonality] = useState('')
  const [habits, setHabits] = useState('')
  const [agents, setAgents] = useState([])

  useEffect(() => { getAgents().then(setAgents) }, [])

  const models = [
    { id: 'claude-opus-4-20250514', label: 'Claude Opus', temp: 0.7 },
    { id: 'claude-sonnet-4-20250514', label: 'Claude Sonnet', temp: 0.5 },
    { id: 'claude-haiku-3-5-20241022', label: 'Claude Haiku', temp: 0.3 },
    { id: 'deepseek-chat', label: 'DeepSeek V3', temp: 0.5 },
    { id: 'qwen3-8b', label: 'Qwen3 8B', temp: 0.5 },
  ]
  const selectedModel = models.find((m) => m.id === model)

  const resumePreview = `# ${agentId || 'agent_name'} 人格档案\n\n## 性格特征\n${personality || '- 待定义'}\n\n## 工作习惯\n${habits || '- 待定义'}\n\n## 协作备注\n- 通过Contract与上下级沟通`
  const racePreview = `model: ${model}\nprovider: ${model.includes('claude') ? 'anthropic' : model.includes('deepseek') ? 'deepseek' : 'ollama'}\ntemperature: ${selectedModel?.temp || 0.5}\nmax_tokens: 4096`

  return (
    <div className="grid grid-cols-2 gap-6 h-full">
      <div className="space-y-4 overflow-y-auto pr-2">
        <div>
          <label className="text-xs text-text-muted mb-1 block">目标岗位</label>
          <select value={agentId} onChange={(e) => setAgentId(e.target.value)} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none">
            <option value="">选择Agent</option>
            {agents.map((a) => <option key={a.id} value={a.id}>{a.display_name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">模型</label>
          <select value={model} onChange={(e) => setModel(e.target.value)} className="w-full bg-[#0a0a0b] border border-[#1f1f23] rounded-lg px-3 py-2 text-sm outline-none">
            {models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">性格描述</label>
          <textarea value={personality} onChange={(e) => setPersonality(e.target.value)} className="w-full h-24 bg-[#0a0a0b] border border-[#1f1f23] rounded-lg p-3 text-sm outline-none resize-none" placeholder="- 严谨细致&#10;- 注重代码质量" />
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">工作习惯</label>
          <textarea value={habits} onChange={(e) => setHabits(e.target.value)} className="w-full h-24 bg-[#0a0a0b] border border-[#1f1f23] rounded-lg p-3 text-sm outline-none resize-none" placeholder="- 先分析再动手&#10;- 代码注释完整" />
        </div>
      </div>

      <div className="space-y-4 overflow-y-auto">
        <div className="glass-card p-5">
          <h3 className="text-xs text-text-muted mb-3">Resume 预览</h3>
          <div className="prose prose-invert prose-sm max-w-none text-text-secondary [&_h1]:text-text-primary [&_h2]:text-text-primary">
            <ReactMarkdown>{resumePreview}</ReactMarkdown>
          </div>
        </div>
        <div className="glass-card p-5">
          <h3 className="text-xs text-text-muted mb-3">Race 配置预览</h3>
          <pre className="text-sm text-text-secondary font-mono">{racePreview}</pre>
        </div>
      </div>
    </div>
  )
}

function StaffManager() {
  const [agents, setAgents] = useState([])
  const [search, setSearch] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(null)
  const { addToast } = useToast()

  useEffect(() => { getAgents().then(setAgents) }, [])

  const filtered = agents.filter((a) =>
    a.display_name.includes(search) || a.id.includes(search) || a.department.includes(search)
  )

  const handleDelete = async (id) => {
    try {
      await deleteAgent(id)
      setAgents(agents.filter((a) => a.id !== id))
      addToast(`Agent ${id} 已解雇`, 'success')
      setConfirmDelete(null)
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 bg-[#141417] border border-[#1f1f23] rounded-lg px-3 py-1.5 w-64">
        <Search size={14} className="text-text-muted" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索Agent..." className="bg-transparent text-sm outline-none flex-1" />
      </div>

      <div className="glass-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1f1f23]">
              <th className="px-4 py-3 text-left text-xs text-text-muted font-medium">Agent</th>
              <th className="px-4 py-3 text-left text-xs text-text-muted font-medium">部门</th>
              <th className="px-4 py-3 text-left text-xs text-text-muted font-medium">级别</th>
              <th className="px-4 py-3 text-left text-xs text-text-muted font-medium">模型</th>
              <th className="px-4 py-3 text-left text-xs text-text-muted font-medium">状态</th>
              <th className="px-4 py-3 text-right text-xs text-text-muted font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((a) => (
              <tr key={a.id} className="border-b border-[#1f1f23]/50 hover:bg-[#1a1a1f] transition-colors">
                <td className="px-4 py-3">
                  <div className="font-medium text-sm">{a.display_name}</div>
                  <div className="text-xs text-text-muted">{a.id}</div>
                </td>
                <td className="px-4 py-3 text-text-secondary">{a.department}</td>
                <td className="px-4 py-3 text-text-secondary">{a.level}</td>
                <td className="px-4 py-3 text-text-secondary">{a.model_short}</td>
                <td className="px-4 py-3">
                  <span className={cn('w-2 h-2 rounded-full inline-block mr-1.5', a.status === 'busy' ? 'bg-accent-green' : 'bg-text-muted')} />
                  <span className="text-text-secondary">{a.status === 'busy' ? '忙碌' : '空闲'}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  {confirmDelete === a.id ? (
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => handleDelete(a.id)} className="text-xs text-accent-red hover:underline">确认解雇</button>
                      <button onClick={() => setConfirmDelete(null)} className="text-xs text-text-muted hover:text-text-primary">取消</button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmDelete(a.id)}
                      disabled={a.id === 'ceo' || a.id === 'hr_lead'}
                      className="p-1.5 rounded hover:bg-accent-red/10 text-text-muted hover:text-accent-red transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
