import type { View } from '../../session/session'
import type { Order, Delivery } from './redemption'
import type { JSX } from '@solidjs/web'
import { createMemo, createSignal, Show } from 'solid-js'
import { api } from '../../api/api'
import { own, requireCurrentView } from '../../session/session'
import { Badge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { statusTone } from '../../ui/labels'
import { Text } from '../../ui/typography'
import { openServiceRecord } from '../services/navigation'
import { orderSchema, deliverySchema, fulfillmentStatus, saveRewardText } from './redemption'
import { RewardFeedback } from './reward-feedback'

export function RewardOrder(props: { order: Order; view: View }): JSX.Element {
  const detail = createMemo(() => `/redemptions/${encodeURIComponent(props.order.redemption_id)}`)
  const [result, setResult] = createSignal<{ current: Order; delivery: Delivery }>()
  return (
    <li class="space-y-3">
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
