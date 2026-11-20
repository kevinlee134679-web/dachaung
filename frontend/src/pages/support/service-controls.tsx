import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For } from 'solid-js'
import * as v from 'valibot'
import { api, ApiError } from '../../api/api'
import { requireCurrentView, ViewChanged } from '../../session/session'
import { Button, Card, Field, Input, Select, Text } from '../../ui/components'
import { labelFor } from '../../ui/labels'
import { serviceWrite } from './service-draft-data'

export const formalServiceStates: Record<string, string> = {
  submitted: '已提交',
  in_progress: '模拟处理中',
  completed: '模拟完成',
  cancelled: '已取消',
  failed: '处理失败',
}

export interface DispatchTask {
  status: string
  kind: string
  meta: { revision: number }
}

export interface DispatchAttempt {
  attempt: number
  execution_status: string
  delivery_status: string
}

export const dispatchTaskSchema: v.GenericSchema<unknown, DispatchTask> = v.looseObject({
  status: v.string(),
  kind: v.string(),
  meta: v.looseObject({ revision: v.number() }),
})
export const dispatchAttemptSchema: v.GenericSchema<unknown, DispatchAttempt> = v.looseObject({
  attempt: v.number(),
  execution_status: v.string(),
  delivery_status: v.string(),
})

export function dispatchDescription(task: DispatchTask, attempt: DispatchAttempt | undefined): string {
  if (attempt?.execution_status === 'outcome_unknown') return '原派发结果未知，请核对原任务及后续回执。'
  if (task.status === 'succeeded' && attempt?.delivery_status === 'submitted')
    return '模拟派发已登记，服务状态请见上方。'
  const labels: Record<string, string> = {
    pending: '等待模拟派发',
    retry_wait: '模拟派发明确失败，等待安全重试',
    running: '模拟派发待核实',
    cancelled: '原派发已停止',
    expired: '派发授权已过期',
    failed: '模拟派发失败',
  }
  const label = labels[task.status]
  return label !== undefined && label !== '' ? label : labelFor(task.status)
}

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
