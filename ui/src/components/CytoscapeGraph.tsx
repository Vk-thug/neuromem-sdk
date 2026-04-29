import { useEffect, useRef } from 'react'
import cytoscape, { type Core, type ElementDefinition } from 'cytoscape'
// @ts-expect-error — no types ship with this layout extension
import coseBilkent from 'cytoscape-cose-bilkent'
import type { Graph2D } from '../lib/api'

cytoscape.use(coseBilkent)

const COLOR_BY_TYPE: Record<string, string> = {
  episodic: '#4f8cff',
  semantic: '#f3b557',
  procedural: '#5fc587',
  affective: '#e74c5c',
  working: '#dcdcdc',
}

const COLOR_BY_LINK: Record<string, string> = {
  derived_from: '#888888',
  contradicts: '#e74c5c',
  reinforces: '#5fc587',
  related: '#4f8cff',
  supersedes: '#f3b557',
}

interface Props {
  data: Graph2D
  onNodeClick?: (id: string) => void
}

/**
 * Obsidian-style 2D knowledge-graph view via Cytoscape.js + cose-bilkent
 * layout. Node colour = MemoryType; node size = log-scaled salience ×
 * (1 + ln(1+reinforcement)). Edge colour = link_type. Flashbulb-tagged
 * memories pulse red.
 */
export default function CytoscapeGraph({ data, onNodeClick }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)

  useEffect(() => {
    if (!ref.current) return

    const elements: ElementDefinition[] = [
      ...data.nodes.map((n) => ({
        data: {
          id: n.id,
          label: n.label || n.id.slice(0, 8),
          memory_type: n.memory_type || 'episodic',
          salience: n.salience ?? 0.5,
          reinforcement: n.reinforcement ?? 0,
          flashbulb: n.flashbulb ? 1 : 0,
          excerpt: n.content_excerpt || '',
        },
      })),
      ...data.edges.map((e, i) => ({
        data: {
          id: `e_${i}`,
          source: e.source_id,
          target: e.target_id,
          link_type: e.link_type,
          strength: e.strength,
        },
      })),
    ]

    const cy = cytoscape({
      container: ref.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (n: cytoscape.NodeSingular) =>
              COLOR_BY_TYPE[n.data('memory_type') as string] || '#666',
            label: 'data(label)',
            color: '#cbd5e1',
            'font-size': 9,
            'text-wrap': 'wrap',
            'text-max-width': '120px',
            width: (n: cytoscape.NodeSingular) =>
              12 + 28 * (n.data('salience') as number) +
              4 * Math.log(1 + (n.data('reinforcement') as number)),
            height: (n: cytoscape.NodeSingular) =>
              12 + 28 * (n.data('salience') as number) +
              4 * Math.log(1 + (n.data('reinforcement') as number)),
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'border-color': (n: cytoscape.NodeSingular) =>
              n.data('flashbulb') ? '#e74c5c' : 'transparent',
            'border-width': (n: cytoscape.NodeSingular) =>
              n.data('flashbulb') ? 3 : 0,
          },
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'line-color': (e: cytoscape.EdgeSingular) =>
              COLOR_BY_LINK[e.data('link_type') as string] || '#555',
            width: (e: cytoscape.EdgeSingular) =>
              0.5 + 2.5 * (e.data('strength') as number),
            'target-arrow-shape': 'triangle',
            'target-arrow-color': (e: cytoscape.EdgeSingular) =>
              COLOR_BY_LINK[e.data('link_type') as string] || '#555',
            opacity: 0.7,
          },
        },
      ],
      layout: {
        name: 'cose-bilkent',
        animate: false,
        idealEdgeLength: 90,
        nodeRepulsion: 4500,
        randomize: true,
      } as cytoscape.LayoutOptions,
      wheelSensitivity: 0.2,
    })

    if (onNodeClick) {
      cy.on('tap', 'node', (evt) => onNodeClick(evt.target.id()))
    }

    cyRef.current = cy
    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [data, onNodeClick])

  return <div ref={ref} className="h-full w-full" />
}
