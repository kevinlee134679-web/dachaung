import type { Entry, Medication } from './drafts'
import type { JSX } from '@solidjs/web'
import { For, untrack } from 'solid-js'
import { Button } from '../../ui/button'
import { Checkbox, Field, Fieldset, Input, Select } from '../../ui/form'

export function EntryEditor(props: {
  entry: Entry
  index: number
  meds: Medication[]
  removable: boolean
  remove: () => void
}): JSX.Element {
  let kind!: HTMLSelectElement
  let times!: HTMLInputElement
  const weekdays: HTMLInputElement[] = []
  const entry = untrack(() => props.entry)
  const selectedWeekdays = entry.schedule?.weekdays ?? []
  function updateSchedule(): void {
    entry.schedule = times.value
      ? {
          kind: kind.value,
          times: times.value
            .split(/[,，]/)
            .map(value => value.trim())
            .filter(Boolean),
          weekdays:
            kind.value === 'daily' ? [] : weekdays.flatMap((input, index) => (input.checked ? [index + 1] : [])),
        }
      : null
  }
  return (
    <Fieldset legend={`药品条目 ${props.index + 1}`}>
      <div class="grid gap-4 md:grid-cols-2">
        <Field label="药品资料">
          <Select
            value={entry.medication_id}
            onChange={event => {
              entry.medication_id = event.currentTarget.value
            }}
          >
            <For each={props.meds}>{med => <option value={med.medication_id}>{med.name}</option>}</For>
          </Select>
        </Field>
        <Field label="每次剂量（原资料数值）">
          <Input
            value={entry.dose_value ?? ''}
            onInput={event => {
              entry.dose_value = event.currentTarget.value || null
            }}
          />
        </Field>
        <Field label="剂量单位（原资料）">
          <Input
            value={entry.dose_unit ?? ''}
            onInput={event => {
              entry.dose_unit = event.currentTarget.value || null
            }}
          />
        </Field>
        <Field label="开始日期">
          <Input
            type="date"
            value={entry.start_date ?? ''}
            onInput={event => {
              entry.start_date = event.currentTarget.value || null
            }}
          />
        </Field>
        <Field label="结束日期（未知可空）">
          <Input
            type="date"
            value={entry.end_date ?? ''}
            onInput={event => {
              entry.end_date = event.currentTarget.value || null
            }}
          />
        </Field>
        <Field label="固定频次">
          <Select ref={kind} value={entry.schedule?.kind ?? 'daily'} onChange={updateSchedule}>
            <option value="daily">每天</option>
            <option value="weekly">每周指定日期</option>
          </Select>
        </Field>
        <Field label="每天时刻（HH:mm，多个用逗号分隔）">
          <Input ref={times} value={entry.schedule?.times.join(',') ?? ''} onInput={updateSchedule} />
        </Field>
        <div>
          <span class="text-sm/6 font-medium text-zinc-950 dark:text-white">每周日期（每天安排不勾选）</span>
          <div class="flex flex-wrap gap-3">
            <For each={['一', '二', '三', '四', '五', '六', '日']}>
              {(day, index) => (
                <Checkbox
                  ref={element => {
                    weekdays[index()] = element
                  }}
                  label={day}
                  checked={selectedWeekdays.includes(index() + 1)}
                  onChange={updateSchedule}
                />
              )}
            </For>
          </div>
        </div>
        <Field label="餐前、餐后等要求（未知可空）">
          <Input
            value={entry.meal_requirement ?? ''}
            onInput={event => {
              entry.meal_requirement = event.currentTarget.value || null
            }}
          />
        </Field>
        <Field label="特殊医嘱原文（未知可空）">
          <Input
            value={entry.medical_notes ?? ''}
            onInput={event => {
              entry.medical_notes = event.currentTarget.value || null
            }}
          />
        </Field>
        <Field label="是否明确严格时间要求">
          <Select
            value={entry.strict_timing === null ? '' : String(entry.strict_timing)}
            onChange={event => {
              entry.strict_timing = event.currentTarget.value === '' ? null : event.currentTarget.value === 'true'
            }}
          >
            <option value="">未知</option>
            <option value="true">是</option>
            <option value="false">原资料明确无严格时间要求</option>
          </Select>
        </Field>
        <Field label="原医嘱最小间隔（分钟，未知可空）">
          <Input
            type="number"
            value={entry.min_interval_minutes ?? ''}
            onInput={event => {
              entry.min_interval_minutes = event.currentTarget.value ? Number(event.currentTarget.value) : null
            }}
          />
        </Field>
      </div>
      <Button variant="plain" disabled={!props.removable} onAction={props.remove}>
        移除此条目
      </Button>
    </Fieldset>
  )
}
