import type { RangeReader } from '../../ui/range-controls'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show, untrack } from 'solid-js'
import * as v from 'valibot'
import { api, ApiError, sha } from '../../api/api'
import { rangeQuery } from '../../api/query'
import { dateText } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import { readGate } from '../../session/read-gate'
import {
  captureView,
  own,
  patientPath,
  referenceKey,
  requireCurrentView,
  scope,
  ViewChanged,
} from '../../session/session'
import { Badge, Button, Disclosure, Field, Input, Select, Subheading, Text, Textarea } from '../../ui/components'
import { labelFor, statusTone } from '../../ui/labels'
import { RangeControls } from '../../ui/range-controls'
import { formalServiceStates } from './service-controls'
import { openServiceRecord } from './service-navigation'

const feedbackDimensions = [
  ['support_needs', '支持需求变化'],
  ['support_acceptance', '支持接受程度'],
  ['intervention_effectiveness', '干预效果（本人描述）'],
] as const
const participationLabels: Record<string, string> = {
  provided: '已自愿填写',
  declined: '明确不参与',
  unable: '无法填写',
}

interface FeedbackInput {
  participation: string
  support_needs: string | null
  support_acceptance: string | null
  intervention_effectiveness: string | null
  willing_to_continue: boolean | null
  missing_reason: string | null
}
interface Feedback extends FeedbackInput {
  feedback_id: string
  feedback_revision: number
  recorded_at: string
  supersedes_feedback_id: string | null
}
interface PendingFeedback {
  clientId: string
  revision: number
  fingerprint: string
}
interface FeedbackRecord {
  record_id: string
  service_status: keyof typeof formalServiceStates
  source_version: string
  recorded_at: string
  is_simulated: boolean
  support_needs: string | null
  support_acceptance: string | null
  intervention_effectiveness: string | null
}
export interface FeedbackProjection {
  availability: string
  reason: string | null
  records: FeedbackRecord[]
}

const feedbackSchema = v.looseObject({
  participation: v.string(),
  support_needs: v.nullable(v.string()),
  support_acceptance: v.nullable(v.string()),
  intervention_effectiveness: v.nullable(v.string()),
  willing_to_continue: v.nullable(v.boolean()),
  missing_reason: v.nullable(v.string()),
  feedback_id: v.string(),
  feedback_revision: v.number(),
  recorded_at: v.string(),
  supersedes_feedback_id: v.nullable(v.string()),
})
export const feedbackProjectionSchema: v.GenericSchema<unknown, FeedbackProjection> = v.looseObject({
  availability: v.string(),
  reason: v.nullable(v.string()),
  records: v.array(
    v.looseObject({
      record_id: v.string(),
      service_status: v.picklist(['submitted', 'in_progress', 'completed', 'cancelled', 'failed']),
      source_version: v.string(),
      recorded_at: v.string(),
      is_simulated: v.boolean(),
      support_needs: v.nullable(v.string()),
      support_acceptance: v.nullable(v.string()),
      intervention_effectiveness: v.nullable(v.string()),
    }),
  ),
})

function feedbackBody(entry: FeedbackInput, revision: number) {
  return {
    expected_feedback_revision: revision,
    participation: entry.participation,
    support_needs: entry.support_needs,
    support_acceptance: entry.support_acceptance,
    intervention_effectiveness: entry.intervention_effectiveness,
    willing_to_continue: entry.willing_to_continue,
    missing_reason: entry.missing_reason,
  }
}

export function ServiceFeedbackHistory(props: { service: { service_id: string; status: string } }): JSX.Element {
  const view = untrack(captureView)
  const service = untrack(() => props.service)
  const path = `/services/${encodeURIComponent(service.service_id)}/feedback`
  const pendingKey = untrack(() => referenceKey(`feedback-submission:${service.service_id}`))
  const isOwner = untrack(own)
  const eligible = ['completed', 'cancelled', 'failed'].includes(service.status)
  const begin = readGate()
  const [history, setHistory] = createSignal<Feedback[]>([])
  const [loaded, setLoaded] = createSignal(false)
  const [readError, setReadError] = createSignal<{ status: number | undefined } | null>(null)
  const [conflict, setConflict] = createSignal(false)
  const [editing, setEditing] = createSignal(false)
  const [initial, setInitial] = createSignal<FeedbackInput | null>(null)
  const pending = (): PendingFeedback | null => {
    const stored = sessionStorage.getItem(pendingKey)
    return v.parse(
      v.nullable(v.looseObject({ clientId: v.string(), revision: v.number(), fingerprint: v.string() })),
      JSON.parse(stored != null && stored !== '' ? stored : 'null'),
    )
  }
  let current: Feedback | undefined
  let retryTyped: FeedbackInput | undefined
  let retryConflict = false

  async function load(typed?: FeedbackInput, hasConflict = false): Promise<void> {
    const check = begin()
    const docs: Feedback[] = []
    try {
      let cursor: string | null = null
      do {
        const query = new URLSearchParams({ limit: '100' })
        if (cursor != null && cursor !== '') query.set('cursor', cursor)
        const page = await api(
          `${path}?${query}`,
          v.looseObject({ items: v.array(feedbackSchema), next_cursor: v.nullable(v.string()) }),
          'GET',
          null,
          view,
        )
        check()
        docs.push(...page.items)
        cursor = page.next_cursor
      } while (cursor != null && cursor !== '')
    } catch (error) {
      check()
      retryTyped = typed
      retryConflict = hasConflict
      setReadError({ status: error instanceof ApiError ? error.status : undefined })
      setEditing(false)
      return
    }
    const known = isOwner ? pending() : null
    let recovered = false
    if (known) {
      const candidate = docs.find(doc => doc.feedback_revision === known.revision + 1)
      if (candidate && (await sha(JSON.stringify(feedbackBody(candidate, known.revision)))) === known.fingerprint) {
        check()
        if (pending()?.clientId === known.clientId) sessionStorage.removeItem(pendingKey)
        recovered = true
      }
    }
    check()
    current = docs.at(-1)
    setHistory(docs.toReversed())
    setReadError(null)
    setLoaded(true)
    setConflict(hasConflict)
    setInitial(typed && !recovered ? typed : null)
    setEditing(!!typed && !recovered && eligible && scope('service-feedback:write'))
    if (recovered) notice('已从历史核实原反馈。')
  }

  async function submit(data: FeedbackInput): Promise<void> {
    if (data.participation !== 'provided' && (data.missing_reason == null || data.missing_reason === ''))
      throw new Error('请填写无法参与或不参与的原因。')
    const revision = current?.feedback_revision ?? 0
    const body = feedbackBody(data, revision)
    const hash = await sha(JSON.stringify(body))
    requireCurrentView(view)
    const known = pending()
    if (known && known.fingerprint !== hash) throw new Error('原提交尚待核实，请以原值重试或重新读取反馈历史。')
    const clientId = known?.clientId != null && known.clientId !== '' ? known.clientId : crypto.randomUUID()
    sessionStorage.setItem(pendingKey, JSON.stringify({ clientId, revision, fingerprint: hash }))
    try {
      await api(path, v.unknown(), 'POST', { ...body, client_feedback_id: clientId }, view)
      requireCurrentView(view)
      if (pending()?.clientId === clientId) sessionStorage.removeItem(pendingKey)
      await load()
      requireCurrentView(view)
      notice('本人反馈已保存。')
    } catch (error) {
      if (error instanceof ViewChanged) throw error
      const failure = error instanceof ApiError ? error : undefined
      requireCurrentView(view)
      if (
        failure !== undefined &&
        failure.status !== 0 &&
        failure.status < 500 &&
        !failure.pendingRecovery &&
        failure.code !== 'OPERATION_IN_PROGRESS'
      ) {
        if (pending()?.clientId === clientId) sessionStorage.removeItem(pendingKey)
      }
      if (
        failure?.code === 'FEEDBACK_REVISION_CONFLICT' ||
        failure === undefined ||
        failure.status === 0 ||
        failure.status >= 500 ||
        failure.pendingRecovery ||
        failure.code === 'OPERATION_IN_PROGRESS'
      ) {
        await load(data, failure?.code === 'FEEDBACK_REVISION_CONFLICT')
        requireCurrentView(view)
        if (
          current?.feedback_revision === revision + 1 &&
          (await sha(JSON.stringify(feedbackBody(current, revision)))) === hash
        ) {
          requireCurrentView(view)
          return
        }
      }
      throw error
    }
  }

  onSettled(() => {
    void load().catch((error: unknown) => {
      if (!(error instanceof ViewChanged)) actionError(error, view)
    })
  })
  return (
    <div class="space-y-4">
      <Subheading level={3}>本人三维反馈</Subheading>
      <div aria-live="polite" class="space-y-4">
        <Show when={readError()}>
          {error => (
            <div>
              <p class="text-sm/6 text-red-600 dark:text-red-400">反馈历史暂不可读取。</p>
              <Show when={error().status !== 403 && error().status !== 404}>
                <Button onAction={() => load(retryTyped, retryConflict)}>重新读取反馈</Button>
              </Show>
            </div>
          )}
        </Show>
        <Show when={!readError() && loaded()}>
          <For each={history()}>
            {doc => (
              <Disclosure
                open={doc === history()[0]}
                summary={
                  <>
                    反馈修订 {doc.feedback_revision} · {participationLabels[doc.participation]}
                  </>
                }
              >
                <Text>来源 C · {dateText(doc.recorded_at)}</Text>
                <Text>反馈编号 {doc.feedback_id}</Text>
                <Show when={doc.supersedes_feedback_id}>
                  <Text>更正自 {doc.supersedes_feedback_id}</Text>
                </Show>
                <Show when={isOwner}>
                  <Show when={doc.participation === 'provided'}>
                    <For each={feedbackDimensions}>
                      {([key, label]) => (
                        <p>
                          {label} · {doc[key] ?? '未填写'}
                        </p>
                      )}
                    </For>
                  </Show>
                  <p>
                    是否愿意继续 ·{' '}
                    {doc.willing_to_continue === null ? '未知' : doc.willing_to_continue ? '愿意' : '不愿意'}
                  </p>
                  <Show when={doc.missing_reason}>
                    <p>未填写说明 · {doc.missing_reason}</p>
                  </Show>
                </Show>
              </Disclosure>
            )}
          </For>
          <Show when={!history().length}>
            <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
              {eligible ? '尚未提交反馈。' : '当前服务状态尚不具备反馈资格。'}
            </Text>
          </Show>
          <Show when={!isOwner}>
            <Text>当前可查看获准反馈记录及修订，描述由本人查看。</Text>
          </Show>
          <Show when={conflict()}>
            <p class="text-sm/6 text-red-600 dark:text-red-400">另一份反馈已提交。请核对最新修订，原输入仍在下方。</p>
          </Show>
          <Show when={isOwner && eligible && scope('service-feedback:write')}>
            <Show
              when={editing()}
              fallback={
                <Button
                  onAction={() => {
                    setInitial(current ?? null)
                    setEditing(true)
                  }}
                >
                  {history().length ? '更正当前反馈' : '填写自愿反馈'}
                </Button>
              }
            >
              <FeedbackEditor initial={initial()} revision={history()[0]?.feedback_revision ?? 0} submit={submit} />
            </Show>
          </Show>
        </Show>
      </div>
    </div>
  )
}

function FeedbackEditor(props: {
  initial: FeedbackInput | null
  revision: number
  submit: (data: FeedbackInput) => Promise<void>
}): JSX.Element {
  const [participation, setParticipation] = createSignal(
    untrack(() =>
      props.initial?.participation != null && props.initial.participation !== ''
        ? props.initial.participation
        : 'provided',
    ),
  )
  let needs!: HTMLTextAreaElement
  let acceptance!: HTMLTextAreaElement
  let effectiveness!: HTMLTextAreaElement
  let willingness!: HTMLSelectElement
  let reason!: HTMLInputElement
  return (
    <div class="space-y-4">
      <Text>基于反馈修订 {props.revision}</Text>
      <Field label="反馈参与情况">
        <Select
          value={participation()}
          onChange={event => {
            setParticipation(event.currentTarget.value)
          }}
        >
          <For each={Object.entries(participationLabels)}>
            {([value, label]) => <option value={value}>{label}</option>}
          </For>
        </Select>
      </Field>
      <div hidden={participation() !== 'provided'} class="space-y-4">
        <Field label="支持需求变化">
          <Textarea ref={needs} rows={2} maxlength={2000} value={props.initial?.support_needs ?? ''} />
        </Field>
        <Field label="支持接受程度">
          <Textarea ref={acceptance} rows={2} maxlength={2000} value={props.initial?.support_acceptance ?? ''} />
        </Field>
        <Field label="干预效果（本人描述）">
          <Textarea
            ref={effectiveness}
            rows={2}
            maxlength={2000}
            value={props.initial?.intervention_effectiveness ?? ''}
          />
        </Field>
      </div>
      <Field label="是否愿意继续">
        <Select
          ref={willingness}
          value={props.initial?.willing_to_continue == null ? '' : props.initial.willing_to_continue ? 'yes' : 'no'}
        >
          <option value="">未知</option>
          <option value="yes">愿意</option>
          <option value="no">不愿意</option>
        </Select>
      </Field>
      <Field label="未填写说明">
        <Input ref={reason} maxlength={500} value={props.initial?.missing_reason ?? ''} />
      </Field>
      <Text>自愿描述本次体验。未知或不适用的内容可留空，并填写说明。</Text>
      <Button
        variant="primary"
        onAction={() =>
          props.submit({
            participation: participation(),
            support_needs: participation() === 'provided' ? needs.value.trim() || null : null,
            support_acceptance: participation() === 'provided' ? acceptance.value.trim() || null : null,
            intervention_effectiveness: participation() === 'provided' ? effectiveness.value.trim() || null : null,
            willing_to_continue: willingness.value ? willingness.value === 'yes' : null,
            missing_reason: reason.value.trim() || null,
          })
        }
      >
        提交本人反馈
      </Button>
    </div>
  )
}

export function CFeedbackProjection(props: { source: FeedbackProjection }): JSX.Element {
  return (
    <div class="space-y-4">
      <p class="font-medium">
        C 社会支持反馈 ·{' '}
        <Badge tone={statusTone(props.source.availability)}>{labelFor(props.source.availability)}</Badge>
      </p>
      <Show when={props.source.reason}>
        <Text>{props.source.reason}</Text>
      </Show>
      <For each={props.source.records}>
        {record => (
          <div class="space-y-2 border-t border-zinc-950/5 py-4 dark:border-white/5">
            <p>
              服务状态{' '}
              <Badge tone={statusTone(record.service_status)}>{formalServiceStates[record.service_status]}</Badge> ·
              来源修订 {record.source_version}
            </p>
            <Text>
              {dateText(record.recorded_at)} · {record.is_simulated ? '模拟' : '已登记'}
            </Text>
            <For each={feedbackDimensions}>
              {([key, label]) => (
                <Show when={record[key] !== null}>
                  <p>
                    {label} · {record[key]}
                  </p>
                </Show>
              )}
            </For>
            <Show when={scope('services:read')}>
              <Button onAction={() => openServiceRecord(record.record_id)}>查看该服务及反馈历史</Button>
            </Show>
          </div>
        )}
      </For>
    </div>
  )
}

export function SupportFeedbackPanel(): JSX.Element {
  const begin = readGate()
  const [result, setResult] = createSignal<FeedbackProjection | null>(null)
  const [error, setError] = createSignal('')
  let range!: RangeReader
  return (
    <Disclosure summary="社会支持反馈来源">
      <RangeControls
        ref={value => {
          range = value
        }}
      />
      <Button
        onAction={async view => {
          const check = begin()
          const { window_start, window_end } = range.read()
          try {
            const data = await api(
              `${patientPath('/support-feedback')}?${rangeQuery({ window_start, window_end, limit: 100 })}`,
              feedbackProjectionSchema,
              'GET',
              null,
              view,
            )
            check()
            setResult(data)
            setError('')
          } catch (failure) {
            check()
            setResult(null)
            setError(failure instanceof Error ? failure.message : '')
          }
        }}
      >
        读取本人社会支持反馈
      </Button>
      <div aria-live="polite">
        <Show when={error()}>
          <p class="text-sm/6 text-red-600 dark:text-red-400">{error()}</p>
        </Show>
        <Show when={result()}>
          {data => (
            <>
              <CFeedbackProjection source={data()} />
              <Show when={data().records.length === 100}>
                <Text>如需查看其他记录，请缩小日期范围。</Text>
              </Show>
            </>
          )}
        </Show>
      </div>
    </Disclosure>
  )
}
