import { cleanup, render, screen } from '@solidjs/testing-library'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { currentNotice, notice } from '../../../src/notice/notice'
import { Notice } from '../../../src/notice/notice-view'
import { QuestionnairePage } from '../../../src/pages/profile/questionnaire-page'
import { state, updateSession } from '../../../src/session/session'

interface SuccessResponse {
  ok: true
  status: 200
  json: () => Promise<{ request_id: string; status: string; data: unknown; error: null }>
}

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
function success(data: unknown): SuccessResponse {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ request_id: 'test', status: 'success', data, error: null }),
  }
}

function choose(id: string): void {
  const access = {
    patient: { patient_id: id, display_name: id, timezone: 'Asia/Shanghai' },
    relationship: 'self',
    effective_scopes: ['questionnaire:assist'],
  }
  updateSession(draft => {
    draft.context = {
      account: { account_id: 'account-a', display_name: 'account-a', is_simulated: true },
      csrf_token: 'csrf-a',
      current_patient_id: id,
      patients: [access],
    }
    draft.patient = access
    draft.response = null
    draft.epoch++
  })
}

beforeEach(() => {
  localStorage.clear()
  notice('')
  choose('pa')
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
  choose('pb')
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
