// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mockSystemApi = vi.hoisted(() => ({
  checkHealth: vi.fn(),
  fetchAvailableModels: vi.fn(),
  updateDefaultModel: vi.fn(),
  triggerUpdate: vi.fn(),
}))

vi.mock('@/api/hermes/system', () => mockSystemApi)

import { useAppStore } from '@/stores/hermes/app'

describe('App Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    window.localStorage.clear()
  })

  it('persists desktop sidebar collapsed state to localStorage', () => {
    const store = useAppStore()

    expect(store.sidebarCollapsed).toBe(false)

    store.toggleSidebarCollapsed()
    expect(store.sidebarCollapsed).toBe(true)
    expect(window.localStorage.getItem('hermes_sidebar_collapsed')).toBe('1')

    store.toggleSidebarCollapsed()
    expect(store.sidebarCollapsed).toBe(false)
    expect(window.localStorage.getItem('hermes_sidebar_collapsed')).toBe('0')
  })
})
