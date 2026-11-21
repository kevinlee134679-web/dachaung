import type { View } from '../../session/session'
import type { Reward, Account, Checkout, Resource, ServiceConfirmation } from './redemption'
import type { JSX } from '@solidjs/web'
import { createSignal, Show } from 'solid-js'
import * as v from 'valibot'
import { all } from '../../api/api'
import { requireCurrentView } from '../../session/session'
import { Badge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { confirm } from '../../ui/confirm'
import { Disclosure } from '../../ui/disclosure'
import { Checkbox, Field, Textarea } from '../../ui/form'
import { statusTone } from '../../ui/labels'
import { Text } from '../../ui/typography'
import { serviceWrite } from '../services/draft-data'
import { rewardAvailability, resourceSchema } from './redemption'

export function RewardItem(props: {
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
