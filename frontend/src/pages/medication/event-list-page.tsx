import type { View } from '../../session/session'
import type { RangeReader } from '../../ui/range-controls'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api } from '../../api/api'
import { rangeQuery } from '../../api/query'
import { submitSource } from '../../api/source'
import { dateText, inputDateTime, localDateTime } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import { readGate } from '../../session/read-gate'
import {
  captureView,
  isCurrentView,
  isDemoAdmin,
  own,
  patientPath,
  requireCurrentView,
  scope,
  state,
  ViewChanged,
} from '../../session/session'
import { Badge, Button, Card, Checkbox, Disclosure, Field, Input, Select, Subheading, Text } from '../../ui/components'
import { IssueList } from '../../ui/data-display'
import { labelFor, metricOptions, statusTone } from '../../ui/labels'
import { RangeControls } from '../../ui/range-controls'
import { evidenceLabels } from './labels'

export interface DoseSlot {
  dose_slot_id: string
  medication_id: string
  plan_id: string
  plan_version: number
  plan_entry_id: string
  scheduled_at: string
  status: string
}

export const doseSlotSchema: v.GenericSchema<unknown, DoseSlot> = v.looseObject({
  dose_slot_id: v.string(),
  medication_id: v.string(),
  plan_id: v.string(),
  plan_version: v.number(),
  plan_entry_id: v.string(),
  scheduled_at: v.string(),
  status: v.string(),
})
const qualitySchema = v.looseObject({
  status: v.picklist(['pending_validation', 'valid', 'needs_review', 'processing_failed']),
  issues: v.array(v.looseObject({ code: v.string(), message: v.string() })),
})
const eventPayloadFieldsSchema = v.looseObject({
  metric_code: v.optional(v.string()),
  value: v.optional(v.nullable(v.number())),
  unit: v.optional(v.nullable(v.string())),
  method_code: v.optional(v.nullable(v.string())),
  missing_reason: v.optional(v.nullable(v.string())),
  reported_status: v.optional(v.nullable(v.string())),
  observation: v.optional(v.nullable(v.string())),
  raw_text: v.optional(v.nullable(v.string())),
  dose_slot_id: v.optional(v.nullable(v.string())),
})
const measurementPayloadSchema = v.looseObject({
  metric_code: v.string(),
  value: v.nullable(v.number()),
  unit: v.nullable(v.string()),
  method_code: v.nullable(v.string()),
  missing_reason: v.nullable(v.string()),
})
const evidencePayloadSchema = v.looseObject({
  reported_status: v.nullable(v.picklist(['taken', 'not_taken', 'postponed', 'unknown'])),
  observation: v.nullable(v.picklist(['box_opened', 'inferred_intake'])),
  dose_slot_id: v.nullable(v.string()),
  raw_text: v.nullable(v.string()),
})
const eventPayloadSchema = v.intersect([
  eventPayloadFieldsSchema,
  v.union([measurementPayloadSchema, evidencePayloadSchema]),
])
const recordEventSchema = v.looseObject({
  event_id: v.string(),
  event_kind: v.picklist(['medication', 'measurement']),
  source: v.string(),
  reporter_account_id: v.nullable(v.string()),
  evidence_type: v.nullable(v.string()),
  occurred_at: v.string(),
  received_at: v.string(),
  state: v.picklist(['effective', 'withdrawn']),
  payload: eventPayloadSchema,
  quality: qualitySchema,
  link_status: v.string(),
  meta: v.looseObject({ revision: v.number(), is_simulated: v.boolean() }),
})
const revisionSchema = v.looseObject({
  revision: v.number(),
  change_kind: v.string(),
  created_at: v.string(),
  reason: v.nullable(v.string()),
  payload: eventPayloadSchema,
})
type Quality = v.InferOutput<typeof qualitySchema>
type EventPayload = v.InferOutput<typeof eventPayloadFieldsSchema>
type RecordEvent = v.InferOutput<typeof recordEventSchema>
type Revision = v.InferOutput<typeof revisionSchema>

const reportOptions: [string, string][] = [
  ['taken', '报告已服'],
  ['not_taken', '报告未服'],
  ['postponed', '暂时延迟'],
  ['unknown', '不清楚'],
]

function ReportSelect(props: {
  label: string
  ref: (element: HTMLSelectElement) => void
  value?: string | null | undefined
}): JSX.Element {
  return (
    <Field label={props.label}>
      <Select ref={props.ref} value={props.value ?? 'taken'}>
        <For each={reportOptions}>{option => <option value={option[0]}>{option[1]}</option>}</For>
      </Select>
    </Field>
  )
}

export function MedicationReportForm(props: { slot?: DoseSlot | null }): JSX.Element {
  let time!: HTMLInputElement
  let status!: HTMLSelectElement
  let notes!: HTMLInputElement
  const [result, setResult] = createSignal<RecordEvent | null>(null)
  async function saveReport(view: View, patientId: string): Promise<void> {
    const slot = props.slot
    const body = {
      occurred_at: inputDateTime(time.value),
      reported_status: status.value,
      medication_id: slot?.medication_id != null && slot.medication_id !== '' ? slot.medication_id : null,
      dose_slot_id: slot?.dose_slot_id != null && slot.dose_slot_id !== '' ? slot.dose_slot_id : null,
      plan_ref: slot ? { plan_id: slot.plan_id, plan_version: slot.plan_version } : null,
      raw_text: notes.value || null,
    }
    const saved = await submitSource(
      `/patients/${encodeURIComponent(patientId)}/medication-events`,
      'medication',
      body,
      recordEventSchema,
      view,
    )
    setResult(saved)
    notice('报告已保存。统计与摘要如已过期，请在用药报告中明确刷新。')
  }
  return (
    <Disclosure summary={own() ? '记录本人的服药情况' : '记录家人报告'}>
      <Text>
        {own()
          ? '这将保存本人的明确报告，不是客观吞服验证。'
          : '当前是家人协助。任何选项都保存为家人报告，不计入本人确认已服。'}
      </Text>
      <Field label="报告发生时间（北京时间，不等同于吞服时间）">
        <Input ref={time} type="datetime-local" value={localDateTime()} />
      </Field>
      <ReportSelect
        label="报告内容"
        ref={element => {
          status = element
        }}
      />
      <Field label="补充原话（可空）">
        <Input ref={notes} />
      </Field>
      <Show when={captureView().patientId} keyed>
        {patientId => (
          <Button variant="primary" onAction={view => saveReport(view, patientId)}>
            明确保存服药报告
          </Button>
        )}
      </Show>
      {!props.slot && (
        <Text>此表没有明确计划时段引用，系统不会按附近时间猜配。可在今日安排选择准确时段，或交受控复核。</Text>
      )}
      <div aria-live="polite">
        <Show when={result()}>
          {saved => (
            <p class="text-sm/6">
              已保存：{evidenceLabels[saved().evidence_type ?? '']}；
              <Badge tone={statusTone(saved().quality.status)}>{labelFor(saved().quality.status)}</Badge>；
              <Badge tone={statusTone(saved().link_status)}>{labelFor(saved().link_status)}</Badge>。
            </p>
          )}
        </Show>
      </div>
    </Disclosure>
  )
}

function MeasurementEditor(props: { payload?: EventPayload; ref: (read: () => EventPayload) => void }): JSX.Element {
  let metric!: HTMLSelectElement
  let value!: HTMLInputElement
  let unit!: HTMLInputElement
  let method!: HTMLInputElement
  let missing!: HTMLInputElement
  let reason!: HTMLInputElement
  onSettled(() =>
    props.ref(() => {
      if (missing.checked && !reason.value.trim()) throw new Error('缺失数值需要明确原因。')
      if (!missing.checked && (value.value === '' || !Number.isFinite(Number(value.value))))
        throw new Error('请填写有限的实际数值，或选择缺失并说明原因。')
      return {
        metric_code: metric.value,
        value: missing.checked ? null : Number(value.value),
        unit: unit.value || null,
        method_code: method.value || null,
        missing_reason: missing.checked ? reason.value : null,
      }
    }),
  )
  return (
    <>
      <Field label="指标">
        <Select ref={metric} value={props.payload?.metric_code ?? 'sleep_duration'}>
          <For each={metricOptions}>{option => <option value={option[0]}>{option[1]}</option>}</For>
        </Select>
      </Field>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="实际数值（缺失时不填）">
          <Input ref={value} type="number" step="any" value={props.payload?.value ?? ''} />
        </Field>
        <Field label="原单位（睡眠h、步数count、心率beats/min）">
          <Input ref={unit} value={props.payload ? (props.payload.unit ?? '') : 'h'} />
        </Field>
      </div>
      <Field label="测量方法（未知留空，不同方法不混合）">
        <Input ref={method} value={props.payload?.method_code ?? ''} />
      </Field>
      <Checkbox
        ref={missing}
        label="本次未采集或数值缺失"
        checked={props.payload ? props.payload.value === null : false}
      />
      <Field label="缺失原因">
        <Input ref={reason} value={props.payload?.missing_reason ?? ''} />
      </Field>
    </>
  )
}

function MeasurementForm(): JSX.Element {
  let time!: HTMLInputElement
  let readPayload!: () => EventPayload
  const [result, setResult] = createSignal<{ quality: Quality } | null>(null)
  async function saveMeasurement(view: View, patientId: string): Promise<void> {
    const body = { occurred_at: inputDateTime(time.value), payload: readPayload() }
    const saved = await submitSource(
      `/patients/${encodeURIComponent(patientId)}/measurements`,
      'measurement',
      body,
      v.looseObject({ quality: qualitySchema }),
      view,
    )
    setResult(saved)
    notice('指标记录已保存，缺失没有补为0；可重新读取记录并刷新报告。')
  }
  return (
    <Disclosure summary="填写指标或缺失记录">
      <Field label="采样时间（北京时间）">
        <Input ref={time} type="datetime-local" value={localDateTime()} />
      </Field>
      <Text>保留原值和原单位；未知单位会交技术复核。此处不采集心理量表或判断医学危险阈值。</Text>
      <MeasurementEditor
        ref={read => {
          readPayload = read
        }}
      />
      <Show when={captureView().patientId} keyed>
        {patientId => (
          <Button variant="primary" onAction={view => saveMeasurement(view, patientId)}>
            保存指标记录
          </Button>
        )}
      </Show>
      <div aria-live="polite">
        <Show when={result()}>
          {saved => (
            <>
              <p class="text-sm/6">
                已保存；<Badge tone={statusTone(saved().quality.status)}>{labelFor(saved().quality.status)}</Badge>。
              </p>
              <IssueList issues={saved().quality.issues} />
            </>
          )}
        </Show>
      </div>
    </Disclosure>
  )
}

function EventCard(props: { event: RecordEvent; reload: (view: View) => Promise<void> }): JSX.Element {
  let time!: HTMLInputElement
  let reason!: HTMLInputElement
  let status!: HTMLSelectElement
  let notes!: HTMLInputElement
  let readPayload!: () => EventPayload
  let timeEdited = false
  const [revisions, setRevisions] = createSignal<Revision[]>([])
  const beginRead = readGate()
  const measurement = () => props.event.event_kind === 'measurement'
  const canWrite = () =>
    props.event.source === 'manual' &&
    props.event.reporter_account_id === state.context?.account.account_id &&
    props.event.state === 'effective' &&
    (own() || scope('records:correct')) &&
    scope(measurement() ? 'measurements:write' : 'records:report')
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
          payload: measurement()
            ? readPayload()
            : { ...props.event.payload, reported_status: status.value, raw_text: notes.value || null },
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
        {measurement() ? (
          `${metricOptions.find(option => option[0] === props.event.payload.metric_code)?.[1] ?? props.event.payload.metric_code}：${props.event.payload.value === null ? '缺失' : props.event.payload.value} ${props.event.payload.unit != null && props.event.payload.unit !== '' ? props.event.payload.unit : '单位未提供'}`
        ) : (
          <>
            {evidenceLabels[props.event.evidence_type ?? ''] ?? props.event.evidence_type ?? ''} ·{' '}
            <Badge
              tone={statusTone(
                props.event.payload.reported_status != null && props.event.payload.reported_status !== ''
                  ? props.event.payload.reported_status
                  : props.event.payload.observation,
              )}
            >
              {labelFor(
                props.event.payload.reported_status != null && props.event.payload.reported_status !== ''
                  ? props.event.payload.reported_status
                  : props.event.payload.observation,
              )}
            </Badge>
          </>
        )}
      </Subheading>
      <Text>
        发生/采样：{dateText(props.event.occurred_at)}；首次收到：{dateText(props.event.received_at)}
      </Text>
      <p class="text-sm/6">
        <Badge tone={statusTone(props.event.state)}>{labelFor(props.event.state)}</Badge> ·{' '}
        <Badge tone={statusTone(props.event.quality.status)}>{labelFor(props.event.quality.status)}</Badge> ·{' '}
        <Badge tone={statusTone(props.event.link_status)}>{labelFor(props.event.link_status)}</Badge>
        ；修订 {props.event.meta.revision}
      </p>
      <Text>{props.event.meta.is_simulated ? '演示记录' : '实际来源记录'}</Text>
      <IssueList issues={props.event.quality.issues} />
      {props.event.payload.missing_reason != null && props.event.payload.missing_reason !== '' && (
        <p class="text-sm/6">缺失原因：{props.event.payload.missing_reason}</p>
      )}
      {props.event.payload.raw_text != null && props.event.payload.raw_text !== '' && (
        <p class="text-sm/6">原话：{props.event.payload.raw_text}</p>
      )}
      {isDemoAdmin() && (
        <p class="text-sm/6">
          技术复核引用：{props.event.event_id}；修订 {props.event.meta.revision}
        </p>
      )}
      {!measurement() && props.event.payload.dose_slot_id != null && props.event.payload.dose_slot_id !== '' && (
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
          {measurement() ? (
            <MeasurementEditor
              payload={props.event.payload}
              ref={read => {
                readPayload = read
              }}
            />
          ) : (
            <>
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
            </>
          )}
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

export function EventListPage(): JSX.Element {
  let range!: RangeReader
  let filter!: HTMLSelectElement
  const [events, setEvents] = createSignal<RecordEvent[] | null>(null)
  const [loading, setLoading] = createSignal(false)
  const beginRead = readGate()
  const measurement = () => state.tab === 'measurements'
  const canRead = () => scope(measurement() ? 'measurements:read' : 'records:read')
  const canWrite = () => scope(measurement() ? 'measurements:write' : 'records:report')
  async function load(view: View): Promise<void> {
    const ensure = beginRead()
    const query = rangeQuery({ ...range.read(), state: filter.value })
    setLoading(true)
    const items = await all(
      `${patientPath(measurement() ? '/measurements' : '/medication-events')}?${query}`,
      recordEventSchema,
      view,
    )
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
      <Subheading>{measurement() ? '指标与缺失记录' : '服药报告与其他证据'}</Subheading>
      {canWrite() && <Card>{measurement() ? <MeasurementForm /> : <MedicationReportForm />}</Card>}
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
                    <ul class="divide-y divide-zinc-950/5 dark:divide-white/5">
                      <For each={items()}>
                        {event => (
                          <li class="py-4 first:pt-0 last:pb-0">
                            <EventCard event={event} reload={load} />
                          </li>
                        )}
                      </For>
                    </ul>
                  ) : (
                    <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
                      此范围没有符合筛选的记录。没有记录不代表未服，缺失也不等于0。
                    </Text>
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
