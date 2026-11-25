import type { View } from '../../session/session'
import type { DoseSlot, RecordEvent } from './events'
import type { JSX } from '@solidjs/web'
import { createSignal, For, Show } from 'solid-js'
import { submitSource } from '../../api/source'
import { inputDateTime, localDateTime } from '../../date/date'
import { notice } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import { captureView, own, scope } from '../../session/session'
import { StatusBadge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Disclosure } from '../../ui/disclosure'
import { Field, Input, Select } from '../../ui/form'
import { missedReasonLabels } from '../../ui/labels'
import { Text } from '../../ui/typography'
import { evidenceLabels } from './event-card'
import { recordEventSchema } from './events'
import { ReportSelect } from './report-select'

export { submitSource } from '../../api/source'

export function MedicationReportForm(props: {
  slot?: DoseSlot | null
  onSaved?: ((view: View) => Promise<void>) | undefined
}): JSX.Element {
  let time!: HTMLInputElement
  let status!: HTMLSelectElement
  let notes!: HTMLInputElement
  let reason!: HTMLSelectElement
  const [selectedStatus, setSelectedStatus] = createSignal('taken')
  const [result, setResult] = createSignal<RecordEvent | null>(null)
  async function saveReport(view: View, patientId: string): Promise<void> {
    const slot = props.slot
    const body = {
      occurred_at: inputDateTime(time.value),
      reported_status: status.value,
      medication_id: slot?.medication_id != null && slot.medication_id !== '' ? slot.medication_id : null,
      dose_slot_id: slot?.dose_slot_id != null && slot.dose_slot_id !== '' ? slot.dose_slot_id : null,
      plan_ref: slot ? { plan_id: slot.plan_id, plan_version: slot.plan_version } : null,
      raw_text: notes.value || null,
      missed_reason: selectedStatus() === 'not_taken' ? reason.value || null : null,
    }
    const saved = await submitSource(
      `/patients/${encodeURIComponent(patientId)}/medication-events`,
      'medication',
      body,
      recordEventSchema,
      view,
    )
    setResult(saved)
    notice('报告已保存。统计与摘要如已过期，请在用药报告中明确刷新。')
    if (props.onSaved) await props.onSaved(view)
  }
  return (
    <Disclosure summary="补记服药情况">
      <Text>
        {own()
          ? '这将保存本人的明确报告，不是客观吞服验证。'
          : '当前是家人协助。任何选项都保存为家人报告，不计入本人确认已服。'}
      </Text>
      <Field label="报告发生时间（北京时间，不等同于吞服时间）">
        <Input ref={time} type="datetime-local" value={localDateTime()} />
      </Field>
      <ReportSelect
        label="报告内容"
        onChange={value => {
          setSelectedStatus(value)
        }}
        ref={element => {
          status = element
        }}
      />
      <Show when={selectedStatus() === 'not_taken'}>
        <Field label="未服原因">
          <Select ref={reason}>
            <option value="">未填写</option>
            <For each={Object.entries(missedReasonLabels)}>
              {([value, label]) => <option value={value}>{label}</option>}
            </For>
          </Select>
        </Field>
      </Show>
      <Field label="补充原话（可空）">
        <Input ref={notes} />
      </Field>
      <Show when={captureView().patientId} keyed>
        {patientId => (
          <Button variant="primary" onAction={view => saveReport(view, patientId)}>
            明确保存服药报告
          </Button>
        )}
      </Show>
      {!props.slot && (
        <Text>此表没有明确计划时段引用，系统不会按附近时间猜配。可在今日安排选择准确时段，或交受控复核。</Text>
      )}
      <div aria-live="polite">
        <Show when={result()}>
          {saved => (
            <div class="space-y-2">
              <p class="text-sm/6">
                已保存：{evidenceLabels[saved().evidence_type ?? '']}；
                <StatusBadge status={saved().quality.status} />；
                <StatusBadge status={saved().link_status} />。
              </p>
              <Show when={props.slot && scope('records:read')}>
                <Button onAction={() => navigate('medication', 'overview')}>查看服药记录</Button>
              </Show>
            </div>
          )}
        </Show>
      </div>
    </Disclosure>
  )
}
