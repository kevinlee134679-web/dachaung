import type { View } from '../../session/session'
import type { Draft, Entry, Medication, Plan } from './drafts'
import type { RecognizedMedication } from './recognition-panel'
import { all, api } from '../../api/api'
import { today } from '../../date/date'
import { navigate } from '../../session/navigation'
import { own, patientPath, referenceKey, scope } from '../../session/session'
import {
  confirmPlan,
  draftBody,
  draftSchema,
  medicationSchema,
  newEntry,
  planSchema,
  planVersionSchema,
} from './drafts'

const defaultTimes: Record<number, string[]> = {
  1: ['08:00'],
  2: ['08:00', '20:00'],
  3: ['08:00', '12:00', '18:00'],
  4: ['08:00', '12:00', '16:00', '20:00'],
}

export interface MedicationList {
  meds: Medication[]
  draft: Draft | null
  plan: Plan | null
  entries: Entry[]
}

export async function loadMedicationList(view: View): Promise<MedicationList> {
  const meds = await all(patientPath('/medications'), medicationSchema, view)
  const drafts = await all(patientPath('/drafts'), draftSchema, view)
  const plans = await all(patientPath('/plans'), planSchema, view)
  const draft = drafts.sort((a, b) => b.meta.updated_at.localeCompare(a.meta.updated_at))[0] ?? null
  const plan =
    plans.sort((a, b) => b.effective_from.localeCompare(a.effective_from) || b.plan_version - a.plan_version)[0] ?? null
  let entries: Entry[]
  if (draft && ['editing', 'returned'].includes(draft.status)) {
    entries = structuredClone(draft.entries)
  } else if (plan) {
    const version = await api(
      `/plans/${encodeURIComponent(plan.plan_id)}/versions/${plan.plan_version}`,
      planVersionSchema,
      'GET',
      null,
      view,
    )
    entries = version.entries.map(entry => ({ ...entry, draft_entry_id: crypto.randomUUID() }))
  } else {
    entries = [{ ...newEntry(''), start_date: today() }]
  }
  return { meds, draft, plan, entries }
}

export async function saveMedicationList(
  view: View,
  loaded: MedicationList,
  entries: Entry[],
): Promise<{ draft: Draft; plan: Plan }> {
  draftBody(entries, true)
  // created ids are written back so a retry after a later failure does not create the medicine twice
  for (const entry of entries) {
    if (entry.new_medication_name !== undefined) {
      const medication = await api(
        patientPath('/medications'),
        medicationSchema,
        'POST',
        { name: entry.new_medication_name.trim(), notes: null },
        view,
      )
      entry.medication_id = medication.medication_id
      delete entry.new_medication_name
    }
  }
  const body = draftBody(entries, true)
  const previous = loaded.draft && ['editing', 'returned'].includes(loaded.draft.status) ? loaded.draft : null
  const draft = await api(
    previous ? `/drafts/${encodeURIComponent(previous.draft_id)}` : patientPath('/drafts'),
    draftSchema,
    previous ? 'PUT' : 'POST',
    previous ? { ...body, expected_revision: previous.meta.revision } : body,
    view,
  )
  const submitted = await api(
    `/drafts/${encodeURIComponent(draft.draft_id)}/submit`,
    draftSchema,
    'POST',
    { expected_revision: draft.meta.revision, content_revision: draft.content_revision },
    view,
  )
  const plan = await confirmPlan(view, submitted, loaded.plan)
  return { draft: submitted, plan }
}

export function entryFromRecognition(med: RecognizedMedication, meds: Medication[], date: string): Entry {
  const match = meds.find(item => item.name === med.name)
  const end =
    med.duration_days === null
      ? null
      : new Date(Date.parse(`${date}T00:00:00Z`) + (med.duration_days - 1) * 86400000).toISOString().slice(0, 10)
  return {
    ...newEntry(match?.medication_id ?? ''),
    ...(match ? {} : { new_medication_name: med.name }),
    dose_value: med.dose_value,
    dose_unit: med.dose_unit,
    schedule: {
      kind: 'daily',
      weekdays: [],
      times: med.times.length ? med.times : (defaultTimes[med.daily_count ?? 0] ?? []),
    },
    start_date: date,
    end_date: end,
  }
}

export function canManageMedicationList(): boolean {
  return own() && ['medication:read', 'drafts:read', 'drafts:write', 'drafts:submit', 'plan:read'].every(scope)
}

export function openMedicationList(medicationId: string): void {
  sessionStorage.setItem(referenceKey('medication-list-medication'), medicationId)
  navigate('medication', 'medication-list')
}
