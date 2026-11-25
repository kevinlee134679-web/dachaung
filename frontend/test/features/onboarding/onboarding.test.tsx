import { webcrypto } from 'node:crypto'
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
      'drafts:read',
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
  vi.stubGlobal('crypto', webcrypto)
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

it('reuses a selected medicine, restores a saved draft and confirms its exact revision', async () => {
  const posts: { url: string; body: Record<string, unknown> }[] = []
  const confirmedPlan = { plan_id: 'plan-a', plan_version: 1, effective_from: '2026-01-01T00:00:00Z' }
  let savedDraft: Record<string, unknown> = {}
  let havePlan = false
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      if (options.method === 'POST') {
        if (typeof options.body !== 'string') throw new TypeError('Expected a JSON request body')
        const parsed: unknown = JSON.parse(options.body)
        if (parsed === null || typeof parsed !== 'object') throw new TypeError('Expected a JSON object')
        const body: Record<string, unknown> = { ...parsed }
        posts.push({ url, body })
        if (url.endsWith('/drafts')) {
          savedDraft = {
            ...body,
            draft_id: 'draft-a',
            content_revision: 3,
            meta: { revision: 7, updated_at: '2026-01-01T00:00:00Z' },
            status: 'editing',
            formal_plan: null,
            return_reason: null,
          }
          return success(savedDraft)
        }
        if (url.endsWith('/submit')) {
          savedDraft = { ...savedDraft, status: 'pending_confirmation' }
          return success(savedDraft)
        }
        if (url.endsWith('/plan-confirmations')) {
          havePlan = true
          savedDraft = {
            ...savedDraft,
            status: 'confirmed',
            formal_plan: { plan_id: 'plan-a', plan_version: 1 },
          }
          throw new TypeError('模拟确认响应丢失')
        }
        throw new Error(`Unexpected POST ${url}`)
      }
      if (url.endsWith('/drafts/draft-a')) return success(savedDraft)
      if (url.endsWith('/plans/plan-a/versions/1')) {
        return success({ ...confirmedPlan, source_draft_id: 'draft-a', entries: savedDraft['entries'] })
      }
      if (url.includes('/plans?')) return success({ items: havePlan ? [confirmedPlan] : [], next_cursor: null })
      if (url.includes('/dose-slots?')) {
        return success({
          items: [
            {
              dose_slot_id: 'slot-a',
              medication_id: 'med-a',
              plan_id: 'plan-a',
              plan_version: 1,
              plan_entry_id: 'entry-a',
              scheduled_at: '2026-01-01T00:00:00Z',
              status: 'active',
            },
          ],
          next_cursor: null,
        })
      }
      return success({ items: [{ medication_id: 'med-a', name: '药甲' }], next_cursor: null })
    }),
  )
  const onConfirmed = vi.fn(() => Promise.resolve())
  const initial = render(() => <MedicationListForm onConfirmed={onConfirmed} />)
  fireEvent.change(await screen.findByLabelText('选择已有药品'), { target: { value: 'med-a' } })
  fireEvent.input(screen.getByLabelText(/每次剂量/), { target: { value: '1' } })
  fireEvent.input(screen.getByLabelText(/剂量单位/), { target: { value: '片' } })
  fireEvent.change(screen.getByLabelText('固定频次'), { target: { value: 'weekly' } })
  fireEvent.click(await screen.findByLabelText('周一'))
  fireEvent.input(screen.getByLabelText('服药时间 1'), { target: { value: '08:00' } })
  fireEvent.click(screen.getByRole('button', { name: '添加时段' }))
  fireEvent.input(await screen.findByLabelText('服药时间 2'), { target: { value: '20:00' } })
  fireEvent.input(screen.getByLabelText(/餐前、餐后/), { target: { value: '餐后' } })
  fireEvent.input(screen.getByLabelText('开始日期'), { target: { value: '2026-01-01' } })
  fireEvent.click(screen.getByRole('button', { name: '保存草稿' }))
  await screen.findByText(/草稿已保存 · 内容修订 3/)
  expect(posts.map(post => post.url)).toEqual(['/api/v1/patients/pa/drafts'])
  expect(posts[0]?.body).toEqual({
    source_file_ids: [],
    entries: [
      expect.objectContaining({
        medication_id: 'med-a',
        dose_value: '1',
        dose_unit: '片',
        start_date: '2026-01-01',
        schedule: { kind: 'weekly', times: ['08:00', '20:00'], weekdays: [1] },
        meal_requirement: '餐后',
      }),
    ],
  })

  initial.unmount()
  render(() => <MedicationListForm onConfirmed={onConfirmed} />)
  await screen.findByText('已恢复上次保存的草稿。')
  expect(screen.getByLabelText<HTMLSelectElement>('选择已有药品').value).toBe('med-a')
  expect(screen.getByLabelText<HTMLInputElement>('服药时间 2').value).toBe('20:00')
  expect(screen.getByLabelText<HTMLInputElement>('周一').checked).toBe(true)

  const confirm = screen.getByRole('button', { name: '确认并生成安排' })
  fireEvent.click(confirm)
  await screen.findByText(/确认正式计划：模拟确认响应丢失/)
  expect(onConfirmed).not.toHaveBeenCalled()
  fireEvent.click(confirm)
  await waitFor(() => expect(onConfirmed).toHaveBeenCalledOnce())
  await screen.findByRole('button', { name: '查看首个安排' })
  expect(posts.map(post => post.url)).toEqual([
    '/api/v1/patients/pa/drafts',
    '/api/v1/drafts/draft-a/submit',
    '/api/v1/patients/pa/plan-confirmations',
  ])
  expect(posts[1]?.body).toEqual({ expected_revision: 7, content_revision: 3 })
  expect(posts[2]?.body).toMatchObject({
    draft_id: 'draft-a',
    draft_revision: 3,
    existing_plan_id: null,
    expected_plan_version: null,
    confirmed: true,
  })
  expect(posts[2]?.body).toHaveProperty('effective_from', expect.any(String))
})
