import { webcrypto } from 'node:crypto'
import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import * as v from 'valibot'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../src/api/api'
import { notice } from '../../src/notice/notice'
import { Notice } from '../../src/notice/notice-view'
import { state, updateSession, ViewChanged } from '../../src/session/session'
import { Button } from '../../src/ui/components'

function success(data: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ request_id: 'test', status: 'success', data, error: null }),
  }
}
function failure(code: string) {
  return {
    ok: false,
    status: 409,
    json: () =>
      Promise.resolve({ request_id: 'test', status: 'error', data: null, error: { code, message: 'expired receipt' } }),
  }
}
function choose(patient = 'pa', account = 'account-a') {
  const access = {
    patient: { patient_id: patient, display_name: patient, timezone: 'Asia/Shanghai' },
    relationship: 'self',
    effective_scopes: [],
  }
  updateSession(draft => {
    draft.context = {
      account: { account_id: account, display_name: account, is_simulated: true },
      csrf_token: `csrf-${account}`,
      current_patient_id: patient,
      patients: [access],
    }
    draft.patient = access
  })
}

beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto)
  localStorage.clear()
  choose()
  notice('')
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

it('does not send after a view changes during fingerprinting', async () => {
  const digest = Promise.withResolvers<ArrayBuffer>()
  vi.spyOn(crypto.subtle, 'digest').mockReturnValueOnce(digest.promise)
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  const request = api('/patients/pa/medications', v.unknown(), 'POST', { name: 'fictional A' })
  choose('pb', 'account-b')
  updateSession(draft => {
    draft.epoch++
  })
  digest.resolve(new Uint8Array(32).buffer)
  await expect(request).rejects.toBeInstanceOf(ViewChanged)
  expect(fetchMock).not.toHaveBeenCalled()
})

it('does not send a file after its view changes during preparation', async () => {
  const bytes = Promise.withResolvers<ArrayBuffer>()
  const file = new File(['a'], 'fictional-A.pdf')
  const body = new FormData()
  body.append('file', file)
  body.append('source_event_id', 'event')
  const uploaded = body.get('file')
  expect(uploaded).not.toBeNull()
  if (uploaded == null) return
  Object.defineProperty(uploaded, 'arrayBuffer', { value: () => bytes.promise })
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  const request = api('/patients/pa/files', v.unknown(), 'POST', body)
  choose('pb')
  updateSession(draft => {
    draft.epoch++
  })
  bytes.resolve(new Uint8Array([1, 2, 3]).buffer)
  await expect(request).rejects.toBeInstanceOf(ViewChanged)
  expect(fetchMock).not.toHaveBeenCalled()
})

it('does not run a stale control', () => {
  const effect = vi.fn()
  render(() => <Button onAction={effect}>save</Button>)
  updateSession(draft => {
    draft.epoch++
  })
  fireEvent.click(screen.getByText('save'))
  expect(effect).not.toHaveBeenCalled()
})

it('retains the idempotency key after an unknown result', async () => {
  const keys: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((_url: string, options: RequestInit) => {
      const key = new Headers(options.headers).get('Idempotency-Key')
      expect(key).not.toBeNull()
      if (key === null) throw new Error('Missing idempotency key')
      keys.push(key)
      if (keys.length === 1) return Promise.reject(new TypeError('connection interrupted'))
      return Promise.resolve(success({ medication_id: 'original-result' }))
    }),
  )
  await expect(api('/patients/pa/medications', v.unknown(), 'POST', { name: 'same intent' })).rejects.toThrow()
  await api('/patients/pa/medications', v.unknown(), 'POST', { name: 'same intent' })
  expect(keys[0]).toBe(keys[1])
  expect(localStorage.length).toBe(0)
})

describe.each(['IDEMPOTENCY_EXPIRED', 'SENSITIVE_RECEIPT_EXPIRED'])('%s recovery', code => {
  it('keeps the key until explicit recovery and sends nothing during recovery', async () => {
    const keys: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, options: RequestInit) => {
        const key = new Headers(options.headers).get('Idempotency-Key')
        expect(key).not.toBeNull()
        if (key === null) throw new Error('Missing idempotency key')
        keys.push(key)
        return Promise.resolve(keys.length < 3 ? failure(code) : success({}))
      }),
    )
    render(() => (
      <>
        <Notice />
        <Button onAction={() => api('/patients/pa/medications', v.unknown(), 'POST', { name: 'same intent' })}>
          save
        </Button>
      </>
    ))
    fireEvent.click(screen.getByText('save'))
    await screen.findByText('已核对原结果，准备新操作')
    const key = localStorage.key(0)
    expect(key).not.toBeNull()
    if (key == null) return
    fireEvent.click(screen.getByText('save'))
    await waitFor(() => expect(keys).toHaveLength(2))
    localStorage.setItem('pending:another-operation', 'unrelated-key')
    fireEvent.click(screen.getByText('已核对原结果，准备新操作'))
    await waitFor(() => expect(localStorage.getItem(key)).toBeNull())
    expect(localStorage.getItem('pending:another-operation')).toBe('unrelated-key')
    expect(keys[0]).toBe(keys[1])
    expect(keys).toHaveLength(2)
    fireEvent.click(screen.getByText('save'))
    await waitFor(() => expect(keys).toHaveLength(3))
    expect(keys[2]).not.toBe(keys[0])
  })
})

it.each(['view', 'operation'])('recovery cannot clear a changed %s', async change => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => failure('IDEMPOTENCY_EXPIRED')),
  )
  render(() => (
    <>
      <Notice />
      <Button onAction={() => api('/patients/pa/medications', v.unknown(), 'POST', {})}>save</Button>
    </>
  ))
  fireEvent.click(screen.getByText('save'))
  const recovery = await screen.findByText('已核对原结果，准备新操作')
  const key = localStorage.key(0)
  expect(key).not.toBeNull()
  if (key == null) return
  if (change === 'view') {
    choose('pb')
    updateSession(draft => {
      draft.epoch++
    })
  } else {
    localStorage.setItem(key, 'replacement-operation')
  }
  const operation = localStorage.getItem(key)
  fireEvent.click(recovery)
  expect(localStorage.getItem(key)).toBe(operation)
  expect(state.context).not.toBeNull()
})
