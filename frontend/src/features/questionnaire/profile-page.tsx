import type { Profile } from './profile'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import { ApiError, api } from '../../api/api'
import { dateText } from '../../date/date'
import { actionError } from '../../notice/notice'
import {
  captureView,
  isCurrentView,
  own,
  patientPath,
  requireCurrentView,
  scope,
  ViewChanged,
} from '../../session/session'
import { Badge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Text } from '../../ui/typography'
import { generateProfile, loadLatestSubmission, profileSchema } from './profile'

export function ProfilePage(props: { onReassess?: () => void } = {}): JSX.Element {
  const [profile, setProfile] = createSignal<Profile | null>(null)
  const [responseId, setResponseId] = createSignal<string | null>(null)
  const [submittedAt, setSubmittedAt] = createSignal<string | null>(null)
  const [loaded, setLoaded] = createSignal(false)
  onSettled(() => {
    const view = captureView()
    void (async () => {
      try {
        if (own()) {
          const latest = await loadLatestSubmission(view)
          requireCurrentView(view)
          setProfile(latest.profile)
          setResponseId(latest.response_id)
          setSubmittedAt(latest.submitted_at)
        } else {
          const result = await api(patientPath('/profiles/current'), profileSchema, 'GET', null, view)
          requireCurrentView(view)
          setProfile(result)
        }
        setLoaded(true)
      } catch (error) {
        if (
          error instanceof ApiError &&
          error.status === 404 &&
          error.code === 'PROFILE_NOT_AVAILABLE' &&
          isCurrentView(view)
        ) {
          setLoaded(true)
        } else if (!(error instanceof ViewChanged) && isCurrentView(view)) {
          actionError(error, view)
        }
      }
    })()
  })
  return (
    <Show when={loaded()}>
      <div class="space-y-4">
        <Show when={submittedAt()}>{at => <Text>问卷提交于 {dateText(at())}</Text>}</Show>
        <Show when={own() && responseId() !== null && !profile()}>
          <Button
            variant="primary"
            onAction={async view => {
              const result = await generateProfile(responseId() ?? '', view)
              requireCurrentView(view)
              setProfile(result)
            }}
          >
            生成结果
          </Button>
        </Show>
        <Show when={!profile() && responseId() === null}>
          <Text>暂无评估结果。</Text>
        </Show>
        <Show when={profile()}>
          {value => (
            <div class="grid gap-4 sm:grid-cols-2">
              <For each={value().cards}>
                {card => (
                  <Card
                    title={card.title}
                    actions={
                      <Badge tone={card.level === 'good' ? 'teal' : card.level === 'attention' ? 'amber' : 'zinc'}>
                        {{ good: '良好', neutral: '一般', attention: '需要关注' }[card.level]}
                      </Badge>
                    }
                  >
                    <div class="space-y-2">
                      <For each={card.answers}>{answer => <Text>{answer}</Text>}</For>
                      <Text class="whitespace-pre-line">{card.note}</Text>
                    </div>
                  </Card>
                )}
              </For>
            </div>
          )}
        </Show>
        <Show when={scope('questionnaire:assist')}>
          <Button onAction={() => props.onReassess?.()}>重新评估</Button>
        </Show>
      </div>
    </Show>
  )
}
