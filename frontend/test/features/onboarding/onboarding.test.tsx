import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { resolveOnboarding } from '../../../src/features/onboarding/onboarding'
import { MedicationListForm } from '../../../src/features/plan-drafts/medication-list-form'
import { state, updateSession } from '../../../src/session/session'

function choose(relationship = 'self'): void {
  const patient = {
    patient: { patient_id: 'pa', display_name: '甲', timezone: 'Asia/Shanghai' },
    relationship,
    effective_scopes: [
      'profile:read',
      'plan:read',
      'medication:read',
      'medication:edit',
      'drafts:write',
      'drafts:submit',
    ],
  }
  updateSession(draft => {
    draft.epoch++
    draft.context = {
      account: { account_id: 'account-a', display_name: '甲', is_simulated: true },
      csrf_token: 'csrf',
      current_patient_id: 'pa',
      patients: [patient],
    }
    draft.patient = patient
    draft.onboarding = null
  })
}

function success(data: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ request_id: 'test', status: 'success', data, error: null }),
  }
}

function missingProfile() {
  return {
    ok: false,
    status: 404,
    json: () =>
      Promise.resolve({
        request_id: 'test',
        status: 'error',
        data: null,
        error: { code: 'PROFILE_NOT_AVAILABLE', message: '没有画像' },
      }),
  }
}

beforeEach(() => {
  sessionStorage.clear()
  localStorage.clear()
  choose()
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
        : missingProfile()
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
  choose('family')
  fetch.mockClear()
  await resolveOnboarding()
  expect(state.onboarding).toBeNull()
  expect(fetch).not.toHaveBeenCalled()
})

it('creates and confirms a medication plan in order', async () => {
  const posts: { url: string; body: unknown }[] = []
  let confirmed = false
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      if (options.method === 'POST') {
        if (typeof options.body !== 'string') throw new TypeError('Expected a JSON request body')
        posts.push({ url, body: JSON.parse(options.body) as unknown })
        if (url.endsWith('/medications')) return success({ medication_id: 'med-a', name: '药甲' })
        if (url.endsWith('/drafts')) return success({ draft_id: 'draft-a', content_revision: 3, meta: { revision: 7 } })
        if (url.endsWith('/submit')) return success({})
        confirmed = true
        return success({})
      }
      if (url.includes('/plans/plan-a/versions/1')) {
        return success({
          entries: [
            {
              medication_id: 'med-a',
              medication_name_snapshot: '药甲',
              dose_value: '1',
              dose_unit: '片',
              start_date: '2026-01-01',
              end_date: null,
              schedule: { times: ['08:00'] },
              meal_requirement: '餐后',
              medical_notes: null,
              strict_timing: null,
              min_interval_minutes: null,
              source_file_ids: [],
            },
          ],
        })
      }
      if (url.includes('/plans?')) {
        return success({
          items: confirmed ? [{ plan_id: 'plan-a', plan_version: 1, effective_from: '2026-01-01T00:00:00Z' }] : [],
          next_cursor: null,
        })
      }
      return success({ items: confirmed ? [{ medication_id: 'med-a', name: '药甲' }] : [], next_cursor: null })
    }),
  )
  const onConfirmed = vi.fn(() => Promise.resolve())
  render(() => <MedicationListForm onConfirmed={onConfirmed} />)
  fireEvent.input(await screen.findByLabelText('药名'), { target: { value: '药甲' } })
  fireEvent.input(screen.getByLabelText('剂量'), { target: { value: '1' } })
  fireEvent.input(screen.getByLabelText('单位'), { target: { value: '片' } })
  fireEvent.input(screen.getByLabelText(/服药时间/), { target: { value: '08:00' } })
  fireEvent.change(screen.getByLabelText('用餐要求'), { target: { value: '餐后' } })
  fireEvent.input(screen.getByLabelText('开始日期'), { target: { value: '2026-01-01' } })
  fireEvent.click(screen.getByRole('button', { name: '确认清单' }))
  await waitFor(() => expect(onConfirmed).toHaveBeenCalledOnce())
  expect(posts.map(post => post.url)).toEqual([
    '/api/v1/patients/pa/medications',
    '/api/v1/patients/pa/drafts',
    '/api/v1/drafts/draft-a/submit',
    '/api/v1/patients/pa/plan-confirmations',
  ])
  expect(posts[0]?.body).toEqual({ name: '药甲', notes: null })
  expect(posts[1]?.body).toEqual({
    source_file_ids: [],
    entries: [
      expect.objectContaining({
        medication_id: 'med-a',
        dose_value: '1',
        dose_unit: '片',
        start_date: '2026-01-01',
        schedule: { kind: 'daily', times: ['08:00'], weekdays: [] },
        meal_requirement: '餐后',
      }),
    ],
  })
  expect(posts[2]?.body).toEqual({ expected_revision: 7, content_revision: 3 })
  expect(posts[3]?.body).toMatchObject({
    draft_id: 'draft-a',
    draft_revision: 3,
    existing_plan_id: null,
    expected_plan_version: null,
    confirmed: true,
  })
  expect(posts[3]?.body).toHaveProperty('effective_from', expect.any(String))
})
