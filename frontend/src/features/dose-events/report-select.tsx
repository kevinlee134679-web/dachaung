import type { JSX } from '@solidjs/web'
import { For } from 'solid-js'
import { Field, Select } from '../../ui/form'

const reportOptions: [string, string][] = [
  ['taken', '报告已服'],
  ['not_taken', '报告未服'],
  ['postponed', '暂时延迟'],
  ['unknown', '不清楚'],
]

export function ReportSelect(props: {
  label: string
  ref: (element: HTMLSelectElement) => void
  value?: string | null | undefined
  onChange?: (value: string) => void
}): JSX.Element {
  return (
    <Field label={props.label}>
      <Select
        ref={props.ref}
        value={props.value ?? 'taken'}
        onChange={event => props.onChange?.(event.currentTarget.value)}
      >
        <For each={reportOptions}>{option => <option value={option[0]}>{option[1]}</option>}</For>
      </Select>
    </Field>
  )
}
