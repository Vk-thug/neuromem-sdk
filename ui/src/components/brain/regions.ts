/**
 * Anatomical region geometry for the 3D "Jarvis" brain view.
 *
 * Each region defines a target attractor point + a soft sphere radius in
 * 3D space. The force-graph layer reads these and pins each node toward
 * its region's target via a custom force, while still letting edges pull
 * connected memories together. The result: episodic memories cluster in
 * a hippocampus core, semantic memories form a cortical shell, etc.,
 * but cross-region links curve naturally.
 *
 * Coordinates are in arbitrary units; the force graph normalises by
 * iterating until layout converges. Z-axis is "depth" — hippocampus and
 * basal ganglia sit deeper in the brain than the cortex, mirroring the
 * mid-sagittal anatomy.
 */

export type Region =
  | 'hippocampus'
  | 'neocortex'
  | 'basal_ganglia'
  | 'amygdala'
  | 'prefrontal_cortex'

export interface RegionGeometry {
  /** Target attractor point for nodes in this region. */
  target: { x: number; y: number; z: number }
  /** Soft sphere radius — how tightly nodes cluster around the target. */
  radius: number
  /** Display colour (matches Tailwind theme `colors.<region>`). */
  color: string
  /** Long-form label for legend / tooltip. */
  label: string
}

export const REGIONS: Record<Region, RegionGeometry> = {
  // Hippocampus — deep, central, blue. Episodic + verbatim live here.
  hippocampus: {
    target: { x: 0, y: 0, z: -40 },
    radius: 30,
    color: '#4f8cff',
    label: 'Hippocampus — episodic + verbatim',
  },
  // Neocortex — outer shell. Semantic memories radiate out from the core.
  neocortex: {
    target: { x: 0, y: 0, z: 90 },
    radius: 110,
    color: '#f3b557',
    label: 'Neocortex — semantic',
  },
  // Basal ganglia — lower band. Procedural memories cluster here.
  basal_ganglia: {
    target: { x: 0, y: -70, z: -10 },
    radius: 35,
    color: '#5fc587',
    label: 'Basal ganglia — procedural',
  },
  // Amygdala — pulse-red cluster. High-emotional / flashbulb only.
  amygdala: {
    target: { x: 50, y: -30, z: -25 },
    radius: 18,
    color: '#e74c5c',
    label: 'Amygdala — flashbulb / high emotional weight',
  },
  // Prefrontal cortex — frontal "executive" ring. Working memory slots.
  prefrontal_cortex: {
    target: { x: 0, y: 80, z: 60 },
    radius: 25,
    color: '#dcdcdc',
    label: 'Prefrontal cortex — working memory (Cowan 4)',
  },
}

export function regionFor(region?: string): RegionGeometry {
  if (region && region in REGIONS) return REGIONS[region as Region]
  return REGIONS.neocortex
}
