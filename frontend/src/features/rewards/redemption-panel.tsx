import type { View } from '../../session/session'
import type { Order, Reward, Account, Checkout } from './redemption'
import type { JSX } from '@solidjs/web'
import { createMemo, createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api, ApiError } from '../../api/api'
import { actionError, notice } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import { isCurrentView, own, requireCurrentView, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { EmptyState, List } from '../../ui/list'
import { Subheading } from '../../ui/typography'
import { orderSchema, checkoutSchema, rewardSchema, accountSchema } from './redemption'
import { RewardItem } from './reward-item'
import { RewardOrder } from './reward-order'

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
            <Show when={history().length} fallback={<EmptyState>暂无兑换记录。</EmptyState>}>
              <List ordered>
                <For each={history()}>{order => <RewardOrder order={order} view={props.view} />}</For>
              </List>
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
