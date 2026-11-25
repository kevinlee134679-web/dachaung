import * as v from 'valibot'

export interface Draft {
  draft_id: string
  status: string
  source_file_ids: string[]
  entries: Entry[]
  content_revision: number
  meta: { revision: number; updated_at: string }
  return_reason: string | null
  formal_plan: { plan_id: string; plan_version: number } | null
}

export interface DraftData {
  drafts: Draft[]
  meds: Medication[]
  files: SourceFile[]
  plans: Plan[]
}

export interface Editor {
  draft: Draft | null
  entries: Entry[]
}

export interface Entry {
  draft_entry_id: string
  medication_id: string
  dose_value: string | null
  dose_unit: string | null
  start_date: string | null
  end_date: string | null
  schedule: { kind: string; times: string[]; weekdays: number[] } | null
  meal_requirement: string | null
  medical_notes: string | null
  strict_timing: boolean | null
  min_interval_minutes: number | null
  source_file_ids: string[]
}

export interface Medication {
  medication_id: string
  name: string
}

export interface SourceFile {
  file_id: string
  original_name: string
  media_type: string
}

export interface Plan {
  plan_id: string
  plan_version: number
  effective_from: string
}

export const medicationSchema: v.GenericSchema<unknown, Medication> = v.looseObject({
  medication_id: v.string(),
  name: v.string(),
})

export const sourceFileSchema: v.GenericSchema<unknown, SourceFile> = v.looseObject({
  file_id: v.string(),
  original_name: v.string(),
  media_type: v.string(),
})

const entryFields = {
  medication_id: v.string(),
  dose_value: v.nullable(v.string()),
  dose_unit: v.nullable(v.string()),
  start_date: v.nullable(v.string()),
  end_date: v.nullable(v.string()),
  schedule: v.nullable(
    v.looseObject({ kind: v.picklist(['daily', 'weekly']), times: v.array(v.string()), weekdays: v.array(v.number()) }),
  ),
  meal_requirement: v.nullable(v.string()),
  medical_notes: v.nullable(v.string()),
  strict_timing: v.nullable(v.boolean()),
  min_interval_minutes: v.nullable(v.number()),
  source_file_ids: v.array(v.string()),
}

const entrySchema = v.looseObject({ draft_entry_id: v.string(), ...entryFields })

export const draftSchema: v.GenericSchema<unknown, Draft> = v.looseObject({
  draft_id: v.string(),
  status: v.picklist(['editing', 'pending_confirmation', 'confirmed', 'returned']),
  source_file_ids: v.array(v.string()),
  entries: v.array(entrySchema),
  content_revision: v.number(),
  meta: v.looseObject({ revision: v.number(), updated_at: v.string() }),
  return_reason: v.nullable(v.string()),
  formal_plan: v.nullable(v.looseObject({ plan_id: v.string(), plan_version: v.number() })),
})

export const planSchema: v.GenericSchema<unknown, Plan> = v.looseObject({
  plan_id: v.string(),
  plan_version: v.number(),
  effective_from: v.string(),
})

interface PlanVersion extends Plan {
  source_draft_id: string
  entries: Omit<Entry, 'draft_entry_id'>[]
}

export const planVersionSchema: v.GenericSchema<unknown, PlanVersion> = v.looseObject({
  plan_id: v.string(),
  plan_version: v.number(),
  effective_from: v.string(),
  source_draft_id: v.string(),
  entries: v.array(v.object(entryFields)),
})

export function newEntry(medicationId: string): Entry {
  return {
    draft_entry_id: crypto.randomUUID(),
    medication_id: medicationId,
    dose_value: null,
    dose_unit: null,
    start_date: null,
    end_date: null,
    schedule: null,
    meal_requirement: null,
    medical_notes: null,
    strict_timing: null,
    min_interval_minutes: null,
    source_file_ids: [],
  }
}
