import type { View } from '../../session/session'
import type { Question, Theme, Response, LegacyResponse } from './answers'
import type { JSX } from '@solidjs/web'
import { createSignal, For, Show, untrack } from 'solid-js'
import { api } from '../../api/api'
import { notice } from '../../notice/notice'
import { requireCurrentView, updateSession } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Checkbox, Field, Fieldset, Input, Select } from '../../ui/form'
import { Subheading, Text } from '../../ui/typography'
import {
  normalizeAnswer,
  answerDefault,
  responseSchema,
  primaryAnswer,
  rankingOf,
  answerWithOther,
  concernAnswer,
  frequencyAnswer,
} from './answers'

export function QuestionForm(props: {
  question: Question<LegacyResponse>
  theme: Theme
  onSaved: (response: Response, index: number) => void
  onSubmitted?: ((response: Response, view: View) => Promise<void>) | undefined
}): JSX.Element {
  const question = untrack(() => props.question)
  const theme = untrack(() => props.theme)
  const id = theme.question_id
  const old = question.response.answers[id]
  const [value, setValue] = createSignal(
    old.state === 'answered'
      ? normalizeAnswer(structuredClone(old.value ?? answerDefault(id)))
      : structuredClone(old.value ?? answerDefault(id)),
  )
  const [answerState, setAnswerState] = createSignal(old.state)
  const [confirmed, setConfirmed] = createSignal(false)
  const single = ['Q1', 'Q3', 'Q6'].includes(id)
  const maxRank = id === 'Q4' ? 2 : 3
  let dragged: string | null = null

  function optionLabel(code: string): string {
    const option = theme.options.find(item => item.code === code)
    if (!option) throw new Error(`Unknown option ${code}`)
    return option.label
  }

  function chosen(code: string): boolean {
    const current = value()
    if ('primary' in current) return current.primary === code
    if ('choice' in current) return current.choice === code
    if ('confidence_level' in current) return String(current.confidence_level) === code
    return current.selected.includes(code)
  }

  function choose(code: string, checked: boolean): void {
    const next = structuredClone(value())
    if ('primary' in next) {
      next.primary = code
      next.additional = next.additional.filter(item => item !== code)
    } else if ('choice' in next) {
      next.choice = code
    } else if ('confidence_level' in next) {
      next.confidence_level = Number(code)
    } else {
      next.selected = checked
        ? code === 'none'
          ? ['none']
          : [...next.selected.filter(item => item !== 'none'), code]
        : next.selected.filter(item => item !== code)
      if ('top_ranked' in next) next.top_ranked = next.top_ranked.filter(item => next.selected.includes(item))
      if ('top_concerns' in next) next.top_concerns = next.top_concerns.filter(item => next.selected.includes(item))
      if ('ranked' in next) next.ranked = next.ranked.filter(item => next.selected.includes(item))
      if ('other_text' in next && !next.selected.includes('other')) next.other_text = null
    }
    setValue(next)
  }

  function setRank(items: string[]): void {
    const current = value()
    if ('top_ranked' in current) setValue({ ...current, top_ranked: items })
    else if ('top_concerns' in current) setValue({ ...current, top_concerns: items })
    else if ('ranked' in current) setValue({ ...current, ranked: items })
  }

  function moveRank(ranked: string[], item: string, index: number): void {
    const items = ranked.filter(code => code !== item)
    items.splice(index, 0, item)
    setRank(items)
  }

  async function save(view: View): Promise<Response> {
    const answers = Object.fromEntries(
      Object.entries(question.response.answers).map(([key, answer]) => [
        key,
        { state: answer.state, value: answer.value },
      ]),
    )
    answers[id] = { state: answerState(), value: answerState() === 'answered' ? value() : null }
    const response = await api(
      `/questionnaire-responses/${question.response.response_id}/answers`,
      responseSchema,
      'PUT',
      { expected_revision: question.response.meta.revision, answers },
      view,
    )
    requireCurrentView(view)
    updateSession(draft => {
      draft.response = response
    })
    return response
  }

  return (
    <Card>
      <div class="space-y-6">
        <Text>第 {question.index + 1} 题，共 8 题</Text>
        <div
          class="h-2 rounded-full bg-zinc-100 dark:bg-zinc-800"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={8}
          aria-valuenow={question.index}
        >
          <div
            class="h-full rounded-full bg-teal-600 dark:bg-teal-400"
            style={{ width: `${(question.index / 8) * 100}%` }}
          />
        </div>
        <div class="sr-only">
          <Subheading>{theme.prompt}</Subheading>
        </div>
        <Fieldset legend={theme.prompt}>
          <div class="flex flex-wrap gap-4">
            <For
              each={[
                { state: 'answered', label: '选择或填写' },
                { state: 'unknown', label: '不清楚 / 无法判断' },
                { state: 'not_applicable', label: '不适用' },
              ]}
            >
              {item => (
                <label
                  class={`flex min-h-11 cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm/6 ring-1 transition-colors duration-75 ring-inset motion-reduce:transition-none ${answerState() === item.state ? 'bg-teal-50 text-teal-900 ring-teal-600 dark:bg-teal-500/10 dark:text-teal-100 dark:ring-teal-400' : 'text-zinc-950 ring-zinc-950/10 hover:bg-zinc-50 dark:text-white dark:ring-white/10 dark:hover:bg-white/5'}`}
                >
                  <input
                    type="radio"
                    class="size-4 accent-teal-600"
                    name="answer-state"
                    value={item.state}
                    checked={answerState() === item.state}
                    onChange={() => {
                      if (item.state === 'answered') setValue(normalizeAnswer(structuredClone(value())))
                      setAnswerState(item.state)
                    }}
                  />
                  {item.label}
                </label>
              )}
            </For>
          </div>
          <Show
            when={answerState() === 'answered'}
            fallback={
              <Text>
                {answerState() === 'not_answered'
                  ? '请选择回答方式；未答题可以先保存进度。'
                  : '本题将保留所选状态，不会填成零。'}
              </Text>
            }
          >
            <div class="grid gap-2">
              <For each={theme.options}>
                {option => (
                  <label
                    class={`flex min-h-11 cursor-pointer items-center gap-3 rounded-lg px-4 py-2 text-sm/6 ring-1 transition-colors duration-75 ring-inset motion-reduce:transition-none ${chosen(option.code) ? 'bg-teal-50 text-teal-900 ring-teal-600 dark:bg-teal-500/10 dark:text-teal-100 dark:ring-teal-400' : 'text-zinc-950 ring-zinc-950/10 hover:bg-zinc-50 dark:text-white dark:ring-white/10 dark:hover:bg-white/5'}`}
                  >
                    <input
                      type={single ? 'radio' : 'checkbox'}
                      class="size-4 accent-teal-600"
                      name="answer-option"
                      value={option.code}
                      checked={chosen(option.code)}
                      onChange={event => choose(option.code, event.currentTarget.checked)}
                    />
                    {option.label}
                  </label>
                )}
              </For>
            </div>
            <Show when={primaryAnswer(value())}>
              {answer => (
                <Fieldset legend="还有其他情况吗？（可选）">
                  <For each={theme.options.filter(option => option.code !== answer().primary)}>
                    {option => (
                      <Checkbox
                        label={option.label}
                        checked={answer().additional.includes(option.code)}
                        onChange={event => {
                          setValue({
                            ...answer(),
                            additional: event.currentTarget.checked
                              ? [...answer().additional, option.code]
                              : answer().additional.filter(item => item !== option.code),
                          })
                        }}
                      />
                    )}
                  </For>
                </Fieldset>
              )}
            </Show>
            <Show when={rankingOf(value())}>
              {ranking => (
                <>
                  <Text>可选：标出最重要的{maxRank}项，可拖动或用按钮调整顺序。</Text>
                  <div class="flex flex-wrap gap-2">
                    <For each={ranking().selected.filter(item => item !== 'none' && !ranking().ranked.includes(item))}>
                      {item => (
                        <Button
                          onAction={() => {
                            if (ranking().ranked.length >= maxRank) throw new Error(`最多选择${maxRank}项优先内容。`)
                            setRank([...ranking().ranked, item])
                          }}
                        >
                          加入优先项：{optionLabel(item)}
                        </Button>
                      )}
                    </For>
                  </div>
                  <For each={ranking().ranked}>
                    {(item, index) => (
                      <div
                        class="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-950/5 py-3 dark:border-white/5"
                        draggable="true"
                        onDragStart={() => {
                          dragged = item
                        }}
                        onDragOver={event => event.preventDefault()}
                        onDrop={event => {
                          event.preventDefault()
                          if (dragged !== null && dragged !== '') moveRank(ranking().ranked, dragged, index())
                        }}
                      >
                        <span>
                          {index() + 1}. {optionLabel(item)}
                        </span>
                        <div class="flex gap-2">
                          <Button
                            disabled={index() === 0}
                            onAction={() => {
                              moveRank(ranking().ranked, item, index() - 1)
                            }}
                          >
                            上移
                          </Button>
                          <Button
                            disabled={index() === ranking().ranked.length - 1}
                            onAction={() => {
                              moveRank(ranking().ranked, item, index() + 1)
                            }}
                          >
                            下移
                          </Button>
                          <Button
                            onAction={() => {
                              setRank(ranking().ranked.filter(code => code !== item))
                            }}
                          >
                            移除
                          </Button>
                        </div>
                      </div>
                    )}
                  </For>
                </>
              )}
            </Show>
            <Show when={answerWithOther(value())}>
              {answer => (
                <Field label="其他原因（简短即可）">
                  <Input
                    value={answer().other_text ?? ''}
                    onInput={event => {
                      setValue({
                        ...answer(),
                        other_text: event.currentTarget.value === '' ? null : event.currentTarget.value,
                      })
                    }}
                  />
                </Field>
              )}
            </Show>
            <Show when={concernAnswer(value())}>
              {answer => (
                <Field label="担忧程度（可不补充，仅描述）">
                  <Select
                    value={answer().intensity ?? ''}
                    onChange={event => {
                      setValue({
                        ...answer(),
                        intensity: event.currentTarget.value === '' ? null : Number(event.currentTarget.value),
                      })
                    }}
                  >
                    <option value="">不补充</option>
                    <For each={[0, 1, 2, 3, 4]}>{number => <option value={number}>{number}</option>}</For>
                  </Select>
                </Field>
              )}
            </Show>
            <Show when={frequencyAnswer(value())}>
              {answer => (
                <Field label="发生频率（可不补充）">
                  <Select
                    value={answer().frequency ?? ''}
                    onChange={event => {
                      setValue({
                        ...answer(),
                        frequency: event.currentTarget.value === '' ? null : event.currentTarget.value,
                      })
                    }}
                  >
                    <option value="">不补充</option>
                    <option value="never">从不</option>
                    <option value="occasionally">偶尔</option>
                    <option value="often">经常</option>
                  </Select>
                </Field>
              )}
            </Show>
          </Show>
        </Fieldset>
        <div class="flex flex-wrap gap-3">
          <Button
            disabled={question.index === 0}
            onAction={async view => props.onSaved(await save(view), question.index - 1)}
          >
            上一题
          </Button>
          <Button
            onAction={async view => {
              props.onSaved(await save(view), question.index)
              notice('进度已保存，稍后可继续。')
            }}
          >
            保存进度
          </Button>
          <Button
            variant="primary"
            onAction={async view => props.onSaved(await save(view), Math.min(question.index + 1, 7))}
          >
            {question.index === 7 ? '保存最后一题' : '保存并下一题'}
          </Button>
        </div>
        <Show when={question.index === 7}>
          <Checkbox
            label="我确认提交本次回答（不清楚与不适用会如实保留）"
            checked={confirmed()}
            onChange={event => {
              setConfirmed(event.currentTarget.checked)
            }}
          />
          <Button
            variant="primary"
            onAction={async view => {
              if (!confirmed()) throw new Error('请先明确确认提交。')
              const saved = await save(view)
              requireCurrentView(view)
              const response = await api(
                `/questionnaire-responses/${question.response.response_id}/submit`,
                responseSchema,
                'POST',
                { expected_revision: saved.meta.revision, confirmed: true },
                view,
              )
              requireCurrentView(view)
              props.onSaved(response, question.index)
              if (props.onSubmitted) await props.onSubmitted(response, view)
              else notice('回答已提交。可以主动生成描述性画像。')
            }}
          >
            {props.onSubmitted ? '提交问卷并生成画像' : '提交问卷'}
          </Button>
        </Show>
      </div>
    </Card>
  )
}
