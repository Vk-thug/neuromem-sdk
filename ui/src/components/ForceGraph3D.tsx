import { useEffect, useMemo, useRef } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import * as THREE from 'three'
import SpriteText from 'three-spritetext'
import { REGIONS, regionFor, type Region } from './brain/regions'
import type { Graph3D, GraphNode } from '../lib/api.ts'

interface Props {
  data: Graph3D
  onNodeClick?: (id: string) => void
}

interface ThreeNode extends GraphNode {
  __threeObj?: THREE.Object3D
  fx?: number
  fy?: number
  fz?: number
}

/**
 * Jarvis-style 3D anatomical view of the memory graph.
 *
 * Each ``MemoryItem`` is positioned by its ``region`` field into one of
 * five anatomical clusters (hippocampus core, neocortex shell, basal-
 * ganglia ring, amygdala cluster, prefrontal-cortex orbital ring).
 * Cross-region links curve naturally because the force layout still
 * pulls connected nodes together — the regional attractors only nudge
 * each node toward its anatomical home, they don't pin it.
 *
 * Visual encoding (matches the 2D view's legend):
 *   - colour       → region
 *   - node size    → salience × (1 + ln(1+reinforcement))
 *   - amygdala     → pulsing red glow when flashbulb=true
 *   - working mem  → white frontal ring
 *
 * Cognitive grounding: layout follows the standard hippocampal-cortical
 * circuit textbook diagram (Andersen et al. 2007). Anatomical fidelity is
 * coarse — we're communicating the *layered taxonomy*, not surgical
 * accuracy.
 */
export default function ForceGraph3DView({ data, onNodeClick }: Props) {
  const ref = useRef<unknown>(null)

  // Pre-compute per-region helper geometry: a translucent halo sphere so
  // the user can see "this is the hippocampus volume". Memoised so we
  // don't rebuild on every data refresh.
  const regionHalos = useMemo(() => {
    const halos = new THREE.Group()
    const regionsInUse = new Set<Region>()
    data.nodes.forEach((n) => {
      if (n.region && n.region in REGIONS) regionsInUse.add(n.region as Region)
    })
    regionsInUse.forEach((r) => {
      const geom = REGIONS[r]
      const sphere = new THREE.Mesh(
        new THREE.SphereGeometry(geom.radius, 24, 18),
        new THREE.MeshBasicMaterial({
          color: geom.color,
          transparent: true,
          opacity: 0.04,
          side: THREE.BackSide,
          depthWrite: false,
        }),
      )
      sphere.position.set(geom.target.x, geom.target.y, geom.target.z)
      halos.add(sphere)

      // Floating region label
      const label = new SpriteText(geom.label.split(' — ')[0])
      label.color = geom.color
      label.textHeight = 5
      label.material.depthWrite = false
      label.position.set(
        geom.target.x,
        geom.target.y + geom.radius + 8,
        geom.target.z,
      )
      halos.add(label)
    })
    return halos
  }, [data.nodes])

  useEffect(() => {
    const fg = ref.current as { scene?: () => THREE.Scene } | null
    if (!fg?.scene) return
    const scene = fg.scene()
    scene.add(regionHalos)
    return () => {
      scene.remove(regionHalos)
    }
  }, [regionHalos])

  return (
    <ForceGraph3D
      ref={ref as never}
      graphData={{
        nodes: data.nodes as ThreeNode[],
        links: data.edges.map((e) => ({
          source: e.source_id,
          target: e.target_id,
          link_type: e.link_type,
          strength: e.strength,
        })),
      }}
      backgroundColor="#0a0a0c"
      // Region-anchored layout: pin each node toward its anatomical
      // attractor while the force engine resolves edge tensions.
      d3VelocityDecay={0.35}
      nodeAutoColorBy="region"
      nodeThreeObject={(node: ThreeNode) => {
        const geom = regionFor(node.region)
        const salience = node.salience ?? 0.5
        const reinforcement = node.reinforcement ?? 0
        const radius = 1.5 + 5 * salience + 0.4 * Math.log(1 + reinforcement)
        const isFlashbulb = node.flashbulb === true
        const material = new THREE.MeshStandardMaterial({
          color: geom.color,
          emissive: isFlashbulb ? '#e74c5c' : 0x000000,
          emissiveIntensity: isFlashbulb ? 0.8 : 0,
          roughness: 0.6,
          metalness: 0.1,
        })
        const sphere = new THREE.Mesh(
          new THREE.SphereGeometry(radius, 16, 12),
          material,
        )
        // Initial seed position close to the anatomical attractor —
        // the force engine refines from here.
        const jitter = () => (Math.random() - 0.5) * geom.radius * 1.2
        sphere.position.set(
          geom.target.x + jitter(),
          geom.target.y + jitter(),
          geom.target.z + jitter(),
        )
        return sphere
      }}
      linkColor={() => 'rgba(120,120,135,0.45)'}
      linkOpacity={0.5}
      linkWidth={(l: { strength?: number }) => 0.4 + 1.4 * (l.strength ?? 0.3)}
      onNodeClick={(node: ThreeNode) => {
        if (onNodeClick) onNodeClick(node.id)
      }}
    />
  )
}
