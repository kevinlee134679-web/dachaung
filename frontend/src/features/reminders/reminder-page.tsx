import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, flush, For, onSettled, Show, untrack } from 'solid-js'
import * as v from 'valibot'
import { api } from '../../api/api'
import { actionError, notice } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import { readGate } from '../../session/read-gate'
import { captureView, isCurrentView, patientPath, requireCurrentView, scope, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Checkbox, Field, Fieldset, Input, Select } from '../../ui/form'
import { Subheading, Text } from '../../ui/typography'

const preferencesSchema = v.looseObject({
  enabled: v.boolean(),
  channels: v.array(v.picklist(['in_app'])),
  sound_enabled: v.boolean(),
  vibration_enabled: v.boolean(),
  routine_mode: v.picklist(['regular', 'night_shift', 'rotating_shift', 'travel', 'custom']),
  anchors: v.array(
    v.looseObject({
      event: v.picklist(['wake', 'breakfast', 'bedtime', 'custom']),
      label: v.nullable(v.string()),
      local_time: v.string(),
      offset_minutes: v.number(),
    }),
  ),
  privacy_enabled: v.boolean(),
  custom_text: v.nullable(v.string()),
  privacy_windows: v.array(v.looseObject({ start: v.string(), end: v.string() })),
  repeat_interval_minutes: v.nullable(v.number()),
  max_repeats: v.number(),
  snooze_minutes: v.nullable(v.number()),
  notify_family: v.boolean(),
  meta: v.looseObject({ revision: v.number() }),
})
type Preferences = v.InferOutput<typeof preferencesSchema>

function ReminderForm(props: { current: Preferences | null; saved: (view: View) => Promise<void> }) {
  const settings = untrack(() => props.current) ?? {
    enabled: false,
    channels: ['in_app'],
    sound_enabled: false,
    vibration_enabled: false,
    routine_mode: 'regular',
    anchors: [],
    privacy_enabled: false,
    custom_text: null,
    privacy_windows: [],
    repeat_interval_minutes: null,
    max_repeats: 0,
    snooze_minutes: null,
    notify_family: false,
  }
  const [anchors, setAnchors] = createSignal<
    { event: string; label: string | null; local_time: string; offset_minutes: number }[]
  >(settings.anchors.map(anchor => ({ ...anchor })))
  const [windows, setWindows] = createSignal(settings.privacy_windows.map(window => ({ ...window })))
  let enabled!: HTMLInputElement
  let privacy!: HTMLInputElement
  let family!: HTMLInputElement
  let routine!: HTMLSelectElement
  let text!: HTMLInputElement
  let interval!: HTMLInputElement
  let repeats!: HTMLInputElement
  let snooze!: HTMLInputElement
  async function save(view: View): Promise<void> {
    await api(
      patientPath('/reminder-preferences'),
      v.unknown(),
      'PUT',
      {
        expected_revision: props.current?.meta.revision ?? 0,
        settings: {
          enabled: enabled.checked,
          channels: ['in_app'],
          sound_enabled: false,
          vibration_enabled: false,
          routine_mode: routine.value,
          anchors: anchors(),
          privacy_enabled: privacy.checked,
          custom_text: text.value || null,
          privacy_windows: windows(),
          repeat_interval_minutes: interval.value ? Number(interval.value) : null,
          max_repeats: Number(repeats.value),
          snooze_minutes: snooze.value ? Number(snooze.value) : null,
          notify_family: family.checked,
        },
      },
      view,
    )
    await props.saved(view)
    requireCurrentView(view)
    notice('提醒偏好已保存；实际任务和投递结果请在“提醒与执行”核对。')
  }
  return (
    <Card>
      <div class="space-y-4">
        <p class="text-sm/6 text-red-600 dark:text-red-400">
          这里保存提醒偏好；请在“提醒与执行”查看实际任务和结果。任务仅由显式维护和执行推进，不保证关闭网页后送达。
        </p>
        <Button onAction={() => navigate('medication', 'reminders')}>查看提醒与执行</Button>
        <Checkbox ref={enabled} label="启用应用内提醒偏好" checked={settings.enabled} />
        <Field label="生活作息">
          <Select ref={routine} value={settings.routine_mode}>
            <option value="regular">常规</option>
            <option value="night_shift">夜班</option>
            <option value="rotating_shift">轮班</option>
            <option value="travel">外出或差旅</option>
            <option value="custom">自定义</option>
          </Select>
        </Field>
        <Checkbox ref={privacy} label="隐私提醒（不显示药品或疾病）" checked={settings.privacy_enabled} />
        <Field label="提醒文字（隐私模式仅中性文案）">
          <Input ref={text} value={settings.custom_text ?? ''} />
        </Field>
        <div>
          <span>通知方式</span>
          <Text>应用内提醒。系统通知、声音及振动尚未接入。</Text>
        </div>
        <div class="grid gap-4 md:grid-cols-3">
          <Field label="重复间隔（30—120分钟，不重复留空）">
            <Input ref={interval} type="number" min={30} max={120} value={settings.repeat_interval_minutes ?? ''} />
          </Field>
          <Field label="最多重复次数（0—2）">
            <Input ref={repeats} type="number" min={0} max={2} value={settings.max_repeats} />
          </Field>
          <Field label="偏好的稍后时长（5—120分钟，可空）">
            <Input ref={snooze} type="number" min={5} max={120} value={settings.snooze_minutes ?? ''} />
          </Field>
        </div>
        <Checkbox ref={family} label="允许已获接收授权的家人接收相关通知" checked={settings.notify_family} />
        <Subheading>生活事件锚点</Subheading>
        <Text>不具备实时作息感知，只保存主动设置的事件。医学约束未知时，后续执行不会据此偏移原医嘱。</Text>
        <For each={anchors()}>
          {anchor => (
            <Fieldset legend="生活事件锚点">
              <Field label="事件">
                <Select
                  value={anchor.event}
                  onChange={event => {
                    anchor.event = event.currentTarget.value
                  }}
                >
                  <option value="wake">起床</option>
                  <option value="breakfast">早餐</option>
                  <option value="bedtime">睡前</option>
                  <option value="custom">自定义</option>
                </Select>
              </Field>
              <Field label="自定义事件名称">
                <Input
                  value={anchor.label ?? ''}
                  onInput={event => {
                    anchor.label = event.currentTarget.value || null
                  }}
                />
              </Field>
              <Field label="用户主动设置的时刻">
                <Input
                  type="time"
                  value={anchor.local_time}
                  onInput={event => {
                    anchor.local_time = event.currentTarget.value
                  }}
                />
              </Field>
              <Field label="偏移分钟（-60至60，只用于通知偏好）">
                <Input
                  type="number"
                  min={-60}
                  max={60}
                  value={anchor.offset_minutes}
                  onInput={event => {
                    anchor.offset_minutes = Number(event.currentTarget.value)
                  }}
                />
              </Field>
              <Button
                onAction={() => {
                  setAnchors(current => current.filter(item => item !== anchor))
                }}
              >
                移除此锚点
              </Button>
            </Fieldset>
          )}
        </For>
        <Button
          onAction={() => {
            setAnchors(current => [...current, { event: 'wake', label: null, local_time: '', offset_minutes: 0 }])
          }}
        >
          添加生活事件锚点
        </Button>
        <Subheading>隐私时段</Subheading>
        <Text>每段为同日时间，跨午夜请分成两段。</Text>
        <For each={windows()}>
          {window => (
            <div class="grid items-end gap-4 md:grid-cols-3">
              <Field label="隐私时段开始">
                <Input
                  type="time"
                  value={window.start}
                  onInput={event => {
                    window.start = event.currentTarget.value
                  }}
                />
              </Field>
              <Field label="隐私时段结束">
                <Input
                  type="time"
                  value={window.end}
                  onInput={event => {
                    window.end = event.currentTarget.value
                  }}
                />
              </Field>
              <Button
                onAction={() => {
                  setWindows(current => current.filter(item => item !== window))
                }}
              >
                移除此隐私时段
              </Button>
            </div>
          )}
        </For>
        <div class="flex flex-wrap gap-3">
          <Button
            onAction={() => {
              setWindows(current => [...current, { start: '', end: '' }])
            }}
          >
            添加隐私时段
          </Button>
          <Button variant="primary" disabled={!scope('reminder:write')} onAction={save}>
            保存提醒偏好
          </Button>
        </div>
      </div>
    </Card>
  )
}

export function ReminderPage(): JSX.Element {
  const [loaded, setLoaded] = createSignal(false)
  const [current, setCurrent] = createSignal<Preferences | null>(null)
  const nextRead = readGate()
  async function load(view: View): Promise<void> {
    const check = nextRead()
    let preferences: Preferences | null = null
    try {
      preferences = await api(patientPath('/reminder-preferences'), preferencesSchema, 'GET', null, view)
    } catch (error) {
      if (!(error instanceof Error) || !error.message.includes('尚未保存')) throw error
    }
    check()
    setCurrent(preferences)
    setLoaded(true)
  }
  async function saved(view: View): Promise<void> {
    requireCurrentView(view)
    setLoaded(false)
    flush()
    await load(view)
  }
  onSettled(() => {
    if (!scope('reminder:read')) return
    const view = captureView()
    void load(view).catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })
  return (
    <Show when={scope('reminder:read')} fallback={<p>当前未获提醒设置查看权限。</p>}>
      <Show when={loaded()}>
        <ReminderForm current={current()} saved={saved} />
      </Show>
    </Show>
  )
}
