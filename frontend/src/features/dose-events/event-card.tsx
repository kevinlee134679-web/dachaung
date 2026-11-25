import type { View } from '../../session/session'
import type { RecordEvent, Revision } from './events'
import type { JSX } from '@solidjs/web'
import { createSignal, For } from 'solid-js'
import * as v from 'valibot'
import { all, api } from '../../api/api'
import { dateText, inputDateTime, localDateTime } from '../../date/date'
import { notice } from '../../notice/notice'
import { readGate } from '../../session/read-gate'
import { isDemoAdmin, own, requireCurrentView, scope, state } from '../../session/session'
import { StatusBadge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { IssueList } from '../../ui/data-display'
import { Disclosure } from '../../ui/disclosure'
import { Field, Input } from '../../ui/form'
import { Subheading, Text } from '../../ui/typography'
import { revisionSchema } from './events'
import { ReportSelect } from './report-select'

export const evidenceLabels: Record<string, string> = {
  self_report: '本人报告',
  family_report: '家人报告（不计入本人已服）',
  box_opening: '开盒证据（不证明已服）',
  device_inference: '设备推断（不证明已服）',
}

export function EventCard(props: { event: RecordEvent; reload: (view: View) => Promise<void> }): JSX.Element {
  let time!: HTMLInputElement
  let reason!: HTMLInputElement
  let status!: HTMLSelectElement
  let notes!: HTMLInputElement
  let timeEdited = false
  const [revisions, setRevisions] = createSignal<Revision[]>([])
  const beginRead = readGate()
  const canWrite = () =>
    props.event.source === 'manual' &&
    props.event.reporter_account_id === state.context?.account.account_id &&
    props.event.state === 'effective' &&
    (own() || scope('records:correct')) &&
    scope('records:report')
  async function loadRevisions(view: View): Promise<void> {
    const ensure = beginRead()
    const history = await all(`/events/${encodeURIComponent(props.event.event_id)}/revisions`, revisionSchema, view)
    ensure()
    setRevisions(history)
  }
  async function change(view: View, withdrawal: boolean): Promise<void> {
    if (!reason.value.trim()) throw new Error(withdrawal ? '请填写撤销原因。' : '请填写更正原因。')
    const body = withdrawal
      ? { expected_revision: props.event.meta.revision, reason: reason.value }
      : {
          expected_revision: props.event.meta.revision,
          reason: reason.value,
          occurred_at: timeEdited ? inputDateTime(time.value) : props.event.occurred_at,
          payload: { ...props.event.payload, reported_status: status.value, raw_text: notes.value || null },
        }
    await api(
      `/events/${encodeURIComponent(props.event.event_id)}/${withdrawal ? 'withdrawals' : 'corrections'}`,
      v.unknown(),
      'POST',
      body,
      view,
    )
    requireCurrentView(view)
    await props.reload(view)
    requireCurrentView(view)
    notice(
      withdrawal
        ? '已撤销当前证据，历史仍保留。请刷新统计和摘要。'
        : '已追加更正并保留旧依据。请刷新需要更新的统计和摘要。',
    )
  }
  async function correct(view: View): Promise<void> {
    await change(view, false)
  }
  async function withdraw(view: View): Promise<void> {
    await change(view, true)
  }
  return (
    <article class="space-y-4">
      <Subheading level={3}>
        {evidenceLabels[props.event.evidence_type ?? ''] ?? props.event.evidence_type ?? ''} ·{' '}
        <StatusBadge status={props.event.payload.reported_status ?? props.event.payload.observation} />
      </Subheading>
      <Text>
        发生/采样：{dateText(props.event.occurred_at)}；首次收到：{dateText(props.event.received_at)}
      </Text>
      <p class="text-sm/6">
        <StatusBadge status={props.event.state} /> · <StatusBadge status={props.event.quality.status} /> ·{' '}
        <StatusBadge status={props.event.link_status} />
        ；修订 {props.event.meta.revision}
      </p>
      <Text>{props.event.meta.is_simulated ? '演示记录' : '实际来源记录'}</Text>
      <IssueList issues={props.event.quality.issues} />
      {props.event.payload.raw_text != null && props.event.payload.raw_text !== '' && (
        <p class="text-sm/6">原话：{props.event.payload.raw_text}</p>
      )}
      {isDemoAdmin() && (
        <p class="text-sm/6">
          技术复核引用：{props.event.event_id}；修订 {props.event.meta.revision}
        </p>
      )}
      {props.event.payload.dose_slot_id != null && props.event.payload.dose_slot_id !== '' && (
        <p class="text-sm/6">关联时段：{props.event.payload.dose_slot_id}</p>
      )}
      <Button onAction={loadRevisions}>查看原始与更正历史</Button>
      <For each={revisions()}>
        {revision => (
          <div class="space-y-2 text-sm/6">
            <p>
              修订 {revision.revision} · {revision.change_kind} · {dateText(revision.created_at)}
            </p>
            <p>{revision.reason != null && revision.reason !== '' ? revision.reason : '原始依据'}</p>
            <pre class="overflow-x-auto">{JSON.stringify(revision.payload, null, 2)}</pre>
          </div>
        )}
      </For>
      {canWrite() && (
        <Disclosure summary="更正或撤销自己的记录">
          <Field label="更正发生/采样时间（北京时间）">
            <Input
              ref={time}
              type="datetime-local"
              value={localDateTime(props.event.occurred_at)}
              onInput={() => {
                timeEdited = true
              }}
              onChange={() => {
                timeEdited = true
              }}
            />
          </Field>
          <Field label="更正或撤销原因（必填）">
            <Input ref={reason} />
          </Field>
          <ReportSelect
            label="更正报告"
            value={props.event.payload.reported_status}
            ref={element => {
              status = element
            }}
          />
          <Field label="更正原话">
            <Input ref={notes} value={props.event.payload.raw_text ?? ''} />
          </Field>
          <Text>原始证据与来源会保留；页面旧修订不能覆盖新修改。撤销不删除历史。</Text>
          <div class="flex flex-wrap gap-3">
            <Button onAction={correct}>保存追加更正</Button>
            <Button onAction={withdraw}>明确撤销本条证据</Button>
          </div>
        </Disclosure>
      )}
    </article>
  )
}
