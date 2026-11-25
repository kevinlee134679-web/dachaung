import type { View } from '../../session/session'
import type { SourceFile } from '../medical-files/files'
import * as v from 'valibot'
import { api } from '../../api/api'
import { patientPath } from '../../session/session'

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
  new_medication_name?: string
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

export interface Plan {
  plan_id: string
  plan_version: number
  effective_from: string
}

export const medicationSchema: v.GenericSchema<unknown, Medication> = v.looseObject({
  medication_id: v.string(),
  name: v.string(),
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

function checkedSchedule(schedule: Entry['schedule'], complete = false): Entry['schedule'] {
  const times = schedule?.times.filter(Boolean) ?? []
  if (!schedule || !times.length) return null
  if (!complete) return { ...schedule, times: [...times].sort() }
  if (!['daily', 'weekly'].includes(schedule.kind)) throw new Error('请核对原资料并选择固定频次。')
  if (times.length !== schedule.times.length) throw new Error('请填写或移除空白服药时段。')
  if (new Set(times).size !== times.length) throw new Error('同一种药的服药时段重复，请核对时间。')
  if (schedule.kind === 'weekly' && !schedule.weekdays.length) throw new Error('请为每周安排选择至少一个服药日。')
  return { kind: schedule.kind, weekdays: schedule.weekdays, times: times.sort() }
}

export function isBlank(entry: Entry): boolean {
  return (
    entry.medication_id === '' &&
    (entry.new_medication_name ?? '') === '' &&
    entry.dose_value === null &&
    entry.dose_unit === null &&
    entry.schedule === null &&
    entry.end_date === null &&
    entry.meal_requirement === null &&
    entry.medical_notes === null &&
    entry.strict_timing === null &&
    entry.min_interval_minutes === null &&
    entry.source_file_ids.length === 0
  )
}

export function draftBody(entries: Entry[], complete: boolean): { source_file_ids: string[]; entries: Entry[] } {
  const prepared = entries.map((entry, index) => {
    const heading = `药品条目 ${index + 1}`
    if (complete && !entry.medication_id && (entry.new_medication_name ?? '').trim() === '')
      throw new Error(`${heading}：请选择药品或填写新药品名称。`)
    const schedule = checkedSchedule(entry.schedule, complete)
    if (
      complete &&
      entry.dose_value !== null &&
      (!/^\d+(?:\.\d+)?$/.test(entry.dose_value) || Number(entry.dose_value) <= 0)
    ) {
      throw new Error(`${heading}：请填写大于零的数值剂量。`)
    }
    if (complete && entry.start_date !== null && entry.end_date !== null && entry.end_date < entry.start_date)
      throw new Error(`${heading}：结束日期早于开始日期。`)
    if (
      complete &&
      (entry.dose_value === null || entry.dose_unit === null || entry.start_date === null || schedule === null)
    ) {
      throw new Error(`${heading}：请补齐每次剂量、单位、开始日期和服药时间。`)
    }
    return { ...entry, schedule }
  })
  return { source_file_ids: [...new Set(prepared.flatMap(entry => entry.source_file_ids))], entries: prepared }
}

export function confirmPlan(
  view: View,
  draft: Draft,
  plan: Plan | null,
  effectiveFrom: string = new Date().toISOString(),
): Promise<Plan> {
  return api(
    patientPath('/plan-confirmations'),
    planSchema,
    'POST',
    {
      draft_id: draft.draft_id,
      draft_revision: draft.content_revision,
      existing_plan_id: plan?.plan_id ?? null,
      expected_plan_version: plan?.plan_version ?? null,
      effective_from: effectiveFrom,
      confirmed: true,
    },
    view,
  )
}
