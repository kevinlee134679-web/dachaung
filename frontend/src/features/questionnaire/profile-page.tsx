import type { Page, View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { ApiError, api } from '../../api/api'
import { dateText } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import {
  captureView,
  isCurrentView,
  own,
  patientPath,
  requireCurrentView,
  scope,
  ViewChanged,
} from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { List } from '../../ui/list'
import { Subheading, Text } from '../../ui/typography'
import { generateProfile } from './profile'

const entryPages = {
  reminder: ['提醒设置', 'medication', 'reminders'],
  organize_plan: ['用药清单', 'profile', 'medication-list'],
  social_support: ['社会支持', 'support', 'social'],
  knowledge: ['药学知识', 'medication', 'knowledge'],
  ai_support: ['AI 对话', 'support', 'overview'],
} as const satisfies Record<string, readonly [string, Page, string]>

const profileSchema = v.looseObject({
  generated_at: v.string(),
  cas: v.looseObject({
    status: v.string(),
    value: v.nullable(v.number()),
    reason: v.nullable(v.string()),
    model_version: v.optional(v.nullable(v.string())),
  }),
  cas_observed: v.optional(
    v.object({
      status: v.picklist(['observed', 'insufficient']),
      value: v.nullable(v.number()),
      reasons: v.array(v.string()),
    }),
  ),
  research_group: v.optional(v.nullable(v.picklist(['high', 'middle', 'low']))),
  primary_type: v.nullable(v.string()),
  classification_reason: v.optional(v.string()),
  demo_classification: v.optional(
    v.object({
      primary_type: v.nullable(v.string()),
      reported_matching_types: v.array(v.string()),
      type_labels: v.record(v.string(), v.string()),
      reason: v.string(),
      entry_codes: v.array(v.picklist(['reminder', 'organize_plan', 'social_support', 'knowledge', 'ai_support'])),
    }),
  ),
  factors: v.array(v.looseObject({ label: v.string(), source_value: v.string() })),
  missing_items: v.array(v.string()),
})
type Profile = v.InferOutput<typeof profileSchema>

const submissionSchema = v.object({
  response_id: v.string(),
  submitted_at: v.string(),
  profile: v.nullable(profileSchema),
})

export function ProfilePage(): JSX.Element {
  const [profile, setProfile] = createSignal<Profile | null>(null)
  const [message, setMessage] = createSignal('')
  const [loaded, setLoaded] = createSignal(false)
  const [submittedAt, setSubmittedAt] = createSignal<string | null>(null)
  async function loadSubmission(view: View) {
    const latest = await api(
      patientPath('/profiles/current?source=latest_submission'),
      submissionSchema,
      'GET',
      null,
      view,
    )
    requireCurrentView(view)
    setSubmittedAt(latest.submitted_at)
    setProfile(latest.profile)
    setMessage(latest.profile ? '' : '最近提交的问卷尚未生成画像。')
    return latest.response_id
  }

  async function load(view: View) {
    try {
      if (own()) {
        await loadSubmission(view)
      } else {
        const result = await api(patientPath('/profiles/current'), profileSchema, 'GET', null, view)
        requireCurrentView(view)
        setProfile(result)
        setMessage('')
      }
      setLoaded(true)
    } catch (error) {
      if (
        error instanceof ViewChanged ||
        !(error instanceof ApiError) ||
        error.status !== 404 ||
        error.code !== 'PROFILE_NOT_AVAILABLE'
      ) {
        throw error
      }
      requireCurrentView(view)
      setProfile(null)
      setMessage(error.message)
      setLoaded(true)
    }
  }
  onSettled(() => {
    if (!scope('profile:read')) return
    const view = captureView()
    void load(view).catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })
  return (
    <Show when={scope('profile:read')} fallback={<p>当前未获画像查看权限。</p>}>
      <Show when={loaded()}>
        <Card>
          <div class="space-y-4">
            <Show when={message()}>
              <Text>{message()}</Text>
            </Show>
            <Show when={submittedAt()}>{at => <Text>问卷提交于 {dateText(at())}</Text>}</Show>
            <Show when={own() && submittedAt()}>
              <Button
                variant="primary"
                onAction={async view => {
                  const responseId = await loadSubmission(view)
                  await generateProfile(responseId, view)
                  await loadSubmission(view)
                  requireCurrentView(view)
                  notice('已保存本次问卷的画像结果。')
                }}
              >
                根据已提交问卷生成画像
              </Button>
            </Show>
            <Show
              when={profile()}
              fallback={
                <Show when={submittedAt() === null && scope('questionnaire:assist')}>
                  <Button onAction={() => navigate('profile', 'questionnaire')}>前往八题问卷</Button>
                </Show>
              }
            >
              {value => (
                <>
                  <Subheading>你的回答与关注重点</Subheading>
                  <Text>生成于 {dateText(value().generated_at)}</Text>
                  <Show when={value().cas_observed} fallback={<Text>旧版问卷未采集实测 CAS 三题。</Text>}>
                    {observed => (
                      <>
                        <p>
                          {observed().status === 'observed'
                            ? `本次问卷 CAS　${observed().value}/15（自报）`
                            : '本次问卷 CAS（自报）资料不足'}
                        </p>
                        <For each={observed().reasons}>{reason => <Text>{reason}</Text>}</For>
                      </>
                    )}
                  </Show>
                  <Show when={value().research_group}>
                    {group => (
                      <p>
                        研究演示分组 ·{' '}
                        {{ low: '低分组（3–9）', middle: '中间组（10–13）', high: '高分组（14–15）' }[group()]}
                      </p>
                    )}
                  </Show>
                  <p>
                    模型预测 CAS ·{' '}
                    {value().cas.status === 'estimated'
                      ? `${value().cas.value?.toFixed(2)} 分（研究估计）`
                      : value().cas.status === 'insufficient'
                        ? '输入不足'
                        : value().cas.model_version != null
                          ? '计算未完成'
                          : '未配置'}
                  </p>
                  <Show when={value().cas.model_version}>{version => <Text>研究重训模型版本 · {version()}</Text>}</Show>
                  <Text>{value().cas.reason}</Text>
                  <Show
                    when={value().demo_classification}
                    fallback={
                      <>
                        <p>
                          演示主类型 ·{' '}
                          {value().primary_type === 'A' ? 'A 维持型' : (value().primary_type ?? '暂不分型')}
                        </p>
                        <Text>{value().classification_reason}</Text>
                      </>
                    }
                  >
                    {result => {
                      const label = (code: string) => `${code} ${result().type_labels[code] ?? ''}`
                      const main = () => result().primary_type
                      return (
                        <>
                          <p>演示主类型 · {main() !== null ? label(main() ?? '') : '暂不分型'}</p>
                          <Show when={result().reported_matching_types.length}>
                            <p>
                              {main() !== null ? '次要匹配' : '符合条件的障碍'} ·{' '}
                              {result().reported_matching_types.map(label).join('、')}
                            </p>
                          </Show>
                          <Text>{result().reason}</Text>
                          <Show when={own()}>
                            <div class="flex flex-wrap gap-2">
                              <For each={result().entry_codes}>
                                {code => (
                                  <Button onAction={() => navigate(entryPages[code][1], entryPages[code][2])}>
                                    查看{entryPages[code][0]}
                                  </Button>
                                )}
                              </For>
                            </div>
                          </Show>
                        </>
                      )
                    }}
                  </Show>
                  <List>
                    <For each={value().factors}>
                      {factor => (
                        <li>
                          <strong>{factor.label}</strong>
                          <p>{factor.source_value}</p>
                        </li>
                      )}
                    </For>
                  </List>
                  <For each={value().missing_items}>{reason => <Text>{reason}</Text>}</For>
                </>
              )}
            </Show>
          </div>
        </Card>
      </Show>
    </Show>
  )
}
