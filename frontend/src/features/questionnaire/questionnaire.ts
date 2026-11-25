import type { View } from '../../session/session'
import * as v from 'valibot'
import { api } from '../../api/api'
import { patientPath } from '../../session/session'

type QuestionId = 'Q1' | 'Q2' | 'Q3' | 'Q4' | 'Q5' | 'Q6' | 'Q7' | 'Q8'

export interface Field {
  key: string
  prompt: string
  kind: 'scale' | 'choice' | 'multiple' | 'selected_choice'
  options: { code: string | number; label: string }[]
  optional?: boolean | undefined
  exclusive?: string[] | undefined
  visible_when?: { field: string; in: string[] } | undefined
  source?: string | undefined
}

export interface Theme {
  question_id: QuestionId
  title: string
  section: 'core' | 'optional'
  fields: Field[]
}

export interface Definition {
  questionnaire_id: string
  version: string
  purpose: string
  themes: Theme[]
}

export type AnswerValue = Record<string, string | number | string[]>

interface Answer {
  value: AnswerValue
  answered_by: 'self' | 'family_assisted'
  updated_at: string
}

export interface QuestionnaireResponse {
  response_id: string
  patient_id: string
  questionnaire_version: string
  respondent_account_id: string
  respondent_mode: 'self' | 'family_assisted'
  status: string
  answers: Record<QuestionId, Answer>
  supersedes_response_id: string | null
  submitted_at: string | null
  meta: { revision: number }
}

const optionSchema = v.object({ code: v.union([v.string(), v.number()]), label: v.string() })
const fieldSchema = v.object({
  key: v.string(),
  prompt: v.string(),
  kind: v.picklist(['scale', 'choice', 'multiple', 'selected_choice']),
  options: v.array(optionSchema),
  optional: v.optional(v.boolean()),
  exclusive: v.optional(v.array(v.string())),
  visible_when: v.optional(v.object({ field: v.string(), in: v.array(v.string()) })),
  source: v.optional(v.string()),
})
const questionIdSchema = v.picklist(['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8'])
const themeSchema = v.object({
  question_id: questionIdSchema,
  title: v.string(),
  section: v.picklist(['core', 'optional']),
  fields: v.array(fieldSchema),
})
const definitionSchema: v.GenericSchema<unknown, Definition> = v.object({
  questionnaire_id: v.string(),
  version: v.string(),
  purpose: v.string(),
  themes: v.array(themeSchema),
})
const valueSchema = v.record(v.string(), v.union([v.string(), v.number(), v.array(v.string())]))
const answerSchema = v.object({
  value: valueSchema,
  answered_by: v.picklist(['self', 'family_assisted']),
  updated_at: v.string(),
})
const responseSchema: v.GenericSchema<unknown, QuestionnaireResponse> = v.looseObject({
  response_id: v.string(),
  patient_id: v.string(),
  questionnaire_version: v.string(),
  respondent_account_id: v.string(),
  respondent_mode: v.picklist(['self', 'family_assisted']),
  status: v.string(),
  answers: v.object({
    Q1: answerSchema,
    Q2: answerSchema,
    Q3: answerSchema,
    Q4: answerSchema,
    Q5: answerSchema,
    Q6: answerSchema,
    Q7: answerSchema,
    Q8: answerSchema,
  }),
  supersedes_response_id: v.nullable(v.string()),
  submitted_at: v.nullable(v.string()),
  meta: v.looseObject({ revision: v.number() }),
})

export function loadDefinition(view: View): Promise<Definition> {
  return api('/questionnaires/initial', definitionSchema, 'GET', null, view)
}

export function loadResponse(id: string, view: View): Promise<QuestionnaireResponse> {
  return api(`/questionnaire-responses/${id}`, responseSchema, 'GET', null, view)
}

export function startResponse(view: View, supersedes: string | null): Promise<QuestionnaireResponse> {
  return api(
    patientPath('/questionnaire-responses'),
    responseSchema,
    'POST',
    { supersedes_response_id: supersedes },
    view,
  )
}

export function saveTheme(
  response: QuestionnaireResponse,
  questionId: string,
  value: AnswerValue,
  view: View,
): Promise<QuestionnaireResponse> {
  return api(
    `/questionnaire-responses/${response.response_id}/answers`,
    responseSchema,
    'PUT',
    {
      expected_revision: response.meta.revision,
      answers: { [questionId]: value },
    },
    view,
  )
}

export function submitResponse(
  response: QuestionnaireResponse,
  sameEpisode: boolean | null,
  view: View,
): Promise<QuestionnaireResponse> {
  return api(
    `/questionnaire-responses/${response.response_id}/submit`,
    responseSchema,
    'POST',
    {
      expected_revision: response.meta.revision,
      confirmed: true,
      same_episode: sameEpisode,
    },
    view,
  )
}

export function visibleFields(theme: Theme, value: AnswerValue): Field[] {
  return theme.fields.flatMap(field => {
    const condition = field.visible_when
    if (condition && !condition.in.some(option => option === value[condition.field])) return []
    if (field.kind !== 'selected_choice') return [field]
    const selected = value[field.source ?? '']
    if (!Array.isArray(selected) || selected.length < 2) return []
    const source = theme.fields.find(candidate => candidate.key === field.source)
    return [
      {
        ...field,
        options:
          source?.options.filter(option => typeof option.code === 'string' && selected.includes(option.code)) ?? [],
      },
    ]
  })
}

export function clearHidden(theme: Theme, value: AnswerValue): AnswerValue {
  const visible = new Set(visibleFields(theme, value).map(field => field.key))
  const result: AnswerValue = Object.fromEntries(Object.entries(value).filter(([key]) => visible.has(key)))
  if (
    typeof result['main_barrier'] === 'string' &&
    (!Array.isArray(result['barriers']) || !result['barriers'].includes(result['main_barrier']))
  ) {
    delete result['main_barrier']
  }
  return result
}
