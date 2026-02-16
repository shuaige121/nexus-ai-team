import { createContext, useContext, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, XCircle, Loader2, Info } from 'lucide-react'

const ToastContext = createContext(null)

let toastId = 0

const icons = {
  success: <CheckCircle size={16} className="text-accent-green" />,
  error: <XCircle size={16} className="text-accent-red" />,
  loading: <Loader2 size={16} className="text-accent-blue animate-spin" />,
  info: <Info size={16} className="text-accent-blue" />,
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info', duration = 3000) => {
    const id = ++toastId
    setToasts((prev) => [...prev, { id, message, type }])
    if (type !== 'loading') {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }, duration)
    }
    return id
  }, [])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[200] space-y-2">
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              className="glass-card flex items-center gap-2.5 px-4 py-3 min-w-[280px] cursor-pointer"
              onClick={() => removeToast(toast.id)}
            >
              {icons[toast.type]}
              <span className="text-sm text-text-primary">{toast.message}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
