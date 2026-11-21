import type { EventPayload } from './events'
import type { JSX } from '@solidjs/web'
import { For, onSettled } from 'solid-js'
import { Checkbox, Field, Input, Select } from '../../ui/form'
import { metricOptions } from '../../ui/labels'

export function MeasurementEditor(props: {
  payload?: EventPayload
  ref: (read: () => EventPayload) => void
}): JSX.Element {
  let metric!: HTMLSelectElement
  let value!: HTMLInputElement
  let unit!: HTMLInputElement
  let method!: HTMLInputElement
  let missing!: HTMLInputElement
  let reason!: HTMLInputElement
  onSettled(() =>
    props.ref(() => {
      if (missing.checked && !reason.value.trim()) throw new Error('缺失数值需要明确原因。')
      if (!missing.checked && (value.value === '' || !Number.isFinite(Number(value.value))))
        throw new Error('请填写有限的实际数值，或选择缺失并说明原因。')
      return {
        metric_code: metric.value,
        value: missing.checked ? null : Number(value.value),
        unit: unit.value || null,
        method_code: method.value || null,
        missing_reason: missing.checked ? reason.value : null,
      }
    }),
  )
  return (
    <>
      <Field label="指标">
        <Select ref={metric} value={props.payload?.metric_code ?? 'sleep_duration'}>
          <For each={metricOptions}>{option => <option value={option[0]}>{option[1]}</option>}</For>
        </Select>
      </Field>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="实际数值（缺失时不填）">
          <Input ref={value} type="number" step="any" value={props.payload?.value ?? ''} />
        </Field>
        <Field label="原单位（睡眠h、步数count、心率beats/min）">
          <Input ref={unit} value={props.payload ? (props.payload.unit ?? '') : 'h'} />
        </Field>
      </div>
      <Field label="测量方法（未知留空，不同方法不混合）">
        <Input ref={method} value={props.payload?.method_code ?? ''} />
      </Field>
      <Checkbox
        ref={missing}
        label="本次未采集或数值缺失"
        checked={props.payload ? props.payload.value === null : false}
      />
      <Field label="缺失原因">
        <Input ref={reason} value={props.payload?.missing_reason ?? ''} />
      </Field>
    </>
  )
}
