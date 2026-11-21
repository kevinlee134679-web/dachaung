import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api } from '../../api/api'
import { today } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import {
  captureView,
  isCurrentView,
  own,
  patientPath,
  requireCurrentView,
  scope,
  ViewChanged,
} from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Field, Input, Select } from '../../ui/form'
import { Text } from '../../ui/typography'

const medicationSchema = v.looseObject({ medication_id: v.string(), name: v.string() })
const planSchema = v.looseObject({ plan_id: v.string(), plan_version: v.number(), effective_from: v.string() })
const entrySchema = v.looseObject({
  medication_name_snapshot: v.string(),
  dose_value: v.string(),
  dose_unit: v.string(),
  start_date: v.string(),
  end_date: v.nullable(v.string()),
  schedule: v.looseObject({ times: v.array(v.string()) }),
  meal_requirement: v.nullable(v.string()),
  medical_notes: v.nullable(v.string()),
  strict_timing: v.nullable(v.boolean()),
  min_interval_minutes: v.nullable(v.number()),
})
const planVersionSchema = v.looseObject({ entries: v.array(entrySchema) })
const draftSchema = v.looseObject({
  draft_id: v.string(),
  content_revision: v.number(),
  meta: v.looseObject({ revision: v.number() }),
})
type Medication = v.InferOutput<typeof medicationSchema>
type Plan = v.InferOutput<typeof planSchema>
interface Row {
  id: string
  name: string
  dose: string
  unit: string
  times: string
  meal: string
  startDate: string
  endDate: string | null
  medicalNotes: string | null
  strictTiming: boolean | null
  minIntervalMinutes: number | null
}

function newRow(): Row {
  return {
    id: crypto.randomUUID(),
    name: '',
    dose: '',
    unit: '',
    times: '',
    meal: '',
    startDate: today(),
    endDate: null,
    medicalNotes: null,
    strictTiming: null,
    minIntervalMinutes: null,
  }
}

export function MedicationListForm(props: { onConfirmed?: (view: View) => Promise<void> }): JSX.Element {
  const [rows, setRows] = createSignal<Row[]>([newRow()])
  const [medications, setMedications] = createSignal<Medication[]>([])
  const [loaded, setLoaded] = createSignal(false)
  const [plan, setPlan] = createSignal<Plan | null>(null)
  const allowed =
    own() && ['medication:read', 'medication:edit', 'drafts:write', 'drafts:submit', 'plan:read'].every(scope)

  function updateRow(row: Row, update: Partial<Row>): void {
    Object.assign(row, update)
  }

  async function load(view: View): Promise<void> {
    const meds = await all(patientPath('/medications'), medicationSchema, view)
    const plans = await all(patientPath('/plans'), planSchema, view)
    const latest = plans.sort(
      (a, b) => b.effective_from.localeCompare(a.effective_from) || b.plan_version - a.plan_version,
    )[0]
    if (latest) {
      const version = await api(
        `/plans/${encodeURIComponent(latest.plan_id)}/versions/${latest.plan_version}`,
        planVersionSchema,
        'GET',
        null,
        view,
      )
      requireCurrentView(view)
      setPlan(latest)
      setRows(
        version.entries.map(entry => ({
          id: crypto.randomUUID(),
          name: entry.medication_name_snapshot,
          dose: entry.dose_value,
          unit: entry.dose_unit,
          times: entry.schedule.times.join(', '),
          meal: entry.meal_requirement ?? '',
          startDate: entry.start_date,
          endDate: entry.end_date,
          medicalNotes: entry.medical_notes,
          strictTiming: entry.strict_timing,
          minIntervalMinutes: entry.min_interval_minutes,
        })),
      )
    }
    requireCurrentView(view)
    setMedications(meds)
    setLoaded(true)
  }

  async function confirm(view: View): Promise<void> {
    const currentRows = rows().map(row => ({ row, times: row.times.split(/[,，]/).map(time => time.trim()) }))
    if (!currentRows.length) throw new Error('请添加至少一种药。')
    for (const { row, times } of currentRows) {
      if (
        !row.name.trim() ||
        !/^\d+(?:\.\d+)?$/.test(row.dose) ||
        Number(row.dose) <= 0 ||
        !row.unit.trim() ||
        !row.startDate ||
        times.some(time => !/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(time))
      ) {
        throw new Error('请填写药名、剂量、单位、开始日期和正确的服药时间。')
      }
    }
    const meds = [...medications()]
    const entries = []
    for (const { row, times } of currentRows) {
      const name = row.name.trim()
      let medication = meds.find(item => item.name === name)
      if (!medication) {
        medication = await api(patientPath('/medications'), medicationSchema, 'POST', { name, notes: null }, view)
        meds.push(medication)
        setMedications([...meds])
      }
      entries.push({
        draft_entry_id: row.id,
        medication_id: medication.medication_id,
        dose_value: row.dose,
        dose_unit: row.unit.trim(),
        start_date: row.startDate,
        end_date: row.endDate,
        schedule: { kind: 'daily', times, weekdays: [] },
        meal_requirement: row.meal || null,
        medical_notes: row.medicalNotes,
        strict_timing: row.strictTiming,
        min_interval_minutes: row.minIntervalMinutes,
        source_file_ids: [],
      })
    }
    const draft = await api(patientPath('/drafts'), draftSchema, 'POST', { source_file_ids: [], entries }, view)
    await api(
      `/drafts/${encodeURIComponent(draft.draft_id)}/submit`,
      v.unknown(),
      'POST',
      { expected_revision: draft.meta.revision, content_revision: draft.content_revision },
      view,
    )
    const previous = plan()
    const effectiveFrom = new Date(
      Math.max(Date.now() + 60_000, previous ? Date.parse(previous.effective_from) + 1000 : 0),
    ).toISOString()
    await api(
      patientPath('/plan-confirmations'),
      v.unknown(),
      'POST',
      {
        draft_id: draft.draft_id,
        draft_revision: draft.content_revision,
        existing_plan_id: previous?.plan_id ?? null,
        expected_plan_version: previous?.plan_version ?? null,
        effective_from: effectiveFrom,
        confirmed: true,
      },
      view,
    )
    await load(view)
    requireCurrentView(view)
    notice('用药清单已确认，今日安排已更新。')
    if (props.onConfirmed) await props.onConfirmed(view)
  }

  onSettled(() => {
    if (!allowed) return
    const view = captureView()
    void load(view).catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })

  return (
    <Show when={allowed} fallback={<Text>当前未获用药清单管理权限。</Text>}>
      <Show when={loaded()}>
        <Card>
          <div class="space-y-6">
            <For each={rows()}>
              {row => (
                <div class="space-y-4 border-b border-zinc-950/10 pb-6 dark:border-white/10">
                  <div class="grid gap-4 sm:grid-cols-2">
                    <Field label="药名">
                      <Input value={row.name} onInput={event => updateRow(row, { name: event.currentTarget.value })} />
                    </Field>
                    <Field label="剂量">
                      <Input
                        type="number"
                        min="0"
                        step="any"
                        value={row.dose}
                        onInput={event => updateRow(row, { dose: event.currentTarget.value })}
                      />
                    </Field>
                    <Field label="单位">
                      <Input
                        placeholder="片、mg"
                        value={row.unit}
                        onInput={event => updateRow(row, { unit: event.currentTarget.value })}
                      />
                    </Field>
                    <Field label="服药时间" description="多个时间用逗号分开，例如 08:00, 20:00">
                      <Input
                        value={row.times}
                        onInput={event => updateRow(row, { times: event.currentTarget.value })}
                      />
                    </Field>
                    <Field label="用餐要求">
                      <Select value={row.meal} onChange={event => updateRow(row, { meal: event.currentTarget.value })}>
                        <option value="">不限</option>
                        <option value="餐前">餐前</option>
                        <option value="餐后">餐后</option>
                        <option value="随餐">随餐</option>
                      </Select>
                    </Field>
                    <Field label="开始日期">
                      <Input
                        type="date"
                        value={row.startDate}
                        onInput={event => updateRow(row, { startDate: event.currentTarget.value })}
                      />
                    </Field>
                  </div>
                  <Button
                    variant="plain"
                    onAction={() => setRows(current => current.filter(item => item.id !== row.id))}
                  >
                    移除
                  </Button>
                </div>
              )}
            </For>
            <div class="flex flex-wrap gap-3">
              <Button onAction={() => setRows(current => [...current, newRow()])}>添加一种药</Button>
              <Button variant="primary" onAction={confirm}>
                确认清单
              </Button>
            </div>
            <Text>这不是医院或药师审核，医嘱变更请先咨询专业人员。</Text>
          </div>
        </Card>
      </Show>
    </Show>
  )
}
