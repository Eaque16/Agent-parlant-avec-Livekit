import { describe, expect, it } from 'vitest'
import { isNewerBusinessState } from './useBusinessState'
import type { BusinessState } from '../types/businessState'

const state = { state_version: 4 } as BusinessState

describe('useBusinessState', () => {
  it('déduplique deux états de même version', () => {
    expect(isNewerBusinessState(state, 3)).toBe(true)
    expect(isNewerBusinessState(state, 4)).toBe(false)
  })

  it('refuse une version ancienne afin que la resynchronisation ne perde pas l’état', () => {
    expect(isNewerBusinessState({ ...state, state_version: 3 }, 4)).toBe(false)
  })
})
