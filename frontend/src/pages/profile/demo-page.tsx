import type { JSX } from '@solidjs/web'
import { createSignal, Show } from 'solid-js'
import * as v from 'valibot'
import { api } from '../../api/api'
import { inputDateTime, localDateTime } from '../../date/date'
import { isDemoAdmin, requireCurrentView, state } from '../../session/session'
import { navigate } from '../../shell/navigation'
import { Badge, Button, Card, Disclosure, Field, Input, Select, Text } from '../../ui/components'
import { IssueList } from '../../ui/data-display'
import { labelFor, statusTone } from '../../ui/labels'
import { issueSchema } from './statistics'

export interface DemoTask {
  patientId: string
  accountId: string
  taskId: string
  revision: number
}

export function DemoPage(): JSX.Element {
  let device!: HTMLInputElement
  let scenario!: HTMLSelectElement
  let run!: HTMLInputElement
  let time!: HTMLInputElement
  let event!: HTMLInputElement
  let revision!: HTMLInputElement
  let slot!: HTMLInputElement
  let reason!: HTMLInputElement
  let taskId!: HTMLInputElement
  let taskRevision!: HTMLInputElement
  let cancelReason!: HTMLInputElement
  const [output, setOutput] = createSignal<JSX.Element>(null)
  const selectedTask = () => {
    const task = state.demoTask
    return task?.patientId === state.patient?.patient.patient_id &&
      task?.accountId === state.context?.account.account_id
      ? task
      : null
  }
  return (
    <Show when={isDemoAdmin()} fallback={<p>演示控制台仅对受控演示管理员开放。</p>}>
      <Card title="用药记录与任务演示">
        <div class="space-y-4">
          <Text>以下操作只用于当前虚构患者。时段物化与任务准备需要显式维护。</Text>
          <Disclosure summary="发送固定场景的模拟设备事件">
            <Field label="当前患者已绑定的模拟设备编号">
              <Input ref={device} />
            </Field>
            <Field label="固定设备场景">
              <Select ref={scenario}>
                <option value="normal_box">正常开盒</option>
                <option value="duplicate">重复上传</option>
                <option value="late_upload">迟到上传</option>
                <option value="measurement_missing">缺失指标</option>
                <option value="unknown_unit">未知单位</option>
                <option value="unbound">未绑定设备（预期拒绝）</option>
              </Select>
            </Field>
            <Field label="场景运行号（同次重放保持不变）">
              <Input ref={run} value={crypto.randomUUID()} />
            </Field>
            <Field label="实际发生/采样时间（北京时间）">
              <Input ref={time} type="datetime-local" value={localDateTime()} />
            </Field>
            <Button
              onAction={async view => {
                const result = await api(
                  '/demo/device-events',
                  v.looseObject({
                    event_id: v.string(),
                    quality: v.looseObject({ status: v.string(), issues: v.array(issueSchema) }),
                    link_status: v.string(),
                  }),
                  'POST',
                  {
                    patient_id: view.patientId,
                    device_id: device.value,
                    scenario: scenario.value,
                    scenario_run_id: run.value,
                    occurred_at: inputDateTime(time.value),
                  },
                  view,
                )
                requireCurrentView(view)
                setOutput(
                  <>
                    <p>
                      模拟事件 {result.event_id}：
                      <Badge tone={statusTone(result.quality.status)}>{labelFor(result.quality.status)}</Badge>；
                      <Badge tone={statusTone(result.link_status)}>{labelFor(result.link_status)}</Badge>。
                    </p>
                    <IssueList issues={result.quality.issues} />
                  </>,
                )
              }}
            >
              发送一次模拟事件
            </Button>
          </Disclosure>
          <Disclosure summary="受控技术复核与重处理">
            <Field label="当前患者事件编号">
              <Input ref={event} />
            </Field>
            <Field label="精确事件修订">
              <Input ref={revision} type="number" min="1" value="1" />
            </Field>
            <Field label="明确关联的时段编号（留空明确解除）">
              <Input ref={slot} />
            </Field>
            <Field label="复核依据（必填）">
              <Input ref={reason} />
            </Field>
            <Text>技术复核不改变本人/家人/设备来源，不判断临床资质，不按附近时间猜配。</Text>
            <Button
              onAction={async view => {
                if (!reason.value.trim()) throw new Error('请提供复核依据。')
                const result = await api(
                  '/dose-matches/review',
                  v.looseObject({ link_status: v.string(), reason: v.nullable(v.string()) }),
                  'POST',
                  {
                    event_id: event.value,
                    expected_revision: Number(revision.value),
                    dose_slot_id: slot.value || null,
                    reason: reason.value,
                  },
                  view,
                )
                requireCurrentView(view)
                setOutput(
                  <p>
                    已保存复核：<Badge tone={statusTone(result.link_status)}>{labelFor(result.link_status)}</Badge>；
                    {result.reason === null || result.reason === '' ? '明确合法引用' : result.reason}
                  </p>,
                )
              }}
            >
              明确保存关联复核
            </Button>
            <Button
              onAction={async view => {
                const result = await api(
                  `/events/${encodeURIComponent(event.value)}/reprocess`,
                  v.looseObject({ status: v.string(), issues: v.array(issueSchema) }),
                  'POST',
                  { expected_revision: Number(revision.value) },
                  view,
                )
                requireCurrentView(view)
                setOutput(
                  <>
                    <p>
                      <Badge tone={statusTone(result.status)}>{labelFor(result.status)}</Badge>
                    </p>
                    <IssueList issues={result.issues} />
                  </>,
                )
              }}
            >
              重跑当前注册清洗规则一次
            </Button>
          </Disclosure>
          <Disclosure summary="公共任务显式执行与取消">
            <Field label="当前患者任务编号">
              <Input ref={taskId} value={selectedTask()?.taskId ?? ''} />
            </Field>
            <Field label="任务当前修订">
              <Input ref={taskRevision} type="number" min="1" value={selectedTask()?.revision ?? 1} />
            </Field>
            <Field label="取消原因">
              <Input ref={cancelReason} />
            </Field>
            <Button
              onAction={async view => {
                const result = await api(
                  `/tasks/${encodeURIComponent(taskId.value)}/run`,
                  v.looseObject({
                    execution_id: v.string(),
                    execution_status: v.string(),
                    delivery_status: v.string(),
                    is_simulated: v.boolean(),
                    error_message: v.nullable(v.string()),
                  }),
                  'POST',
                  { expected_revision: Number(taskRevision.value) },
                  view,
                )
                requireCurrentView(view)
                setOutput(
                  <>
                    <p>
                      执行 {result.execution_id}：
                      <Badge tone={statusTone(result.execution_status)}>{labelFor(result.execution_status)}</Badge>
                      ；投递 <Badge tone={statusTone(result.delivery_status)}>{labelFor(result.delivery_status)}</Badge>
                      ；{result.is_simulated ? '模拟' : '实际适配'}
                    </p>
                    <p>{result.error_message ?? ''}</p>
                  </>,
                )
              }}
            >
              显式执行此任务一次
            </Button>
            <Button
              onAction={async view => {
                if (!cancelReason.value.trim()) throw new Error('请填写取消原因。')
                const result = await api(
                  `/tasks/${encodeURIComponent(taskId.value)}/cancel`,
                  v.looseObject({ status: v.string(), cancellation_requested: v.boolean() }),
                  'POST',
                  { expected_revision: Number(taskRevision.value), reason: cancelReason.value },
                  view,
                )
                requireCurrentView(view)
                setOutput(
                  <p>
                    <Badge tone={statusTone(result.status)}>{labelFor(result.status)}</Badge>
                    {result.cancellation_requested ? '；已记录在途取消请求，不宣称副作用已撤回' : ''}
                  </p>,
                )
              }}
            >
              明确取消或请求取消此任务
            </Button>
            <Button onAction={() => navigate('medication', 'executions')}>查看当前患者全部任务</Button>
          </Disclosure>
          <div aria-live="polite">{output()}</div>
        </div>
      </Card>
    </Show>
  )
}
