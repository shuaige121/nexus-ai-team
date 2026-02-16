import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { getOrgTree, getOrg } from '@/lib/api'
import OrgTree from '@/components/org/OrgTree'
import SlidePanel from '@/components/layout/SlidePanel'
import AgentDetail from '@/components/org/AgentDetail'

export default function Organization() {
  const [orgTree, setOrgTree] = useState(null)
  const [org, setOrg] = useState(null)
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [filters, setFilters] = useState({})

  useEffect(() => {
    getOrgTree().then(setOrgTree)
    getOrg().then(setOrg)
  }, [])

  const departments = org?.departments || []

  const toggleDept = (name) => {
    setFilters((prev) => ({ ...prev, [name]: !prev[name] }))
  }

  // Filter nodes based on department checkboxes
  const filteredData = orgTree ? (() => {
    const hiddenDepts = Object.entries(filters).filter(([, hidden]) => hidden).map(([k]) => k)
    if (hiddenDepts.length === 0) return orgTree
    const visibleNodes = orgTree.nodes.filter((n) => !hiddenDepts.includes(n.department))
    const visibleIds = new Set(visibleNodes.map((n) => n.id))
    const visibleLinks = orgTree.links.filter((l) => {
      const sId = typeof l.source === 'object' ? l.source.id : l.source
      const tId = typeof l.target === 'object' ? l.target.id : l.target
      return visibleIds.has(sId) && visibleIds.has(tId)
    })
    return { nodes: visibleNodes, links: visibleLinks }
  })() : null

  return (
    <div className="p-6 h-full flex flex-col">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between mb-4"
      >
        <h1 className="text-lg font-semibold">组织架构</h1>
      </motion.div>

      {/* Department filter */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="flex gap-2 mb-4 flex-wrap"
      >
        {departments.map((dept) => (
          <button
            key={dept.name}
            onClick={() => toggleDept(dept.name)}
            className={`px-3 py-1.5 rounded-lg text-xs transition-colors border ${
              filters[dept.name]
                ? 'bg-transparent border-[#1f1f23] text-text-muted'
                : 'bg-[#1f1f23] border-[#2a2a30] text-text-secondary'
            }`}
          >
            {dept.display_name}
            <span className="ml-1.5 text-text-muted">({dept.agents.length})</span>
          </button>
        ))}
      </motion.div>

      {/* Force graph */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.15 }}
        className="flex-1 glass-card overflow-hidden"
      >
        {filteredData && (
          <OrgTree
            data={filteredData}
            width={1200}
            height={700}
            onNodeClick={(node) => setSelectedAgent(node.id)}
          />
        )}
      </motion.div>

      <SlidePanel
        open={!!selectedAgent}
        onClose={() => setSelectedAgent(null)}
        title="Agent 详情"
      >
        {selectedAgent && <AgentDetail agentId={selectedAgent} />}
      </SlidePanel>
    </div>
  )
}
