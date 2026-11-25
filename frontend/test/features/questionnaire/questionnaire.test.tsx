import type { SuccessResponse } from '../../support'
import { cleanup, fireEvent, render, screen, waitFor } from '@solidjs/testing-library'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ProfilePage } from '../../../src/features/questionnaire/profile-page'
import { QuestionnairePage } from '../../../src/features/questionnaire/questionnaire-page'
import { ReviewForm } from '../../../src/features/questionnaire/review-form'
import { currentNotice, notice } from '../../../src/notice/notice'
import { Notice } from '../../../src/notice/notice-view'
import { state, updateSession } from '../../../src/session/session'
import { choose, success } from '../../support'

const definition = {
  questionnaire_id: 'initial',
  purpose: 'fictional questionnaire',
  version: 'initial-v0.1',
  themes: Array.from({ length: 8 }, (_, index) => ({
    question_id: `Q${index + 1}`,
    prompt: '虚构问题',
    interaction: 'scenario',
    options: [{ code: 'none', label: '无' }],
    allows_unknown: true,
    allows_not_applicable: true,
  })),
}
function latestProfile(profile: unknown, responseId = 'submitted') {
  return success({ response_id: responseId, submitted_at: '2026-11-24T00:00:00Z', profile })
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
})

it('preserves the saved reference when questionnaire restore fails transiently', async () => {
  const reference = 'reference:account-a:pa:questionnaire'
  localStorage.setItem(reference, 'response-a')
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      url.includes('/questionnaires/initial')
        ? success(definition)
        : {
            ok: false,
            status: 503,
            json: () =>
              Promise.resolve({
                request_id: 'test',
                status: 'error',
                data: null,
                error: { code: 'DEPENDENCY_NOT_READY', message: 'temporary storage failure' },
              }),
          },
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
  const answer = { state: 'not_answered', value: null, answered_by: 'self', updated_at: '2026-01-01T00:00:00+00:00' }
  response.resolve(
    success({
      response_id: 'response-a',
      patient_id: 'pa',
      questionnaire_version: 'initial-v0.1',
      respondent_account_id: 'account-a',
      respondent_mode: 'self',
      status: 'draft',
      supersedes_response_id: null,
      submitted_at: null,
      answers: { Q1: answer, Q2: answer, Q3: answer, Q4: answer, Q5: answer, Q6: answer, Q7: answer, Q8: answer },
      meta: { revision: 1 },
    }),
  )
  const settled = Promise.withResolvers<undefined>()
  setTimeout(settled.resolve, 0)
  await settled.promise
  expect(state.response).toBeNull()
  expect(currentNotice().text).toBe('')
  expect(localStorage.getItem(a)).toBe('response-a')
  expect(localStorage.getItem(b)).toBe('response-b')
})

it('restores the wording of a legacy draft after the default changes', async () => {
  localStorage.setItem('reference:account-a:pa:questionnaire', 'old')
  const answer = { state: 'not_answered', value: null }
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.endsWith('/initial')) {
        return success({
          ...definition,
          version: 'initial-cas-review-v1-core1',
          themes: definition.themes.map(t => ({ ...t, prompt: '新版问题' })),
        })
      }
      if (url.endsWith('?version=initial-v0.1')) return success(definition)
      return success({
        questionnaire_version: 'initial-v0.1',
        response_id: 'old',
        status: 'draft',
        meta: { revision: 1 },
        answers: Object.fromEntries(definition.themes.map(t => [t.question_id, answer])),
      })
    }),
  )
  render(() => <QuestionnairePage />)
  expect(await screen.findByRole('group', { name: '虚构问题' })).toBeTruthy()
  expect(screen.queryByText('新版问题')).toBeNull()
})

it.each([
  { observed: undefined, expected: '旧版问卷未采集实测 CAS 三题。' },
  { observed: { status: 'observed', value: 11, reasons: [] }, expected: /11\/15（自报）/ },
  {
    observed: { status: 'insufficient', value: null, reasons: ['Q3 坚持用药的难度未取得有效回答'] },
    expected: /Q3 坚持用药的难度/,
  },
])('shows the stored result and independent prediction state', async ({ observed, expected }) => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      latestProfile({
        generated_at: '2026-11-24T00:00:00Z',
        primary_type: null,
        cas: { status: 'unavailable', value: null, reason: '模型待验证' },
        cas_observed: observed,
        missing_items: [],
        factors: [],
      }),
    ),
  )
  render(() => <ProfilePage />)
  expect(await screen.findByText(expected)).toBeTruthy()
  expect(screen.getByText(/模型预测 CAS · 未配置/)).toBeTruthy()
})

it('shows the research estimate with its model version alongside the self-reported score', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      latestProfile({
        generated_at: '2026-11-24T00:00:00Z',
        primary_type: null,
        factors: [],
        missing_items: [],
        cas_observed: { status: 'observed', value: 9, reasons: [] },
        cas: { status: 'estimated', value: 10.6713438, reason: null, model_version: 'cas-dl2-retrain-20261124' },
      }),
    ),
  )
  render(() => <ProfilePage />)
  expect(await screen.findByText(/模型预测 CAS · 10.67 分（研究估计）/)).toBeTruthy()
  expect(screen.getByText(/研究重训模型版本 · cas-dl2-retrain-20261124/)).toBeTruthy()
  expect(screen.getByText(/9\/15（自报）/)).toBeTruthy()
})

it('generates the latest submitted response even when the browser points to a newer draft', async () => {
  localStorage.setItem('reference:account-a:pa:questionnaire', 'empty-draft')
  const result = {
    generated_at: '2026-11-24T00:00:00Z',
    primary_type: null,
    factors: [],
    missing_items: [],
    cas_observed: { status: 'observed', value: 15, reasons: [] },
    cas: { status: 'insufficient', value: null, reason: '未填补充题' },
  }
  let generated = false
  const fetcher = vi.fn((url: string, options: RequestInit) => {
    if (url.endsWith('/profiles/current?source=latest_submission')) {
      return latestProfile(generated ? result : null, 'new-submission')
    }
    if (url.endsWith('/profiles') && options.method === 'POST') {
      generated = true
      return success(result)
    }
    throw new Error('unexpected request')
  })
  vi.stubGlobal('fetch', fetcher)
  render(() => <ProfilePage />)
  await screen.findByText('最近提交的问卷尚未生成画像。')
  expect(screen.queryByText('你的回答与关注重点')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '根据已提交问卷生成画像' }))
  expect(await screen.findByText(/15\/15（自报）/)).toBeTruthy()
  expect(fetcher).toHaveBeenCalledWith(
    '/api/v1/patients/pa/profiles',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ response_id: 'new-submission' }),
    }),
  )
  expect(localStorage.getItem('reference:account-a:pa:questionnaire')).toBe('empty-draft')
})

it('generates and opens the submitted self reassessment using the response returned by submit', async () => {
  const ref = 'reference:account-a:pa:questionnaire'
  localStorage.setItem(ref, 'self-reassessment')
  const qs = definition.themes.map((t, i) => ({ ...t, fields: [], prompt: `测试题组${i + 1}` }))
  const answers = Object.fromEntries(
    qs.map((t, i) => [t.question_id, { state: i < 3 ? 'unknown' : 'not_answered', value: null }]),
  )
  const response = {
    questionnaire_version: 'initial-cas-review-v1',
    response_id: 'self-reassessment',
    status: 'draft',
    answers,
    meta: { revision: 1 },
  }
  const fetcher = vi.fn((url: string, options: RequestInit) => {
    if (url.endsWith('/questionnaires/initial')) {
      return success({ ...definition, version: response.questionnaire_version, themes: qs })
    }
    if (url.endsWith('/self-reassessment')) return success(response)
    if (url.endsWith('/answers')) return success({ ...response, meta: { revision: 2 } })
    if (url.endsWith('/submit')) {
      localStorage.setItem(ref, 'another-tab-draft')
      return success({ ...response, status: 'submitted', meta: { revision: 3 } })
    }
    if (url.endsWith('/profiles') && options.method === 'POST') {
      return success({
        generated_at: '2026-11-24T00:00:00Z',
        primary_type: null,
        factors: [],
        missing_items: [],
        cas: { status: 'insufficient', value: null, reason: '输入不足' },
      })
    }
    throw new Error('unexpected request')
  })
  vi.stubGlobal('fetch', fetcher)
  render(() => <QuestionnairePage />)
  fireEvent.click(await screen.findByLabelText(/我确认提交本次问卷/))
  fireEvent.click(screen.getByRole('button', { name: '提交问卷并生成画像' }))
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      '/api/v1/patients/pa/profiles',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ response_id: 'self-reassessment' }),
      }),
    ),
  )
  await waitFor(() => expect(state.tab).toBe('assessment'))
})

it('offers only selected Q4 barriers as main and clears hidden answers before saving', async () => {
  const blank = { state: 'not_answered', value: null }
  const response = {
    questionnaire_version: 'initial-cas-review-v1' as const,
    response_id: 'draft',
    status: 'draft',
    meta: { revision: 1 },
    answers: { Q1: blank, Q2: blank, Q3: blank, Q4: blank, Q5: blank, Q6: blank, Q7: blank, Q8: blank },
  }
  const saved = vi.fn<() => void>()
  const fetcher = vi.fn(() => success(response))
  vi.stubGlobal('fetch', fetcher)
  render(() => (
    <ReviewForm
      response={response}
      index={3}
      onSaved={saved}
      theme={{
        question_id: 'Q4',
        prompt: '发生过什么？',
        options: [],
        fields: [
          {
            key: 'reported_pattern',
            prompt: '实际行为',
            kind: 'choice',
            options: [
              { code: 'both', label: '两种都有' },
              { code: 'none_reported', label: '未发生' },
            ],
          },
          {
            key: 'barriers',
            prompt: '实际原因',
            kind: 'multiple',
            options: [
              { code: 'forgot_or_habit_disrupted', label: '忘记' },
              { code: 'other', label: '其他' },
            ],
          },
          { key: 'main_barrier', prompt: '主要原因', kind: 'selected_choice', options: [] },
        ],
      }}
    />
  ))
  expect(screen.queryByLabelText('忘记')).toBeNull()
  fireEvent.change(screen.getByLabelText('实际行为'), { target: { value: 'both' } })
  fireEvent.click(await screen.findByLabelText('忘记'))
  const main = await screen.findByLabelText<HTMLSelectElement>('主要原因')
  expect(Array.from(main.options, o => o.value)).toEqual(['', 'forgot_or_habit_disrupted'])
  fireEvent.change(main, { target: { value: 'forgot_or_habit_disrupted' } })
  fireEvent.click(screen.getByLabelText('其他'))
  await waitFor(() =>
    expect(Array.from(screen.getByLabelText<HTMLSelectElement>('主要原因').options, o => o.value)).toContain('other'),
  )
  fireEvent.click(screen.getByLabelText('忘记'))
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>('主要原因').value).toBe(''))
  fireEvent.change(screen.getByLabelText('实际行为'), { target: { value: 'none_reported' } })
  await waitFor(() => expect(screen.queryByLabelText('主要原因')).toBeNull())
  fireEvent.click(screen.getByRole('button', { name: '保存进度' }))
  await waitFor(() => expect(saved).toHaveBeenCalled())
  expect(fetcher).toHaveBeenCalledWith(
    expect.any(String),
    expect.objectContaining({
      body: JSON.stringify({
        expected_revision: 1,
        answers: { ...response.answers, Q4: { state: 'answered', value: { reported_pattern: 'none_reported' } } },
      }),
    }),
  )
})

it('shows both matching barriers when the participant gave no primary cause', async () => {
  const fetcher = vi.fn(() =>
    latestProfile({
      generated_at: '2026-11-24T00:00:00Z',
      primary_type: null,
      missing_items: [],
      factors: [],
      cas_observed: { status: 'observed', value: 9, reasons: [] },
      cas: { status: 'unavailable', value: null, reason: '网页预测关闭' },
      demo_classification: {
        primary_type: null,
        reported_matching_types: ['B1', 'C2'],
        type_labels: { B1: '遗忘与习惯缺失型', C2: '用药顾虑与心理抗拒型' },
        reason: '保留匹配',
        entry_codes: ['reminder'],
      },
    }),
  )
  vi.stubGlobal('fetch', fetcher)
  render(() => <ProfilePage />)
  expect(await screen.findByText(/演示主类型 · 暂不分型/)).toBeTruthy()
  expect(screen.getByText(/符合条件的障碍 · B1 遗忘与习惯缺失型、C2 用药顾虑与心理抗拒型/)).toBeTruthy()
  expect(fetcher).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: '查看提醒设置' }))
  await waitFor(() => expect(state.tab).toBe('reminders'))
  expect(fetcher).toHaveBeenCalledTimes(1)
})
