import { useState, useEffect, useCallback } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import Sidebar from '@/components/layout/Sidebar'
import CommandPalette from '@/components/layout/CommandPalette'
import Dashboard from '@/pages/Dashboard'
import Chat from '@/pages/Chat'
import Organization from '@/pages/Organization'
import Tasks from '@/pages/Tasks'
import WorkOrders from '@/pages/WorkOrders'
import HR from '@/pages/HR'
import Analytics from '@/pages/Analytics'
import Metrics from '@/pages/Metrics'
import Settings from '@/pages/Settings'

const pageTransition = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.2 },
}

function AnimatedPage({ children }) {
  return <motion.div {...pageTransition} className="h-full">{children}</motion.div>
}

export default function App() {
  const [cmdOpen, setCmdOpen] = useState(false)
  const location = useLocation()

  const handleKeyDown = useCallback((e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault()
      setCmdOpen((prev) => !prev)
    }
  }, [])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  return (
    <div className="flex h-screen bg-bg-primary">
      <Sidebar onCommandPalette={() => setCmdOpen(true)} />
      <main className="ml-[220px] flex-1 overflow-y-auto">
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={<AnimatedPage><Dashboard /></AnimatedPage>} />
            <Route path="/chat" element={<AnimatedPage><Chat /></AnimatedPage>} />
            <Route path="/organization" element={<AnimatedPage><Organization /></AnimatedPage>} />
            <Route path="/tasks" element={<AnimatedPage><Tasks /></AnimatedPage>} />
            <Route path="/work-orders" element={<AnimatedPage><WorkOrders /></AnimatedPage>} />
            <Route path="/hr" element={<AnimatedPage><HR /></AnimatedPage>} />
            <Route path="/analytics" element={<AnimatedPage><Analytics /></AnimatedPage>} />
            <Route path="/metrics" element={<AnimatedPage><Metrics /></AnimatedPage>} />
            <Route path="/settings" element={<AnimatedPage><Settings /></AnimatedPage>} />
          </Routes>
        </AnimatePresence>
      </main>
      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
    </div>
  )
}
