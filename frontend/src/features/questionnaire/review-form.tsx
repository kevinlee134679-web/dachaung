import type { View } from '../../session/session'
import type { Response, ReviewResponse, ReviewValue, Theme } from './answers'
import type { JSX } from '@solidjs/web'
import { createSignal, For, Show, untrack } from 'solid-js'
import { api } from '../../api/api'
import { notice } from '../../notice/notice'
import { own, requireCurrentView } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Checkbox, Field, Fieldset, Select } from '../../ui/form'
import { Text } from '../../ui/typography'
import { responseSchema, reviewVersion } from './answers'

export function ReviewForm(props: {
  response: ReviewResponse
  theme: Theme
  index: number
  onSaved: (response: Response, index: number) => void
  onSubmitted?: ((response: Response, view: View) => Promise<void>) | undefined
}): JSX.Element {
  let saved = untrack(() => props.response)
  const theme = untrack(() => props.theme)
  const old = saved.answers[theme.question_id]
  const [values, setValues] = createSignal<ReviewValue>({ ...old.value })
  const [missing, setMissing] = createSignal(old.state === 'answered' ? 'not_answered' : old.state)
  const [sameEpisode, setSameEpisode] = createSignal(false)
  const [confirmed, setConfirmed] = createSignal(false)
  const basePath = `/questionnaire-responses/${saved.response_id}`

  function change(key: string, value: string | number | string[]): void {
    const next = { ...values(), [key]: value }
    if (key === 'reported_pattern' && !isEvent(value)) {
      delete next['barriers']
      delete next['main_barrier']
    }
    if (key === 'barriers' && Array.isArray(value) && !value.includes(String(next['main_barrier']))) {
      delete next['main_barrier']
    }
    setValues(Object.fromEntries(Object.entries(next).filter(([, v]) => v !== '' && !(Array.isArray(v) && !v.length))))
    setMissing('not_answered')
  }
  function isEvent(value: ReviewValue[string] | undefined): boolean {
    return value === 'both' || value === 'intentional' || value === 'unintentional'
  }

  const mainOptions = () => {
    const selected = values()['barriers']
    return Array.isArray(selected)
      ? (theme.fields?.find(f => f.key === 'barriers')?.options.filter(o => selected.includes(o.code)) ?? [])
      : []
  }

  async function save(view: View): Promise<ReviewResponse> {
    const answers = Object.fromEntries(
      Object.entries(saved.answers).map(([id, a]) => [id, { state: a.state, value: a.value }]),
    )
    answers[theme.question_id] = Object.keys(values()).length
      ? { state: 'answered', value: values() }
      : { state: missing(), value: null }
    const response = await api(
      `${basePath}/answers`,
      responseSchema,
      'PUT',
      { expected_revision: saved.meta.revision, answers },
      view,
    )
    requireCurrentView(view)
    if (response.questionnaire_version !== saved.questionnaire_version) throw new Error('问卷版本不一致')
    saved = response
    return response
  }
  return (
    <Card>
      <div class="space-y-5">
        <Text>
          第 {props.index + 1} 题组，共 8 组{props.index >= 4 ? ' · 自愿补充' : ' · 请回顾最近同一次规律用药经历'}
        </Text>
        <Fieldset legend={theme.prompt}>
          <For
            each={theme.fields?.filter(field =>
              field.key === 'barriers'
                ? isEvent(values()['reported_pattern'])
                : field.kind === 'selected_choice'
                  ? mainOptions().length > 0
                  : true,
            )}
          >
            {field =>
              field.kind === 'multiple' ? (
                <Fieldset legend={field.prompt}>
                  <For each={field.options}>
                    {option => {
                      const selected = () => {
                        const v = values()[field.key]
                        return Array.isArray(v) ? v : []
                      }
                      return (
                        <Checkbox
                          label={option.label}
                          checked={selected().includes(option.code)}
                          onChange={e => {
                            const remaining = selected().filter(x => x !== option.code && x !== 'req_none')
                            change(
                              field.key,
                              e.currentTarget.checked
                                ? option.code === 'req_none'
                                  ? ['req_none']
                                  : [...remaining, option.code]
                                : selected().filter(x => x !== option.code),
                            )
                          }}
                        />
                      )
                    }}
                  </For>
                </Fieldset>
              ) : (
                <Field label={field.prompt}>
                  <Select
                    value={String(values()[field.key] ?? '')}
                    onChange={e => {
                      const v = e.currentTarget.value
                      change(field.key, v && field.kind === 'scale' ? Number(v) : v)
                    }}
                  >
                    <option value="">请选择，可留空</option>
                    <For each={field.kind === 'selected_choice' ? mainOptions() : field.options}>
                      {option => <option value={option.code}>{option.label}</option>}
                    </For>
                  </Select>
                </Field>
              )
            }
          </For>
          <Field label="本题组作答状态">
            <Select
              value={Object.keys(values()).length ? 'answered' : missing()}
              onChange={e => {
                setMissing(e.currentTarget.value)
                setValues({})
              }}
            >
              <option value="answered" disabled>
                已填写
              </option>
              <option value="not_answered">整组未答</option>
              <option value="unknown">不清楚</option>
              <option value="not_applicable">不适用</option>
              <option value={saved.questionnaire_version === reviewVersion ? 'prefer_not_to_answer' : 'declined'}>
                不愿回答
              </option>
            </Select>
          </Field>
          <Show when={props.index === 3 && saved.questionnaire_version !== reviewVersion}>
            <Text>本版记录实际发生的行为。具体原因及主要原因的选项待核对。</Text>
          </Show>
        </Fieldset>
        <div class="flex flex-wrap gap-3">
          <Button disabled={props.index === 0} onAction={async v => props.onSaved(await save(v), props.index - 1)}>
            上一题组
          </Button>
          <Button
            onAction={async v => {
              props.onSaved(await save(v), props.index)
              notice('进度已保存。')
            }}
          >
            保存进度
          </Button>
          <Show when={props.index < 7}>
            <Button onAction={async v => props.onSaved(await save(v), props.index + 1)}>
              {props.index === 3 ? '继续填写自愿补充题' : '保存并下一题'}
            </Button>
          </Show>
        </div>
        <Show when={props.index >= 3}>
          <Show when={own()}>
            <Checkbox
              label="我确认 Q1–Q3 回答的是本人同一次规律用药经历"
              checked={sameEpisode()}
              onChange={e => {
                setSameEpisode(e.currentTarget.checked)
              }}
            />
          </Show>
          <Checkbox
            label="我确认提交本次问卷，留空项按未答保存"
            checked={confirmed()}
            onChange={e => {
              setConfirmed(e.currentTarget.checked)
            }}
          />
          <Button
            variant="primary"
            onAction={async view => {
              if (!confirmed()) throw new Error('请先确认提交本次问卷。')
              const current = await save(view)
              const result = await api(
                `${basePath}/submit`,
                responseSchema,
                'POST',
                {
                  expected_revision: current.meta.revision,
                  confirmed: true,
                  same_episode: own() && sameEpisode(),
                },
                view,
              )
              requireCurrentView(view)
              props.onSaved(result, props.index)
              if (props.onSubmitted) await props.onSubmitted(result, view)
              else notice('问卷已提交，可查看画像。')
            }}
          >
            {props.onSubmitted ? '提交问卷并生成画像' : '提交问卷'}
          </Button>
        </Show>
      </div>
    </Card>
  )
}
