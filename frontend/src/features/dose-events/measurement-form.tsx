import type { View } from '../../session/session'
import type { EventPayload, Quality } from './events'
import type { JSX } from '@solidjs/web'
import { createSignal, Show } from 'solid-js'
import * as v from 'valibot'
import { submitSource } from '../../api/source'
import { inputDateTime, localDateTime } from '../../date/date'
import { notice } from '../../notice/notice'
import { captureView } from '../../session/session'
import { StatusBadge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { IssueList } from '../../ui/data-display'
import { Disclosure } from '../../ui/disclosure'
import { Field, Input } from '../../ui/form'
import { Text } from '../../ui/typography'
import { qualitySchema } from './events'
import { MeasurementEditor } from './measurement-editor'

export function MeasurementForm(): JSX.Element {
  let time!: HTMLInputElement
  let readPayload!: () => EventPayload
  const [result, setResult] = createSignal<{ quality: Quality } | null>(null)
  async function saveMeasurement(view: View, patientId: string): Promise<void> {
    const body = { occurred_at: inputDateTime(time.value), payload: readPayload() }
    const saved = await submitSource(
      `/patients/${encodeURIComponent(patientId)}/measurements`,
      'measurement',
      body,
      v.looseObject({ quality: qualitySchema }),
      view,
    )
    setResult(saved)
    notice('指标记录已保存，缺失没有补为0；可重新读取记录并刷新报告。')
  }
  return (
    <Disclosure summary="填写指标或缺失记录">
      <Field label="采样时间（北京时间）">
        <Input ref={time} type="datetime-local" value={localDateTime()} />
      </Field>
      <Text>保留原值和原单位；未知单位会交技术复核。此处不采集心理量表或判断医学危险阈值。</Text>
      <MeasurementEditor
        ref={read => {
          readPayload = read
        }}
      />
      <Show when={captureView().patientId} keyed>
        {patientId => (
          <Button variant="primary" onAction={view => saveMeasurement(view, patientId)}>
            保存指标记录
          </Button>
        )}
      </Show>
      <div aria-live="polite">
        <Show when={result()}>
          {saved => (
            <>
              <p class="text-sm/6">
                已保存；
                <StatusBadge status={saved().quality.status} />。
              </p>
              <IssueList issues={saved().quality.issues} />
            </>
          )}
        </Show>
      </div>
    </Disclosure>
  )
}
