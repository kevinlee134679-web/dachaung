import type { View } from '../../session/session'
import * as v from 'valibot'
import { api } from '../../api/api'
import { patientPath } from '../../session/session'

export interface Profile {
  profile_id: string
  patient_id: string
  response_id: string
  questionnaire_version: string
  status: string
  cas_observed: { status: string; value: number | null; missing_items: string[]; reasons: string[] }
  cas: { status: string; value: number | null; model_version: string | null; reason: string | null }
  cards: {
    question_id: string
    title: string
    answers: string[]
    level: 'good' | 'neutral' | 'attention'
    note: string
  }[]
  factors: unknown[]
  assessment_method_version: string
  generated_at: string
  meta: { revision: number }
}

interface LatestSubmission {
  response_id: string
  submitted_at: string
  profile: Profile | null
}

export const profileSchema: v.GenericSchema<unknown, Profile> = v.looseObject({
  profile_id: v.string(),
  patient_id: v.string(),
  response_id: v.string(),
  questionnaire_version: v.string(),
  status: v.string(),
  cas_observed: v.object({
    status: v.string(),
    value: v.nullable(v.number()),
    missing_items: v.array(v.string()),
    reasons: v.array(v.string()),
  }),
  cas: v.object({
    status: v.string(),
    value: v.nullable(v.number()),
    model_version: v.nullable(v.string()),
    reason: v.nullable(v.string()),
  }),
  cards: v.array(
    v.object({
      question_id: v.string(),
      title: v.string(),
      answers: v.array(v.string()),
      level: v.picklist(['good', 'neutral', 'attention']),
      note: v.string(),
    }),
  ),
  factors: v.array(v.unknown()),
  assessment_method_version: v.string(),
  generated_at: v.string(),
  meta: v.looseObject({ revision: v.number() }),
})

const submissionSchema: v.GenericSchema<unknown, LatestSubmission> = v.object({
  response_id: v.string(),
  submitted_at: v.string(),
  profile: v.nullable(profileSchema),
})

export function generateProfile(responseId: string, view: View): Promise<Profile> {
  return api(patientPath('/profiles'), profileSchema, 'POST', { response_id: responseId }, view)
}

export function loadLatestSubmission(view: View): Promise<LatestSubmission> {
  return api(patientPath('/questionnaire-responses/latest-submitted'), submissionSchema, 'GET', null, view)
}
