import type { View } from '../../session/session'
import type { Definition, QuestionnaireResponse } from './questionnaire'
import type { JSX } from '@solidjs/web'
import { createSignal, onSettled, Show, untrack } from 'solid-js'
import { ApiError } from '../../api/api'
import { actionError, notice } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import {
  captureView,
  isCurrentView,
  own,
  referenceKey,
  requireCurrentView,
  scope,
  state,
  updateSession,
  ViewChanged,
} from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { confirm } from '../../ui/confirm'
import { generateProfile } from './profile'
import { QuestionWizard } from './question-wizard'
import { loadDefinition, loadResponse, startResponse } from './questionnaire'

const privacyText = `本问卷收集的信息仅用于生成你的用药情况评估，并为你提供用药提醒和支持建议。
使用 AI 支持对话时，相关的问卷要点会发送给大模型服务（DeepSeek）用于生成回复。
不想回答的题目可以选择“无法判断”，选填部分可以整段跳过。本平台为演示项目，账号与数据均为虚构。
点击“确认”即表示你已阅读并同意以上说明。`

export function QuestionnairePage(props: {
  onSubmitted?: (view: View, responseId: string) => void
  supersedes?: string | null
}): JSX.Element {
  const [definition, setDefinition] = createSignal<Definition | null>(null)
  const [response, setResponse] = createSignal<QuestionnaireResponse | null>(null)
  const view = untrack(captureView)
  const allowed = untrack(() => scope('questionnaire:assist'))
  onSettled(() => {
    if (!allowed) return
    void (async () => {
      try {
        const result = await loadDefinition(view)
        requireCurrentView(view)
        const key = referenceKey('questionnaire')
        const reference = localStorage.getItem(key)
        let saved = state.response
        if (!saved && reference !== null && reference !== '') {
          try {
            saved = await loadResponse(reference, view)
            requireCurrentView(view)
          } catch (error) {
            requireCurrentView(view)
            if (!(error instanceof ApiError) || error.status !== 404 || error.code !== 'RESOURCE_NOT_FOUND') throw error
            localStorage.removeItem(key)
          }
        }
        setDefinition(result)
        if (saved?.status === 'draft') setResponse(saved)
      } catch (error) {
        if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
      }
    })()
  })
  async function submitted(saved: QuestionnaireResponse, actionView: View): Promise<void> {
    requireCurrentView(actionView)
    localStorage.removeItem(referenceKey('questionnaire'))
    updateSession(draft => {
      draft.response = null
    })
    if (own()) await generateProfile(saved.response_id, actionView)
    else notice('问卷已提交。')
    requireCurrentView(actionView)
    if (props.onSubmitted) props.onSubmitted(actionView, saved.response_id)
    else navigate('profile', 'adherence')
  }
  return (
    <Show when={allowed} fallback={<p>当前未获问卷作答权限。</p>}>
      <Show when={definition()}>
        {loaded => (
          <Show
            when={response()}
            fallback={
              <Card>
                <div class="space-y-4">
                  <p>{loaded().purpose}</p>
                  <Button
                    variant="primary"
                    onAction={async actionView => {
                      if (!(await confirm(privacyText))) return
                      requireCurrentView(actionView)
                      const saved = await startResponse(actionView, props.supersedes ?? null)
                      requireCurrentView(actionView)
                      localStorage.setItem(referenceKey('questionnaire'), saved.response_id)
                      updateSession(draft => {
                        draft.response = saved
                      })
                      setResponse(saved)
                    }}
                  >
                    开始评估
                  </Button>
                </div>
              </Card>
            }
            keyed
          >
            {saved => <QuestionWizard definition={loaded()} response={saved} onSubmitted={submitted} />}
          </Show>
        )}
      </Show>
    </Show>
  )
}
