import { webcrypto } from 'node:crypto'
import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import { Show } from 'solid-js'
import * as v from 'valibot'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { notice } from '../../../src/notice/notice'
import { Notice } from '../../../src/notice/notice-view'
import { ServiceConsentPage } from '../../../src/pages/profile/service-consent-page'
import { PointsPage } from '../../../src/pages/rewards/points-page'
import { rememberServicePage, restoreServicePage } from '../../../src/pages/support/service-navigation'
import { SocialSupportPage } from '../../../src/pages/support/social-support-page'
import { state, updateSession } from '../../../src/session/session'
import { navigate } from '../../../src/shell/navigation'

vi.mock('../../../src/ui/confirm', () => ({ confirm: () => Promise.resolve(true) }))

interface SuccessResponse {
  ok: boolean
  status: number
  json: () => Promise<{ request_id: string; status: string; data: unknown; error: null }>
}
function success(data: unknown): SuccessResponse {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ request_id: 'test', status: 'success', data, error: null }),
  }
}
function failure(status: number, code: string, message: string) {
  return {
    ok: false,
    status,
    json: () => Promise.resolve({ request_id: 'test', status: 'error', data: null, error: { code, message } }),
  }
}
const catalogResource = {
  resource_id: 'demo-resource',
  resource_version: 'demo-v2',
  name: '药学咨询资源（模拟）',
  description: '演示资源介绍',
  service_kind: 'pharmacist_consultation',
  peer_group_id: null,
  provider: {
    provider_id: 'mock-subject',
    provider_type: 'pharmacist',
    display_name: '虚构主体（模拟）',
    qualification_status: 'not_verified',
    is_simulated: true,
  },
  availability: 'available',
  access_mode: 'support_free',
  is_essential: false,
  is_simulated: true,
  required_shared_categories: ['support_question'],
  optional_shared_categories: ['medication_plan'],
}
const recommendation = {
  need_status: 'needed',
  primary_action: { resource_id: 'demo-resource', title: catalogResource.name, reason: '符合本次需求。' },
  secondary_actions: [],
  missing_items: [],
  source_refs: [
    {
      module: 'O',
      record_kind: 'profile',
      record_id: 'o-profile-a',
      version: '1',
      recorded_at: '2026-11-18T00:00:00Z',
    },
    {
      module: 'C',
      record_kind: 'support_resource',
      record_id: 'demo-resource',
      version: 'demo-v2',
      recorded_at: '2026-11-18T00:00:00Z',
    },
  ],
}

function choose(scopes: string[], relationship = 'self', patientId = 'pa', accountId = 'account-a') {
  const patient = {
    patient: { patient_id: patientId, display_name: patientId, timezone: 'Asia/Shanghai' },
    relationship,
    effective_scopes: scopes,
  }
  updateSession(draft => {
    draft.context = {
      account: { account_id: accountId, display_name: accountId, is_simulated: true },
      current_patient_id: patientId,
      patients: [patient],
      csrf_token: `csrf-${accountId}`,
    }
    draft.patient = patient
    draft.epoch++
  })
}

function TestPage() {
  return (
    <>
      <Notice />
      <Show when={state.epoch + 1} keyed>
        <PageContent />
      </Show>
    </>
  )
}

function PageContent() {
  return (
    <>
      {state.page === 'support' && state.tab === 'social' ? (
        <SocialSupportPage />
      ) : state.page === 'rewards' ? (
        <PointsPage />
      ) : state.page === 'profile' && state.tab === 'service-consents' ? (
        <ServiceConsentPage />
      ) : null}
    </>
  )
}

function renderSocial(scopes = ['support:read']) {
  choose(scopes)
  navigate('support', 'social')
  render(() => <TestPage />)
}

async function prepareDraft() {
  fireEvent.click(await screen.findByRole('button', { name: '查看资源详情' }))
  fireEvent.click(await screen.findByRole('button', { name: '准备服务问题' }))
  return screen.findByLabelText<HTMLTextAreaElement>('本次服务问题')
}

interface Call {
  url: string
  method: string
  body: Record<string, unknown> | null
  key: string | undefined
}

function draftEnvironment({ family = false, conflict = false, lost = false } = {}) {
  const calls: Call[] = []
  const resource = catalogResource
  let draft: typeof catalogResource & {
    service_draft_id: string
    patient_id: string
    draft_revision: number
    request_text: string
    status: string
    confirmation_ref_id: string | null
    sharing_scope_ref_id: string | null
    service_id: string | null
    meta: { revision: number }
  } = {
    service_draft_id: 'draft-a',
    patient_id: 'pa',
    draft_revision: 1,
    ...resource,
    request_text: '原问题',
    status: 'preparing',
    confirmation_ref_id: null,
    sharing_scope_ref_id: null,
    service_id: null,
    meta: { revision: 1 },
  }
  let consent = {
    confirmation_ref_id: 'confirm-a',
    resource_version: resource.resource_version,
    status: 'active',
    confirmed_at: '2026-11-18T00:00:00Z',
    valid_until: '2026-11-19T00:00:00Z',
    meta: { revision: 1 },
    sharing_scope: {
      sharing_scope_ref_id: 'scope-a',
      recipient_id: 'mock-subject',
      purpose_code: 'pharmacist_consultation',
      data_categories: ['support_question'],
    },
  }
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      const method = options.method ?? 'GET'
      const body =
        typeof options.body === 'string' ? v.parse(v.record(v.string(), v.unknown()), JSON.parse(options.body)) : null
      const key = new Headers(options.headers).get('Idempotency-Key') ?? undefined
      calls.push({ url, method, body, key })
      if (url.endsWith('/demo-resource')) return Promise.resolve(success(resource))
      if (url.endsWith('/support-resources')) return Promise.resolve(success({ items: [resource], next_cursor: null }))
      if (url.endsWith('/service-drafts')) {
        if (lost) {
          lost = false
          return Promise.reject(new Error('网络断开'))
        }
        draft = { ...draft, ...body }
        return Promise.resolve(success(draft))
      }
      if (url.endsWith('/service-drafts/draft-a') && method === 'PUT') {
        if (conflict) {
          conflict = false
          draft = { ...draft, request_text: '服务器较新内容', draft_revision: 2, meta: { revision: 2 } }
          return Promise.resolve(failure(409, 'SERVICE_DRAFT_REVISION_CONFLICT', '草稿已更新'))
        }
        expect(body).not.toBeNull()
        if (body == null) throw new Error('Missing draft body')
        draft = {
          ...draft,
          ...v.parse(v.looseObject({ request_text: v.string() }), body['content']),
          draft_revision: draft.draft_revision + 1,
          meta: { revision: draft.meta.revision + 1 },
        }
        return Promise.resolve(success(draft))
      }
      if (url.endsWith('/service-drafts/draft-a')) return Promise.resolve(success(draft))
      if (url.endsWith('/service-confirmations')) {
        expect(body).not.toBeNull()
        if (body == null) throw new Error('Missing consent body')
        consent = {
          ...consent,
          sharing_scope: {
            ...consent.sharing_scope,
            data_categories: v.parse(v.array(v.string()), body['shared_categories']),
          },
        }
        draft = { ...draft, confirmation_ref_id: 'confirm-a', sharing_scope_ref_id: 'scope-a' }
        return Promise.resolve(success(consent))
      }
      if (url.endsWith('/service-confirmations/confirm-a/revoke')) {
        consent = { ...consent, status: 'revoked', meta: { revision: 2 } }
        draft = { ...draft, confirmation_ref_id: null, sharing_scope_ref_id: null }
        return Promise.resolve(success(consent))
      }
      if (url.endsWith('/service-confirmations/confirm-a')) return Promise.resolve(success(consent))
      throw new Error(`Unexpected request ${url}`)
    }),
  )
  choose(['support:read', 'services:prepare'], family ? 'family' : 'self')
  navigate('support', 'social')
  render(() => <TestPage />)
  return calls
}

beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto)
  localStorage.clear()
  sessionStorage.clear()
  notice('')
  updateSession(draft => {
    draft.context = null
    draft.patient = null
    draft.page = 'home'
    draft.tab = 'overview'
    draft.epoch++
    draft.switchingPatient = false
    draft.draft = null
  })
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it('catalog and matching show exact source versions and browse only with GET', async () => {
  const calls: [string, string | undefined, string | undefined][] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      calls.push([url, options.method, new Headers(options.headers).get('Idempotency-Key') ?? undefined])
      if (url.endsWith('need=professional')) return success(recommendation)
      if (url.endsWith('/demo-resource')) return success(catalogResource)
      return success({ items: [catalogResource], next_cursor: null })
    }),
  )
  renderSocial(['support:read', 'profile:read'])
  expect(await screen.findByRole('button', { name: '查看已登记画像' })).toBeTruthy()
  await screen.findByRole('button', { name: '查看资源详情' })
  fireEvent.change(screen.getByLabelText('本次支持需求'), { target: { value: 'professional' } })
  fireEvent.click(screen.getByRole('button', { name: '查看匹配' }))
  expect(await screen.findByText(/O 画像 o-profile-a · 修订 1/)).toBeTruthy()
  expect(document.body.textContent).toMatch(/符合本次需求。.*版本 demo-v2 · mock\/demo/s)
  fireEvent.click(screen.getByRole('button', { name: '查看候选详情' }))
  expect(await screen.findByText(/资质未核验/)).toBeTruthy()
  expect(screen.getByText(/潜在的必要共享类别\s+支持问题/)).toBeTruthy()
  expect(calls).toEqual([
    ['/api/v1/support-resources', 'GET', undefined],
    ['/api/v1/patients/pa/support-recommendations?need=professional', 'GET', undefined],
    ['/api/v1/support-resources/demo-resource', 'GET', undefined],
  ])
})

it('ignores a delayed matching result after the selected need or patient changes', async () => {
  const response = Promise.withResolvers<SuccessResponse>()
  const sent = Promise.withResolvers<undefined>()
  const fetchMock = vi.fn((url: string) => {
    if (url.includes('support-recommendations')) {
      sent.resolve(undefined)
      return response.promise
    }
    return Promise.resolve(success({ items: [], next_cursor: null }))
  })
  vi.stubGlobal('fetch', fetchMock)
  renderSocial()
  const button = await screen.findByRole('button', { name: '查看匹配' })
  fireEvent.click(button)
  await sent.promise
  fireEvent.change(screen.getByLabelText('本次支持需求'), { target: { value: 'none' } })
  response.resolve(success(recommendation))
  if (!(button instanceof HTMLButtonElement)) throw new TypeError('Expected button')
  await waitFor(() => expect(button.disabled).toBe(false))
  expect(document.body.textContent).not.toMatch(/o-profile-a|匹配结果/)
  choose([], 'self', 'pb')
  navigate('support', 'social')
  expect(await screen.findByText(/获准查看社会支持/)).toBeTruthy()
  const count = fetchMock.mock.calls.length
  fireEvent.click(button)
  expect(fetchMock.mock.calls.length).toBe(count)
  expect(document.body.textContent).not.toMatch(/o-profile-a|本次支持需求/)
})

it('stale resource version is reported and never labeled as the prior match', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.includes('support-recommendations')) return success(recommendation)
      if (url.endsWith('/demo-resource')) return success({ ...catalogResource, resource_version: 'demo-v3' })
      return success({ items: [catalogResource], next_cursor: null })
    }),
  )
  renderSocial()
  fireEvent.click(await screen.findByRole('button', { name: '查看匹配' }))
  fireEvent.click(await screen.findByRole('button', { name: '查看候选详情' }))
  await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/版本已更新/))
  expect(document.body.textContent).not.toMatch(/演示资源介绍|demo-v3/)
})

it('family prepares a manual draft and restores it without confirmation or revoke controls', async () => {
  const calls = draftEnvironment({ family: true })
  const text = await prepareDraft()
  fireEvent.input(text, { target: { value: '家属据实代录' } })
  fireEvent.click(screen.getByRole('button', { name: '保存草稿' }))
  expect(await screen.findByText(/草稿编号 draft-a/)).toBeTruthy()
  expect(screen.queryByRole('button', { name: /明确确认共享范围|撤销共享授权/ })).toBeNull()
  expect(calls.find(call => call.method === 'POST')?.body).toEqual({
    resource_id: 'demo-resource',
    resource_version: 'demo-v2',
    request_text: '家属据实代录',
  })
  rememberServicePage()
  navigate('home')
  expect(await restoreServicePage()).toBe(true)
  await waitFor(() => expect(screen.getByLabelText<HTMLTextAreaElement>('本次服务问题').value).toBe('家属据实代录'))
})

it('stale draft edit reloads revisions while preserving the unsaved text', async () => {
  const calls = draftEnvironment({ conflict: true })
  fireEvent.input(await prepareDraft(), { target: { value: '首次录入' } })
  fireEvent.click(screen.getByRole('button', { name: '保存草稿' }))
  const saveChanges = await screen.findByRole('button', { name: '保存草稿修改' })
  fireEvent.input(screen.getByLabelText('本次服务问题'), { target: { value: '此项修改应保留' } })
  fireEvent.click(saveChanges)
  expect(await screen.findByText(/内容修订 2/)).toBeTruthy()
  expect(screen.getByLabelText<HTMLTextAreaElement>('本次服务问题').value).toBe('此项修改应保留')
  fireEvent.click(screen.getByRole('button', { name: '保存草稿修改' }))
  await waitFor(() => expect(calls.filter(call => call.method === 'PUT')).toHaveLength(2))
  const writes = calls.filter(call => call.method === 'PUT')
  expect(writes.map(call => call.body?.['expected_revision'])).toEqual([1, 2])
  expect(writes[1]?.body?.['content']).toMatchObject({ request_text: '此项修改应保留' })
})

it('explicit patient confirmation submits only checked options and retains revoked history', async () => {
  const calls = draftEnvironment()
  fireEvent.input(await prepareDraft(), { target: { value: '本人核对的演示问题' } })
  fireEvent.click(screen.getByRole('button', { name: '保存草稿' }))
  const optional = await screen.findByLabelText<HTMLInputElement>('正式用药安排')
  expect(optional.checked).toBe(false)
  fireEvent.click(screen.getByRole('button', { name: '明确确认共享范围' }))
  await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/勾选|确认/))
  expect(calls.some(call => call.url.endsWith('/service-confirmations'))).toBe(false)
  fireEvent.click(optional)
  fireEvent.click(screen.getByLabelText('我已核对本次问题、接收主体和共享范围'))
  fireEvent.click(screen.getByRole('button', { name: '明确确认共享范围' }))
  fireEvent.click(await screen.findByRole('button', { name: '查看确认及历史' }))
  const issued = calls.find(call => call.url.endsWith('/service-confirmations'))
  expect(issued?.body?.['shared_categories']).toEqual(['medication_plan', 'support_question'])
  expect(issued?.body?.['draft_revision']).toBe(1)
  fireEvent.input(await screen.findByLabelText('撤销原因'), { target: { value: '只限演示' } })
  fireEvent.click(screen.getByLabelText('明确撤销此共享范围'))
  fireEvent.click(screen.getByRole('button', { name: '撤销共享授权' }))
  expect(
    await screen.findByText(
      (_, element) => element?.tagName === 'P' && element.textContent.includes('共享确认：已撤销'),
    ),
  ).toBeTruthy()
  expect(screen.queryByRole('button', { name: '撤销共享授权' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'confirm-a' }))
  expect(
    await screen.findByText(
      (_, element) => element?.tagName === 'P' && element.textContent.includes('共享确认：已撤销'),
    ),
  ).toBeTruthy()
})

it('unknown draft write uses the original key and blocks a changed request', async () => {
  const calls = draftEnvironment({ lost: true })
  const text = await prepareDraft()
  fireEvent.input(text, { target: { value: '原提交正文' } })
  fireEvent.click(screen.getByRole('button', { name: '保存草稿' }))
  await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/网络断开/))
  fireEvent.input(text, { target: { value: '另一个正文' } })
  fireEvent.click(screen.getByRole('button', { name: '保存草稿' }))
  await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/上一次提交结果尚未核实/))
  expect(calls.filter(call => call.method === 'POST')).toHaveLength(1)
  fireEvent.input(text, { target: { value: '原提交正文' } })
  fireEvent.click(screen.getByRole('button', { name: '保存草稿' }))
  expect(await screen.findByText(/草稿编号 draft-a/)).toBeTruthy()
  const posts = calls.filter(call => call.method === 'POST')
  expect(posts).toHaveLength(2)
  expect(posts[0]?.key).toBe(posts[1]?.key)
  expect(Object.values(localStorage).every(value => !String(value).includes('原提交正文'))).toBe(true)
})

it('points view reads actual zero and history with no write; missing family grant suppresses account requests', async () => {
  const calls: [string, string | undefined][] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      calls.push([url, options.method])
      if (url.endsWith('/points/rules')) return success({ rules_version: 'points-demo-v1', rules: [] })
      if (url.endsWith('/points')) return success({ balance: 0, meta: { revision: 1 } })
      return success({ items: [], next_cursor: null })
    }),
  )
  choose(['points:read'])
  navigate('rewards')
  render(() => <TestPage />)
  expect(await screen.findByText(/可用积分 0/)).toBeTruthy()
  expect(await screen.findByText(/暂无积分流水/)).toBeTruthy()
  await waitFor(() => expect(calls.some(([url]) => url.includes('/management-reviews?'))).toBe(true))
  await screen.findByText(/暂无兑换记录/)
  expect(calls.every(([, method]) => method === 'GET')).toBe(true)
  calls.length = 0
  choose([], 'family', 'pa', 'account-family')
  expect(await screen.findByText(/当前身份没有该患者的积分读取权限/)).toBeTruthy()
  expect(calls).toEqual([['/api/v1/points/rules', 'GET']])
})

it('weekly review uses local ISO week and recovers a committed write from the server after loss of response', async () => {
  let saved: { week_start: string; reflection: string; completed_at: string } | null = null
  vi.setSystemTime(new Date('2026-11-22T15:59:59Z'))
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      if (url.endsWith('/points/rules')) return Promise.resolve(success({ rules_version: 'points-demo-v1', rules: [] }))
      if (url.endsWith('/points')) return Promise.resolve(success({ balance: 0, meta: { revision: 1 } }))
      if (options.method === 'POST') {
        expect(new Headers(options.headers).get('Idempotency-Key')).toHaveLength(36)
        if (typeof options.body !== 'string') throw new TypeError('Expected request body')
        const submission = v.parse(
          v.looseObject({ week_start: v.string(), reflection: v.string(), confirmed_completed: v.boolean() }),
          JSON.parse(options.body),
        )
        expect(submission.confirmed_completed).toBe(true)
        expect(submission.week_start).toBe('2026-11-23')
        saved = {
          week_start: submission.week_start,
          reflection: submission.reflection,
          completed_at: new Date().toISOString(),
        }
        return Promise.reject(new Error('Response lost after commit'))
      }
      return Promise.resolve(
        success({ items: url.includes('/management-reviews?') && saved ? [saved] : [], next_cursor: null }),
      )
    }),
  )
  choose(['points:read'])
  navigate('rewards')
  render(() => <TestPage />)
  expect(await screen.findByText(/当周起始日 2026-11-16/)).toBeTruthy()
  vi.setSystemTime(new Date('2026-11-22T16:00:00Z'))
  navigate('rewards')
  expect(await screen.findByText(/当周起始日 2026-11-23/)).toBeTruthy()
  fireEvent.input(await screen.findByLabelText('回顾内容（可留空）'), { target: { value: '虚构回顾' } })
  fireEvent.click(screen.getByLabelText('我已完成本周管理回顾'))
  fireEvent.click(screen.getByRole('button', { name: '确认完成本周回顾' }))
  expect(await screen.findByText(/已记录本周回顾/)).toBeTruthy()
  expect(screen.getByText('虚构回顾')).toBeTruthy()
  expect(screen.getByText(/可用积分 0/)).toBeTruthy()
})
