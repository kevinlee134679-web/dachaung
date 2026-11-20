import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, flush, For, onSettled, Show, untrack } from 'solid-js'
import * as v from 'valibot'
import { ApiError, api } from '../../api/api'
import { copyValue } from '../../data/copy'
import { actionError, notice } from '../../notice/notice'
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
import { navigate } from '../../shell/navigation'
import { Button, Card, Checkbox, Field, Fieldset, Input, Select, Subheading, Text } from '../../ui/components'

type QuestionId = 'Q1' | 'Q2' | 'Q3' | 'Q4' | 'Q5' | 'Q6' | 'Q7' | 'Q8'

interface PrimaryAnswer {
  primary: string | null
  additional: string[]
}

interface OtherAnswer {
  selected: string[]
  top_ranked: string[]
  other_text: string | null
}

interface ChoiceAnswer {
  choice: string | null
}

interface ConcernAnswer {
  selected: string[]
  top_concerns: string[]
  intensity: number | null
}

interface FrequencyAnswer {
  selected: string[]
  frequency: string | null
}

interface ConfidenceAnswer {
  confidence_level: number | null
}

interface SelectionAnswer {
  selected: string[]
}

interface RankedAnswer {
  selected: string[]
  ranked: string[]
}

// the field set tells the questions apart, matching the backend's validate_answers
type AnswerValue =
  | PrimaryAnswer
  | OtherAnswer
  | ChoiceAnswer
  | ConcernAnswer
  | FrequencyAnswer
  | ConfidenceAnswer
  | SelectionAnswer
  | RankedAnswer

interface Ranking {
  selected: string[]
  ranked: string[]
}

interface Answer {
  state: string
  value: AnswerValue | null
}

export interface Response {
  response_id: string
  status: string
  answers: Record<QuestionId, Answer>
  meta: { revision: number }
}

interface Theme {
  question_id: QuestionId
  prompt: string
  options: { code: string; label: string }[]
}

interface Definition {
  purpose: string
  version: string
  themes: Theme[]
}

function answerSchema(value: v.GenericSchema<unknown, AnswerValue>) {
  return v.looseObject({
    state: v.picklist(['answered', 'unknown', 'not_applicable', 'not_answered']),
    value: v.nullable(value),
  })
}
const responseSchema: v.GenericSchema<unknown, Response> = v.looseObject({
  response_id: v.string(),
  status: v.string(),
  answers: v.looseObject({
    Q1: answerSchema(v.looseObject({ primary: v.string(), additional: v.array(v.string()) })),
    Q2: answerSchema(
      v.looseObject({
        selected: v.array(v.string()),
        top_ranked: v.array(v.string()),
        other_text: v.nullable(v.string()),
      }),
    ),
    Q3: answerSchema(v.looseObject({ choice: v.string() })),
    Q4: answerSchema(
      v.looseObject({
        selected: v.array(v.string()),
        top_concerns: v.array(v.string()),
        intensity: v.nullable(v.number()),
      }),
    ),
    Q5: answerSchema(
      v.looseObject({
        selected: v.array(v.string()),
        frequency: v.nullable(v.picklist(['never', 'occasionally', 'often'])),
      }),
    ),
    Q6: answerSchema(v.looseObject({ confidence_level: v.number() })),
    Q7: answerSchema(v.looseObject({ selected: v.array(v.string()) })),
    Q8: answerSchema(v.looseObject({ selected: v.array(v.string()), ranked: v.array(v.string()) })),
  }),
  meta: v.looseObject({ revision: v.number() }),
})
const definitionSchema: v.GenericSchema<unknown, Definition> = v.looseObject({
  purpose: v.string(),
  version: v.string(),
  themes: v.array(
    v.looseObject({
      question_id: v.picklist(['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8']),
      prompt: v.string(),
      options: v.array(v.looseObject({ code: v.string(), label: v.string() })),
    }),
  ),
})

interface Question {
  response: Response
  index: number
}

let lastQuestion: { responseId: string; index: number } | null = null

function answerDefault(question: QuestionId): AnswerValue {
  switch (question) {
    case 'Q1':
      return { primary: null, additional: [] }
    case 'Q2':
      return { selected: [], top_ranked: [], other_text: null }
    case 'Q3':
      return { choice: null }
    case 'Q4':
      return { selected: [], top_concerns: [], intensity: null }
    case 'Q5':
      return { selected: [], frequency: null }
    case 'Q6':
      return { confidence_level: null }
    case 'Q7':
      return { selected: [] }
    case 'Q8':
    default:
      return { selected: [], ranked: [] }
  }
}

function normalizeAnswer(value: AnswerValue): AnswerValue {
  if ('primary' in value) value.additional = value.additional.filter(item => item !== value.primary)
  if ('other_text' in value && !value.selected.includes('other')) value.other_text = null
  return value
}

function primaryAnswer(value: AnswerValue): PrimaryAnswer | null {
  return 'primary' in value ? value : null
}

function answerWithOther(value: AnswerValue): OtherAnswer | null {
  return 'other_text' in value && value.selected.includes('other') ? value : null
}

function concernAnswer(value: AnswerValue): ConcernAnswer | null {
  return 'intensity' in value ? value : null
}

function frequencyAnswer(value: AnswerValue): FrequencyAnswer | null {
  return 'frequency' in value ? value : null
}

function rankingOf(value: AnswerValue): Ranking | null {
  if ('top_ranked' in value) return { selected: value.selected, ranked: value.top_ranked }
  if ('top_concerns' in value) return { selected: value.selected, ranked: value.top_concerns }
  if ('ranked' in value) return { selected: value.selected, ranked: value.ranked }
  return null
}

function QuestionForm(props: {
  question: Question
  theme: Theme
  onSaved: (response: Response, index: number) => void
}) {
  const question = untrack(() => props.question)
  const theme = untrack(() => props.theme)
  const id = theme.question_id
  const old = question.response.answers[id]
  const [value, setValue] = createSignal(
    old.state === 'answered'
      ? normalizeAnswer(copyValue(old.value ?? answerDefault(id)))
      : copyValue(old.value ?? answerDefault(id)),
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
    const next = copyValue(value())
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
                      if (item.state === 'answered') setValue(normalizeAnswer(copyValue(value())))
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
              notice('回答已提交。可以主动生成描述性画像。')
            }}
          >
            提交问卷
          </Button>
        </Show>
      </div>
    </Card>
  )
}

export function QuestionnairePage(): JSX.Element {
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
                      <Button variant="primary" onAction={() => navigate('profile', 'assessment')}>
                        查看画像结果
                      </Button>
                      <Button onAction={async view => start(view, loaded().version, current.response)}>
                        重新填写或更正
                      </Button>
                    </div>
                  </Card>
                }
              >
                <Show when={loaded().themes[current.index]} keyed>
                  {theme => <QuestionForm question={current} theme={theme} onSaved={publish} />}
                </Show>
              </Show>
            )}
          </Show>
        )}
      </Show>
    </Show>
  )
}
