/**
 * Tab persistence — stores open memory ids in localStorage so reopening
 * the UI restores the workspace exactly. Keyed by user_id so multiple
 * users on one machine don't share tab state.
 *
 * Cognitive note: Cowan's working memory limit is ~4 items. We
 * deliberately allow more than 4 tabs but render a subtle "exceeds
 * working-memory capacity" warning past 4 — a UX nudge that lines up
 * with the brain layer's PFC slot count.
 */

interface TabState {
  open: string[]      // memory ids
  active: string | null
}

const KEY = 'neuromem.tabs'

export function loadTabs(userId: string): TabState {
  try {
    const raw = localStorage.getItem(`${KEY}:${userId}`)
    if (!raw) return { open: [], active: null }
    const parsed = JSON.parse(raw) as TabState
    return {
      open: Array.isArray(parsed.open) ? parsed.open : [],
      active: parsed.active ?? null,
    }
  } catch {
    return { open: [], active: null }
  }
}

export function saveTabs(userId: string, state: TabState): void {
  try {
    localStorage.setItem(`${KEY}:${userId}`, JSON.stringify(state))
  } catch {
    // localStorage quota / disabled — non-fatal.
  }
}
