import { cleanup } from '@solidjs/testing-library'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { resolveOnboarding } from '../../../src/features/onboarding/onboarding'
import { state, updateSession } from '../../../src/session/session'
import { choose, failure, success } from '../../support'

const scopes = [
  'profile:read',
  'plan:read',
  'medication:read',
  'medication:edit',
  'drafts:read',
  'drafts:write',
  'drafts:submit',
]

beforeEach(() => {
  sessionStorage.clear()
  localStorage.clear()
  choose({ scopes })
  updateSession(draft => {
    draft.epoch++
    draft.onboarding = null
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('chooses the first incomplete onboarding step only for the patient', async () => {
  let profileExists = false
  let planExists = false
  const fetch = vi.fn((url: string) =>
    url.includes('/profiles/current')
      ? profileExists
        ? success({})
        : failure(404, 'PROFILE_NOT_AVAILABLE', '没有画像')
      : success({ items: planExists ? [{}] : [], next_cursor: null }),
  )
  vi.stubGlobal('fetch', fetch)
  await resolveOnboarding()
  expect(state.onboarding).toBe('questionnaire')
  profileExists = true
  await resolveOnboarding()
  expect(state.onboarding).toBe('medication')
  planExists = true
  await resolveOnboarding()
  expect(state.onboarding).toBeNull()
  choose({ relationship: 'family', scopes })
  updateSession(draft => {
    draft.epoch++
    draft.onboarding = null
  })
  fetch.mockClear()
  await resolveOnboarding()
  expect(state.onboarding).toBeNull()
  expect(fetch).not.toHaveBeenCalled()
})
