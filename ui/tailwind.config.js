/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Anatomical palette — used by both the 3D view and the legend
        // chips in the 2D Cytoscape view, so the 2 modes share a visual
        // language. Drawn from the colour scheme commonly used in
        // hippocampal-circuit textbook diagrams (Andersen et al. 2007).
        hippocampus: '#4f8cff',       // crisp blue
        neocortex: '#f3b557',          // warm gold
        basal_ganglia: '#5fc587',      // verdant green
        amygdala: '#e74c5c',           // alarm red
        prefrontal_cortex: '#dcdcdc',  // pale white-grey
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
