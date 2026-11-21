import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal } from 'solid-js'
import * as v from 'valibot'
import { api, sha } from '../../api/api'
import { requireCurrentView } from '../../session/session'
import { Button } from '../../ui/button'
import { Disclosure } from '../../ui/disclosure'
import { Field, Select, Textarea } from '../../ui/form'

export function RewardFeedback(props: { detail: string; view: View }): JSX.Element {
  let participation!: HTMLSelectElement
  let experience!: HTMLTextAreaElement
  const [result, setResult] = createSignal('')
  return (
    <Disclosure summary="自愿评价本次权益">
      <Field label="评价参与">
        <Select ref={participation}>
          <option value="provided">自愿填写</option>
          <option value="declined">不参加</option>
          <option value="unable">暂无法填写</option>
        </Select>
      </Field>
      <Field label="权益体验（可留空）">
        <Textarea ref={experience} rows={2} maxlength={2000} />
      </Field>
      <Button
        view={props.view}
        onAction={async view => {
          const body = {
            participation: participation.value,
            experience: participation.value === 'provided' ? experience.value.trim() || null : null,
            service_feedback_id: null,
          }
          const key = `reward-feedback:${view.accountId}:${props.detail}:${await sha(JSON.stringify(body))}`
          requireCurrentView(view)
          let id = localStorage.getItem(key)
          if (id === null || id === '') {
            id = crypto.randomUUID()
            localStorage.setItem(key, id)
          }
          await api(`${props.detail}/feedback`, v.unknown(), 'POST', { client_feedback_id: id, ...body }, view)
          requireCurrentView(view)
          setResult('体验已保存。')
        }}
      >
        保存权益体验
      </Button>
      <p>{result()}</p>
    </Disclosure>
  )
}
