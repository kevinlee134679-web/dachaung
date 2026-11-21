import { webcrypto } from 'node:crypto'
import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { TaskPage } from '../../../src/features/tasks/task-page'
import { updateSession } from '../../../src/session/session'

function success(data: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ request_id: 'request-a', status: 'success', data, error: null }),
  }
}

beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto)
  localStorage.clear()
  const patient = {
    patient: { patient_id: 'pa', display_name: 'pa', timezone: 'Asia/Shanghai' },
    relationship: 'self',
    effective_scopes: ['tasks:read', 'reminder:write'],
  }
  updateSession(draft => {
    draft.context = {
      account: { account_id: 'account-a', display_name: 'account-a', is_simulated: true },
      current_patient_id: 'pa',
      patients: [patient],
      csrf_token: 'csrf-account-a',
    }
    draft.patient = patient
    draft.epoch++
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it('snooze sends only the original task revision and never creates medication evidence', async () => {
  const writes: { url: string; body: unknown }[] = []
  const task = {
    task_id: 'task-a',
    patient_id: 'pa',
    kind: 'deliver_reminder',
    owner_module: 'O',
    owner_operation_key: 'reminder-a',
    payload: { dose_slot_id: 'slot-a', reminder_revision: 1, content_ref: 'content-a' },
    intervention_id: null,
    rule_version: 'v1',
    status: 'succeeded',
    attempt_count: 1,
    max_attempts: 3,
    scheduled_at: '2026-11-17T00:00:00Z',
    valid_until: '2026-11-17T00:30:00Z',
    failure_reason: null,
    cancellation_requested: false,
    next_attempt_at: null,
    meta: {
      created_at: '2026-11-17T00:00:00Z',
      updated_at: '2026-11-17T00:00:00Z',
      revision: 4,
      contract_version: 'A-v0.4',
      is_simulated: true,
    },
  }
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      if (options.method !== 'GET') {
        if (typeof options.body !== 'string') throw new TypeError('Expected JSON request body')
        writes.push({ url, body: JSON.parse(options.body) })
        return success(task)
      }
      return success({ items: [task], next_cursor: null })
    }),
  )
  render(() => <TaskPage />)
  fireEvent.click(await screen.findByText('明确稍后提醒'))
  await waitFor(() => expect(writes).toHaveLength(1))
  expect(writes[0]?.url.endsWith('/reminder-snoozes')).toBe(true)
  expect(writes[0]?.body).toEqual({ source_task_id: 'task-a', expected_task_revision: 4, snooze_minutes: 10 })
})

it.each([
  ['pending', -7, true],
  ['pending', 1, false],
  ['succeeded', -7, false],
  ['retry_wait', -7, true],
] as const)(
  '%s task with deadline %i days from now preserves history and projects expiry only for waiting tasks',
  async (status, daysFromNow, expectedExpiredProjection) => {
    const methods: (string | undefined)[] = []
    const deadline = new Date(Date.now() + daysFromNow * 86400000).toISOString()
    const task = {
      task_id: 'task-history',
      patient_id: 'pa',
      kind: 'deliver_reminder',
      owner_module: 'O',
      owner_operation_key: 'reminder-history',
      payload: { dose_slot_id: 'slot-a', reminder_revision: 1, content_ref: 'content-a' },
      intervention_id: null,
      rule_version: 'v1',
      status,
      attempt_count: status === 'pending' ? 0 : 1,
      max_attempts: 3,
      scheduled_at: new Date(new Date(deadline).getTime() - 1800000).toISOString(),
      valid_until: deadline,
      failure_reason: null,
      cancellation_requested: false,
      next_attempt_at: null,
      meta: { created_at: deadline, updated_at: deadline, revision: 2, contract_version: 'A-v0.4', is_simulated: true },
    }
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, options: RequestInit) => {
        methods.push(options.method)
        return success({ items: [task], next_cursor: null })
      }),
    )
    const { container } = render(() => <TaskPage />)
    await screen.findByText(/有效期至/)
    expect(container.textContent.includes('已过有效期')).toBe(expectedExpiredProjection)
    expect(container.textContent.includes('历史待显式维护')).toBe(expectedExpiredProjection)
    expect(task.status).toBe(status)
    expect(task.valid_until).toBe(deadline)
    if (status === 'succeeded') expect(container.textContent).toContain('执行成功')
    expect(methods).toEqual(['GET'])
  },
)
