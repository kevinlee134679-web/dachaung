import type { FeedbackInput } from './feedback'
import type { JSX } from '@solidjs/web'
import { createSignal, For, untrack } from 'solid-js'
import { Button } from '../../../ui/button'
import { Field, Input, Select, Textarea } from '../../../ui/form'
import { Text } from '../../../ui/typography'
import { participationLabels } from './feedback'

export function FeedbackEditor(props: {
  initial: FeedbackInput | null
  revision: number
  submit: (data: FeedbackInput) => Promise<void>
}): JSX.Element {
  const [participation, setParticipation] = createSignal(
    untrack(() =>
      props.initial?.participation != null && props.initial.participation !== ''
        ? props.initial.participation
        : 'provided',
    ),
  )
  let needs!: HTMLTextAreaElement
  let acceptance!: HTMLTextAreaElement
  let effectiveness!: HTMLTextAreaElement
  let willingness!: HTMLSelectElement
  let reason!: HTMLInputElement
  return (
    <div class="space-y-4">
      <Text>基于反馈修订 {props.revision}</Text>
      <Field label="反馈参与情况">
        <Select
          value={participation()}
          onChange={event => {
            setParticipation(event.currentTarget.value)
          }}
        >
          <For each={Object.entries(participationLabels)}>
            {([value, label]) => <option value={value}>{label}</option>}
          </For>
        </Select>
      </Field>
      <div hidden={participation() !== 'provided'} class="space-y-4">
        <Field label="支持需求变化">
          <Textarea ref={needs} rows={2} maxlength={2000} value={props.initial?.support_needs ?? ''} />
        </Field>
        <Field label="支持接受程度">
          <Textarea ref={acceptance} rows={2} maxlength={2000} value={props.initial?.support_acceptance ?? ''} />
        </Field>
        <Field label="干预效果（本人描述）">
          <Textarea
            ref={effectiveness}
            rows={2}
            maxlength={2000}
            value={props.initial?.intervention_effectiveness ?? ''}
          />
        </Field>
      </div>
      <Field label="是否愿意继续">
        <Select
          ref={willingness}
          value={props.initial?.willing_to_continue == null ? '' : props.initial.willing_to_continue ? 'yes' : 'no'}
        >
          <option value="">未知</option>
          <option value="yes">愿意</option>
          <option value="no">不愿意</option>
        </Select>
      </Field>
      <Field label="未填写说明">
        <Input ref={reason} maxlength={500} value={props.initial?.missing_reason ?? ''} />
      </Field>
      <Text>自愿描述本次体验。未知或不适用的内容可留空，并填写说明。</Text>
      <Button
        variant="primary"
        onAction={() =>
          props.submit({
            participation: participation(),
            support_needs: participation() === 'provided' ? needs.value.trim() || null : null,
            support_acceptance: participation() === 'provided' ? acceptance.value.trim() || null : null,
            intervention_effectiveness: participation() === 'provided' ? effectiveness.value.trim() || null : null,
            willing_to_continue: willingness.value ? willingness.value === 'yes' : null,
            missing_reason: reason.value.trim() || null,
          })
        }
      >
        提交本人反馈
      </Button>
    </div>
  )
}
