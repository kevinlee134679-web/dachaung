import type { Entry, Medication } from './drafts'
import type { JSX } from '@solidjs/web'
import { createSignal, For, Show, untrack } from 'solid-js'
import { Button } from '../../ui/button'
import { Disclosure } from '../../ui/disclosure'
import { Field, Fieldset, Input, Select } from '../../ui/form'
import { ScheduleFields } from './schedule-fields'

export function EntryEditor(props: {
  entry: Entry
  index: number
  meds: Medication[]
  allowNew?: boolean
  removable: boolean
  remove: () => void
}): JSX.Element {
  const entry = untrack(() => props.entry)
  const [selected, setSelected] = createSignal(entry.new_medication_name !== undefined ? 'new' : entry.medication_id)

  function select(id: string): void {
    entry.medication_id = id === 'new' ? '' : id
    if (id === 'new') entry.new_medication_name = ''
    else delete entry.new_medication_name
    setSelected(id)
  }

  return (
    <Fieldset legend={`药品条目 ${props.index + 1}`}>
      <div class="grid gap-4 md:grid-cols-2">
        <Field label="选择已有药品">
          <Select value={selected()} onChange={event => select(event.currentTarget.value)}>
            <option value="">请选择药品</option>
            <For each={props.meds}>{med => <option value={med.medication_id}>{med.name}</option>}</For>
            <Show when={props.allowNew}>
              <option value="new">新增药品…</option>
            </Show>
          </Select>
        </Field>
        <Show when={selected() === 'new'}>
          <Field label="新药品名称">
            <Input
              value={entry.new_medication_name ?? ''}
              onInput={event => {
                entry.new_medication_name = event.currentTarget.value
              }}
            />
          </Field>
        </Show>
        <Field label="每次剂量（原资料数值）">
          <Input
            value={entry.dose_value ?? ''}
            inputmode="decimal"
            onInput={event => {
              entry.dose_value = event.currentTarget.value.trim() || null
            }}
          />
        </Field>
        <Field label="剂量单位（原资料）">
          <Input
            value={entry.dose_unit ?? ''}
            onInput={event => {
              entry.dose_unit = event.currentTarget.value.trim() || null
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
      </div>
      <ScheduleFields
        schedule={entry.schedule}
        requireKind={entry.source_file_ids.length > 0}
        onChange={schedule => {
          entry.schedule = schedule
        }}
      />
      <Field label="餐前、餐后等要求（未知可空）">
        <Input
          value={entry.meal_requirement ?? ''}
          onInput={event => {
            entry.meal_requirement = event.currentTarget.value || null
          }}
        />
      </Field>
      <Disclosure summary="其他原医嘱信息">
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
            min="1"
            value={entry.min_interval_minutes ?? ''}
            onInput={event => {
              entry.min_interval_minutes = event.currentTarget.value ? Number(event.currentTarget.value) : null
            }}
          />
        </Field>
      </Disclosure>
      <Button variant="plain" disabled={!props.removable} onAction={props.remove}>
        移除此条目
      </Button>
    </Fieldset>
  )
}
