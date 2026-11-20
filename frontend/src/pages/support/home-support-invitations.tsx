import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { api } from '../../api/api'
import { actionError } from '../../notice/notice'
import {
  captureView,
  isCurrentView,
  own,
  patientPath,
  referenceKey,
  requireCurrentView,
  updateSession,
  ViewChanged,
} from '../../session/session'
import { navigate } from '../../shell/navigation'
import { Badge, Button, Card, Subheading, Text } from '../../ui/components'
import { statusTone } from '../../ui/labels'

export interface Invitation {
  invitation_id: string
  title: string
  description: string
  status: 'pending' | 'accepted' | 'declined' | 'expired' | 'cancelled'
  valid_until: string
  session_id: string | null
}

export const invitationSchema: v.GenericSchema<unknown, Invitation> = v.looseObject({
  invitation_id: v.string(),
  title: v.string(),
  description: v.string(),
  status: v.picklist(['pending', 'accepted', 'declined', 'expired', 'cancelled']),
  valid_until: v.string(),
  session_id: v.nullable(v.string()),
})

export async function openSupportSession(
  view: View,
  invitation: Invitation | null = null,
  caseId: string | null = null,
): Promise<void> {
  const session = await api(
    '/sessions',
    v.looseObject({ session_id: v.string() }),
    'POST',
    {
      patient_id: view.patientId,
      case_id: caseId,
      entry_source: invitation ? 'accepted_invitation' : 'user',
      invitation_id: invitation?.invitation_id ?? null,
    },
    view,
  )
  requireCurrentView(view)
  sessionStorage.setItem(referenceKey('support-session'), session.session_id)
  navigate('support')
}

export function refreshSupport(view: View): void {
  requireCurrentView(view)
  updateSession(draft => {
    draft.epoch++
  })
}

export function InvitationList(props: { items: Invitation[]; evaluatedAt?: string }): JSX.Element {
  const labels: Record<string, string> = {
    accepted: '已接受',
    declined: '已拒绝',
    cancelled: '已取消',
    expired: '已到期',
  }
  const expired = (item: Invitation) =>
    Date.parse(item.valid_until) <= Date.parse(props.evaluatedAt ?? new Date().toISOString())
  async function respond(item: Invitation, choice: string, view: View): Promise<void> {
    await api(
      `/invitations/${encodeURIComponent(item.invitation_id)}/response`,
      v.unknown(),
      'POST',
      { choice, expected_status: 'pending', session_id: null },
      view,
    )
    requireCurrentView(view)
    if (choice === 'accepted') await openSupportSession(view, item)
    else refreshSupport(view)
  }
  return (
    <Card title="支持邀请">
      <ul class="divide-y divide-zinc-950/5 dark:divide-white/5">
        <For each={props.items}>
          {item => (
            <li class="space-y-3 py-4 first:pt-0 last:pb-0">
              <Subheading level={3}>{item.title}</Subheading>
              <Text>{item.description}</Text>
              <Show
                when={item.status === 'pending' && expired(item)}
                fallback={
                  <Show
                    when={item.status === 'pending' && own()}
                    fallback={
                      <Show
                        when={item.status === 'accepted' && !expired(item) && own()}
                        fallback={<Badge tone={statusTone(item.status)}>{labels[item.status] ?? '等待本人响应'}</Badge>}
                      >
                        <Button onAction={view => openSupportSession(view, item)}>进入已接受的邀请</Button>
                      </Show>
                    }
                  >
                    <div class="flex flex-wrap gap-3">
                      <Button variant="primary" onAction={view => respond(item, 'accepted', view)}>
                        接受并进入对话
                      </Button>
                      <Button onAction={view => respond(item, 'declined', view)}>拒绝邀请</Button>
                    </div>
                  </Show>
                }
              >
                <Badge tone={statusTone('expired')}>已到期 · 历史待维护</Badge>
              </Show>
            </li>
          )}
        </For>
      </ul>
    </Card>
  )
}

export function HomeSupportInvitations(): JSX.Element {
  const [items, setItems] = createSignal<Invitation[]>([])
  onSettled(() => {
    const view = captureView()
    void api(patientPath('/invitations'), v.looseObject({ items: v.array(invitationSchema) }), 'GET', null, view)
      .then(data => {
        requireCurrentView(view)
        setItems(
          data.items.filter(
            item =>
              (item.session_id === null || item.session_id === '') && ['pending', 'accepted'].includes(item.status),
          ),
        )
      })
      .catch((error: unknown) => {
        if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
      })
  })
  return (
    <Show when={items().length > 0}>
      <InvitationList items={items()} />
    </Show>
  )
}
