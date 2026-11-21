import type { JSX } from '@solidjs/web'
import { onSettled } from 'solid-js'
import { inputDateTime, localDateTime, today } from '../date/date'
import { dataEnvironment } from '../session/session'
import { Field, Input } from './form'

export interface RangeValue {
  window_start: string
  window_end: string
  data_environment: 'real' | 'demo'
}

export interface RangeReader {
  read: () => RangeValue
}

export interface RangeControlsProps {
  ref: (reader: RangeReader) => void
}

export function RangeControls(props: RangeControlsProps): JSX.Element {
  const end = today()
  const start = new Date(new Date(`${end}T00:00:00+08:00`).getTime() - 6 * 86400000).toISOString()
  const endExclusive = new Date(new Date(`${end}T00:00:00+08:00`).getTime() + 86400000).toISOString()
  let startInput!: HTMLInputElement
  let endInput!: HTMLInputElement
  onSettled(() =>
    props.ref({
      read() {
        const window_start = inputDateTime(`${startInput.value}T00:00`)
        const window_end = inputDateTime(`${endInput.value}T00:00`)
        const days = (new Date(window_end).getTime() - new Date(window_start).getTime()) / 86400000
        if (!(days > 0 && days <= 31)) throw new Error('请选择大于0、最多31天的范围。')
        return { window_start, window_end, data_environment: dataEnvironment() }
      },
    }),
  )
  return (
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Field label="起始日期（北京时间）">
        <Input ref={startInput} type="date" value={localDateTime(start).slice(0, 10)} />
      </Field>
      <Field label="结束日期（不含当日，北京时间）">
        <Input ref={endInput} type="date" value={localDateTime(endExclusive).slice(0, 10)} />
      </Field>
    </div>
  )
}
