import type { View } from '../../session/session'
import type { AnswerValue, Definition, Field, QuestionnaireResponse, Theme } from './questionnaire'
import type { JSX } from '@solidjs/web'
import { createMemo, createSignal, For, Show, untrack } from 'solid-js'
import { actionError } from '../../notice/notice'
import { captureView, isCurrentView, own, requireCurrentView, updateSession, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Checkbox } from '../../ui/form'
import { Subheading, Text } from '../../ui/typography'
import { clearHidden, saveTheme, submitResponse, visibleFields } from './questionnaire'

type Step = { kind: 'field'; theme: Theme; field: Field } | { kind: 'optional' } | { kind: 'submit' }

export function QuestionWizard(props: {
  definition: Definition
  response: QuestionnaireResponse
  onSubmitted: (response: QuestionnaireResponse, view: View) => void | Promise<void>
}): JSX.Element {
  const [response, setResponse] = createSignal(untrack(() => props.response))
  const [sameEpisode, setSameEpisode] = createSignal(false)
  const [confirmed, setConfirmed] = createSignal(false)
  const [busy, setBusy] = createSignal(false)
  const answerValue = (questionId: Theme['question_id']): AnswerValue => response().answers[questionId].value
  const steps = createMemo<Step[]>(() => {
    const result: Step[] = []
    let optional = false
    for (const theme of props.definition.themes) {
      if (theme.section === 'optional' && !optional) {
        result.push({ kind: 'optional' })
        optional = true
      }
      for (const field of visibleFields(theme, answerValue(theme.question_id)))
        result.push({ kind: 'field', theme, field })
    }
    result.push({ kind: 'submit' })
    return result
  })
  const initial = untrack(() =>
    steps().findIndex(
      step =>
        step.kind === 'field' && !step.field.optional && answerValue(step.theme.question_id)[step.field.key] == null,
    ),
  )
  const [index, setIndex] = createSignal(initial < 0 ? untrack(() => steps().length - 1) : initial)
  const current = () => steps()[index()]
  const currentField = () => {
    const step = current()
    return step?.kind === 'field' ? step : undefined
  }

  async function choose(theme: Theme, field: Field, code: string | number): Promise<void> {
    const view = captureView()
    const value: AnswerValue = { ...answerValue(theme.question_id) }
    if (field.kind === 'multiple') {
      const previous = value[field.key]
      const selected = Array.isArray(previous) ? previous : []
      const exclusive = field.exclusive ?? []
      value[field.key] = selected.includes(String(code))
        ? selected.filter(item => item !== code)
        : exclusive.includes(String(code))
          ? [String(code)]
          : [...selected.filter(item => !exclusive.includes(item)), String(code)]
    } else {
      value[field.key] = code
    }
    setBusy(true)
    try {
      const saved = await saveTheme(response(), theme.question_id, clearHidden(theme, value), view)
      requireCurrentView(view)
      updateSession(draft => {
        draft.response = saved
      })
      setResponse(saved)
      if (field.kind !== 'multiple' && !field.optional) setIndex(index() + 1)
    } catch (error) {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <div class="space-y-5">
        <Show when={currentField()}>
          {step => {
            const value = () => answerValue(step().theme.question_id)[step().field.key]
            const selected = (code: string | number) => {
              const answer = value()
              return Array.isArray(answer) ? answer.includes(String(code)) : answer === code
            }
            const answered = () => {
              const answer = value()
              return Array.isArray(answer) ? answer.length > 0 : answer != null
            }
            return (
              <>
                <Subheading>{step().theme.title}</Subheading>
                <Text>
                  第{' '}
                  {
                    steps()
                      .slice(0, index() + 1)
                      .filter(item => item.kind === 'field').length
                  }{' '}
                  / {steps().filter(item => item.kind === 'field').length} 题
                </Text>
                <div class="h-1.5 rounded-full bg-zinc-200 dark:bg-zinc-700">
                  <div
                    class="h-full rounded-full bg-teal-600"
                    style={{ width: `${Math.min(100, ((index() + 1) / steps().length) * 100)}%` }}
                  />
                </div>
                <p class="font-medium">{step().field.prompt}</p>
                <div
                  class="grid gap-2"
                  role={step().field.kind === 'multiple' ? 'group' : 'radiogroup'}
                  aria-label={step().field.prompt}
                >
                  <For each={step().field.options}>
                    {option => (
                      <button
                        type="button"
                        role={step().field.kind === 'multiple' ? 'checkbox' : 'radio'}
                        aria-checked={selected(option.code) ? 'true' : 'false'}
                        disabled={busy()}
                        class={`rounded-xl border px-4 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600 ${selected(option.code) ? 'border-teal-600 bg-teal-50 text-teal-900 dark:border-teal-400 dark:bg-teal-950 dark:text-teal-100' : 'border-zinc-200 text-zinc-900 hover:border-zinc-300 dark:border-zinc-700 dark:text-zinc-100 dark:hover:border-zinc-500'}`}
                        onClick={() => void choose(step().theme, step().field, option.code)}
                      >
                        {option.label}
                      </button>
                    )}
                  </For>
                </div>
                <Show when={step().field.optional === true || answered()}>
                  <Button onAction={() => setIndex(index() + 1)}>下一题</Button>
                </Show>
              </>
            )
          }}
        </Show>
        <Show when={current()?.kind === 'optional'}>
          <Text>以下题目用于模型评估，可选填写</Text>
          <div class="flex flex-wrap gap-3">
            <Button variant="primary" onAction={() => setIndex(index() + 1)}>
              继续填写
            </Button>
            <Button onAction={() => setIndex(steps().length - 1)}>跳过选填部分</Button>
          </div>
        </Show>
        <Show when={current()?.kind === 'submit'}>
          <Subheading>提交问卷</Subheading>
          <Show when={own()}>
            <Checkbox
              label="我确认 Q1–Q3 回答的是本人同一次规律用药经历"
              checked={sameEpisode()}
              onChange={event => {
                setSameEpisode(event.currentTarget.checked)
              }}
            />
          </Show>
          <Checkbox
            label="我确认提交本次问卷，留空项按未答保存"
            checked={confirmed()}
            onChange={event => {
              setConfirmed(event.currentTarget.checked)
            }}
          />
          <Button
            variant="primary"
            disabled={!confirmed()}
            onAction={async view => {
              const submitted = await submitResponse(response(), own() ? sameEpisode() : null, view)
              requireCurrentView(view)
              await props.onSubmitted(submitted, view)
            }}
          >
            提交问卷
          </Button>
        </Show>
        <Button variant="plain" disabled={index() === 0 || busy()} onAction={() => setIndex(index() - 1)}>
          上一题
        </Button>
      </div>
    </Card>
  )
}
