import type { View } from '../../session/session'
import type { Response, Definition, Question } from './answers'
import type { JSX } from '@solidjs/web'
import { createSignal, flush, onSettled, Show, untrack } from 'solid-js'
import { ApiError, api } from '../../api/api'
import { actionError } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import {
  captureView,
  isCurrentView,
  own,
  patientPath,
  referenceKey,
  requireCurrentView,
  scope,
  state,
  updateSession,
  ViewChanged,
} from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { definitionSchema, responseSchema } from './answers'
import { QuestionForm } from './question-form'

let lastQuestion: { responseId: string; index: number } | null = null

export function QuestionnairePage(props: {
  onSubmitted?: (response: Response, view: View) => Promise<void>
}): JSX.Element {
  const [definition, setDefinition] = createSignal<Definition | null>(null)
  const [question, setQuestion] = createSignal<Question | null>(null)
  const allowed = untrack(() => scope('questionnaire:assist'))
  const view = untrack(captureView)

  function publish(response: Response, index: number): void {
    requireCurrentView(view)
    lastQuestion = { responseId: response.response_id, index }
    updateSession(draft => {
      draft.response = response
    })
    setQuestion({ response, index })
    flush()
  }

  onSettled(() => {
    if (!allowed) return
    void (async () => {
      try {
        const result = await api('/questionnaires/initial', definitionSchema, 'GET', null, view)
        requireCurrentView(view)
        const key = referenceKey('questionnaire')
        const reference = localStorage.getItem(key)
        let response = state.response
        let index = response && lastQuestion?.responseId === response.response_id ? lastQuestion.index : 0
        if (!response && reference !== null && reference !== '') {
          try {
            response = await api(`/questionnaire-responses/${reference}`, responseSchema, 'GET', null, view)
            requireCurrentView(view)
            if (response.status === 'draft') {
              const pending = Object.values(response.answers).findIndex(answer => answer.state === 'not_answered')
              index = pending < 0 ? 7 : pending
            }
          } catch (error) {
            requireCurrentView(view)
            if (!(error instanceof ApiError) || error.status !== 404 || error.code !== 'RESOURCE_NOT_FOUND') throw error
            localStorage.removeItem(key)
          }
        }
        requireCurrentView(view)
        setDefinition(result)
        if (response) publish(response, index)
      } catch (error) {
        if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
      }
    })()
  })

  async function start(actionView: View, version: string, previous?: Response): Promise<void> {
    const response = await api(
      patientPath('/questionnaire-responses'),
      responseSchema,
      'POST',
      {
        questionnaire_version: version,
        ...(previous ? { supersedes_response_id: previous.response_id } : {}),
      },
      actionView,
    )
    requireCurrentView(actionView)
    localStorage.setItem(referenceKey('questionnaire'), response.response_id)
    publish(response, 0)
  }

  return (
    <Show when={allowed} fallback={<p>当前未获问卷作答权限。</p>}>
      <Show when={definition()}>
        {loaded => (
          <Show
            when={question()}
            fallback={
              <Card>
                <div class="space-y-4">
                  <p>{loaded().purpose}</p>
                  <p>{own() ? '请根据自己的情况作答。' : '你正在协助患者作答。不了解其主观感受时，请选择不清楚。'}</p>
                  <Button variant="primary" onAction={async view => start(view, loaded().version)}>
                    开始八题问卷
                  </Button>
                </div>
              </Card>
            }
            keyed
          >
            {current => (
              <Show
                when={current.response.status !== 'submitted'}
                fallback={
                  <Card>
                    <p>本次回答已经提交，原回答会保留。</p>
                    <div class="my-5 flex flex-wrap gap-3">
                      <Show when={props.onSubmitted}>
                        {submitted => (
                          <Button variant="primary" onAction={view => submitted()(current.response, view)}>
                            继续
                          </Button>
                        )}
                      </Show>
                      <Show when={!props.onSubmitted}>
                        <Button variant="primary" onAction={() => navigate('profile', 'assessment')}>
                          查看画像结果
                        </Button>
                      </Show>
                      <Button onAction={async view => start(view, loaded().version, current.response)}>
                        重新填写或更正
                      </Button>
                    </div>
                  </Card>
                }
              >
                <Show when={loaded().themes[current.index]} keyed>
                  {theme => (
                    <QuestionForm question={current} theme={theme} onSaved={publish} onSubmitted={props.onSubmitted} />
                  )}
                </Show>
              </Show>
            )}
          </Show>
        )}
      </Show>
    </Show>
  )
}
