import type { View } from '../../session/session'
import type { DoseSlot } from './events'
import type { JSX } from '@solidjs/web'
import { createSignal, For, Show } from 'solid-js'
import { notice } from '../../notice/notice'
import { patientPath } from '../../session/session'
import { Button } from '../../ui/button'
import { Field, Textarea } from '../../ui/form'
import { missedReasonLabels } from '../../ui/labels'
import { recordEventSchema } from './events'
import { submitSource } from './report-form'

export function SlotActions(props: { slot: DoseSlot; onSaved: () => void }): JSX.Element {
  const [open, setOpen] = createSignal(false)
  const [reason, setReason] = createSignal('')
  let notes!: HTMLTextAreaElement
  let occurredAt = ''
  async function save(view: View, status: 'taken' | 'not_taken' | 'unknown'): Promise<void> {
    occurredAt ||= new Date().toISOString()
    await submitSource(
      patientPath('/medication-events'),
      'medication',
      {
        occurred_at: occurredAt,
        reported_status: status,
        medication_id: props.slot.medication_id,
        dose_slot_id: props.slot.dose_slot_id,
        plan_ref: { plan_id: props.slot.plan_id, plan_version: props.slot.plan_version },
        raw_text: status === 'not_taken' ? notes.value || null : null,
        missed_reason: status === 'not_taken' ? reason() : null,
      },
      recordEventSchema,
      view,
    )
    occurredAt = ''
    setOpen(false)
    notice('服药情况已记录')
    props.onSaved()
  }
  return (
    <div class="space-y-3">
      <div class="flex flex-wrap gap-2">
        <Button variant="primary" onAction={view => save(view, 'taken')}>
          已服
        </Button>
        <Button onAction={() => setOpen(!open())}>没服</Button>
        <Button onAction={view => save(view, 'unknown')}>不确定</Button>
      </div>
      <Show when={open()}>
        <div class="space-y-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
          <fieldset class="space-y-2">
            <legend class="text-sm font-medium">请选择原因</legend>
            <For each={Object.entries(missedReasonLabels)}>
              {([value, label]) => (
                <label class="flex cursor-pointer items-center gap-3 rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700">
                  <input
                    type="radio"
                    name={`reason-${props.slot.dose_slot_id}`}
                    value={value}
                    checked={reason() === value}
                    onChange={() => {
                      setReason(value)
                    }}
                  />
                  {label}
                </label>
              )}
            </For>
          </fieldset>
          <Field label="备注（可选）">
            <Textarea ref={notes} />
          </Field>
          <Show when={reason()}>
            <Button variant="primary" onAction={view => save(view, 'not_taken')}>
              记录没服
            </Button>
          </Show>
        </div>
      </Show>
    </div>
  )
}
