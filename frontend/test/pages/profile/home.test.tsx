import type { PatientAccess } from '../../../src/session/session'
import { cleanup, render, screen, waitFor } from '@solidjs/testing-library'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { HomePage } from '../../../src/pages/home/home-page'
import { updateSession } from '../../../src/session/session'

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
  })
}
function success(data: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ request_id: 'test', status: 'success', data, error: null }),
  }
}
beforeEach(() => choose([]))
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('home reads authoritative support and service status without writes or markup execution', async () => {
  choose(['support:read', 'services:read'])
  const calls: [string, string | undefined][] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      calls.push([url, options.method])
      return url.includes('support-recommendations')
        ? success({
            need_status: 'needed',
            primary_action: { title: '<img src=x onerror=evil()>', reason: '明确需求' },
            secondary_actions: [],
          })
        : success({
            items: [{ service_id: 'service-a', service_name: '虚构服务', status: 'in_progress' }],
            next_cursor: null,
          })
    }),
  )
  const { container } = render(() => <HomePage />)
  await screen.findByText((_, element) => element?.tagName === 'P' && element.textContent === '虚构服务 · 模拟处理中')
  expect(screen.getByText('<img src=x onerror=evil()>')).toBeTruthy()
  expect(container.querySelector('img')).toBeNull()
  expect(calls.every(([, method]) => method === 'GET')).toBe(true)
})

it('home does not request support facts without their exact scopes', async () => {
  const fetch = vi.fn(() => success({}))
  vi.stubGlobal('fetch', fetch)
  render(() => <HomePage />)
  await waitFor(() => expect(screen.getByText(/当前对象/)).toBeTruthy())
  expect(fetch).not.toHaveBeenCalled()
})

it('home discards delayed service content after switching patient', async () => {
  choose(['services:read'])
  const reply = Promise.withResolvers<{
    ok: boolean
    status: number
    json: () => Promise<{ status: string; data: unknown }>
  }>()
  const fetch = vi.fn(() => reply.promise)
  vi.stubGlobal('fetch', fetch)
  const { container } = render(() => <HomePage />)
  await waitFor(() => expect(fetch).toHaveBeenCalled())
  updateSession(draft => {
    draft.epoch++
    draft.patient = { ...patient, patient: { ...patient.patient, patient_id: 'pb' }, effective_scopes: [] }
  })
  reply.resolve(
    success({
      items: [{ service_id: 'old', service_name: 'PRIVATE_OLD_PATIENT', status: 'completed' }],
      next_cursor: null,
    }),
  )
  const settled = Promise.withResolvers<undefined>()
  setTimeout(settled.resolve, 0)
  await settled.promise
  expect(fetch).toHaveBeenCalledWith('/api/v1/patients/pa/services?limit=3&order=desc', expect.anything())
  expect(container.textContent).not.toContain('PRIVATE_OLD_PATIENT')
})
