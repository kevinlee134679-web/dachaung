import type { RangeReader } from '../../../ui/range-controls'
import type { FeedbackProjection } from './feedback'
import type { JSX } from '@solidjs/web'
import { createSignal, Show } from 'solid-js'
import { api } from '../../../api/api'
import { rangeQuery } from '../../../api/query'
import { readGate } from '../../../session/read-gate'
import { patientPath } from '../../../session/session'
import { Button } from '../../../ui/button'
import { Disclosure } from '../../../ui/disclosure'
import { RangeControls } from '../../../ui/range-controls'
import { Text } from '../../../ui/typography'
import { feedbackProjectionSchema } from './feedback'
import { CFeedbackProjection } from './feedback-projection'

export function SupportFeedbackPanel(): JSX.Element {
  const begin = readGate()
  const [result, setResult] = createSignal<FeedbackProjection | null>(null)
  const [error, setError] = createSignal('')
  let range!: RangeReader
  return (
    <Disclosure summary="社会支持反馈来源">
      <RangeControls
        ref={value => {
          range = value
        }}
      />
      <Button
        onAction={async view => {
          const check = begin()
          const { window_start, window_end } = range.read()
          try {
            const data = await api(
              `${patientPath('/support-feedback')}?${rangeQuery({ window_start, window_end, limit: 100 })}`,
              feedbackProjectionSchema,
              'GET',
              null,
              view,
            )
            check()
            setResult(data)
            setError('')
          } catch (failure) {
            check()
            setResult(null)
            setError(failure instanceof Error ? failure.message : '')
          }
        }}
      >
        读取本人社会支持反馈
      </Button>
      <div aria-live="polite">
        <Show when={error()}>
          <p class="text-sm/6 text-red-600 dark:text-red-400">{error()}</p>
        </Show>
        <Show when={result()}>
          {data => (
            <>
              <CFeedbackProjection source={data()} />
              <Show when={data().records.length === 100}>
                <Text>如需查看其他记录，请缩小日期范围。</Text>
              </Show>
            </>
          )}
        </Show>
      </div>
    </Disclosure>
  )
}
