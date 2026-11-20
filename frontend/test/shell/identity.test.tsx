import { webcrypto } from 'node:crypto'
import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { state, updateSession } from '../../src/session/session'
import { App } from '../../src/shell/App'
import { navigate } from '../../src/shell/navigation'

function patient(id: string, relationship = 'self') {
  return {
    patient: { patient_id: id, display_name: id, timezone: 'Asia/Shanghai' },
    relationship,
    effective_scopes: [],
  }
}
function context(account = 'demo-patient-a') {
  return {
    account: { account_id: account, display_name: account, is_simulated: true },
    csrf_token: `csrf-${account}`,
    current_patient_id: 'pa',
    patients: [patient('pa'), patient('pb', 'family')],
  }
}
function success(data: unknown): { ok: boolean; status: number; json: () => Promise<unknown> } {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ request_id: 'test', status: 'success', data, error: null }),
  }
}
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto)
  localStorage.clear()
  updateSession(draft => {
    draft.context = null
    draft.patient = null
    draft.page = 'home'
    draft.tab = 'overview'
    draft.epoch++
    draft.switchingPatient = false
  })
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it.each(['demo-patient-a', 'demo-family', 'demo-admin'])('logout survives navigation for %s', async account => {
  const sent = Promise.withResolvers<undefined>()
  const reply = Promise.withResolvers<ReturnType<typeof success>>()
  const requests: [string, string | undefined, string | undefined][] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      if (url.endsWith('/health')) return Promise.resolve(success({}))
      if (url.endsWith('/auth/me')) return Promise.resolve(success(context(account)))
      // rewards page reads are irrelevant; only writes must follow the session
      if (options.method === 'GET') return Promise.resolve(success({ items: [], next_cursor: null }))
      requests.push([url, options.method, new Headers(options.headers).get('X-CSRF-Token') ?? undefined])
      sent.resolve(undefined)
      return reply.promise
    }),
  )
  render(() => <App />)
  const logout = await screen.findByText('退出')
  navigate('rewards')
  fireEvent.click(logout)
  await sent.promise
  navigate('rewards')
  reply.resolve(success({ outcome: 'logged_out' }))
  await screen.findByText('管理自己的用药')
  expect(requests).toEqual([['/api/v1/auth/logout', 'POST', `csrf-${account}`]])
  expect(state.context).toBeNull()
  expect(state.patient).toBeNull()
  expect(screen.getByRole('status').textContent).toBe('当前会话已退出。')
})

it('retained logout cannot affect a replacement session', async () => {
  const requests: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      requests.push(url)
      return success(url.endsWith('/auth/me') ? context() : {})
    }),
  )
  render(() => <App />)
  const logout = await screen.findByText('退出')
  updateSession(draft => {
    expect(draft.context).not.toBeNull()
    if (draft.context != null) draft.context.csrf_token = 'replacement-session-csrf'
  })
  fireEvent.click(logout)
  expect(requests.some(url => url.endsWith('/auth/logout'))).toBe(false)
  expect(state.context?.csrf_token).toBe('replacement-session-csrf')
})

it('prevents navigation while switching patients', async () => {
  const sent = Promise.withResolvers<undefined>()
  const reply = Promise.withResolvers<ReturnType<typeof success>>()
  let switched = false
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.endsWith('/auth/current-patient')) {
        sent.resolve(undefined)
        const result = await reply.promise
        switched = true
        return result
      }
      if (url.endsWith('/auth/me')) {
        return success(
          switched ? { ...context(), current_patient_id: 'pb', patients: [patient('pb', 'family')] } : context(),
        )
      }
      return success({})
    }),
  )
  render(() => <App />)
  const picker = await screen.findByLabelText('当前管理对象')
  fireEvent.change(picker, { target: { value: 'pb' } })
  await sent.promise
  const epoch = state.epoch
  navigate('support')
  expect(state.epoch).toBe(epoch)
  const support = screen.getByRole('button', { name: '支持服务' })
  expect(support).toBeInstanceOf(HTMLButtonElement)
  if (!(support instanceof HTMLButtonElement)) throw new TypeError('Expected button')
  expect(support.disabled).toBe(true)
  reply.resolve(success({ outcome: 'selected' }))
  await waitFor(() => expect(state.patient?.patient.patient_id).toBe('pb'))
  await waitFor(() => expect(state.switchingPatient).toBe(false))
  expect(state.patient?.relationship).toBe('family')
  navigate('support')
  expect(state.page).toBe('support')
})

it('releases navigation after a rejected patient switch', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      url.endsWith('/auth/current-patient')
        ? {
            ok: false,
            status: 403,
            json: () =>
              Promise.resolve({
                request_id: 'test',
                status: 'error',
                data: null,
                error: { code: 'FORBIDDEN', message: '无该对象权限' },
              }),
          }
        : success(url.endsWith('/auth/me') ? context() : {}),
    ),
  )
  render(() => <App />)
  fireEvent.change(await screen.findByLabelText('当前管理对象'), { target: { value: 'pb' } })
  await screen.findByText('无该对象权限')
  expect(state.switchingPatient).toBe(false)
  expect(state.patient?.patient.patient_id).toBe('pa')
  navigate('support')
  expect(state.page).toBe('support')
})
