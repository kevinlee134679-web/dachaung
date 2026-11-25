import type { View } from '../../session/session'
import type { Entry, Medication } from './drafts'
import type { JSX } from '@solidjs/web'
import { createSignal, For, Show, untrack } from 'solid-js'
import { Button } from '../../ui/button'
import { Disclosure } from '../../ui/disclosure'
import { Field, Fieldset, Input, Select } from '../../ui/form'
import { Text } from '../../ui/typography'
import { ScheduleFields } from './schedule-fields'

export function EntryEditor(props: {
  entry: Entry
  index: number
  meds: Medication[]
  suggestedName?: string | undefined
  addMedication?: ((view: View, name: string, notes: string | null) => Promise<Medication>) | undefined
  removable: boolean
  remove: () => void
}): JSX.Element {
  const entry = untrack(() => props.entry)
  const [selected, setSelected] = createSignal(entry.medication_id)
  const [search, setSearch] = createSignal('')
  const [adding, setAdding] = createSignal(false)
  let name!: HTMLInputElement
  let notes!: HTMLInputElement

  function select(id: string): void {
    entry.medication_id = id
    setSelected(id)
  }

  async function add(view: View): Promise<void> {
    if (!props.addMedication) return
    const value = name.value.trim()
    if (!value) throw new Error('请输入药品名称。')
    const result = await props.addMedication(view, value, notes.value.trim() || null)
    setSearch('')
    select(result.medication_id)
    setAdding(false)
  }

  return (
    <Fieldset legend={`药品条目 ${props.index + 1}`}>
      <Show when={props.suggestedName}>{suggestion => <Text>资料候选药名 · {suggestion()}</Text>}</Show>
      <Show when={entry.source_file_ids.length}>
        <Text>关联 {entry.source_file_ids.length} 份用药原资料</Text>
      </Show>
      <div class="grid gap-4 md:grid-cols-2">
        <Show when={props.meds.length > 5}>
          <Field label="搜索已有药品">
            <Input
              value={search()}
              onInput={event => {
                setSearch(event.currentTarget.value)
              }}
            />
          </Field>
        </Show>
        <Field label="选择已有药品">
          <Select value={selected()} onChange={event => select(event.currentTarget.value)}>
            <option value="">请选择药品</option>
            <For each={props.meds}>
              {med => (
                <Show
                  when={
                    med.medication_id === selected() ||
                    med.name.toLocaleLowerCase().includes(search().trim().toLocaleLowerCase())
                  }
                >
                  <option value={med.medication_id}>{med.name}</option>
                </Show>
              )}
            </For>
          </Select>
        </Field>
        <Show when={props.addMedication}>
          <div class="space-y-3 self-end">
            <Show when={adding()} fallback={<Button onAction={() => setAdding(true)}>添加新药品资料</Button>}>
              <Field label="新药品名称">
                <Input ref={name} value={props.suggestedName ?? ''} />
              </Field>
              <Field label="新药品备注（可空）">
                <Input ref={notes} />
              </Field>
              <div class="flex flex-wrap gap-2">
                <Button onAction={add}>保存并选用</Button>
                <Button variant="plain" onAction={() => setAdding(false)}>
                  取消添加
                </Button>
              </div>
            </Show>
          </div>
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
