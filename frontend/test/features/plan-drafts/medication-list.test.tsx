import { cleanup, fireEvent, render, screen, waitFor, within } from '@solidjs/testing-library'
import * as v from 'valibot'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MedicationListForm } from '../../../src/features/plan-drafts/medication-list-form'
import { choose, pageOf, success } from '../../support'

const plan = { plan_id: 'plan-a', plan_version: 1, effective_from: '2026-01-01T00:00:00Z' }
const entry = {
  draft_entry_id: 'entry-a',
  medication_id: 'med-a',
  dose_value: '1',
  dose_unit: '片',
  start_date: '2026-01-01',
  end_date: null,
  schedule: { kind: 'daily', times: ['08:00'], weekdays: [] },
  meal_requirement: null,
  medical_notes: null,
  strict_timing: null,
  min_interval_minutes: null,
  source_file_ids: [],
}
const file = {
  file_id: 'file-a',
  original_name: '病历.png',
  media_type: 'image/png',
  size_bytes: 100,
  meta: { created_at: '2026-01-01T00:00:00Z' },
}

beforeEach(() => {
  sessionStorage.clear()
  localStorage.clear()
  choose({
    scopes: [
      'medication:read',
      'medication:edit',
      'drafts:read',
      'drafts:write',
      'drafts:submit',
      'plan:read',
      'files:read',
    ],
  })
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function setup(hasPlan = false, failFirst = false) {
  const requests: { url: string; body: Record<string, unknown> }[] = []
  let failed = false
  let currentPlan = hasPlan
  let saved: Record<string, unknown> = {}
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      if (options.method === 'POST' || options.method === 'PUT') {
        const body = v.parse(
          v.record(v.string(), v.unknown()),
          JSON.parse(v.parse(v.string(), options.body)) as unknown,
        )
        requests.push({ url, body })
        if (url.endsWith('/medications')) return success({ medication_id: 'med-b', name: body['name'] })
        if (url.endsWith('/drafts')) {
          if (failFirst && !failed) {
            failed = true
            throw new TypeError('网络错误')
          }
          saved = {
            ...body,
            draft_id: 'draft-a',
            status: 'editing',
            content_revision: 3,
            meta: { revision: 7, updated_at: '2026-01-01T00:00:00Z' },
            formal_plan: null,
            return_reason: null,
          }
          return success(saved)
        }
        if (url.endsWith('/submit')) return success({ ...saved, status: 'pending_confirmation' })
        if (url.endsWith('/plan-confirmations')) {
          currentPlan = true
          return success(plan)
        }
      }
      if (url.includes('/medication-recognition')) {
        return success({
          status: 'ready',
          medications: [
            {
              name: '新药',
              dose_value: '1',
              dose_unit: '片',
              daily_count: 2,
              times: [],
              duration_days: 5,
              source_text: '新药',
            },
          ],
          allergies: null,
          diagnosis: null,
        })
      }
      if (url.includes('/versions/'))
        return success({ ...plan, source_draft_id: 'draft-a', entries: saved['entries'] ?? [entry] })
      if (url.includes('/medications?')) return success(pageOf([{ medication_id: 'med-a', name: '药甲' }]))
      if (url.includes('/plans?')) return success(pageOf(currentPlan ? [plan] : []))
      if (url.includes('/files?')) return success(pageOf([file]))
      return success(pageOf([]))
    }),
  )
  return requests
}

async function fillExisting() {
  fireEvent.change(await screen.findByLabelText('选择已有药品'), { target: { value: 'med-a' } })
  fireEvent.input(screen.getByLabelText(/每次剂量/), { target: { value: '1' } })
  fireEvent.input(screen.getByLabelText(/剂量单位/), { target: { value: '片' } })
  fireEvent.input(screen.getByLabelText('服药时间 1'), { target: { value: '08:00' } })
}

it('saves an existing and a new medication in one operation', async () => {
  const requests = setup()
  render(() => <MedicationListForm />)
  await fillExisting()
  fireEvent.click(screen.getByRole('button', { name: '添加一种药' }))
  await waitFor(() => expect(screen.getAllByLabelText('选择已有药品')).toHaveLength(2))
  const second = within(screen.getByRole('group', { name: '药品条目 2' }))
  fireEvent.change(second.getByLabelText('选择已有药品'), { target: { value: 'new' } })
  fireEvent.input(await screen.findByLabelText('新药品名称'), { target: { value: '新药' } })
  fireEvent.input(second.getByLabelText(/每次剂量/), { target: { value: '2' } })
  fireEvent.input(second.getByLabelText(/剂量单位/), { target: { value: '片' } })
  fireEvent.input(second.getByLabelText('服药时间 1'), { target: { value: '20:00' } })
  fireEvent.click(screen.getByRole('button', { name: '保存并生效' }))
  await waitFor(() => expect(requests).toHaveLength(4))
  expect(requests[0]?.body).toEqual({ name: '新药', notes: null })
  expect(requests[1]?.body).toEqual({
    source_file_ids: [],
    entries: [
      expect.objectContaining({ medication_id: 'med-a', dose_value: '1', dose_unit: '片' }),
      expect.objectContaining({ medication_id: 'med-b', dose_value: '2', dose_unit: '片' }),
    ],
  })
  expect(requests[2]?.body).toEqual({ expected_revision: 7, content_revision: 3 })
  const effectiveFrom: unknown = expect.any(String)
  expect(requests[3]?.body).toEqual({
    draft_id: 'draft-a',
    draft_revision: 3,
    existing_plan_id: null,
    expected_plan_version: null,
    effective_from: effectiveFrom,
    confirmed: true,
  })
})

it('disables saving an unchanged plan until an entry changes', async () => {
  setup(true)
  render(() => <MedicationListForm />)
  const button = await screen.findByRole('button', { name: '保存并生效' })
  expect(button.hasAttribute('disabled')).toBe(true)
  fireEvent.input(screen.getByLabelText(/每次剂量/), { target: { value: '2' } })
  await waitFor(() => expect(button.hasAttribute('disabled')).toBe(false))
})

it('allows another save after a failed draft creation and an edit', async () => {
  const requests = setup(false, true)
  render(() => <MedicationListForm />)
  await fillExisting()
  fireEvent.click(screen.getByRole('button', { name: '保存并生效' }))
  await waitFor(() => expect(requests).toHaveLength(1))
  fireEvent.input(screen.getByLabelText(/每次剂量/), { target: { value: '2' } })
  fireEvent.click(screen.getByRole('button', { name: '保存并生效' }))
  await waitFor(() => expect(requests).toHaveLength(4))
})

it('fills default times and duration and keeps recognition after saving', async () => {
  const requests = setup()
  render(() => <MedicationListForm />)
  fireEvent.click(await screen.findByText('AI 病历识别'))
  await screen.findByRole('option', { name: '病历.png' })
  fireEvent.change(await screen.findByLabelText('选择病历'), { target: { value: 'file-a' } })
  await waitFor(() => expect(screen.getByRole('button', { name: 'AI 识别' }).hasAttribute('disabled')).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: 'AI 识别' }))
  fireEvent.click(await screen.findByRole('button', { name: '填入清单' }))
  await screen.findByDisplayValue('新药')
  expect((await screen.findByLabelText<HTMLInputElement>('服药时间 1')).value).toBe('08:00')
  expect(screen.getByLabelText<HTMLInputElement>('服药时间 2').value).toBe('20:00')
  const start = screen.getByLabelText<HTMLInputElement>('开始日期').value
  const end = screen.getByLabelText<HTMLInputElement>('结束日期（未知可空）').value
  expect(Date.parse(end) - Date.parse(start)).toBe(4 * 86400000)
  fireEvent.click(screen.getByRole('button', { name: '保存并生效' }))
  await waitFor(() => expect(requests).toHaveLength(4))
  await screen.findByText(/正式计划第 1 版/)
  expect(screen.getByText('AI 病历识别')).toBeTruthy()
})
