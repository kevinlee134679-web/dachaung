import * as v from 'valibot'

type QuestionId = 'Q1' | 'Q2' | 'Q3' | 'Q4' | 'Q5' | 'Q6' | 'Q7' | 'Q8'

interface PrimaryAnswer {
  primary: string | null
  additional: string[]
}

interface OtherAnswer {
  selected: string[]
  top_ranked: string[]
  other_text: string | null
}

interface ChoiceAnswer {
  choice: string | null
}

interface ConcernAnswer {
  selected: string[]
  top_concerns: string[]
  intensity: number | null
}

interface FrequencyAnswer {
  selected: string[]
  frequency: string | null
}

interface ConfidenceAnswer {
  confidence_level: number | null
}

interface SelectionAnswer {
  selected: string[]
}

interface RankedAnswer {
  selected: string[]
  ranked: string[]
}

// the field set tells the questions apart, matching the backend's validate_answers
type AnswerValue =
  | PrimaryAnswer
  | OtherAnswer
  | ChoiceAnswer
  | ConcernAnswer
  | FrequencyAnswer
  | ConfidenceAnswer
  | SelectionAnswer
  | RankedAnswer

interface Ranking {
  selected: string[]
  ranked: string[]
}

interface Answer {
  state: string
  value: AnswerValue | null
}

export interface Response {
  response_id: string
  status: string
  answers: Record<QuestionId, Answer>
  meta: { revision: number }
}

export interface Theme {
  question_id: QuestionId
  prompt: string
  options: { code: string; label: string }[]
}

export interface Definition {
  purpose: string
  version: string
  themes: Theme[]
}

function answerSchema(value: v.GenericSchema<unknown, AnswerValue>) {
  return v.looseObject({
    state: v.picklist(['answered', 'unknown', 'not_applicable', 'not_answered']),
    value: v.nullable(value),
  })
}

export const responseSchema: v.GenericSchema<unknown, Response> = v.looseObject({
  response_id: v.string(),
  status: v.string(),
  answers: v.looseObject({
    Q1: answerSchema(v.looseObject({ primary: v.string(), additional: v.array(v.string()) })),
    Q2: answerSchema(
      v.looseObject({
        selected: v.array(v.string()),
        top_ranked: v.array(v.string()),
        other_text: v.nullable(v.string()),
      }),
    ),
    Q3: answerSchema(v.looseObject({ choice: v.string() })),
    Q4: answerSchema(
      v.looseObject({
        selected: v.array(v.string()),
        top_concerns: v.array(v.string()),
        intensity: v.nullable(v.number()),
      }),
    ),
    Q5: answerSchema(
      v.looseObject({
        selected: v.array(v.string()),
        frequency: v.nullable(v.picklist(['never', 'occasionally', 'often'])),
      }),
    ),
    Q6: answerSchema(v.looseObject({ confidence_level: v.number() })),
    Q7: answerSchema(v.looseObject({ selected: v.array(v.string()) })),
    Q8: answerSchema(v.looseObject({ selected: v.array(v.string()), ranked: v.array(v.string()) })),
  }),
  meta: v.looseObject({ revision: v.number() }),
})

export const definitionSchema: v.GenericSchema<unknown, Definition> = v.looseObject({
  purpose: v.string(),
  version: v.string(),
  themes: v.array(
    v.looseObject({
      question_id: v.picklist(['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8']),
      prompt: v.string(),
      options: v.array(v.looseObject({ code: v.string(), label: v.string() })),
    }),
  ),
})

export interface Question {
  response: Response
  index: number
}

export function answerDefault(question: QuestionId): AnswerValue {
  switch (question) {
    case 'Q1':
      return { primary: null, additional: [] }
    case 'Q2':
      return { selected: [], top_ranked: [], other_text: null }
    case 'Q3':
      return { choice: null }
    case 'Q4':
      return { selected: [], top_concerns: [], intensity: null }
    case 'Q5':
      return { selected: [], frequency: null }
    case 'Q6':
      return { confidence_level: null }
    case 'Q7':
      return { selected: [] }
    case 'Q8':
    default:
      return { selected: [], ranked: [] }
  }
}

export function normalizeAnswer(value: AnswerValue): AnswerValue {
  if ('primary' in value) value.additional = value.additional.filter(item => item !== value.primary)
  if ('other_text' in value && !value.selected.includes('other')) value.other_text = null
  return value
}

export function primaryAnswer(value: AnswerValue): PrimaryAnswer | null {
  return 'primary' in value ? value : null
}

export function answerWithOther(value: AnswerValue): OtherAnswer | null {
  return 'other_text' in value && value.selected.includes('other') ? value : null
}

export function concernAnswer(value: AnswerValue): ConcernAnswer | null {
  return 'intensity' in value ? value : null
}

export function frequencyAnswer(value: AnswerValue): FrequencyAnswer | null {
  return 'frequency' in value ? value : null
}

export function rankingOf(value: AnswerValue): Ranking | null {
  if ('top_ranked' in value) return { selected: value.selected, ranked: value.top_ranked }
  if ('top_concerns' in value) return { selected: value.selected, ranked: value.top_concerns }
  if ('ranked' in value) return { selected: value.selected, ranked: value.ranked }
  return null
}
