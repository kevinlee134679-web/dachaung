import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For } from 'solid-js'
import * as v from 'valibot'
import { api, ApiError } from '../../api/api'
import { requireCurrentView, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Field, Input, Select } from '../../ui/form'
import { Text } from '../../ui/typography'
import { dispatchAttemptSchema, dispatchDescription, dispatchTaskSchema, formalServiceStates } from './dispatch'
import { serviceWrite } from './draft-data'

export function ServiceDemoControls(): JSX.Element {
  let task!: HTMLInputElement
  let service!: HTMLInputElement
  let revision!: HTMLInputElement
  let target!: HTMLSelectElement
  let reason!: HTMLInputElement
  const [output, setOutput] = createSignal('')

  async function runDispatch(view: View): Promise<void> {
    const path = `/tasks/${encodeURIComponent(task.value.trim())}`
    const current = await api(path, dispatchTaskSchema, 'GET', null, view)
    requireCurrentView(view)
    if (current.kind !== 'dispatch_service') throw new Error('此处只执行正式服务的模拟派发。')
    if (['pending', 'retry_wait'].includes(current.status)) {
      try {
        await api(`${path}/run`, v.unknown(), 'POST', { expected_revision: current.meta.revision }, view)
      } catch (caught) {
        if (
          caught instanceof ViewChanged ||
          (caught instanceof ApiError && (caught.status === 403 || caught.status === 404))
        ) {
          throw caught
        }
      }
    }
    requireCurrentView(view)
    const [latest, attempts] = await Promise.all([
      api(path, dispatchTaskSchema, 'GET', null, view),
      api(`${path}/executions`, v.looseObject({ items: v.array(dispatchAttemptSchema) }), 'GET', null, view),
    ])
    requireCurrentView(view)
    setOutput(dispatchDescription(latest, attempts.items.at(-1)))
  }

  async function recordTransition(view: View): Promise<void> {
    if (!service.value.trim() || !revision.valueAsNumber || !reason.value.trim())
      throw new Error('请填写编号、修订和原因。')
    const value = await serviceWrite(
      `/demo/services/${encodeURIComponent(service.value.trim())}/transitions`,
      'POST',
      { expected_revision: revision.valueAsNumber, target_status: target.value, reason: reason.value.trim() },
      v.looseObject({ status: v.string(), meta: v.looseObject({ revision: v.number() }) }),
      view,
    )
    requireCurrentView(view)
    revision.value = String(value.meta.revision)
    setOutput(`服务状态 ${formalServiceStates[value.status]} · 修订 ${value.meta.revision}`)
  }

  return (
    <Card title="社会支持演示控制台">
      <div class="space-y-4">
        <Text>仅用于本地虚构服务。</Text>
        <Field label="正式服务派发任务编号">
          <Input ref={task} maxlength={128} />
        </Field>
        <Button onAction={runDispatch}>执行一次模拟派发</Button>
        <Field label="正式服务编号">
          <Input ref={service} maxlength={128} />
        </Field>
        <Field label="当前服务修订">
          <Input ref={revision} type="number" value="1" min={1} />
        </Field>
        <Field label="模拟状态变化">
          <Select ref={target}>
            <For each={Object.entries(formalServiceStates).slice(1)}>
              {entry => <option value={entry[0]}>{entry[1]}</option>}
            </For>
          </Select>
        </Field>
        <Field label="模拟原因或结果">
          <Input ref={reason} maxlength={500} />
        </Field>
        <Button onAction={recordTransition}>记录模拟状态变化</Button>
        <div aria-live="polite">{output()}</div>
      </div>
    </Card>
  )
}
