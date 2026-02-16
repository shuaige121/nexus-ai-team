import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

export const levelColors = {
  'c-suite': { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30', fill: '#eab308' },
  director: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30', fill: '#3b82f6' },
  manager: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30', fill: '#3b82f6' },
  worker: { bg: 'bg-zinc-500/20', text: 'text-zinc-400', border: 'border-zinc-500/30', fill: '#a1a1aa' },
}

export const priorityColors = {
  high: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' },
  medium: { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/30' },
  low: { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/30' },
}

export const typeColors = {
  task: { bg: 'bg-blue-500/20', text: 'text-blue-400' },
  report: { bg: 'bg-green-500/20', text: 'text-green-400' },
  revision: { bg: 'bg-orange-500/20', text: 'text-orange-400' },
  escalation: { bg: 'bg-red-500/20', text: 'text-red-400' },
  assistance: { bg: 'bg-purple-500/20', text: 'text-purple-400' },
}

export const statusIcons = {
  completed: '✅',
  executing: '⏳',
  pending: '🔵',
  failed: '❌',
  archived: '📦',
}

export function formatTime(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  const now = new Date()
  const diff = now - d
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  return `${days}天前`
}

export function formatCost(usd) {
  if (usd < 0.01) return `$${usd.toFixed(4)}`
  return `$${usd.toFixed(2)}`
}

export function formatTokens(n) {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}
