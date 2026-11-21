import * as v from 'valibot'

export interface DoseSlot {
  dose_slot_id: string
  medication_id: string
  plan_id: string
  plan_version: number
  plan_entry_id: string
  scheduled_at: string
  status: string
}

export const doseSlotSchema: v.GenericSchema<unknown, DoseSlot> = v.looseObject({
  dose_slot_id: v.string(),
  medication_id: v.string(),
  plan_id: v.string(),
  plan_version: v.number(),
  plan_entry_id: v.string(),
  scheduled_at: v.string(),
  status: v.string(),
})

export interface Quality {
  status: 'pending_validation' | 'valid' | 'needs_review' | 'processing_failed'
  issues: { code: string; message: string }[]
}

export interface EventPayload {
  metric_code?: string | undefined
  value?: number | null | undefined
  unit?: string | null | undefined
  method_code?: string | null | undefined
  missing_reason?: string | null | undefined
  reported_status?: string | null | undefined
  observation?: string | null | undefined
  raw_text?: string | null | undefined
  dose_slot_id?: string | null | undefined
}

type ValidatedPayload = EventPayload &
  (
    | {
        metric_code: string
        value: number | null
        unit: string | null
        method_code: string | null
        missing_reason: string | null
      }
    | {
        reported_status: 'taken' | 'not_taken' | 'postponed' | 'unknown' | null
        observation: 'box_opened' | 'inferred_intake' | null
        dose_slot_id: string | null
        raw_text: string | null
      }
  )

export interface RecordEvent {
  event_id: string
  event_kind: 'medication' | 'measurement'
  source: string
  reporter_account_id: string | null
  evidence_type: string | null
  occurred_at: string
  received_at: string
  state: 'effective' | 'withdrawn'
  payload: ValidatedPayload
  quality: Quality
  link_status: string
  meta: { revision: number; is_simulated: boolean }
}

export interface Revision {
  revision: number
  change_kind: string
  created_at: string
  reason: string | null
  payload: ValidatedPayload
}

export const qualitySchema: v.GenericSchema<unknown, Quality> = v.looseObject({
  status: v.picklist(['pending_validation', 'valid', 'needs_review', 'processing_failed']),
  issues: v.array(v.looseObject({ code: v.string(), message: v.string() })),
})

const eventPayloadFieldsSchema = v.looseObject({
  metric_code: v.optional(v.string()),
  value: v.optional(v.nullable(v.number())),
  unit: v.optional(v.nullable(v.string())),
  method_code: v.optional(v.nullable(v.string())),
  missing_reason: v.optional(v.nullable(v.string())),
  reported_status: v.optional(v.nullable(v.string())),
  observation: v.optional(v.nullable(v.string())),
  raw_text: v.optional(v.nullable(v.string())),
  dose_slot_id: v.optional(v.nullable(v.string())),
})

const measurementPayloadSchema = v.looseObject({
  metric_code: v.string(),
  value: v.nullable(v.number()),
  unit: v.nullable(v.string()),
  method_code: v.nullable(v.string()),
  missing_reason: v.nullable(v.string()),
})

const evidencePayloadSchema = v.looseObject({
  reported_status: v.nullable(v.picklist(['taken', 'not_taken', 'postponed', 'unknown'])),
  observation: v.nullable(v.picklist(['box_opened', 'inferred_intake'])),
  dose_slot_id: v.nullable(v.string()),
  raw_text: v.nullable(v.string()),
})

const eventPayloadSchema = v.intersect([
  eventPayloadFieldsSchema,
  v.union([measurementPayloadSchema, evidencePayloadSchema]),
])

export const recordEventSchema: v.GenericSchema<unknown, RecordEvent> = v.looseObject({
  event_id: v.string(),
  event_kind: v.picklist(['medication', 'measurement']),
  source: v.string(),
  reporter_account_id: v.nullable(v.string()),
  evidence_type: v.nullable(v.string()),
  occurred_at: v.string(),
  received_at: v.string(),
  state: v.picklist(['effective', 'withdrawn']),
  payload: eventPayloadSchema,
  quality: qualitySchema,
  link_status: v.string(),
  meta: v.looseObject({ revision: v.number(), is_simulated: v.boolean() }),
})

export const revisionSchema: v.GenericSchema<unknown, Revision> = v.looseObject({
  revision: v.number(),
  change_kind: v.string(),
  created_at: v.string(),
  reason: v.nullable(v.string()),
  payload: eventPayloadSchema,
})
