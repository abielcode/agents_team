import { create } from 'zustand'

/**
 * Global app state via Zustand.
 * Keeps active project + sprint selection so nav stays in sync.
 */
export const useStore = create((set) => ({
  activeProjectId: null,
  activeSprintId: null,
  setActiveProject: (id) => set({ activeProjectId: id }),
  setActiveSprint: (id) => set({ activeSprintId: id }),
}))
