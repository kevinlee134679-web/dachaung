import { webcrypto } from 'node:crypto'
import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ReportPage } from '../../../src/features/report/report-page'
import { notice } from '../../../src/notice/notice'
import { Notice } from '../../../src/notice/notice-view'
import { updateSession } from '../../../src/session/session'

function success(data: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ request_id: 'test', status: 'success', data, error: null }),
  }
}
function failure(message: string) {
  return {
    ok: false,
    status: 409,
    json: () =>
      Promise.resolve({
        request_id: 'test',
        status: 'error',
        data: null,
        error: { code: 'SCHEDULE_WINDOW_NOT_READY', message },
      }),
  }
}

function statistic() {
  return {
    window_start: '2026-11-10T00:00:00+08:00',
    window_end: '2026-11-17T00:00:00+08:00',
    as_of: '2026-11-17T00:00:00Z',
    patient_confirmed_count: 1,
    reported_not_taken_count: 0,
    postponed_count: 0,
    unconfirmed_evidence_count: 2,
    unknown_count: 1,
    planned_dose_count: 4,
    patient_confirmation_ratio: 0.25,
    issues: [],
    is_simulated: true,
  }
}

function summary() {
  return {
    record_overview: statistic(),
    measurement_overview: [],
    feedback_overview: {
      sources: [
        { source_module: 'B', availability: 'available', reason: null, records: [] },
        {
          source_module: 'C',
          availability: 'available',
          reason: null,
          records: [
            {
              record_kind: 'service',
              record_id: 'service-a',
              service_status: 'completed',
              source_version: '2',
              recorded_at: '2026-11-17T00:00:00Z',
              is_simulated: true,
              support_needs: '需要陪伴',
              support_acceptance: null,
              intervention_effectiveness: null,
            },
          ],
        },
      ],
    },
    missing_items: [],
  }
}

beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto)
  localStorage.clear()
  const patient = {
    patient: { patient_id: 'pa', display_name: 'pa', timezone: 'Asia/Shanghai' },
    relationship: 'self',
    effective_scopes: ['statistics:read', 'summary:read', 'measurements:read', 'records:read'],
  }
  updateSession(draft => {
    draft.context = {
      account: { account_id: 'account-a', display_name: 'account-a', is_simulated: true },
      current_patient_id: 'pa',
      patients: [patient],
      csrf_token: 'csrf-account-a',
    }
    draft.patient = patient
    draft.page = 'profile'
    draft.tab = 'report'
    draft.epoch++
  })
  notice('')
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function setupReport(errorMessage: string, failures = 1) {
  const calls: { url: string; method: string; body: unknown }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      expect(options.body == null || typeof options.body === 'string').toBe(true)
      if (options.body != null && typeof options.body !== 'string')
        return Promise.reject(new Error('Unexpected request body'))
      calls.push({
        url,
        method: options.method ?? 'GET',
        body: options.body != null ? JSON.parse(options.body) : null,
      })
      if (url.includes('/summary?')) {
        if (failures > 0) {
          failures--
          return Promise.resolve(failure(errorMessage))
        }
        return Promise.resolve(success(summary()))
      }
      if (url.includes('/medication-trends'))
        return Promise.resolve(success({ items: [statistic()], aggregate: statistic() }))
      if (url.includes('/dose-matches')) return Promise.resolve(success({ items: [], next_cursor: null }))
      return Promise.resolve(success(statistic()))
    }),
  )
  render(() => (
    <>
      <Notice />
      <ReportPage />
    </>
  ))
  return calls
}

it('report entry only reads; explicit refresh binds statistics and trend to the returned cutoff', async () => {
  const calls = setupReport('window not maintained', 0)
  await screen.findByText(/总比例直接使用后端汇总/)
  await waitFor(() => expect(calls.filter(call => call.url.includes('/dose-matches'))).toHaveLength(1))
  fireEvent.click(screen.getByRole('button', { name: '明确刷新统计与摘要' }))
  await waitFor(() => expect(calls.filter(call => call.url.includes('/dose-matches'))).toHaveLength(2))
  expect(calls.filter(call => call.url.includes('/summary?'))).toHaveLength(2)
  expect(calls.every(call => call.method === 'GET' && call.body === null)).toBe(true)
  for (const call of calls.filter(call => /medication-statistics|medication-trends|dose-matches/.test(call.url)))
    expect(new URL(call.url, 'http://test').searchParams.get('as_of')).toBe('2026-11-17T00:00:00Z')
  expect(document.body.textContent).toContain('25.0%')
  expect(document.body.textContent).toContain('需要陪伴')
  expect(document.body.textContent).not.toContain('50.0%')
})

it('successful report refresh after a rejected window replaces its old error notice', async () => {
  setupReport('OLD_WINDOW_ERROR', 2)
  await screen.findByText(/时段窗口尚未维护/)
  fireEvent.click(screen.getByRole('button', { name: '读取报告' }))
  await screen.findByText('OLD_WINDOW_ERROR')
  expect(screen.getByRole('status').className).toContain('text-red-800')
  fireEvent.input(screen.getByLabelText('起始日期（北京时间）'), { target: { value: '2026-11-10' } })
  fireEvent.input(screen.getByLabelText('结束日期（不含当日，北京时间）'), { target: { value: '2026-11-17' } })
  fireEvent.click(screen.getByRole('button', { name: '明确刷新统计与摘要' }))
  await screen.findByText(/已刷新统计与摘要/)
  expect(screen.getByRole('status').textContent).not.toContain('OLD_WINDOW_ERROR')
  expect(screen.getByRole('status').className).toContain('text-teal-800')
  expect(document.body.textContent).toContain('25.0%')
})

it('render initial 409 leaves no detached old error after a successful report refresh', async () => {
  setupReport('DETACHED_INITIAL_ERROR')
  await screen.findByText(/时段窗口尚未维护/)
  fireEvent.click(screen.getByRole('button', { name: '明确刷新统计与摘要' }))
  await screen.findByText(/已刷新统计与摘要/)
  expect(document.body.textContent).not.toContain('DETACHED_INITIAL_ERROR')
  expect(document.body.textContent).not.toContain('时段窗口尚未维护')
  expect(document.body.textContent).toContain('25.0%')
})

it('received unusable measurements display unavailable with their actual quality reason', async () => {
  const result = {
    ...summary(),
    measurement_overview: [
      {
        metric_code: 'sleep_duration',
        availability: 'unavailable',
        latest_value: null,
        unit: null,
        sampled_at: null,
        missing_items: ['已有记录，但原单位未知，当前不能形成可用指标'],
      },
    ],
  }
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.includes('/summary?')) return success(result)
      if (url.includes('/medication-trends')) return success({ items: [] })
      if (url.includes('/dose-matches')) return success({ items: [], next_cursor: null })
      return success(statistic())
    }),
  )
  render(() => <ReportPage />)
  await screen.findByText(/已有记录，但原单位未知/)
  expect(document.body.textContent).toContain('睡眠时长：不可用')
  expect(document.body.textContent).not.toContain('未采集')
  expect(document.body.textContent).not.toContain('未采样')
})
