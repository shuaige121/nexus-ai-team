import { useEffect, useRef, useCallback } from 'react'
import * as d3 from 'd3'

const LEVEL_COLORS = {
  'c-suite': '#eab308',
  director: '#3b82f6',
  manager: '#3b82f6',
  worker: '#a1a1aa',
}

const LEVEL_RADIUS = {
  'c-suite': 28,
  director: 22,
  manager: 20,
  worker: 16,
}

export default function OrgTree({ data, onNodeClick, width = 800, height = 600, mini = false }) {
  const svgRef = useRef(null)
  const simRef = useRef(null)

  const drawGraph = useCallback(() => {
    if (!data || !data.nodes || !svgRef.current) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const w = width
    const h = height

    svg.attr('viewBox', `0 0 ${w} ${h}`)

    const g = svg.append('g')

    // Zoom
    if (!mini) {
      const zoom = d3.zoom()
        .scaleExtent([0.3, 3])
        .on('zoom', (event) => g.attr('transform', event.transform))
      svg.call(zoom)
    }

    // Arrow marker
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#2a2a30')

    const simulation = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(data.links).id((d) => d.id).distance(mini ? 60 : 120))
      .force('charge', d3.forceManyBody().strength(mini ? -200 : -400))
      .force('center', d3.forceCenter(w / 2, h / 2))
      .force('collision', d3.forceCollide().radius((d) => (LEVEL_RADIUS[d.level] || 16) + 10))

    simRef.current = simulation

    // Links
    const link = g.append('g')
      .selectAll('line')
      .data(data.links)
      .join('line')
      .attr('stroke', '#1f1f23')
      .attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#arrowhead)')

    // Node groups
    const node = g.append('g')
      .selectAll('g')
      .data(data.nodes)
      .join('g')
      .style('cursor', 'pointer')
      .on('click', (event, d) => onNodeClick?.(d))

    if (!mini) {
      node.call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x; d.fy = d.y
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null; d.fy = null
        }))
    }

    // Hover effects
    node.on('mouseenter', function (event, d) {
      link.attr('stroke', (l) => (l.source.id === d.id || l.target.id === d.id) ? '#3b82f6' : '#111')
        .attr('stroke-width', (l) => (l.source.id === d.id || l.target.id === d.id) ? 2.5 : 0.5)
      node.selectAll('circle')
        .attr('opacity', (n) => (n.id === d.id || data.links.some(
          (l) => (l.source.id === d.id && l.target.id === n.id) || (l.target.id === d.id && l.source.id === n.id)
        )) ? 1 : 0.2)
      node.selectAll('text')
        .attr('opacity', (n) => (n.id === d.id || data.links.some(
          (l) => (l.source.id === d.id && l.target.id === n.id) || (l.target.id === d.id && l.source.id === n.id)
        )) ? 1 : 0.2)
    }).on('mouseleave', () => {
      link.attr('stroke', '#1f1f23').attr('stroke-width', 1.5)
      node.selectAll('circle').attr('opacity', 1)
      node.selectAll('text').attr('opacity', 1)
    })

    // Circle
    node.append('circle')
      .attr('r', (d) => LEVEL_RADIUS[d.level] || 16)
      .attr('fill', (d) => {
        const color = LEVEL_COLORS[d.level] || '#a1a1aa'
        return color + '20'
      })
      .attr('stroke', (d) => LEVEL_COLORS[d.level] || '#a1a1aa')
      .attr('stroke-width', 2)

    // Initial letter
    node.append('text')
      .text((d) => d.name[0])
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', (d) => LEVEL_COLORS[d.level] || '#a1a1aa')
      .attr('font-size', (d) => mini ? '10px' : '13px')
      .attr('font-weight', 'bold')

    // Name label below
    if (!mini) {
      node.append('text')
        .text((d) => d.name)
        .attr('text-anchor', 'middle')
        .attr('dy', (d) => (LEVEL_RADIUS[d.level] || 16) + 14)
        .attr('fill', '#a1a1aa')
        .attr('font-size', '11px')

      // Model label
      node.append('text')
        .text((d) => d.model)
        .attr('text-anchor', 'middle')
        .attr('dy', (d) => (LEVEL_RADIUS[d.level] || 16) + 28)
        .attr('fill', '#71717a')
        .attr('font-size', '9px')
    }

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y)
      node.attr('transform', (d) => `translate(${d.x},${d.y})`)
    })

    return () => simulation.stop()
  }, [data, width, height, mini, onNodeClick])

  useEffect(() => {
    const cleanup = drawGraph()
    return () => {
      cleanup?.()
      simRef.current?.stop()
    }
  }, [drawGraph])

  return (
    <svg
      ref={svgRef}
      width="100%"
      height="100%"
      className="bg-transparent"
    />
  )
}
