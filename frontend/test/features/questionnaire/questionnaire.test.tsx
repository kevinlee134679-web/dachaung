import type { AnswerValue, Definition, QuestionnaireResponse } from '../../../src/features/questionnaire/questionnaire'
import type { SuccessResponse } from '../../support'
import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import * as v from 'valibot'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AdherencePage } from '../../../src/features/questionnaire/adherence-page'
import { ProfilePage } from '../../../src/features/questionnaire/profile-page'
import { QuestionWizard } from '../../../src/features/questionnaire/question-wizard'
import { QuestionnairePage } from '../../../src/features/questionnaire/questionnaire-page'
import { currentNotice, notice } from '../../../src/notice/notice'
import { Notice } from '../../../src/notice/notice-view'
import { state, updateSession } from '../../../src/session/session'
import { ConfirmHost } from '../../../src/ui/confirm'
import { choose, failure, success } from '../../support'

const definition: Definition = {
  questionnaire_id: 'initial',
  version: 'initial-cas-review-v1',
  purpose: '用药评估',
  themes: [
    {
      question_id: 'Q1',
      title: '用药知识',
      section: 'core',
      fields: [
        {
          key: 'knowledge',
          prompt: '了解用药',
          kind: 'scale',
          options: [
            { code: 4, label: '符合' },
            { code: 'unknown', label: '无法判断' },
          ],
        },
      ],
    },
    {
      question_id: 'Q2',
      title: '漏服频率',
      section: 'core',
      fields: [
        {
          key: 'adherence_freq',
          prompt: '漏服频率',
          kind: 'choice',
          options: [{ code: '从不漏服', label: '从不漏服' }],
        },
      ],
    },
    {
      question_id: 'Q3',
      title: '用药难度',
      section: 'core',
      fields: [{ key: 'difficulty', prompt: '用药难度', kind: 'scale', options: [{ code: 1, label: '没有难度' }] }],
    },
    {
      question_id: 'Q4',
      title: '用药障碍',
      section: 'core',
      fields: [
        {
          key: 'reported_pattern',
          prompt: '实际行为',
          kind: 'choice',
          options: [
            { code: 'none_reported', label: '未发生' },
            { code: 'intentional', label: '主动选择' },
          ],
        },
        {
          key: 'barriers',
          prompt: '实际原因',
          kind: 'multiple',
          optional: true,
          visible_when: { field: 'reported_pattern', in: ['unintentional', 'intentional', 'both'] },
          options: [
            { code: 'forgot_or_habit_disrupted', label: '忘记' },
            { code: 'other', label: '其他' },
            { code: 'execution_or_access', label: '取药不便' },
          ],
        },
        {
          key: 'main_barrier',
          prompt: '主要原因',
          kind: 'selected_choice',
          optional: true,
          source: 'barriers',
          options: [],
        },
      ],
    },
    {
      question_id: 'Q5',
      title: '选填问题',
      section: 'optional',
      fields: [
        { key: 'drug_duration', prompt: '用药时长', kind: 'choice', options: [{ code: '1-3年', label: '1-3年' }] },
      ],
    },
  ],
}

function draftResponse(values: Record<string, AnswerValue> = {}): QuestionnaireResponse {
  const answer = (questionId: string) => ({
    value: values[questionId] ?? {},
    answered_by: 'self' as const,
    updated_at: '2026-01-01T00:00:00Z',
  })
  return {
    response_id: 'response-a',
    patient_id: 'pa',
    questionnaire_version: 'initial-cas-review-v1',
    respondent_account_id: 'account-a',
    respondent_mode: 'self',
    status: 'draft',
    supersedes_response_id: null,
    submitted_at: null,
    answers: {
      Q1: answer('Q1'),
      Q2: answer('Q2'),
      Q3: answer('Q3'),
      Q4: answer('Q4'),
      Q5: answer('Q5'),
      Q6: answer('Q6'),
      Q7: answer('Q7'),
      Q8: answer('Q8'),
    },
    meta: { revision: 1 },
  }
}

const profile = {
  profile_id: 'profile-a',
  patient_id: 'pa',
  response_id: 'response-a',
  questionnaire_version: 'initial-cas-review-v1',
  status: 'current',
  cas_observed: { status: 'observed', value: 12, missing_items: [], reasons: [] },
  cas: { status: 'unavailable', value: null, model_version: null, reason: '未配置 CAS 模型' },
  cards: [{ question_id: 'Q1', title: '用药知识', answers: ['符合'], level: 'good', note: '继续保持。' }],
  factors: [],
  assessment_method_version: 'cas-questionnaire-v2',
  generated_at: '2026-11-24T00:00:00Z',
  meta: { revision: 1 },
}

const showModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal')
const closeDialog = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close')
const answerValueSchema = v.record(v.string(), v.union([v.string(), v.number(), v.array(v.string())]))
const answerRequestSchema = v.object({
  expected_revision: v.number(),
  answers: v.record(v.string(), answerValueSchema),
})

function answerRequest(body: BodyInit | null | undefined) {
  return v.parse(answerRequestSchema, JSON.parse(v.parse(v.string(), body)))
}

beforeEach(() => {
  localStorage.clear()
  notice('')
  choose({ patient: 'pa', scopes: ['questionnaire:assist', 'profile:read'] })
  updateSession(draft => {
    draft.response = null
    draft.epoch++
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  if (showModal) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', showModal)
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal')
  if (closeDialog) Object.defineProperty(HTMLDialogElement.prototype, 'close', closeDialog)
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'close')
})

it('preserves the saved reference when questionnaire restore fails transiently', async () => {
  const reference = 'reference:account-a:pa:questionnaire'
  localStorage.setItem(reference, 'response-a')
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      url.includes('/questionnaires/initial')
        ? success(definition)
        : failure(503, 'DEPENDENCY_NOT_READY', 'temporary storage failure'),
    ),
  )
  render(() => (
    <>
      <Notice />
      <QuestionnairePage />
    </>
  ))
  await screen.findByText('temporary storage failure')
  expect(localStorage.getItem(reference)).toBe('response-a')
})

it('does not let an old questionnaire restore change the newly selected patient reference', async () => {
  const requested = Promise.withResolvers<undefined>()
  const response = Promise.withResolvers<SuccessResponse>()
  const a = 'reference:account-a:pa:questionnaire'
  const b = 'reference:account-a:pb:questionnaire'
  localStorage.setItem(a, 'response-a')
  localStorage.setItem(b, 'response-b')
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.includes('/questionnaires/initial')) return Promise.resolve(success(definition))
      requested.resolve(undefined)
      return response.promise
    }),
  )
  render(() => <QuestionnairePage />)
  await requested.promise
  choose({ patient: 'pb', scopes: ['questionnaire:assist', 'profile:read'] })
  updateSession(draft => {
    draft.response = null
    draft.epoch++
  })
  response.resolve(success(draftResponse()))
  const settled = Promise.withResolvers<undefined>()
  setTimeout(settled.resolve, 0)
  await settled.promise
  expect(state.response).toBeNull()
  expect(currentNotice().text).toBe('')
  expect(localStorage.getItem(a)).toBe('response-a')
  expect(localStorage.getItem(b)).toBe('response-b')
})

it('creates a response only after privacy consent', async () => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
    configurable: true,
    value(this: HTMLDialogElement) {
      this.setAttribute('open', '')
    },
  })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', {
    configurable: true,
    value(this: HTMLDialogElement) {
      this.removeAttribute('open')
    },
  })
  const fetcher = vi.fn((url: string, options: RequestInit) =>
    url.endsWith('/questionnaires/initial')
      ? success(definition)
      : options.method === 'POST'
        ? success(draftResponse())
        : failure(404, 'NOT_FOUND', '没有答卷'),
  )
  vi.stubGlobal('fetch', fetcher)
  render(() => (
    <>
      <ConfirmHost />
      <QuestionnairePage />
    </>
  ))
  fireEvent.click(await screen.findByRole('button', { name: '开始评估' }))
  fireEvent.click(await screen.findByRole('button', { name: '取消' }))
  expect(fetcher.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(0)
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: '开始评估' }).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: '开始评估' }))
  fireEvent.click(await screen.findByRole('button', { name: '确认' }))
  await waitFor(() => expect(fetcher.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1))
})

it('saves the whole Q1 value and advances after a single choice', async () => {
  const response = draftResponse()
  const fetcher = vi.fn((_: string, _options: RequestInit) =>
    success({
      ...response,
      answers: {
        ...response.answers,
        Q1: { value: { knowledge: 4 }, answered_by: 'self', updated_at: '2026-01-01T00:00:00Z' },
      },
      meta: { revision: 2 },
    }),
  )
  vi.stubGlobal('fetch', fetcher)
  render(() => <QuestionWizard definition={definition} response={response} onSubmitted={() => {}} />)
  fireEvent.click(await screen.findByRole('radio', { name: '符合' }))
  await waitFor(() => expect(fetcher).toHaveBeenCalled())
  expect(answerRequest(fetcher.mock.calls[0]?.[1].body)).toEqual({
    expected_revision: 1,
    answers: { Q1: { knowledge: 4 } },
  })
  expect(await screen.findByRole('radio', { name: '从不漏服' })).toBeTruthy()
})

it('shows only selected Q4 barriers and clears hidden answers when the pattern changes', async () => {
  let response = draftResponse({ Q1: { knowledge: 4 }, Q2: { adherence_freq: '从不漏服' }, Q3: { difficulty: 1 } })
  const fetcher = vi.fn((_: string, options: RequestInit) => {
    const body = answerRequest(options.body)
    response = {
      ...response,
      answers: {
        ...response.answers,
        Q4: {
          value: v.parse(answerValueSchema, body.answers['Q4']),
          answered_by: 'self',
          updated_at: '2026-01-01T00:00:00Z',
        },
      },
      meta: { revision: response.meta.revision + 1 },
    }
    return success(response)
  })
  vi.stubGlobal('fetch', fetcher)
  render(() => <QuestionWizard definition={definition} response={response} onSubmitted={() => {}} />)
  fireEvent.click(await screen.findByRole('radio', { name: '未发生' }))
  expect(await screen.findByText('以下题目用于模型评估，可选填写')).toBeTruthy()
  expect(screen.queryByRole('checkbox', { name: '忘记' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '上一题' }))
  fireEvent.click(await screen.findByRole('radio', { name: '主动选择' }))
  fireEvent.click(await screen.findByRole('checkbox', { name: '忘记' }))
  await waitFor(() => expect(screen.getByRole('checkbox', { name: '忘记' }).getAttribute('aria-checked')).toBe('true'))
  fireEvent.click(await screen.findByRole('checkbox', { name: '其他' }))
  await waitFor(() => expect(screen.getByRole('checkbox', { name: '其他' }).getAttribute('aria-checked')).toBe('true'))
  fireEvent.click(screen.getByRole('button', { name: '下一题' }))
  expect(await screen.findByRole('radio', { name: '忘记' })).toBeTruthy()
  expect(screen.getByRole('radio', { name: '其他' })).toBeTruthy()
  expect(screen.queryByRole('radio', { name: '取药不便' })).toBeNull()
  fireEvent.click(screen.getByRole('radio', { name: '忘记' }))
  await waitFor(() => expect(screen.getByRole('radio', { name: '忘记' }).getAttribute('aria-checked')).toBe('true'))
  fireEvent.click(screen.getByRole('button', { name: '下一题' }))
  await screen.findByText('以下题目用于模型评估，可选填写')
  fireEvent.click(screen.getByRole('button', { name: '上一题' }))
  await screen.findByRole('radiogroup', { name: '主要原因' })
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: '上一题' }).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: '上一题' }))
  await screen.findByRole('group', { name: '实际原因' })
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: '上一题' }).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: '上一题' }))
  fireEvent.click(await screen.findByRole('radio', { name: '未发生' }))
  await waitFor(() =>
    expect(answerRequest(fetcher.mock.calls.at(-1)?.[1].body).answers['Q4']).toEqual({
      reported_pattern: 'none_reported',
    }),
  )
})

it('skips optional questions, generates a profile and shows its result', async () => {
  localStorage.setItem('reference:account-a:pa:questionnaire', 'response-a')
  const response = draftResponse({ Q1: { knowledge: 4 }, Q2: { adherence_freq: '从不漏服' }, Q3: { difficulty: 1 } })
  const fetcher = vi.fn((url: string, options: RequestInit) => {
    if (url.endsWith('/questionnaires/initial')) return success(definition)
    if (url.endsWith('/latest-submitted')) {
      return success({ response_id: 'response-a', submitted_at: '2026-11-24T00:00:00Z', profile })
    }
    if (url.endsWith('/answers')) {
      return success({
        ...response,
        answers: {
          ...response.answers,
          Q4: { value: { reported_pattern: 'none_reported' }, answered_by: 'self', updated_at: '2026-01-01T00:00:00Z' },
        },
        meta: { revision: 2 },
      })
    }
    if (url.endsWith('/submit')) {
      return success({ ...response, status: 'submitted', submitted_at: '2026-11-24T00:00:00Z' })
    }
    if (url.endsWith('/profiles') && options.method === 'POST') return success(profile)
    return success(response)
  })
  vi.stubGlobal('fetch', fetcher)
  render(() => <AdherencePage />)
  fireEvent.click(await screen.findByRole('radio', { name: '未发生' }))
  fireEvent.click(await screen.findByRole('button', { name: '跳过选填部分' }))
  fireEvent.click(await screen.findByLabelText(/我确认提交本次问卷/))
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: '提交问卷' }).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: '提交问卷' }))
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      '/api/v1/patients/pa/profiles',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ response_id: 'response-a' }) }),
    ),
  )
  expect(await screen.findByText('继续保持。')).toBeTruthy()
})

it('shows result cards without CAS scores or types', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => success({ response_id: 'response-a', submitted_at: '2026-11-24T00:00:00Z', profile })),
  )
  const view = render(() => <ProfilePage />)
  expect(await screen.findByText('用药知识')).toBeTruthy()
  expect(screen.getByText('良好')).toBeTruthy()
  expect(screen.getByText('继续保持。')).toBeTruthy()
  expect(view.container.textContent).not.toContain('CAS')
  expect(view.container.textContent).not.toContain('类型')
})
