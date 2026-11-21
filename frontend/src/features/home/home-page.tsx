import type { View } from '../../session/session'
import type { SupportSession } from '../support/conversation'
import type { JSX } from '@solidjs/web'
import { createSignal, onSettled, Show } from 'solid-js'
import { all } from '../../api/api'
import { today } from '../../date/date'
import { actionError } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import {
  captureView,
  isCurrentView,
  own,
  referenceKey,
  requireCurrentView,
  scope,
  state,
  ViewChanged,
} from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Text } from '../../ui/typography'
import { DoseSlotList } from '../schedule/schedule-page'
import { supportSessionSchema } from '../support/conversation'
import { HomeSupportInvitations, openSupportSession } from '../support/invitations'
import { SupportConversation } from '../support/support-conversation'

export function HomePage(): JSX.Element {
  const [selected, setSelected] = createSignal<SupportSession | null>()

  async function loadSessions(view: View, patientId: string): Promise<void> {
    const items = await all(`/sessions?patient_id=${encodeURIComponent(patientId)}`, supportSessionSchema, view)
    requireCurrentView(view)
    const stored = sessionStorage.getItem(referenceKey('support-session'))
    setSelected(
      items.find(item => item.session_id === stored) ?? items.filter(item => item.status === 'active').at(-1) ?? null,
    )
  }

  onSettled(() => {
    if (!state.patient || !scope('dialogue:read')) return
    const view = captureView()
    void loadSessions(view, state.patient.patient.patient_id).catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })

  return (
    <div class="space-y-6">
      <Card title="今日待办">
        <div class="space-y-4">
          <Show when={scope('plan:read')}>
            <DoseSlotList
              day={today()}
              empty={
                <div class="space-y-3">
                  <Text>今天没有服药安排。</Text>
                  <Button onAction={() => navigate('profile', 'medication-list')}>填写用药清单</Button>
                </div>
              }
            />
          </Show>
          <Show when={scope('interventions:read')}>
            <HomeSupportInvitations />
          </Show>
        </div>
      </Card>
      <Card
        title="AI 对话"
        actions={
          <Show when={scope('dialogue:read')}>
            <Button variant="plain" onAction={() => navigate('support')}>
              全部会话
            </Button>
          </Show>
        }
      >
        <Show when={scope('dialogue:read')} fallback={<Text>当前未获对话查看权限。</Text>}>
          <Show when={selected() !== undefined} fallback={<Text>正在读取对话…</Text>}>
            <Show
              when={selected()}
              fallback={
                <Show when={own() && state.patient} fallback={<Text>暂无会话。</Text>}>
                  {patient => (
                    <Button
                      variant="primary"
                      onAction={async view => {
                        await openSupportSession(view)
                        await loadSessions(view, patient().patient.patient_id)
                      }}
                    >
                      开始对话
                    </Button>
                  )}
                </Show>
              }
            >
              {session => <SupportConversation session={session()} />}
            </Show>
          </Show>
        </Show>
      </Card>
    </div>
  )
}
