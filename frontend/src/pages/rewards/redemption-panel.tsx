import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createMemo, createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api, ApiError, sha } from '../../api/api'
import { actionError, notice } from '../../notice/notice'
import { isCurrentView, own, requireCurrentView, ViewChanged } from '../../session/session'
import { navigate } from '../../shell/navigation'
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Disclosure,
  Field,
  Select,
  Subheading,
  Text,
  Textarea,
} from '../../ui/components'
import { confirm } from '../../ui/confirm'
import { statusTone } from '../../ui/labels'
import { serviceWrite } from '../support/service-draft-data'
import { openServiceRecord } from '../support/service-navigation'

const rewardAvailability: Record<string, string> = {
  available: '可兑换',
  unavailable: '暂不可用',
  unknown: '条件待核查',
}
const fulfillmentStatus: Record<string, string> = {
  pending: '等待模拟履约',
  in_progress: '模拟履约处理中',
  completed: '已确认模拟交付',
  failed: '已确认未交付',
  cancelled: '已确认取消且未交付',
  outcome_unknown: '交付结果未知，请先核查原订单',
}

const rewardSchema = v.looseObject({
  reward_id: v.string(),
  reward_version: v.string(),
  name: v.string(),
  description: v.string(),
  points_cost: v.number(),
  availability: v.string(),
  kind: v.string(),
  resource_id: v.nullable(v.string()),
})
type Reward = v.InferOutput<typeof rewardSchema>
const orderSchema = v.looseObject({
  redemption_id: v.string(),
  reward_name: v.string(),
  points_status: v.string(),
  points_spent: v.number(),
  status: v.string(),
  refund_ledger_id: v.nullable(v.string()),
  debit_ledger_id: v.string(),
})
type Order = v.InferOutput<typeof orderSchema>
const deliverySchema = v.looseObject({
  status: v.string(),
  failure_reason: v.nullable(v.string()),
  task_id: v.nullable(v.string()),
  artifact: v.nullable(v.looseObject({ text: v.string() })),
  service_id: v.nullable(v.string()),
})
type Delivery = v.InferOutput<typeof deliverySchema>
const resourceSchema = v.looseObject({
  resource_id: v.string(),
  resource_version: v.string(),
  provider: v.looseObject({ display_name: v.string() }),
  required_shared_categories: v.array(v.string()),
})
type Resource = v.InferOutput<typeof resourceSchema>
const accountSchema = v.looseObject({ balance: v.number(), meta: v.looseObject({ revision: v.number() }) })
type Account = v.InferOutput<typeof accountSchema>
interface ServiceConfirmation {
  service_draft_id: string
  draft_revision: number
  confirmation_ref_id: string
  sharing_scope_ref_id: string
}
const checkoutSchema = v.looseObject({
  reward_id: v.string(),
  reward_version: v.string(),
  expected_account_revision: v.number(),
  confirmed: v.boolean(),
  service_draft_id: v.exactOptional(v.string()),
  draft_revision: v.exactOptional(v.number()),
  confirmation_ref_id: v.exactOptional(v.string()),
  sharing_scope_ref_id: v.exactOptional(v.string()),
})
type Checkout = v.InferOutput<typeof checkoutSchema>

function RewardFeedback(props: { detail: string; view: View }): JSX.Element {
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

function saveRewardText(artifact: { text: string }): void {
  const url = URL.createObjectURL(new Blob([artifact.text], { type: 'text/plain;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = '模拟管理资料.txt'
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function RewardOrder(props: { order: Order; view: View }): JSX.Element {
  const detail = createMemo(() => `/redemptions/${encodeURIComponent(props.order.redemption_id)}`)
  const [result, setResult] = createSignal<{ current: Order; delivery: Delivery }>()
  return (
    <li class="space-y-3 py-4 first:pt-0 last:pb-0">
      <strong>{props.order.reward_name}</strong>
      <Text>兑换编号 {props.order.redemption_id}</Text>
      <p>
        {props.order.points_status === 'refunded' ? '已全额退回 ' : '原兑换扣减 '}
        {props.order.points_spent} 积分
      </p>
      <Button
        view={props.view}
        onAction={async view => {
          const [current, delivery] = await Promise.all([
            api(detail(), orderSchema, 'GET', null, view),
            api(`${detail()}/fulfillment`, deliverySchema, 'GET', null, view),
          ])
          requireCurrentView(view)
          setResult({ current, delivery })
        }}
      >
        查看交付结果
      </Button>
      <div aria-live="polite">
        <Show when={result()}>
          {value => (
            <>
              <p>
                <Badge tone={statusTone(value().delivery.status)}>{fulfillmentStatus[value().delivery.status]}</Badge>
              </p>
              <Show when={value().delivery.failure_reason}>
                <p>{value().delivery.failure_reason}</p>
              </Show>
              <Text>
                {value().current.points_status === 'refunded'
                  ? `全额退分流水 ${value().current.refund_ledger_id}`
                  : `原扣减流水 ${value().current.debit_ledger_id}`}
              </Text>
              <Show when={value().delivery.task_id}>
                <Text>原履约任务编号 {value().delivery.task_id}</Text>
              </Show>
              <Show when={value().delivery.artifact}>
                {artifact => (
                  <>
                    <pre class="whitespace-pre-wrap">{artifact().text}</pre>
                    <Button view={props.view} onAction={() => saveRewardText(artifact())}>
                      保存模拟管理文本
                    </Button>
                  </>
                )}
              </Show>
              <Show when={value().delivery.service_id}>
                {id => (
                  <Button view={props.view} onAction={() => openServiceRecord(id())}>
                    查看关联的模拟服务
                  </Button>
                )}
              </Show>
              <Show when={own() && ['completed', 'failed'].includes(value().current.status)}>
                <RewardFeedback detail={detail()} view={props.view} />
              </Show>
            </>
          )}
        </Show>
      </div>
    </li>
  )
}

function RewardItem(props: {
  reward: Reward
  account: Account | null
  path: string
  view: View
  send: (body: Checkout, view: View) => Promise<void>
  pendingKey: string
}): JSX.Element {
  const [resource, setResource] = createSignal<Resource>()
  const [confirmation, setConfirmation] = createSignal<ServiceConfirmation>()
  let question!: HTMLTextAreaElement
  let consent!: HTMLInputElement
  const canBuy = () =>
    props.account && props.reward.availability === 'available' && props.account.balance >= props.reward.points_cost
  const checkout = (account: Account, service: Partial<ServiceConfirmation> = {}): JSX.Element => (
    <Button
      variant="primary"
      view={props.view}
      onAction={async view => {
        if (localStorage.getItem(props.pendingKey) !== null) throw new Error('请先核查原兑换。')
        if (!(await confirm(`确认使用 ${props.reward.points_cost} 积分兑换「${props.reward.name}」？`))) return
        requireCurrentView(view)
        await props.send(
          {
            reward_id: props.reward.reward_id,
            reward_version: props.reward.reward_version,
            expected_account_revision: account.meta.revision,
            confirmed: true,
            ...service,
          },
          view,
        )
      }}
    >
      确认兑换 {props.reward.points_cost} 积分
    </Button>
  )
  return (
    <Disclosure
      summary={
        <>
          {props.reward.name} · {props.reward.points_cost} 积分
        </>
      }
    >
      <p>{props.reward.description}</p>
      <Text>
        <Badge tone={statusTone(props.reward.availability)}>{rewardAvailability[props.reward.availability]}</Badge> ·
        版本 {props.reward.reward_version}
      </Text>
      <Show when={props.account && props.reward.availability === 'available' && !canBuy()}>
        <p>当前余额不足。</p>
      </Show>
      <Show when={canBuy() && props.reward.kind === 'digital_content' && props.account}>
        {account => checkout(account())}
      </Show>
      <Show when={canBuy() && props.reward.kind === 'service_appointment'}>
        <Button
          view={props.view}
          onAction={async view => {
            const resources = await all('/support-resources?channel=rewards', resourceSchema, view)
            requireCurrentView(view)
            const found = resources.find(item => item.resource_id === props.reward.resource_id)
            if (!found) throw new Error('该权益的模拟人员资源暂不可用。')
            setResource(found)
            setConfirmation(undefined)
          }}
        >
          准备陪伴服务草稿
        </Button>
      </Show>
      <div aria-live="polite">
        <Show when={resource()}>
          {item => (
            <Show
              when={confirmation()}
              fallback={
                <>
                  <p>模拟接收方 {item().provider.display_name}</p>
                  <Field label="本次希望陪伴讨论的问题">
                    <Textarea ref={question} rows={2} maxlength={2000} />
                  </Field>
                  <Checkbox ref={consent} label="我核对了问题，并同意只共享本次支持问题" />
                  <Button
                    view={props.view}
                    onAction={async view => {
                      if (!question.value.trim() || !consent.checked) throw new Error('请本人填写并核对共享范围。')
                      const draft = await serviceWrite(
                        `${props.path}/service-drafts`,
                        'POST',
                        {
                          resource_id: item().resource_id,
                          resource_version: item().resource_version,
                          request_text: question.value.trim(),
                        },
                        v.looseObject({ service_draft_id: v.string(), draft_revision: v.number() }),
                        view,
                      )
                      requireCurrentView(view)
                      const saved = await serviceWrite(
                        `${props.path}/service-confirmations`,
                        'POST',
                        {
                          service_draft_id: draft.service_draft_id,
                          draft_revision: draft.draft_revision,
                          shared_categories: item().required_shared_categories,
                          confirmed: true,
                        },
                        v.looseObject({
                          confirmation_ref_id: v.string(),
                          sharing_scope: v.looseObject({ sharing_scope_ref_id: v.string() }),
                        }),
                        view,
                      )
                      requireCurrentView(view)
                      setConfirmation({
                        service_draft_id: draft.service_draft_id,
                        draft_revision: draft.draft_revision,
                        confirmation_ref_id: saved.confirmation_ref_id,
                        sharing_scope_ref_id: saved.sharing_scope.sharing_scope_ref_id,
                      })
                    }}
                  >
                    保存并确认陪伴草稿
                  </Button>
                </>
              }
            >
              {saved => (
                <>
                  <p>已确认共享本次支持问题。</p>
                  <Show when={props.account}>{account => checkout(account(), { ...saved() })}</Show>
                </>
              )}
            </Show>
          )}
        </Show>
      </div>
    </Disclosure>
  )
}

export function RedemptionPanel(props: { path: string; view: View }): JSX.Element {
  const [orders, setOrders] = createSignal<Order[]>()
  const [rewards, setRewards] = createSignal<Reward[]>([])
  const [account, setAccount] = createSignal<Account | null>(null)
  const [directoryError, setDirectoryError] = createSignal('')
  const [pending, setPending] = createSignal<Checkout | null>(null)
  const [pendingMessage, setPendingMessage] = createSignal('')
  const pendingKey = createMemo(() => `reward-pending:${props.view.accountId}:${props.view.patientId}`)
  const post = createMemo(() => `${props.path}/redemptions`)
  async function send(body: Checkout, view: View): Promise<void> {
    localStorage.setItem(pendingKey(), JSON.stringify(body))
    try {
      const order = await api(post(), orderSchema, 'POST', body, view)
      requireCurrentView(view)
      localStorage.removeItem(pendingKey())
      navigate('rewards')
      notice(`已核实本次兑换。订单编号 ${order.redemption_id}`)
    } catch (error) {
      if (error instanceof ViewChanged) throw error
      requireCurrentView(view)
      if (
        error instanceof ApiError &&
        error.status >= 400 &&
        error.status < 500 &&
        !['OPERATION_IN_PROGRESS', 'IDEMPOTENCY_EXPIRED'].includes(error.code ?? '')
      ) {
        localStorage.removeItem(pendingKey())
      } else {
        setPending(body)
        setPendingMessage('原提交结果待核查。先核对订单记录，重试会使用原兑换条件。')
      }
      throw error
    }
  }
  onSettled(() => {
    void (async () => {
      try {
        const history = await all(post(), orderSchema, props.view)
        requireCurrentView(props.view)
        setOrders(history.reverse())
        const original = own() ? localStorage.getItem(pendingKey()) : null
        if (original !== null && original !== '') {
          setPending(v.parse(checkoutSchema, JSON.parse(original)))
          setPendingMessage('存在待核查的兑换操作。')
        }
        try {
          const directory = await all('/rewards', rewardSchema, props.view)
          requireCurrentView(props.view)
          const balance = own() ? await api(`${props.path}/points`, accountSchema, 'GET', null, props.view) : null
          requireCurrentView(props.view)
          setRewards(directory.sort((a, b) => a.points_cost - b.points_cost))
          setAccount(balance)
        } catch (error) {
          requireCurrentView(props.view)
          setDirectoryError(error instanceof Error ? error.message : '')
        }
      } catch (error) {
        if (!(error instanceof ViewChanged) && isCurrentView(props.view)) actionError(error, props.view)
      }
    })()
  })
  return (
    <Show when={orders()}>
      {history => (
        <Card title="额外权益与兑换记录">
          <div class="space-y-4">
            <Subheading level={3}>虚构权益目录</Subheading>
            <div class="space-y-3">
              <For each={rewards()}>
                {reward => (
                  <RewardItem
                    reward={reward}
                    account={account()}
                    path={props.path}
                    view={props.view}
                    send={send}
                    pendingKey={pendingKey()}
                  />
                )}
              </For>
            </div>
            <Show when={directoryError()}>
              <p class="text-sm/6 text-red-600 dark:text-red-400">{directoryError()}</p>
            </Show>
            <Subheading level={3}>兑换记录</Subheading>
            <Show
              when={history().length}
              fallback={
                <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
                  暂无兑换记录。
                </Text>
              }
            >
              <ol class="divide-y divide-zinc-950/5 dark:divide-white/5">
                <For each={history()}>{order => <RewardOrder order={order} view={props.view} />}</For>
              </ol>
            </Show>
            <Button view={props.view} onAction={() => navigate('rewards')}>
              刷新权益和订单
            </Button>
            <div aria-live="polite">
              <Show when={pending()}>
                {body => (
                  <>
                    <p>{pendingMessage()}</p>
                    <Button view={props.view} onAction={view => send(body(), view)}>
                      用原条件核查兑换
                    </Button>
                  </>
                )}
              </Show>
            </div>
          </div>
        </Card>
      )}
    </Show>
  )
}
