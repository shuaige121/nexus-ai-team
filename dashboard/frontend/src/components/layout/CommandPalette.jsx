import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Network, ListTodo, Users, BarChart3, Settings,
  Search, UserPlus, Building, Zap,
} from 'lucide-react'

const commands = [
  { id: 'dashboard', label: '总览', icon: LayoutDashboard, action: 'nav', path: '/' },
  { id: 'org', label: '组织架构', icon: Network, action: 'nav', path: '/organization' },
  { id: 'tasks', label: '任务中心', icon: ListTodo, action: 'nav', path: '/tasks' },
  { id: 'hr', label: '人事管理', icon: Users, action: 'nav', path: '/hr' },
  { id: 'analytics', label: '数据分析', icon: BarChart3, action: 'nav', path: '/analytics' },
  { id: 'settings', label: '系统配置', icon: Settings, action: 'nav', path: '/settings' },
  { id: 'recruit', label: '招聘新员工', icon: UserPlus, action: 'nav', path: '/hr' },
  { id: 'create-dept', label: '创建部门', icon: Building, action: 'nav', path: '/hr' },
  { id: 'activate', label: '发送指令', icon: Zap, action: 'nav', path: '/' },
]

export default function CommandPalette({ open, onClose }) {
  const [query, setQuery] = useState('')
  const inputRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (open) {
      setQuery('')
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  const filtered = commands.filter(
    (c) => c.label.toLowerCase().includes(query.toLowerCase()) || c.id.includes(query.toLowerCase())
  )

  const handleSelect = (cmd) => {
    if (cmd.action === 'nav') {
      navigate(cmd.path)
    }
    onClose()
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="cmd-overlay fixed inset-0 z-[100]"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.15 }}
            className="fixed left-1/2 top-[20%] -translate-x-1/2 w-[560px] bg-[#141417] border border-[#1f1f23] rounded-xl shadow-2xl z-[101] overflow-hidden"
          >
            <div className="flex items-center gap-3 px-4 py-3 border-b border-[#1f1f23]">
              <Search size={16} className="text-text-muted" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索命令、Agent、页面..."
                className="flex-1 bg-transparent text-sm text-text-primary placeholder-text-muted outline-none"
              />
              <kbd className="text-xs bg-[#1f1f23] text-text-muted px-1.5 py-0.5 rounded">ESC</kbd>
            </div>
            <div className="max-h-[320px] overflow-y-auto py-2">
              {filtered.length === 0 && (
                <div className="px-4 py-6 text-center text-sm text-text-muted">没有匹配的命令</div>
              )}
              {filtered.map((cmd) => {
                const Icon = cmd.icon
                return (
                  <button
                    key={cmd.id}
                    onClick={() => handleSelect(cmd)}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-text-secondary hover:bg-[#1a1a1f] hover:text-text-primary transition-colors"
                  >
                    <Icon size={16} className="text-text-muted" />
                    <span>{cmd.label}</span>
                  </button>
                )
              })}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
