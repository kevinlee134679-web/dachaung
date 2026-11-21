import { webcrypto } from 'node:crypto'
import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import { afterEach, expect, it, vi } from 'vitest'
import { App } from '../../../src/app/App'
import { navigate } from '../../../src/session/navigation'
import { updateSession } from '../../../src/session/session'

interface MockResponse {
  ok: boolean
  status: number
  json: () => Promise<{ request_id: string; status: string; data: unknown; error: null }>
}

function success(data: unknown): MockResponse {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ request_id: 'request-a', status: 'success', data, error: null }),
  }
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it('subpage change invalidates a delayed old medication list', async () => {
  const response = Promise.withResolvers<MockResponse>()
  const sent = Promise.withResolvers<undefined>()
  const received = Promise.withResolvers<undefined>()
  const knowledgeRequests: string[] = []
  const patient = {
    patient: { patient_id: 'pa', display_name: '患者', timezone: 'Asia/Shanghai' },
    relationship: 'self',
    effective_scopes: ['medication:read', 'knowledge:read'],
  }
  vi.stubGlobal('crypto', webcrypto)
  localStorage.clear()
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.endsWith('/health')) return Promise.resolve(success({}))
      if (url.endsWith('/auth/me')) {
        return Promise.resolve(
          success({
            account: { account_id: 'demo-patient-a', display_name: '患者', is_simulated: true },
            csrf_token: 'csrf',
            current_patient_id: 'pa',
            patients: [patient],
          }),
        )
      }
      if (url.includes('/medications')) {
        sent.resolve(undefined)
        return response.promise
      }
      if (url.startsWith('/api/v1/knowledge')) knowledgeRequests.push(url)
      return Promise.resolve(success({ items: [], next_cursor: null }))
    }),
  )
  updateSession(draft => {
    draft.context = null
    draft.patient = null
    draft.page = 'home'
    draft.tab = 'overview'
    draft.epoch++
    draft.switchingPatient = false
  })
  render(() => <App />)
  await screen.findByText('退出')
  navigate('medication', 'meds')
  await sent.promise
  fireEvent.click(screen.getByRole('button', { name: '药学知识' }))
  await waitFor(() => expect(knowledgeRequests).toEqual(['/api/v1/knowledge?kind=medical&limit=100']))
  expect(await screen.findByText('目前没有适用的审核药学资料。用药问题请向实际医生或药师核实。')).toBeTruthy()
  response.resolve({
    ok: true,
    status: 200,
    json: () => {
      received.resolve(undefined)
      return Promise.resolve({
        request_id: 'request-a',
        status: 'success',
        data: {
          items: [{ medication_id: 'old-med', name: 'STALE_MEDICATION', notes: null, meta: { revision: 1 } }],
          next_cursor: null,
        },
        error: null,
      })
    },
  })
  await received.promise
  const settled = Promise.withResolvers<undefined>()
  setTimeout(settled.resolve, 0)
  await settled.promise
  expect(screen.queryByText('STALE_MEDICATION')).toBeNull()
})
