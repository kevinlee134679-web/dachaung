import type { formalServiceStates } from '../dispatch'
import * as v from 'valibot'

export const feedbackDimensions: readonly (readonly [
  'support_needs' | 'support_acceptance' | 'intervention_effectiveness',
  string,
])[] = [
  ['support_needs', '支持需求变化'],
  ['support_acceptance', '支持接受程度'],
  ['intervention_effectiveness', '干预效果（本人描述）'],
] as const
export const participationLabels: Record<string, string> = {
  provided: '已自愿填写',
  declined: '明确不参与',
  unable: '无法填写',
}

export interface FeedbackInput {
  participation: string
  support_needs: string | null
  support_acceptance: string | null
  intervention_effectiveness: string | null
  willing_to_continue: boolean | null
  missing_reason: string | null
}
export interface Feedback extends FeedbackInput {
  feedback_id: string
  feedback_revision: number
  recorded_at: string
  supersedes_feedback_id: string | null
}
export interface PendingFeedback {
  clientId: string
  revision: number
  fingerprint: string
}
interface FeedbackRecord {
  record_id: string
  service_status: keyof typeof formalServiceStates
  source_version: string
  recorded_at: string
  is_simulated: boolean
  support_needs: string | null
  support_acceptance: string | null
  intervention_effectiveness: string | null
}
export interface FeedbackProjection {
  availability: string
  reason: string | null
  records: FeedbackRecord[]
}

export const feedbackSchema: v.GenericSchema<unknown, Feedback> = v.looseObject({
  participation: v.string(),
  support_needs: v.nullable(v.string()),
  support_acceptance: v.nullable(v.string()),
  intervention_effectiveness: v.nullable(v.string()),
  willing_to_continue: v.nullable(v.boolean()),
  missing_reason: v.nullable(v.string()),
  feedback_id: v.string(),
  feedback_revision: v.number(),
  recorded_at: v.string(),
  supersedes_feedback_id: v.nullable(v.string()),
})
export const feedbackProjectionSchema: v.GenericSchema<unknown, FeedbackProjection> = v.looseObject({
  availability: v.string(),
  reason: v.nullable(v.string()),
  records: v.array(
    v.looseObject({
      record_id: v.string(),
      service_status: v.picklist(['submitted', 'in_progress', 'completed', 'cancelled', 'failed']),
      source_version: v.string(),
      recorded_at: v.string(),
      is_simulated: v.boolean(),
      support_needs: v.nullable(v.string()),
      support_acceptance: v.nullable(v.string()),
      intervention_effectiveness: v.nullable(v.string()),
    }),
  ),
})

export function feedbackBody(
  entry: FeedbackInput,
  revision: number,
): FeedbackInput & { expected_feedback_revision: number } {
  return {
    expected_feedback_revision: revision,
    participation: entry.participation,
    support_needs: entry.support_needs,
    support_acceptance: entry.support_acceptance,
    intervention_effectiveness: entry.intervention_effectiveness,
    willing_to_continue: entry.willing_to_continue,
    missing_reason: entry.missing_reason,
  }
}
