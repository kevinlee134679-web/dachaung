import type { PatientAccess } from '../../../src/session/session'
import { webcrypto } from 'node:crypto'
import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import { Show } from 'solid-js'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { HomePage } from '../../../src/features/home/home-page'
import { state, updateSession } from '../../../src/session/session'

const patient: PatientAccess = {
  patient: { patient_id: 'pa', display_name: '甲', timezone: 'Asia/Shanghai' },
  relationship: 'self',
  effective_scopes: [],
}
function choose(scopes: string[]) {
  updateSession(draft => {
    draft.epoch++
    draft.patient = { ...patient, effective_scopes: scopes }
    draft.context = {
      account: { account_id: 'account-a', display_name: '甲', is_simulated: true },
      csrf_token: 'csrf',
      current_patient_id: 'pa',
      patients: [],
    }
    draft.page = 'home'
    draft.switchingPatient = false
  })
}
interface TestResponse {
  ok: boolean
  status: number
  json: () => Promise<{ request_id: string; status: string; data: unknown; error: null }>
}
function success(data: unknown): TestResponse {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ request_id: 'test', status: 'success', data, error: null }),
  }
}
const page = (items: unknown[]) => ({ items, next_cursor: null })
const session = {
  session_id: 'session-a',
  status: 'active',
  ui_mode: 'normal',
  turn_count: 0,
  opened_at: '2026-11-17T00:00:00Z',
  meta: { revision: 1 },
}
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto)
  localStorage.clear()
  sessionStorage.clear()
  choose([])
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it('home requests nothing without read scopes', async () => {
  const fetch = vi.fn(() => success({}))
  vi.stubGlobal('fetch', fetch)
  render(() => <HomePage />)
  expect(screen.getByText('今日待办')).toBeTruthy()
  expect(screen.getByText('AI 对话')).toBeTruthy()
  await waitFor(() => expect(fetch).not.toHaveBeenCalled())
})

it('home loads dose slots and plans only with plan access and displays slot text safely', async () => {
  choose(['plan:read'])
  const markup = '<img src=x onerror=evil()>'
  const fetch = vi.fn((url: string) => {
    if (url.includes('/dose-slots?')) {
      return success(
        page([
          {
            dose_slot_id: 'slot-a',
            medication_id: 'medication-a',
            plan_id: 'plan-a',
            plan_version: 1,
            plan_entry_id: 'entry-a',
            scheduled_at: '2026-11-17T00:00:00Z',
            status: 'active',
          },
        ]),
      )
    }
    return success(
      page([
        {
          plan_id: 'plan-a',
          plan_version: 1,
          entries: [
            {
              plan_entry_id: 'entry-a',
              medication_name_snapshot: markup,
              dose_value: '1',
              dose_unit: '片',
            },
          ],
        },
      ]),
    )
  })
  vi.stubGlobal('fetch', fetch)
  const { container } = render(() => <HomePage />)
  await screen.findByText(markup)
  expect(container.querySelector('img')).toBeNull()
  expect(fetch.mock.calls.map(([url]) => url)).toEqual([
    expect.stringContaining('/patients/pa/dose-slots?'),
    '/api/v1/patients/pa/plans?limit=100',
  ])
})

it('home offers the medication list when today has no slots', async () => {
  choose(['plan:read', 'medication:read', 'drafts:read', 'drafts:write', 'drafts:submit'])
  vi.stubGlobal(
    'fetch',
    vi.fn(() => success(page([]))),
  )
  render(() => <HomePage />)
  await screen.findByText('今天没有服药安排。')
  fireEvent.click(screen.getByText('填写用药清单'))
  await waitFor(() => expect([state.page, state.tab]).toEqual(['medication', 'medication-list']))
})

it('home displays pending invitations with intervention access', async () => {
  choose(['interventions:read'])
  const fetch = vi.fn(() =>
    success({
      items: [
        {
          invitation_id: 'invite-a',
          title: '支持邀请',
          description: '可以选择对话',
          status: 'pending',
          valid_until: '2099-01-01T00:00:00Z',
          session_id: null,
        },
      ],
    }),
  )
  vi.stubGlobal('fetch', fetch)
  render(() => <HomePage />)
  await screen.findByText('可以选择对话')
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetch).toHaveBeenCalledWith('/api/v1/patients/pa/invitations', expect.anything())
})

it('home loads dialogue with its scope and starts a conversation inline', async () => {
  choose(['dialogue:read'])
  let opened = false
  const markup = '<img src=x onerror=evil()>'
  const fetch = vi.fn((url: string, options: RequestInit) => {
    if (url === '/api/v1/sessions' && options.method === 'POST') {
      opened = true
      return success({ session_id: session.session_id })
    }
    if (url === '/api/v1/sessions?patient_id=pa&limit=100') return success(page(opened ? [session] : []))
    if (url === '/api/v1/sessions/session-a/messages?limit=100') {
      return success(
        page([
          {
            role: 'assistant',
            content: markup,
            generation_status: 'not_applicable',
            message_id: 'm',
            generation_id: 'g',
          },
        ]),
      )
    }
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetch)
  const { container } = render(() => <HomePage />)
  fireEvent.click(await screen.findByText('开始对话'))
  await screen.findByText(markup)
  expect(container.querySelector('img')).toBeNull()
  expect(state.page).toBe('home')
  expect(fetch.mock.calls.map(([url]) => url)).toEqual([
    '/api/v1/sessions?patient_id=pa&limit=100',
    '/api/v1/sessions',
    '/api/v1/sessions?patient_id=pa&limit=100',
    '/api/v1/sessions/session-a/messages?limit=100',
  ])
})

it('home opens the saved conversation before a newer active session', async () => {
  choose(['dialogue:read'])
  sessionStorage.setItem('reference:account-a:pa:support-session', session.session_id)
  const fetch = vi.fn((url: string) => {
    if (url === '/api/v1/sessions?patient_id=pa&limit=100') {
      return success(
        page([
          { ...session, status: 'closed' },
          { ...session, session_id: 'session-b' },
        ]),
      )
    }
    if (url === '/api/v1/sessions/session-a/messages?limit=100') {
      return success(
        page([
          {
            role: 'assistant',
            content: '保存的对话',
            generation_status: 'not_applicable',
            message_id: 'm',
            generation_id: 'g',
          },
        ]),
      )
    }
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetch)
  render(() => <HomePage />)
  await screen.findByText('保存的对话')
  expect(fetch).toHaveBeenCalledTimes(2)
})

it('home discards delayed dose content after switching patient', async () => {
  choose(['plan:read'])
  const reply = Promise.withResolvers<TestResponse>()
  const fetch = vi.fn(() => reply.promise)
  vi.stubGlobal('fetch', fetch)
  const { container } = render(() => (
    <Show when={state.epoch + 1} keyed>
      <HomePage />
    </Show>
  ))
  await waitFor(() => expect(fetch).toHaveBeenCalled())
  updateSession(draft => {
    draft.epoch++
    draft.patient = { ...patient, patient: { ...patient.patient, patient_id: 'pb' }, effective_scopes: [] }
  })
  reply.resolve(success(page([{ dose_slot_id: 'PRIVATE_OLD_PATIENT' }])))
  const settled = Promise.withResolvers<undefined>()
  setTimeout(settled.resolve, 0)
  await settled.promise
  expect(container.textContent).not.toContain('PRIVATE_OLD_PATIENT')
  expect(fetch).toHaveBeenCalledTimes(1)
})
