import { useState, useEffect } from 'react'
import { getAgent, updateAgentJD, updateAgentResume, updateAgentMemory, updateAgentRace } from '@/lib/api'
import { useToast } from '@/components/layout/Toast'
import { cn, levelColors } from '@/lib/utils'
import { Save, FileText, User, Brain, Cpu } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

const tabs = [
  { id: 'jd', label: 'JD', icon: FileText },
  { id: 'resume', label: 'Resume', icon: User },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'race', label: 'Race', icon: Cpu },
]

export default function AgentDetail({ agentId }) {
  const [agent, setAgent] = useState(null)
  const [activeTab, setActiveTab] = useState('jd')
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const { addToast } = useToast()

  useEffect(() => {
    if (agentId) {
      getAgent(agentId).then(setAgent).catch(() => addToast('加载Agent失败', 'error'))
    }
  }, [agentId])

  if (!agent) {
    return <div className="p-6 text-text-muted text-sm">加载中...</div>
  }

  const levelColor = levelColors[agent.level] || levelColors.worker

  const contentMap = {
    jd: agent.jd,
    resume: agent.resume,
    memory: agent.memory,
    race: agent.race,
  }

  const currentContent = contentMap[activeTab] || ''

  const handleEdit = () => {
    setEditContent(currentContent)
    setEditing(true)
  }

  const handleSave = async () => {
    const updateFn = { jd: updateAgentJD, resume: updateAgentResume, memory: updateAgentMemory, race: updateAgentRace }[activeTab]
    try {
      await updateFn(agentId, editContent)
      setAgent({ ...agent, [activeTab]: editContent })
      setEditing(false)
      addToast(`${agent.display_name} ${activeTab.toUpperCase()} 已更新`, 'success')
    } catch (e) {
      addToast('保存失败: ' + e.message, 'error')
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Agent header */}
      <div className="px-5 py-4 border-b border-[#1f1f23]">
        <div className="flex items-center gap-3">
          <div className={cn(
            'w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold',
            levelColor.bg, levelColor.text
          )}>
            {agent.display_name[0]}
          </div>
          <div>
            <div className="font-medium text-sm">{agent.display_name}</div>
            <div className="text-xs text-text-muted flex items-center gap-2">
              <span className={cn('px-1.5 py-0.5 rounded text-xs', levelColor.bg, levelColor.text)}>
                {agent.level}
              </span>
              <span>{agent.department}</span>
              <span>·</span>
              <span>{agent.model_short}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#1f1f23] px-5">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => { setActiveTab(id); setEditing(false) }}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2.5 text-xs transition-colors border-b-2 -mb-px',
              activeTab === id
                ? 'text-accent-blue border-accent-blue'
                : 'text-text-muted hover:text-text-secondary border-transparent'
            )}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5">
        {editing ? (
          <div className="space-y-3">
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="w-full h-[400px] bg-[#0a0a0b] border border-[#1f1f23] rounded-lg p-4 text-sm text-text-primary font-mono resize-none outline-none focus:border-accent-blue/50"
            />
            <div className="flex gap-2">
              <button
                onClick={handleSave}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-accent-blue text-white rounded-lg text-xs hover:bg-accent-blue/80 transition-colors"
              >
                <Save size={12} />
                保存
              </button>
              <button
                onClick={() => setEditing(false)}
                className="px-3 py-1.5 text-text-muted hover:text-text-primary rounded-lg text-xs transition-colors"
              >
                取消
              </button>
            </div>
          </div>
        ) : (
          <div>
            <div className="flex justify-end mb-3">
              <button
                onClick={handleEdit}
                className="text-xs text-text-muted hover:text-accent-blue transition-colors"
              >
                编辑
              </button>
            </div>
            {activeTab === 'race' ? (
              <pre className="text-sm text-text-secondary font-mono bg-[#0a0a0b] rounded-lg p-4 whitespace-pre-wrap">
                {currentContent}
              </pre>
            ) : (
              <div className="prose prose-invert prose-sm max-w-none text-text-secondary [&_h1]:text-text-primary [&_h2]:text-text-primary [&_h3]:text-text-primary [&_strong]:text-text-primary [&_li]:text-text-secondary">
                <ReactMarkdown>{currentContent}</ReactMarkdown>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
