import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

export default function Metrics() {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [period, setPeriod] = useState('today')

  useEffect(() => {
    fetchMetrics()
  }, [period])

  const fetchMetrics = async () => {
    setLoading(true)
    setError(null)

    try {
      const res = await fetch(`/api/metrics?period=${period}`)
      const data = await res.json()

      if (data.ok) {
        setMetrics(data)
      } else {
        setError(data.error || 'Failed to fetch metrics')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num) => {
    return new Intl.NumberFormat('en-US').format(num || 0)
  }

  const formatCurrency = (num) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(num || 0)
  }

  return (
    <div className="h-screen bg-bg-primary p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-text-primary">Metrics</h1>
          <p className="mt-1 text-sm text-text-secondary">
            System performance and token usage
          </p>
        </div>

        <div>
          <label className="mr-2 text-sm font-medium text-text-secondary">
            Period:
          </label>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="rounded-lg border border-border-primary bg-bg-secondary px-4 py-2 text-text-primary focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          >
            <option value="today">Today</option>
            <option value="week">Last 7 Days</option>
            <option value="month">Last 30 Days</option>
            <option value="all">All Time</option>
          </select>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="text-text-secondary">Loading metrics...</div>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <div className="font-medium text-red-600">Error</div>
          <div className="mt-1 text-sm text-red-700">{error}</div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Token Usage */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-lg border border-border-primary bg-bg-secondary p-6"
          >
            <h2 className="text-xl font-semibold text-text-primary mb-4">
              Token Usage
            </h2>
            <div className="grid grid-cols-3 gap-6">
              <div>
                <div className="text-sm text-text-tertiary">Prompt Tokens</div>
                <div className="mt-2 text-3xl font-bold text-blue-600">
                  {formatNumber(metrics?.token_usage?.prompt_tokens)}
                </div>
              </div>
              <div>
                <div className="text-sm text-text-tertiary">Completion Tokens</div>
                <div className="mt-2 text-3xl font-bold text-green-600">
                  {formatNumber(metrics?.token_usage?.completion_tokens)}
                </div>
              </div>
              <div>
                <div className="text-sm text-text-tertiary">Total Tokens</div>
                <div className="mt-2 text-3xl font-bold text-purple-600">
                  {formatNumber(metrics?.token_usage?.total_tokens)}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Cost */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="rounded-lg border border-border-primary bg-bg-secondary p-6"
          >
            <h2 className="text-xl font-semibold text-text-primary mb-4">
              Cost Analysis
            </h2>
            <div>
              <div className="text-sm text-text-tertiary">Total Cost (USD)</div>
              <div className="mt-2 text-4xl font-bold text-green-600">
                {formatCurrency(metrics?.cost?.total_usd)}
              </div>
            </div>
          </motion.div>

          {/* Work Orders */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="rounded-lg border border-border-primary bg-bg-secondary p-6"
          >
            <h2 className="text-xl font-semibold text-text-primary mb-4">
              Work Orders
            </h2>
            <div className="grid grid-cols-4 gap-6">
              <div>
                <div className="text-sm text-text-tertiary">Queued</div>
                <div className="mt-2 text-3xl font-bold text-yellow-600">
                  {formatNumber(metrics?.work_orders?.queued)}
                </div>
              </div>
              <div>
                <div className="text-sm text-text-tertiary">In Progress</div>
                <div className="mt-2 text-3xl font-bold text-blue-600">
                  {formatNumber(metrics?.work_orders?.in_progress)}
                </div>
              </div>
              <div>
                <div className="text-sm text-text-tertiary">Completed</div>
                <div className="mt-2 text-3xl font-bold text-green-600">
                  {formatNumber(metrics?.work_orders?.completed)}
                </div>
              </div>
              <div>
                <div className="text-sm text-text-tertiary">Failed</div>
                <div className="mt-2 text-3xl font-bold text-red-600">
                  {formatNumber(metrics?.work_orders?.failed)}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Request Count */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="rounded-lg border border-border-primary bg-bg-secondary p-6"
          >
            <h2 className="text-xl font-semibold text-text-primary mb-4">
              API Activity
            </h2>
            <div>
              <div className="text-sm text-text-tertiary">Recent Requests</div>
              <div className="mt-2 text-3xl font-bold text-blue-600">
                {formatNumber(metrics?.request_count)}
              </div>
            </div>
          </motion.div>

          {/* Timestamp */}
          {metrics?.timestamp && (
            <div className="text-center text-sm text-text-tertiary">
              Last updated: {new Date(metrics.timestamp).toLocaleString()}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
