import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, MessageSquare, Network, ListTodo, ClipboardList, Users, BarChart3, LineChart, Settings, Command,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '总览' },
  { to: '/chat', icon: MessageSquare, label: '对话' },
  { to: '/organization', icon: Network, label: '组织架构' },
  { to: '/tasks', icon: ListTodo, label: '任务中心' },
  { to: '/work-orders', icon: ClipboardList, label: '工作单' },
  { to: '/hr', icon: Users, label: '人事管理' },
  { to: '/analytics', icon: BarChart3, label: '数据分析' },
  { to: '/metrics', icon: LineChart, label: '指标监控' },
  { to: '/settings', icon: Settings, label: '系统配置' },
]

export default function Sidebar({ onCommandPalette }) {
  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[220px] bg-[#0e0e10] border-r border-[#1f1f23] flex flex-col z-30">
      <div className="h-14 flex items-center px-5 border-b border-[#1f1f23]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-accent-blue flex items-center justify-center text-white text-xs font-bold">
            A
          </div>
          <span className="font-semibold text-sm text-text-primary">AgentOffice</span>
        </div>
      </div>

      <nav className="flex-1 py-3 px-3 space-y-0.5 overflow-y-auto">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-accent-blue/10 text-accent-blue'
                  : 'text-text-secondary hover:text-text-primary hover:bg-[#1a1a1f]'
              )
            }
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-[#1f1f23]">
        <button
          onClick={onCommandPalette}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-text-muted hover:text-text-secondary hover:bg-[#1a1a1f] transition-colors"
        >
          <Command size={14} />
          <span>命令面板</span>
          <kbd className="ml-auto text-xs bg-[#1f1f23] px-1.5 py-0.5 rounded">⌘K</kbd>
        </button>
      </div>
    </aside>
  )
}
