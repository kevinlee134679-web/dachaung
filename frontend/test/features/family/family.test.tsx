import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import * as v from 'valibot'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { FamilyPage } from '../../../src/features/family/family-page'
import { updateSession } from '../../../src/session/session'
import { success } from '../../support'

const patient = {
  patient: { patient_id: 'pa', display_name: '患者', timezone: 'Asia/Shanghai' },
  relationship: 'self',
  effective_scopes: [],
}
const context = {
  account: { account_id: 'demo-patient-a', display_name: '患者', is_simulated: true },
  csrf_token: 'csrf',
  current_patient_id: 'pa',
  patients: [patient],
}
beforeEach(() => {
  localStorage.clear()
  updateSession(draft => {
    draft.context = context
    draft.patient = patient
    draft.page = 'profile'
    draft.tab = 'family'
    draft.epoch++
    draft.switchingPatient = false
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

async function grantEnvironment() {
  const writes: { scopes: string[]; valid_until: string | null; confirmed: boolean }[] = []
  const grant: {
    grant_id: string
    binding_id: string
    status: string
    valid_until: string | null
    scopes: string[]
    meta: { revision: number }
    patient_id: string
    grantee_account_id: string
    grant_version: number
    confirmed_at: string
    revoked_at: null
  } = {
    grant_id: 'grant-a',
    binding_id: 'binding-a',
    patient_id: 'pa',
    grantee_account_id: 'demo-family',
    grant_version: 1,
    confirmed_at: '2026-01-01T00:00:00+00:00',
    revoked_at: null,
    status: 'active',
    valid_until: '2030-12-01T02:03:45.123456+00:00',
    scopes: ['patient:read'],
    meta: { revision: 2 },
  }
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      if (options.method !== 'GET') {
        if (typeof options.body !== 'string') throw new TypeError('Expected a JSON request body')
        const body = v.parse(
          v.looseObject({ scopes: v.array(v.string()), valid_until: v.nullable(v.string()), confirmed: v.boolean() }),
          JSON.parse(options.body),
        )
        writes.push(body)
        grant.scopes = body.scopes
        grant.valid_until = body.valid_until
        return success(grant)
      }
      if (url.includes('/family-bindings')) {
        return success({
          items: [
            {
              binding_id: 'binding-a',
              patient_id: 'pa',
              family_account_id: 'demo-family',
              status: 'active',
              established_at: '2026-01-01T00:00:00+00:00',
              revoked_at: null,
              meta: { revision: 1 },
            },
          ],
          next_cursor: null,
        })
      }
      if (url.includes('/grants')) return success({ items: [grant], next_cursor: null })
      if (url.endsWith('/auth/me')) return success(context)
      return success({})
    }),
  )
  render(() => <FamilyPage />)
  await screen.findByText('编辑精确授权范围')
  return { writes, grant }
}

function input(label: string): HTMLInputElement {
  const element = screen.getByLabelText(label)
  if (!(element instanceof HTMLInputElement)) throw new TypeError('Expected an input')
  return element
}

it('patient can explicitly grant and remove dialogue reading and see the saved scope', async () => {
  const { writes } = await grantEnvironment()
  const dialogue = () => input('支持对话历史（只读）')
  expect(dialogue().checked).toBe(false)
  fireEvent.click(dialogue())
  fireEvent.click(screen.getByText('明确确认并保存授权'))
  await screen.findByText(
    (_, element) =>
      element?.tagName === 'P' && element.textContent === '授权：有效，基础资料查看、支持对话历史（只读）',
  )
  expect(writes[0]?.scopes).toEqual(['patient:read', 'dialogue:read'])
  expect(writes[0]?.confirmed).toBe(true)
  expect(dialogue().checked).toBe(true)
  fireEvent.click(dialogue())
  fireEvent.click(screen.getByText('明确确认并保存授权'))
  await screen.findByText(
    (_, element) => element?.tagName === 'P' && element.textContent === '授权：有效，基础资料查看',
  )
  expect(writes[1]?.scopes).toEqual(['patient:read'])
  expect(dialogue().checked).toBe(false)
})

it('editing grant scopes keeps its exact current expiration by default', async () => {
  const { writes } = await grantEnvironment()
  const deadline = input('授权截止时间（北京时间，留空表示无预设截止）')
  expect(deadline.value).toBe('2030-12-01T10:03')
  fireEvent.click(screen.getByLabelText('基础资料编辑'))
  fireEvent.click(screen.getByText('明确确认并保存授权'))
  await waitFor(() => expect(writes).toHaveLength(1))
  expect(writes[0]?.scopes).toContain('patient:edit')
  expect(writes[0]?.valid_until).toBe('2030-12-01T02:03:45.123456+00:00')
})

it('grant expiration is removed only by an explicit clear', async () => {
  const { writes } = await grantEnvironment()
  fireEvent.input(screen.getByLabelText('授权截止时间（北京时间，留空表示无预设截止）'), { target: { value: '' } })
  fireEvent.click(screen.getByText('明确确认并保存授权'))
  await waitFor(() => expect(writes).toHaveLength(1))
  expect(writes[0]?.valid_until).toBeNull()
})

it('an explicit grant expiration change is sent with its timezone', async () => {
  const { writes } = await grantEnvironment()
  fireEvent.input(screen.getByLabelText('授权截止时间（北京时间，留空表示无预设截止）'), {
    target: { value: '2031-01-02T15:16' },
  })
  fireEvent.click(screen.getByText('明确确认并保存授权'))
  await waitFor(() => expect(writes).toHaveLength(1))
  expect(writes[0]?.valid_until).toBe('2031-01-02T07:16:00.000Z')
})

it('patient can explicitly grant and remove support:read independently of profile:read', async () => {
  const { writes } = await grantEnvironment()
  const support = () => input('社会支持目录和候选（只读）')
  expect(support().checked).toBe(false)
  fireEvent.click(support())
  fireEvent.click(screen.getByText('明确确认并保存授权'))
  await screen.findByText(
    (_, element) =>
      element?.tagName === 'P' && element.textContent === '授权：有效，基础资料查看、社会支持目录和候选（只读）',
  )
  expect(writes[0]?.scopes).toEqual(['patient:read', 'support:read'])
  expect(support().checked).toBe(true)
  fireEvent.click(support())
  fireEvent.click(screen.getByText('明确确认并保存授权'))
  await screen.findByText(
    (_, element) => element?.tagName === 'P' && element.textContent === '授权：有效，基础资料查看',
  )
  expect(writes[1]?.scopes).toEqual(['patient:read'])
  expect(support().checked).toBe(false)
})
