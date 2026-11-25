import type { SuccessResponse } from '../../support'
import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import * as v from 'valibot'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { EventListPage } from '../../../src/features/dose-events/event-list-page'
import { MedicationReportForm } from '../../../src/features/dose-events/report-form'
import { currentNotice, notice } from '../../../src/notice/notice'
import { updateSession } from '../../../src/session/session'
import { choose, pageOf, success } from '../../support'

const slot = {
  dose_slot_id: 'slot-a',
  medication_id: 'med-a',
  plan_id: 'plan-a',
  plan_version: 1,
  plan_entry_id: 'entry-a',
  scheduled_at: '2026-11-16T00:00:00Z',
  status: 'active',
}
function event(payload: Record<string, unknown> = {}) {
  return {
    event_id: 'event-a',
    patient_id: 'pa',
    event_kind: 'medication',
    source: 'manual',
    source_event_id: 'source-a',
    evidence_type: 'self_report',
    reporter_account_id: 'account-a',
    device_id: null,
    occurred_at: '2026-11-16T00:00:45.123456Z',
    received_at: '2026-11-16T01:00:00Z',
    state: 'effective',
    payload: {
      reported_status: 'taken',
      observation: null,
      medication_id: 'med-a',
      dose_slot_id: 'slot-a',
      plan_ref: { plan_id: 'plan-a', plan_version: 1 },
      raw_text: 'original',
      ...payload,
    },
    quality: {
      event_id: 'event-a',
      event_revision: 2,
      status: 'valid',
      issues: [],
      normalized_measurement: null,
      processing_version: 'quality-v1',
      processed_at: '2026-11-16T01:00:00Z',
    },
    link_status: 'matched',
    meta: {
      created_at: '2026-11-16T01:00:00Z',
      updated_at: '2026-11-16T01:00:00Z',
      revision: 2,
      contract_version: 'A-v0.4',
      is_simulated: true,
    },
  }
}
function requestBody(options: RequestInit): unknown {
  if (typeof options.body !== 'string') throw new TypeError('Expected JSON request body')
  return JSON.parse(options.body)
}

const scopes = ['records:read', 'records:report', 'records:correct']

beforeEach(() => {
  localStorage.clear()
  choose({ scopes })
  updateSession(draft => {
    draft.page = 'medication'
    draft.tab = 'records'
    draft.epoch++
  })
  notice('')
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

it('slot report retries an unknown result with the same source and idempotency keys', async () => {
  const posts: { body: Record<string, unknown>; key: string }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((_url: string, options: RequestInit) => {
      const key = new Headers(options.headers).get('Idempotency-Key')
      expect(key).toBeDefined()
      if (key === null) throw new Error('Missing idempotency key')
      posts.push({
        body: v.parse(v.record(v.string(), v.unknown()), requestBody(options)),
        key,
      })
      if (posts.length === 1) return Promise.reject(new TypeError('connection interrupted'))
      return Promise.resolve(success(event()))
    }),
  )
  render(() => <MedicationReportForm slot={slot} />)
  const save = screen.getByRole('button', { name: '明确保存服药报告' })
  fireEvent.click(save)
  await waitFor(() => expect(currentNotice().error).toBe(true))
  fireEvent.click(save)
  await waitFor(() => expect(posts).toHaveLength(2))
  expect(posts[0]?.key).toBe(posts[1]?.key)
  expect(posts[0]?.body).toEqual(posts[1]?.body)
  expect(posts[1]?.body['dose_slot_id']).toBe('slot-a')
  expect(posts[1]?.body).not.toHaveProperty('evidence_type')
})

it('family report controls keep the family boundary and cannot act after patient switch', () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  choose({ patient: 'pa', account: 'family-a', relationship: 'family', scopes })
  updateSession(draft => {
    draft.epoch++
  })
  render(() => <MedicationReportForm slot={slot} />)
  expect(screen.getByText(/不计入本人确认已服/)).toBeTruthy()
  const save = screen.getByRole('button', { name: '明确保存服药报告' })
  choose({ patient: 'pb', account: 'family-a', relationship: 'family', scopes })
  updateSession(draft => {
    draft.epoch++
  })
  fireEvent.click(save)
  expect(fetchMock).not.toHaveBeenCalled()
})

it('an unchanged successful report keeps its source identity when the form is submitted again', async () => {
  const sources: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((_url: string, options: RequestInit) => {
      sources.push(v.parse(v.looseObject({ source_event_id: v.string() }), requestBody(options)).source_event_id)
      return success(event())
    }),
  )
  render(() => <MedicationReportForm slot={slot} />)
  const save = screen.getByRole('button', { name: '明确保存服药报告' })
  fireEvent.click(save)
  await screen.findByText(/已保存：/)
  await waitFor(() => expect(save.hasAttribute('disabled')).toBe(false))
  fireEvent.click(save)
  await waitFor(() => expect(sources).toHaveLength(2))
  await waitFor(() => expect(save.hasAttribute('disabled')).toBe(false))
  fireEvent.change(screen.getByLabelText('报告内容'), { target: { value: 'not_taken' } })
  fireEvent.click(save)
  await waitFor(() => expect(sources).toHaveLength(3))
  expect(sources[0]).toBe(sources[1])
  expect(sources[2]).not.toBe(sources[0])
})

it('patient switch during source-fingerprint preparation sends no old slot report', async () => {
  const digest = Promise.withResolvers<ArrayBuffer>()
  vi.spyOn(crypto.subtle, 'digest').mockReturnValueOnce(digest.promise)
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  render(() => <MedicationReportForm slot={slot} />)
  fireEvent.click(screen.getByRole('button', { name: '明确保存服药报告' }))
  choose({ patient: 'pb', scopes })
  updateSession(draft => {
    draft.epoch++
  })
  digest.resolve(new Uint8Array(32).buffer)
  await waitFor(() =>
    expect(screen.getByRole('button', { name: '明确保存服药报告' }).hasAttribute('disabled')).toBe(false),
  )
  expect(fetchMock).not.toHaveBeenCalled()
  expect(localStorage.length).toBe(0)
})

it('unchanged correction time retains exact precision and the current expected revision', async () => {
  const writes: Record<string, unknown>[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((_url: string, options: RequestInit) => {
      if (options.method === 'GET') return success(pageOf([event()]))
      writes.push(v.parse(v.record(v.string(), v.unknown()), requestBody(options)))
      return success(event())
    }),
  )
  render(() => <EventListPage />)
  await screen.findByText(/原话：original/)
  fireEvent.input(screen.getByLabelText('更正或撤销原因（必填）'), { target: { value: 'correct original report' } })
  fireEvent.click(screen.getByRole('button', { name: '保存追加更正' }))
  await waitFor(() => expect(writes).toHaveLength(1))
  expect(writes[0]?.['expected_revision']).toBe(2)
  expect(writes[0]?.['occurred_at']).toBe(event().occurred_at)
  expect(writes[0]).not.toHaveProperty('source')
  expect(writes[0]).not.toHaveProperty('reporter_account_id')
})

it('a delayed old record list cannot pollute a new patient page', async () => {
  const response = Promise.withResolvers<SuccessResponse>()
  const consumed = Promise.withResolvers<undefined>()
  const fetchMock = vi.fn(() => response.promise)
  vi.stubGlobal('fetch', fetchMock)
  render(() => <EventListPage />)
  await waitFor(() => expect(fetchMock).toHaveBeenCalled())
  choose({ patient: 'pb', scopes })
  updateSession(draft => {
    draft.epoch++
  })
  response.resolve({
    ok: true,
    status: 200,
    json: () => {
      consumed.resolve(undefined)
      return Promise.resolve({
        request_id: 'request-a',
        status: 'success',
        data: { items: [event({ raw_text: 'STALE_PATIENT_REPORT' })], next_cursor: null },
        error: null,
      })
    },
  })
  await consumed.promise
  const settled = Promise.withResolvers<undefined>()
  setTimeout(settled.resolve, 0)
  await settled.promise
  expect(screen.queryByText(/STALE_PATIENT_REPORT/)).toBeNull()
})

it('a completed old correction cannot put its success notice onto a new patient after rereading', async () => {
  const response = Promise.withResolvers<SuccessResponse>()
  const consumed = Promise.withResolvers<undefined>()
  let reads = 0
  vi.stubGlobal(
    'fetch',
    vi.fn((_url: string, options: RequestInit) => {
      if (options.method !== 'GET') return Promise.resolve(success(event()))
      return ++reads === 1 ? Promise.resolve(success(pageOf([event()]))) : response.promise
    }),
  )
  render(() => <EventListPage />)
  await screen.findByText(/原话：original/)
  fireEvent.input(screen.getByLabelText('更正或撤销原因（必填）'), { target: { value: 'correct original report' } })
  fireEvent.click(screen.getByRole('button', { name: '保存追加更正' }))
  await waitFor(() => expect(reads).toBe(2))
  choose({ patient: 'pb', scopes })
  updateSession(draft => {
    draft.epoch++
  })
  response.resolve({
    ok: true,
    status: 200,
    json: () => {
      consumed.resolve(undefined)
      return Promise.resolve({
        request_id: 'request-a',
        status: 'success',
        data: { items: [], next_cursor: null },
        error: null,
      })
    },
  })
  await consumed.promise
  const settled = Promise.withResolvers<undefined>()
  setTimeout(settled.resolve, 0)
  await settled.promise
  expect(currentNotice().text).not.toContain('已追加更正')
})
