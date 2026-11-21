import type { View } from '../../session/session'
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
  referenceKey,
  requireCurrentView,
  scope,
  ViewChanged,
} from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { List } from '../../ui/list'
import { Subheading, Text } from '../../ui/typography'

const profileSchema = v.looseObject({
  generated_at: v.string(),
  cas: v.looseObject({ reason: v.string() }),
  factors: v.array(v.looseObject({ label: v.string(), source_value: v.string() })),
  missing_items: v.array(v.string()),
})
type Profile = v.InferOutput<typeof profileSchema>

export function ProfilePage(): JSX.Element {
  const [profile, setProfile] = createSignal<Profile | null>(null)
  const [message, setMessage] = createSignal('')
  const [loaded, setLoaded] = createSignal(false)
  async function load(view: View) {
    try {
      const result = await api(patientPath('/profiles/current'), profileSchema, 'GET', null, view)
      requireCurrentView(view)
      setProfile(result)
      setMessage('')
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
            <Show when={own() && localStorage.getItem(referenceKey('questionnaire'))}>
              <Button
                variant="primary"
                onAction={async view => {
                  await api(
                    patientPath('/profiles'),
                    v.unknown(),
                    'POST',
                    { response_id: localStorage.getItem(referenceKey('questionnaire')) },
                    view,
                  )
                  await load(view)
                  requireCurrentView(view)
                  notice('已保存独立画像结果；没有生成CAS或分类预测。')
                }}
              >
                根据已提交回答生成描述性结果
              </Button>
            </Show>
            <Show
              when={profile()}
              fallback={<Button onAction={() => navigate('profile', 'questionnaire')}>前往八题问卷</Button>}
            >
              {value => (
                <>
                  <Subheading>你的回答与关注重点</Subheading>
                  <Text>生成于 {dateText(value().generated_at)}</Text>
                  <p>CAS：尚未适配，当前没有预测值。</p>
                  <Text>{value().cas.reason}</Text>
                  <p>主要分类：暂不判型；分类方法尚未适配，不用标签替代你的真实情况。</p>
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
