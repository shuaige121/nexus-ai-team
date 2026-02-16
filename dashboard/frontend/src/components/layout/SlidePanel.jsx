import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'

export default function SlidePanel({ open, onClose, title, children, width = 'w-[480px]' }) {
  useEffect(() => {
    const handleEsc = (e) => { if (e.key === 'Escape') onClose() }
    if (open) window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            className={`fixed right-0 top-0 bottom-0 ${width} bg-[#0e0e10] border-l border-[#1f1f23] z-50 flex flex-col`}
          >
            <div className="h-14 flex items-center justify-between px-5 border-b border-[#1f1f23] shrink-0">
              <h2 className="font-semibold text-sm">{title}</h2>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg hover:bg-[#1f1f23] text-text-muted hover:text-text-primary transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              {children}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
