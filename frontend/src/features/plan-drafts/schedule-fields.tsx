import type { Entry } from './drafts'
import type { JSX } from '@solidjs/web'
import { createSignal, For, Show, untrack } from 'solid-js'
import { Button } from '../../ui/button'
import { Checkbox, Field, Fieldset, Input, Select } from '../../ui/form'

export function ScheduleFields(props: {
  schedule: Entry['schedule']
  requireKind: boolean
  onChange: (schedule: Entry['schedule']) => void
}): JSX.Element {
  const original = untrack(() => props.schedule)
  const [kind, setKind] = createSignal(original?.kind ?? untrack(() => (props.requireKind ? '' : 'daily')))
  const [weekdays, setWeekdays] = createSignal(original?.weekdays ?? [])
  const [slots, setSlots] = createSignal(
    (original && original.times.length > 0 ? original.times : ['']).map(value => ({ value })),
  )

  function updateSchedule(nextKind: string, days: number[], times: string[]): void {
    props.onChange({ kind: nextKind, weekdays: nextKind === 'weekly' ? days : [], times })
  }

  return (
    <Fieldset legend="服药时间">
      <Field label="固定频次">
        <Select
          value={kind()}
          onChange={event => {
            const next = event.currentTarget.value
            setKind(next)
            updateSchedule(
              next,
              weekdays(),
              slots().map(slot => slot.value),
            )
          }}
        >
          <Show when={props.requireKind}>
            <option value="">请选择固定频次</option>
          </Show>
          <option value="daily">每天</option>
          <option value="weekly">每周指定日期</option>
        </Select>
      </Field>
      <Show when={kind() === 'weekly'}>
        <div class="flex flex-wrap gap-3" role="group" aria-label="每周服药日">
          <For each={['一', '二', '三', '四', '五', '六', '日']}>
            {(day, index) => (
              <Checkbox
                label={`周${day}`}
                checked={weekdays().includes(index() + 1)}
                onChange={event => {
                  const weekday = index() + 1
                  const days = event.currentTarget.checked
                    ? [...weekdays(), weekday].sort((a, b) => a - b)
                    : weekdays().filter(item => item !== weekday)
                  setWeekdays(days)
                  updateSchedule(
                    kind(),
                    days,
                    slots().map(slot => slot.value),
                  )
                }}
              />
            )}
          </For>
        </div>
      </Show>
      <For each={slots()}>
        {(slot, index) => (
          <div class="flex flex-wrap items-end gap-2">
            <Field label={`服药时间 ${index() + 1}`}>
              <Input
                type="time"
                value={slot.value}
                onInput={event => {
                  slot.value = event.currentTarget.value
                  updateSchedule(
                    kind(),
                    weekdays(),
                    slots().map(item => item.value),
                  )
                }}
              />
            </Field>
            <Show when={slots().length > 1}>
              <Button
                variant="plain"
                aria-label={`移除时段 ${index() + 1}`}
                onAction={() => {
                  const next = slots().filter(item => item !== slot)
                  setSlots(next)
                  updateSchedule(
                    kind(),
                    weekdays(),
                    next.map(item => item.value),
                  )
                }}
              >
                移除时段
              </Button>
            </Show>
          </div>
        )}
      </For>
      <Button
        onAction={() => {
          const next = [...slots(), { value: '' }]
          setSlots(next)
          updateSchedule(
            kind(),
            weekdays(),
            next.map(item => item.value),
          )
        }}
      >
        添加时段
      </Button>
    </Fieldset>
  )
}
