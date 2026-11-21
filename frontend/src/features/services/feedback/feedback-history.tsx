import type { Feedback, FeedbackInput, PendingFeedback } from './feedback'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show, untrack } from 'solid-js'
import * as v from 'valibot'
import { api, ApiError, sha } from '../../../api/api'
import { dateText } from '../../../date/date'
import { actionError, notice } from '../../../notice/notice'
import { readGate } from '../../../session/read-gate'
import { captureView, own, referenceKey, requireCurrentView, scope, ViewChanged } from '../../../session/session'
import { Button } from '../../../ui/button'
import { Disclosure } from '../../../ui/disclosure'
import { EmptyState } from '../../../ui/list'
import { Subheading, Text } from '../../../ui/typography'
import { feedbackBody, feedbackDimensions, feedbackSchema, participationLabels } from './feedback'
import { FeedbackEditor } from './feedback-editor'

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
            <EmptyState>{eligible ? '尚未提交反馈。' : '当前服务状态尚不具备反馈资格。'}</EmptyState>
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
