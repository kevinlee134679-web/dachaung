import type { View } from '../../session/session'
import type { DoseSlot, RecordEvent } from './events'
import type { JSX } from '@solidjs/web'
import { createSignal, Show } from 'solid-js'
import { submitSource } from '../../api/source'
import { inputDateTime, localDateTime } from '../../date/date'
import { notice } from '../../notice/notice'
import { captureView, own } from '../../session/session'
import { StatusBadge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Disclosure } from '../../ui/disclosure'
import { Field, Input } from '../../ui/form'
import { Text } from '../../ui/typography'
import { evidenceLabels } from './event-card'
import { recordEventSchema } from './events'
import { ReportSelect } from './report-select'

export function MedicationReportForm(props: { slot?: DoseSlot | null }): JSX.Element {
  let time!: HTMLInputElement
  let status!: HTMLSelectElement
  let notes!: HTMLInputElement
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
  }
  return (
    <Disclosure summary={own() ? '记录本人的服药情况' : '记录家人报告'}>
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
        ref={element => {
          status = element
        }}
      />
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
            <p class="text-sm/6">
              已保存：{evidenceLabels[saved().evidence_type ?? '']}；
              <StatusBadge status={saved().quality.status} />；
              <StatusBadge status={saved().link_status} />。
            </p>
          )}
        </Show>
      </div>
    </Disclosure>
  )
}
