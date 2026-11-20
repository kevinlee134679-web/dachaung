import type { SupportSession } from '../../../src/pages/support/support-conversation'
import { webcrypto } from 'node:crypto'
import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import { Show } from 'solid-js'
import * as v from 'valibot'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Notice } from '../../../src/notice/notice-view'
import { invitationSchema, InvitationList } from '../../../src/pages/support/home-support-invitations'
import { SupportMessage, supportSessionSchema } from '../../../src/pages/support/support-conversation'
import { SupportPage } from '../../../src/pages/support/support-page'
import { state, updateSession } from '../../../src/session/session'

function success(data: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ request_id: 'test', status: 'success', data, error: null }),
  }
}
function failure(status: number, code: string) {
  return {
    ok: false,
    status,
    json: () => Promise.resolve({ request_id: 'test', status: 'error', data: null, error: { code, message: code } }),
  }
}
const generationOutput = {
  business_output: {
    assistant_reply: '我在听。',
    support_focus: 'listening',
    communication_strategy: ['reflection'],
    difficulty_cues: [],
    knowledge_citations: [],
    suggested_action: null,
    change_readiness: null,
  },
  generation: {
    generation_id: 'generation',
    patient_id: 'pa',
    user_message_id: 'message',
    status: 'completed',
    mode: 'mock',
    requested_pipeline: 'single_pass',
    actual_pipeline: 'single_pass',
    fallback_reason: null,
    session_id: 'support-s',
    input_snapshot: {
      snapshot_id: 'snapshot',
      patient_id: 'pa',
      session_id: 'support-s',
      user_message_id: 'message',
      history_message_ids: [],
      profile_id: null,
      plan_refs: [],
      summary_ref: null,
      retrieval_id: null,
      version_refs: [],
      missing_items: [],
      captured_at: '2026-11-17T12:00:00Z',
    },
    budget: {
      max_network_attempts: 1,
      used_network_attempts: 0,
      max_candidates: 1,
      max_output_tokens: null,
      deadline_at: '2026-11-17T12:01:00Z',
    },
    calls: [],
    error_code: null,
    started_at: '2026-11-17T12:00:00Z',
    finished_at: '2026-11-17T12:00:01Z',
    is_simulated: true,
  },
  user_message: {
    message_id: 'message',
    patient_id: 'pa',
    session_id: 'support-s',
    client_message_id: 'client-message',
    role: 'user',
    content: '你好',
    author_account_id: 'account',
    source_message_id: null,
    generation_id: 'generation',
    generation_status: 'completed',
    created_at: '2026-11-17T12:00:00Z',
    is_simulated: true,
  },
  assistant_message: {
    message_id: 'reply',
    patient_id: 'pa',
    session_id: 'support-s',
    client_message_id: null,
    role: 'assistant',
    content: '我在听。',
    author_account_id: null,
    source_message_id: 'message',
    generation_id: 'generation',
    generation_status: 'not_applicable',
    created_at: '2026-11-17T12:00:01Z',
    is_simulated: true,
  },
  intervention_id: null,
  suggestion_ids: [],
}
function session() {
  return v.parse(supportSessionSchema, {
    session_id: 'support-s',
    patient_id: 'pa',
    case_id: null,
    entry_source: 'user',
    invitation_id: null,
    turn_count: 2,
    status: 'active',
    ui_mode: 'normal',
    opened_at: '2026-11-17T12:00:00Z',
    closed_at: null,
    meta: {
      revision: 1,
      created_at: '2026-11-17T12:00:00Z',
      updated_at: '2026-11-17T12:00:00Z',
      contract_version: 'B-v0.4',
      is_simulated: true,
    },
  })
}
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto)
  localStorage.clear()
  sessionStorage.clear()
  const patient = {
    patient: { patient_id: 'pa', display_name: '患者', timezone: 'Asia/Shanghai' },
    relationship: 'self',
    effective_scopes: ['dialogue:read'],
  }
  updateSession(draft => {
    draft.context = {
      account: { account_id: 'account', display_name: '用户', is_simulated: true },
      csrf_token: 'csrf',
      current_patient_id: 'pa',
      patients: [patient],
    }
    draft.patient = patient
    draft.page = 'support'
    draft.tab = 'overview'
    draft.switchingPatient = false
    draft.epoch++
  })
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it('support reply renders model markup as literal text', () => {
  const markup = '<img src="x" onerror="evil()">'
  const { container } = render(() => (
    <SupportMessage
      session={session()}
      message={{
        role: 'assistant',
        content: markup,
        generation_status: 'not_applicable',
        message_id: 'message',
        generation_id: 'generation',
      }}
      canWrite={false}
    />
  ))
  expect(container.textContent).toContain(markup)
  expect(container.querySelector('img')).toBeNull()
})

it('an expired pending support invitation has no acceptance control', () => {
  const { container } = render(() => (
    <InvitationList
      evaluatedAt="2026-11-17T12:00:00Z"
      items={[
        v.parse(invitationSchema, {
          status: 'pending',
          invitation_id: 'test',
          title: '支持邀请',
          description: '可自行选择',
          valid_until: '2026-11-17T12:00:00Z',
          session_id: null,
          patient_id: 'pa',
          trigger_type: 'state_event',
          trigger_ref: 'trigger',
          created_at: '2026-11-17T11:00:00Z',
          displayed_at: null,
          resolved_session_id: null,
          rule_version: 'support-default',
          is_simulated: true,
        }),
      ]}
    />
  ))
  expect(container.textContent).toContain('已到期')
  expect(container.querySelector('button')).toBeNull()
})

async function openComposer(handler: (url: string, options: RequestInit, current: SupportSession) => Promise<unknown>) {
  const current = session()
  const events: [string | undefined, string][] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options: RequestInit) => {
      events.push([options.method, url])
      if (url === '/api/v1/sessions?patient_id=pa&limit=100')
        return Promise.resolve(success({ items: [current], next_cursor: null }))
      if (url === '/api/v1/sessions/support-s/messages?limit=100')
        return Promise.resolve(success({ items: [], next_cursor: null }))
      return handler(url, options, current)
    }),
  )
  render(() => (
    <>
      <Notice />
      <Show when={state.epoch + 1} keyed>
        <SupportPage />
      </Show>
    </>
  ))
  await screen.findByLabelText('你想说的话')
  return {
    events,
    editor: () => {
      const element = screen.getByLabelText('你想说的话')
      if (!(element instanceof HTMLTextAreaElement)) throw new TypeError('Expected textarea')
      return element
    },
    click: (label: string) => fireEvent.click(screen.getByRole('button', { name: label })),
  }
}

it('rejected support turn with absent original refreshes the session and waits for explicit resend', async () => {
  const posts: { body: { client_message_id: string; expected_turn_count: number; content: string }; key: string }[] = []
  const env = await openComposer((url, options, current) => {
    if (options.method === 'GET') {
      expect(url).toBe(`/api/v1/sessions/support-s/messages?client_message_id=${posts[0]?.body.client_message_id}`)
      return Promise.resolve(failure(404, 'RESOURCE_NOT_FOUND'))
    }
    const key = new Headers(options.headers).get('Idempotency-Key')
    expect(key).toBeDefined()
    if (key === null) throw new Error('Missing idempotency key')
    if (typeof options.body !== 'string') throw new TypeError('Missing request body')
    posts.push({
      body: v.parse(
        v.looseObject({ client_message_id: v.string(), expected_turn_count: v.number(), content: v.string() }),
        JSON.parse(options.body),
      ),
      key,
    })
    if (posts.length === 1) {
      current.turn_count = 3
      return Promise.resolve(failure(409, 'SESSION_REVISION_CONFLICT'))
    }
    expect(posts.at(-1)?.body.expected_turn_count).toBe(current.turn_count)
    current.turn_count++
    return Promise.resolve(success(generationOutput))
  })
  fireEvent.input(env.editor(), { target: { value: '留在页面内的草稿' } })
  const original = env.editor()
  env.click('发送')
  await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/再次点击发送/))
  expect(posts).toHaveLength(1)
  expect(env.events.filter(([, url]) => url.startsWith('/api/v1/sessions?'))).toHaveLength(2)
  expect(env.editor()).not.toBe(original)
  expect(env.editor().value).toBe('留在页面内的草稿')
  expect(sessionStorage.length).toBe(0)
  expect(localStorage.length).toBe(0)
  env.click('发送')
  await waitFor(() => expect(posts).toHaveLength(2))
  expect(posts.map(post => post.body.expected_turn_count)).toEqual([2, 3])
  expect(posts[1]?.body.content).toBe(posts[0]?.body.content)
  expect(posts[1]?.body.client_message_id).not.toBe(posts[0]?.body.client_message_id)
  expect(posts[1]?.key).not.toBe(posts[0]?.key)
})

it('lookup of an in-flight support submission preserves its ID and never starts another generation', async () => {
  let posted = ''
  let count = 0
  let status = 'running'
  const env = await openComposer((url, options, current) => {
    if (options.method === 'POST') {
      count++
      if (typeof options.body !== 'string') throw new TypeError('Missing request body')
      const body = v.parse(v.looseObject({ client_message_id: v.string() }), JSON.parse(options.body))
      posted = body.client_message_id
      current.turn_count = 3
      return Promise.resolve(failure(409, 'OPERATION_IN_PROGRESS'))
    }
    expect(url).toBe(`/api/v1/sessions/support-s/messages?client_message_id=${posted}`)
    return Promise.resolve(
      success({
        items: [
          {
            role: 'user',
            content: '发送中的消息',
            generation_status: status,
            message_id: 'message',
            generation_id: 'generation',
            client_message_id: posted,
            patient_id: 'pa',
            session_id: 'support-s',
            author_account_id: 'account',
            source_message_id: null,
            created_at: '2026-11-17T12:00:00Z',
            is_simulated: true,
          },
        ],
        next_cursor: null,
      }),
    )
  })
  fireEvent.input(env.editor(), { target: { value: '发送中的消息' } })
  env.click('发送')
  await screen.findByRole('button', { name: '核查原消息' })
  const key = sessionStorage.key(0)
  expect(key).not.toBeNull()
  if (key == null) return
  const serialized = sessionStorage.getItem(key)
  expect(serialized).not.toBeNull()
  if (serialized == null) return
  const pending = v.parse(v.looseObject({ id: v.string() }), JSON.parse(serialized))
  expect(pending.id).toBe(posted)
  expect(localStorage.length).toBe(1)
  status = 'completed'
  env.click('核查原消息')
  await waitFor(() => expect(screen.getByRole('status').textContent).toBe('已核对原消息。'))
  expect(count).toBe(1)
  expect(sessionStorage.length).toBe(0)
})

it('support timeout and absent lookup retain the original turn and both idempotency identifiers', async () => {
  const posts: { body: string; key: string }[] = []
  const env = await openComposer((url, options) => {
    if (options.method === 'GET') {
      const original = posts[0]
      expect(original).toBeDefined()
      if (original == null) throw new Error('Missing original post')
      const pending = v.parse(v.looseObject({ client_message_id: v.string() }), JSON.parse(original.body))
      expect(url).toBe(`/api/v1/sessions/support-s/messages?client_message_id=${pending.client_message_id}`)
      return Promise.resolve(failure(404, 'RESOURCE_NOT_FOUND'))
    }
    const key = new Headers(options.headers).get('Idempotency-Key')
    expect(key).toBeDefined()
    if (key === null) throw new Error('Missing idempotency key')
    if (typeof options.body !== 'string') throw new TypeError('Missing request body')
    posts.push({ body: options.body, key })
    if (posts.length === 1) return Promise.reject(Object.assign(new Error('test abort'), { name: 'AbortError' }))
    return Promise.resolve(success(generationOutput))
  })
  fireEvent.input(env.editor(), { target: { value: '结果尚待核对的消息' } })
  env.click('发送')
  await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/等待超时/))
  const key = sessionStorage.key(0)
  expect(key).not.toBeNull()
  if (key == null) return
  const serialized = sessionStorage.getItem(key)
  expect(serialized).not.toBeNull()
  if (serialized == null) return
  const pending = v.parse(v.looseObject({ id: v.string() }), JSON.parse(serialized))
  const submitted = posts[0]
  expect(submitted).toBeDefined()
  if (submitted == null) return
  const original = v.parse(v.looseObject({ client_message_id: v.string() }), JSON.parse(submitted.body))
  expect(pending.id).toBe(original.client_message_id)
  env.click('发送')
  await waitFor(() => expect(posts).toHaveLength(2))
  expect(posts[1]).toEqual(posts[0])
  await waitFor(() => expect(sessionStorage.length).toBe(0))
})
