import type { View } from '../../session/session'
import type { RangeReader } from '../../ui/range-controls'
import type { RecordEvent } from './events'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import { all } from '../../api/api'
import { rangeQuery } from '../../api/query'
import { actionError } from '../../notice/notice'
import { readGate } from '../../session/read-gate'
import { captureView, isCurrentView, patientPath, scope, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Field, Select } from '../../ui/form'
import { EmptyState, List } from '../../ui/list'
import { RangeControls } from '../../ui/range-controls'
import { Subheading, Text } from '../../ui/typography'
import { EventCard } from './event-card'
import { recordEventSchema } from './events'
import { MedicationReportForm } from './report-form'

export function EventListPage(): JSX.Element {
  let range!: RangeReader
  let filter!: HTMLSelectElement
  const [events, setEvents] = createSignal<RecordEvent[] | null>(null)
  const [loading, setLoading] = createSignal(false)
  const beginRead = readGate()
  const canRead = () => scope('records:read')
  async function load(view: View): Promise<void> {
    const ensure = beginRead()
    const query = rangeQuery({ ...range.read(), state: filter.value })
    setLoading(true)
    const items = await all(`${patientPath('/medication-events')}?${query}`, recordEventSchema, view)
    ensure()
    setEvents(items)
    setLoading(false)
  }
  onSettled(() => {
    if (!canRead()) return
    const view = captureView()
    void Promise.resolve()
      .then(() => load(view))
      .catch((error: unknown) => {
        if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
      })
  })
  return (
    <section class="space-y-6">
      <Subheading>服药报告与其他证据</Subheading>
      {scope('records:report') && (
        <Card>
          <MedicationReportForm onSaved={canRead() ? load : undefined} />
        </Card>
      )}
      {!canRead() ? (
        <Text>当前未获此类记录查看权限。保存权限与查看权限分别核验。</Text>
      ) : (
        <Card>
          <div class="space-y-4">
            <RangeControls
              ref={reader => {
                range = reader
              }}
            />
            <Field label="记录状态">
              <Select ref={filter}>
                <option value="effective">当前有效</option>
                <option value="all">全部（含撤销）</option>
                <option value="withdrawn">已撤销</option>
              </Select>
            </Field>
            <Button onAction={load}>读取记录</Button>
            {loading() ? (
              <Text>正在读取原始来源和质量…</Text>
            ) : (
              <Show when={events()}>
                {items =>
                  items().length ? (
                    <List>
                      <For each={items()}>
                        {event => (
                          <li>
                            <EventCard event={event} reload={load} />
                          </li>
                        )}
                      </For>
                    </List>
                  ) : (
                    <EmptyState>此范围没有符合筛选的记录。没有记录不代表未服，缺失也不等于0。</EmptyState>
                  )
                }
              </Show>
            )}
          </div>
        </Card>
      )}
    </section>
  )
}
