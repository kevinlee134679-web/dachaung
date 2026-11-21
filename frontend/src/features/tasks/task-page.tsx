import type { PatientAccess, SessionContext, View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api } from '../../api/api'
import { dateText } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import { readGate } from '../../session/read-gate'
import {
  captureView,
  isCurrentView,
  isDemoAdmin,
  patientPath,
  requireCurrentView,
  scope,
  state,
  updateSession,
  ViewChanged,
} from '../../session/session'
import { StatusBadge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Field, Input } from '../../ui/form'
import { EmptyState, List } from '../../ui/list'
import { Subheading, Text } from '../../ui/typography'

const taskLabels: Record<string, string> = {
  deliver_reminder: '应用内提醒',
  check_in_node: 'B检查（未接入）',
  deliver_intervention: 'B投递（未接入）',
}

const taskSchema = v.looseObject({
  task_id: v.string(),
  kind: v.string(),
  owner_module: v.string(),
  status: v.string(),
  attempt_count: v.number(),
  max_attempts: v.number(),
  scheduled_at: v.string(),
  valid_until: v.string(),
  failure_reason: v.nullable(v.string()),
  cancellation_requested: v.boolean(),
  meta: v.looseObject({ revision: v.number(), is_simulated: v.boolean() }),
})
const executionSchema = v.looseObject({
  attempt: v.number(),
  execution_status: v.string(),
  delivery_status: v.string(),
  is_simulated: v.boolean(),
  error_message: v.nullable(v.string()),
  started_at: v.string(),
  delivered_at: v.nullable(v.string()),
})
type Task = v.InferOutput<typeof taskSchema>
type Execution = v.InferOutput<typeof executionSchema>

function TaskCard(props: { task: Task; reload: (view: View) => Promise<void> }) {
  const [history, setHistory] = createSignal<Execution[] | null>(null)
  let snooze!: HTMLInputElement
  async function loadHistory(view: View): Promise<void> {
    const result = await all(`/tasks/${encodeURIComponent(props.task.task_id)}/executions`, executionSchema, view)
    requireCurrentView(view)
    setHistory(result)
  }
  async function saveSnooze(view: View): Promise<void> {
    await api(
      patientPath('/reminder-snoozes'),
      v.unknown(),
      'POST',
      {
        source_task_id: props.task.task_id,
        expected_task_revision: props.task.meta.revision,
        snooze_minutes: Number(snooze.value),
      },
      view,
    )
    await props.reload(view)
    requireCurrentView(view)
    notice('稍后通知任务已保存，医嘱与服药证据未改变；实际执行结果请另行核对。')
  }
  function openConsole(patient: PatientAccess, context: SessionContext): void {
    const demoTask = {
      taskId: props.task.task_id,
      revision: props.task.meta.revision,
      patientId: patient.patient.patient_id,
      accountId: context.account.account_id,
    }
    updateSession(draft => {
      draft.demoTask = demoTask
    })
    navigate('profile', 'demo')
  }
  return (
    <li class="space-y-3">
      <Subheading level={3}>{taskLabels[props.task.kind] ?? props.task.kind}</Subheading>
      <p class="text-sm/6">
        <StatusBadge status={props.task.status} />
        ；尝试 {props.task.attempt_count}/{props.task.max_attempts}；
        {props.task.meta.is_simulated ? '演示任务' : '实际来源任务'}
      </p>
      <p>
        通知/执行计划：{dateText(props.task.scheduled_at)}；有效期至 {dateText(props.task.valid_until)}
      </p>
      <Text>{props.task.failure_reason}</Text>
      <Show
        when={
          ['pending', 'retry_wait'].includes(props.task.status) &&
          Date.now() >= new Date(props.task.valid_until).getTime()
        }
      >
        <p>
          已过有效期，原状态
          <StatusBadge status={props.task.status} />
          ，历史待显式维护。当前查询不会重新发送此任务。
        </p>
      </Show>
      <Show when={props.task.cancellation_requested}>
        <p>已记录取消请求，不能据此认定在途副作用已撤回。</p>
      </Show>
      <Button onAction={loadHistory}>查看执行与投递历史</Button>
      <Show when={history()}>
        {items => (
          <Show when={items().length} fallback={<EmptyState>尚无执行。</EmptyState>}>
            <List>
              <For each={items()}>
                {execution => (
                  <li>
                    <p>
                      第 {execution.attempt} 次：
                      <StatusBadge status={execution.execution_status} />
                      ；投递：
                      <StatusBadge status={execution.delivery_status} />；{execution.is_simulated ? '模拟' : '实际适配'}
                    </p>
                    <p>{execution.error_message}</p>
                    <Text>
                      开始 {dateText(execution.started_at)}；
                      {execution.delivered_at !== null && execution.delivered_at !== ''
                        ? `渠道回执 ${dateText(execution.delivered_at)}`
                        : '没有送达回执，不标记已读'}
                    </Text>
                  </li>
                )}
              </For>
            </List>
          </Show>
        )}
      </Show>
      <Show when={props.task.kind === 'deliver_reminder' && props.task.owner_module === 'O' && scope('reminder:write')}>
        <Field label="稍后收到通知（5—120分钟）">
          <Input ref={snooze} type="number" value="10" min="5" max="120" />
        </Field>
        <Button disabled={props.task.status !== 'succeeded'} onAction={saveSnooze}>
          明确稍后提醒
        </Button>
        <Text>只推迟通知，不等于延迟服药或建议补服。严格医嘱未知、下一时段、4小时边界或总3次上限由后端重新核验。</Text>
      </Show>
      <Show when={isDemoAdmin()}>
        <Text>
          控制台引用：{props.task.task_id}；当前修订 {props.task.meta.revision}
        </Text>
        <Show when={state.patient} keyed>
          {patient => (
            <Show when={state.context} keyed>
              {context => <Button onAction={() => openConsole(patient, context)}>在控制台操作此任务</Button>}
            </Show>
          )}
        </Show>
      </Show>
    </li>
  )
}

export function TaskPage(): JSX.Element {
  const [tasks, setTasks] = createSignal<Task[] | null>(null)
  const beginRead = readGate()
  async function load(view: View): Promise<void> {
    const ensure = beginRead()
    const result = await all(patientPath('/tasks'), taskSchema, view)
    ensure()
    setTasks(result)
  }
  onSettled(() => {
    if (!scope('tasks:read')) return
    const view = captureView()
    void load(view).catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })
  return (
    <Card title="提醒与执行记录">
      <div class="space-y-4">
        <Text>
          刷新只读取持久化状态，不会启动调度或发送通知。已提交、送达、展示和本人响应分别记录；模拟投递不代表真实收到。
        </Text>
        <Show when={scope('tasks:read')} fallback={<p>当前未获任务状态查看权限。</p>}>
          <Button onAction={load}>重新读取执行状态</Button>
          <Show when={tasks()}>
            {items => (
              <Show
                when={items().length}
                fallback={
                  <EmptyState>当前没有任务。提醒配置保存后，需通过显式维护准备任务，执行仍需明确操作。</EmptyState>
                }
              >
                <List>
                  <For each={items()}>{task => <TaskCard task={task} reload={load} />}</For>
                </List>
              </Show>
            )}
          </Show>
        </Show>
      </div>
    </Card>
  )
}
