import type { JSX } from '@solidjs/web'
import { createSignal, onSettled, Show } from 'solid-js'
import { ApiError } from '../../api/api'
import { actionError } from '../../notice/notice'
import { captureView, isCurrentView, own, referenceKey, scope, state, ViewChanged } from '../../session/session'
import { loadLatestSubmission } from './profile'
import { ProfilePage } from './profile-page'
import { QuestionnairePage } from './questionnaire-page'

export function AdherencePage(): JSX.Element {
  const [mode, setMode] = createSignal<'result' | 'questionnaire' | null>(null)
  const [latestResponse, setLatestResponse] = createSignal<string | null>(null)
  onSettled(() => {
    if (
      state.response?.status === 'draft' ||
      localStorage.getItem(referenceKey('questionnaire')) !== null ||
      !scope('profile:read')
    ) {
      setMode('questionnaire')
      return
    }
    if (!own()) {
      setMode('result')
      return
    }
    const view = captureView()
    void loadLatestSubmission(view)
      .then(latest => {
        if (isCurrentView(view)) {
          setLatestResponse(latest.response_id)
          setMode('result')
        }
      })
      .catch((error: unknown) => {
        if (
          error instanceof ApiError &&
          error.status === 404 &&
          error.code === 'PROFILE_NOT_AVAILABLE' &&
          isCurrentView(view)
        ) {
          setMode('questionnaire')
        } else if (!(error instanceof ViewChanged) && isCurrentView(view)) {
          actionError(error, view)
        }
      })
  })
  return (
    <Show when={mode()}>
      <Show
        when={mode() === 'questionnaire'}
        fallback={
          <ProfilePage
            onReassess={() => {
              setMode('questionnaire')
            }}
          />
        }
      >
        <QuestionnairePage
          supersedes={latestResponse()}
          onSubmitted={(_view, responseId) => {
            setLatestResponse(responseId)
            setMode('result')
          }}
        />
      </Show>
    </Show>
  )
}
