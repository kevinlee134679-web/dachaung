import type { DoseSlot } from './event-list-page'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all } from '../../api/api'
import { dateText, today } from '../../date/date'
import { actionError } from '../../notice/notice'
import { readGate } from '../../session/read-gate'
import { captureView, isCurrentView, patientPath, scope, ViewChanged } from '../../session/session'
import { Badge, Button, Card, Field, Input, Text } from '../../ui/components'
import { statusTone } from '../../ui/labels'
import { doseSlotSchema, MedicationReportForm } from './event-list-page'

const planSchema = v.looseObject({
  plan_id: v.string(),
  plan_version: v.number(),
  entries: v.array(
    v.looseObject({
      plan_entry_id: v.string(),
      medication_name_snapshot: v.string(),
      dose_value: v.string(),
      dose_unit: v.string(),
    }),
  ),
})
type Plan = v.InferOutput<typeof planSchema>

export function SchedulePage(): JSX.Element {
  let day!: HTMLInputElement
  const [slots, setSlots] = createSignal<DoseSlot[] | null>(null)
  const [plans, setPlans] = createSignal<Plan[]>([])
  const beginRead = readGate()

  async function load(): Promise<void> {
    const ensure = beginRead()
    setSlots(null)
    if (!day.value) return
    const start = `${day.value}T00:00:00+08:00`
    const end = new Date(new Date(start).getTime() + 86400000).toISOString()
    const items = await all(
      `${patientPath('/dose-slots')}?window_start=${encodeURIComponent(start)}&window_end=${encodeURIComponent(end)}`,
      doseSlotSchema,
    )
    ensure()
    const result = await all(patientPath('/plans'), planSchema)
    ensure()
    setPlans(result)
    setSlots(items)
  }

  onSettled(() => {
    if (!scope('plan:read')) return
    const view = captureView()
    void load().catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })

  return (
    <Show when={scope('plan:read')} fallback={<p>当前未获正式安排查看权限。</p>}>
      <Card title="已确认的安排">
        <div class="space-y-4">
          <Field label="安排日期（北京时间）">
            <Input ref={day} type="date" value={today()} />
          </Field>
          <Button onAction={load}>查看安排</Button>
          <Show when={slots()} fallback={<p>正在读取安排…</p>}>
            {items => (
              <>
                <Show when={!items().length}>
                  <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
                    这一天没有已物化的正式安排。未确认草稿不会出现在这里。
                  </Text>
                </Show>
                <ul class="divide-y divide-zinc-950/5 dark:divide-white/5">
                  <For each={items()}>
                    {slot => {
                      const entry = () =>
                        plans()
                          .find(plan => plan.plan_id === slot.plan_id && plan.plan_version === slot.plan_version)
                          ?.entries.find(item => item.plan_entry_id === slot.plan_entry_id)
                      return (
                        <li class="space-y-2 py-4 first:pt-0 last:pb-0">
                          <strong class="text-sm/6 font-medium">
                            {(entry()?.medication_name_snapshot ?? '') || '计划药品'}
                          </strong>
                          <p class="text-sm/6">
                            {dateText(slot.scheduled_at)} ·{' '}
                            <Badge tone={statusTone(slot.status)}>
                              {slot.status === 'active' ? '正式安排' : '已被后续版本替代'}
                            </Badge>
                          </p>
                          <Text>
                            <Show when={entry()} fallback="请查看计划原资料">
                              {item => `原资料：${item().dose_value} ${item().dose_unit}`}
                            </Show>
                          </Text>
                          <Show when={slot.status === 'active' && scope('records:report')}>
                            <MedicationReportForm slot={slot} />
                          </Show>
                        </li>
                      )
                    }}
                  </For>
                </ul>
              </>
            )}
          </Show>
          <Text>此处展示计划时间，不推断已经服药、未服或漏服。</Text>
        </div>
      </Card>
    </Show>
  )
}
