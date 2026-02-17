import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

const STATUS_COLORS = {
  queued: 'bg-yellow-500',
  in_progress: 'bg-blue-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
}

const STATUS_LABELS = {
  queued: 'Queued',
  in_progress: 'In Progress',
  completed: 'Completed',
  failed: 'Failed',
}

export default function WorkOrders() {
  const [workOrders, setWorkOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filterStatus, setFilterStatus] = useState('')
  const [filterOwner, setFilterOwner] = useState('')

  useEffect(() => {
    fetchWorkOrders()
  }, [filterStatus, filterOwner])

  const fetchWorkOrders = async () => {
    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      if (filterStatus) params.set('status', filterStatus)
      if (filterOwner) params.set('owner', filterOwner)

      const res = await fetch(`/api/work-orders?${params}`)
      const data = await res.json()

      if (data.ok) {
        setWorkOrders(data.work_orders || [])
      } else {
        setError(data.error || 'Failed to fetch work orders')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-screen bg-bg-primary p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-text-primary">Work Orders</h1>
        <p className="mt-1 text-sm text-text-secondary">
          View and manage all work orders
        </p>
      </div>

      {/* Filters */}
      <div className="mb-6 flex gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-text-secondary">
            Status
          </label>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="rounded-lg border border-border-primary bg-bg-secondary px-4 py-2 text-text-primary focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          >
            <option value="">All</option>
            <option value="queued">Queued</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-text-secondary">
            Owner
          </label>
          <select
            value={filterOwner}
            onChange={(e) => setFilterOwner(e.target.value)}
            className="rounded-lg border border-border-primary bg-bg-secondary px-4 py-2 text-text-primary focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          >
            <option value="">All</option>
            <option value="ceo">CEO</option>
            <option value="director">Director</option>
            <option value="intern">Intern</option>
            <option value="admin">Admin</option>
          </select>
        </div>

        <div className="flex items-end">
          <button
            onClick={fetchWorkOrders}
            className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white transition-colors hover:bg-blue-700"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="text-text-secondary">Loading work orders...</div>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <div className="font-medium text-red-600">Error</div>
          <div className="mt-1 text-sm text-red-700">{error}</div>
        </div>
      ) : workOrders.length === 0 ? (
        <div className="flex h-64 items-center justify-center">
          <div className="text-center">
            <h2 className="text-xl font-semibold text-text-secondary">
              No work orders found
            </h2>
            <p className="mt-2 text-sm text-text-tertiary">
              Try adjusting your filters
            </p>
          </div>
        </div>
      ) : (
        <div className="grid gap-4">
          {workOrders.map((wo) => (
            <motion.div
              key={wo.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-lg border border-border-primary bg-bg-secondary p-4 hover:border-border-hover transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="font-mono text-sm font-medium text-text-primary">
                      {wo.id}
                    </h3>
                    <div className={`h-2 w-2 rounded-full ${STATUS_COLORS[wo.status]}`} />
                    <span className="text-sm text-text-secondary">
                      {STATUS_LABELS[wo.status]}
                    </span>
                  </div>

                  <p className="mt-2 text-text-primary">{wo.intent}</p>

                  <div className="mt-3 flex gap-4 text-sm">
                    <div>
                      <span className="text-text-tertiary">Owner:</span>{' '}
                      <span className="font-medium text-text-secondary">
                        {wo.owner.toUpperCase()}
                      </span>
                    </div>
                    <div>
                      <span className="text-text-tertiary">Difficulty:</span>{' '}
                      <span className="font-medium text-text-secondary">
                        {wo.difficulty}
                      </span>
                    </div>
                    <div>
                      <span className="text-text-tertiary">Created:</span>{' '}
                      <span className="text-text-secondary">
                        {new Date(wo.created_at).toLocaleString()}
                      </span>
                    </div>
                  </div>

                  {wo.last_error && (
                    <div className="mt-3 rounded border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-700">
                      <strong>Error:</strong> {wo.last_error}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}
