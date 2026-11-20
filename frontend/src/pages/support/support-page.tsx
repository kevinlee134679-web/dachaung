import type { Invitation } from './home-support-invitations'
import type { SupportSession } from './support-conversation'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import { all } from '../../api/api'
import { dateText } from '../../date/date'
import { actionError } from '../../notice/notice'
import {
  captureView,
  isCurrentView,
  isDemoAdmin,
  own,
  patientPath,
  referenceKey,
  requireCurrentView,
  scope,
  state,
  ViewChanged,
} from '../../session/session'
import { navigate } from '../../shell/navigation'
import { Badge, Button, Card, Disclosure, Text } from '../../ui/components'
import { statusTone } from '../../ui/labels'
import { invitationSchema, InvitationList, openSupportSession } from './home-support-invitations'
import { SupportFeedbackPanel } from './service-feedback'
import { SupportConversation, supportSessionSchema } from './support-conversation'

const supportCases: Record<string, string> = {
  'demo-patient-a-self': 'case-low-mood',
  'demo-patient-b-self': 'case-anxiety',
  'demo-family-self': 'case-fatigue',
}

export function SupportPage(): JSX.Element {
  const [sessions, setSessions] = createSignal<SupportSession[] | null>(null)
  const [selected, setSelected] = createSignal<SupportSession | null>(null)
  const [invitations, setInvitations] = createSignal<Invitation[]>([])
  onSettled(() => {
    if (isDemoAdmin() || !state.patient || !scope('dialogue:read')) return
    const view = captureView()
    const patientId = state.patient.patient.patient_id
    void (async () => {
      const items = await all(`/sessions?patient_id=${encodeURIComponent(patientId)}`, supportSessionSchema, view)
      requireCurrentView(view)
      const stored = sessionStorage.getItem(referenceKey('support-session'))
      const current =
        items.find(item => item.session_id === stored) ?? items.filter(item => item.status === 'active').at(-1) ?? null
      const invites = scope('interventions:read') ? await all(patientPath('/invitations'), invitationSchema, view) : []
      requireCurrentView(view)
      setSessions(items)
      setSelected(current)
      setInvitations(invites)
    })().catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })
  return (
    <Show
      when={!isDemoAdmin()}
      fallback={
        <>
          <p>演示管理员可在「我的」管理虚构案例及故障场景。</p>
          <Button onAction={() => navigate('profile', 'demo')}>打开演示控制台</Button>
        </>
      }
    >
      <Show when={state.patient && scope('dialogue:read')} fallback={<p>请先选择本人或具备专门对话读取授权的对象。</p>}>
        <Card title="AI 情感支持">
          <Show when={own() && sessions() !== null}>
            <div class="flex flex-wrap gap-3">
              <Button variant="primary" onAction={view => openSupportSession(view)}>
                开始自由对话
              </Button>
              <Show when={state.patient && supportCases[state.patient.patient.patient_id]}>
                {caseId => (
                  <Button onAction={view => openSupportSession(view, null, caseId())}>打开虚构案例会话</Button>
                )}
              </Show>
            </div>
          </Show>
        </Card>
        <Show when={sessions()}>
          {items => (
            <>
              <Show
                when={selected()}
                fallback={
                  <Card>
                    <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
                      暂无会话。
                    </Text>
                  </Card>
                }
              >
                {session => <SupportConversation session={session()} />}
              </Show>
              <Show when={invitations().length}>
                <InvitationList items={invitations()} />
              </Show>
              <Show when={items().some(item => item.session_id !== selected()?.session_id)}>
                <Card>
                  <Disclosure summary="其他会话">
                    <For
                      each={items()
                        .toReversed()
                        .filter(item => item.session_id !== selected()?.session_id)}
                    >
                      {item => (
                        <Button
                          onAction={() => {
                            sessionStorage.setItem(referenceKey('support-session'), item.session_id)
                            navigate('support')
                          }}
                        >
                          {dateText(item.opened_at)}
                          {' · '}
                          <Badge tone={statusTone(item.status)}>{item.status === 'closed' ? '已关闭' : '进行中'}</Badge>
                        </Button>
                      )}
                    </For>
                  </Disclosure>
                </Card>
              </Show>
              <Show when={scope('support:read')}>
                <Button onAction={() => navigate('support', 'social')}>查看社会支持</Button>
              </Show>
              <Show when={own() && scope('feedback:read') && scope('services:read')}>
                <SupportFeedbackPanel />
              </Show>
            </>
          )}
        </Show>
      </Show>
    </Show>
  )
}
