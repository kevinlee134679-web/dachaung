import type { View } from '../../session/session'
import type { DispatchAttempt, DispatchTask } from './dispatch'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { ApiError, api } from '../../api/api'
import { dateText } from '../../date/date'
import { actionError } from '../../notice/notice'
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
import { Badge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Checkbox, Field, Input, Select } from '../../ui/form'
import { labelFor, statusTone } from '../../ui/labels'
import { EmptyState } from '../../ui/list'
import { Subheading, Text } from '../../ui/typography'
import { peerResumeFromDraft } from '../peer/peer'
import { dispatchAttemptSchema, dispatchDescription, dispatchTaskSchema, formalServiceStates } from './dispatch'
import { serviceWrite } from './draft-data'
import { ServiceFeedbackHistory } from './feedback/feedback-history'

interface ServiceRecord {
  service_id: string
  service_name: string
  status: string
  resource_version: string
  provider: { display_name: string }
  request_text: string
  submitted_at: string
  started_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  failed_at: string | null
  failure_reason: string | null
  cancellation_reason: string | null
  result_summary: string | null
  provider_response: { text: string } | null
  service_kind: string
  service_draft_id: string
  dispatch_task_id: string | null
  meta: { revision: number }
}

const serviceRecordSchema: v.GenericSchema<unknown, ServiceRecord> = v.looseObject({
  service_id: v.string(),
  service_name: v.string(),
  status: v.string(),
  resource_version: v.string(),
  provider: v.looseObject({ display_name: v.string() }),
  request_text: v.string(),
  submitted_at: v.string(),
  started_at: v.nullable(v.string()),
  completed_at: v.nullable(v.string()),
  cancelled_at: v.nullable(v.string()),
  failed_at: v.nullable(v.string()),
  failure_reason: v.nullable(v.string()),
  cancellation_reason: v.nullable(v.string()),
  result_summary: v.nullable(v.string()),
  provider_response: v.nullable(v.looseObject({ text: v.string() })),
  service_kind: v.string(),
  service_draft_id: v.string(),
  dispatch_task_id: v.nullable(v.string()),
  meta: v.looseObject({ revision: v.number() }),
})

interface DispatchDetails {
  task: DispatchTask
  attempts: DispatchAttempt[]
}

export function ServiceRecordsPage(): JSX.Element {
  let filter!: HTMLSelectElement
  let reason!: HTMLInputElement
  let explicit!: HTMLInputElement
  const beginDetail = readGate()
  const beginList = readGate()
  const [records, setRecords] = createSignal<ServiceRecord[]>([])
  const [cursor, setCursor] = createSignal<string | null>(null)
  const [loaded, setLoaded] = createSignal(false)
  const [record, setRecord] = createSignal<ServiceRecord | null>(null)
  const [unsavedReason, setUnsavedReason] = createSignal('')
  const [dispatch, setDispatch] = createSignal<DispatchDetails | null>(null)
  const [dispatchError, setDispatchError] = createSignal(false)
  let detailCheck = () => {}

  async function list(view: View, next: string | null = null): Promise<void> {
    const check = beginList()
    const query = new URLSearchParams({ limit: '20' })
    if (filter.value) query.set('status', filter.value)
    if (next !== null && next !== '') query.set('cursor', next)
    const page = await api(
      `${patientPath('/services')}?${query}`,
      v.looseObject({ items: v.array(serviceRecordSchema), next_cursor: v.nullable(v.string()) }),
      'GET',
      null,
      view,
    )
    check()
    requireCurrentView(view)
    setRecords(previous => (next !== null && next !== '' ? [...previous, ...page.items] : page.items))
    setCursor(page.next_cursor)
    setLoaded(true)
  }

  async function load(view: View, id: string, retainedReason = ''): Promise<void> {
    const check = beginDetail()
    detailCheck = check
    setRecord(null)
    setDispatch(null)
    setDispatchError(false)
    const value = await api(`/services/${encodeURIComponent(id)}`, serviceRecordSchema, 'GET', null, view)
    check()
    requireCurrentView(view)
    sessionStorage.setItem(referenceKey('formal-service'), id)
    setUnsavedReason(retainedReason)
    setRecord(value)
    if (value.dispatch_task_id !== null && value.dispatch_task_id !== '' && scope('tasks:read')) {
      const path = `/tasks/${encodeURIComponent(value.dispatch_task_id)}`
      try {
        const [task, attempts] = await Promise.all([
          api(path, dispatchTaskSchema, 'GET', null, view),
          api(`${path}/executions`, v.looseObject({ items: v.array(dispatchAttemptSchema) }), 'GET', null, view),
        ])
        check()
        requireCurrentView(view)
        setDispatch({ task, attempts: attempts.items })
      } catch (caught) {
        check()
        requireCurrentView(view)
        if (!(caught instanceof ApiError) || (caught.status !== 403 && caught.status !== 404)) setDispatchError(true)
      }
    }
  }

  async function refreshRecord(view: View, current: ServiceRecord): Promise<void> {
    const check = detailCheck
    const id = current.service_id
    await list(view)
    check()
    await load(view, id)
  }

  function openRecord(id: string): (view: View) => Promise<void> {
    return async view => {
      await load(view, id)
    }
  }

  function loadNext(next: string): (view: View) => Promise<void> {
    return async view => {
      await list(view, next)
    }
  }

  async function resumePeer(view: View, current: ServiceRecord): Promise<void> {
    const check = detailCheck
    const draft = await api(
      `/service-drafts/${encodeURIComponent(current.service_draft_id)}`,
      v.looseObject({ peer_group_id: v.nullable(v.string()) }),
      'GET',
      null,
      view,
    )
    check()
    requireCurrentView(view)
    if (draft.peer_group_id !== null && draft.peer_group_id !== '')
      peerResumeFromDraft({ peer_group_id: draft.peer_group_id })
  }

  async function cancelRecord(view: View, current: ServiceRecord): Promise<void> {
    const check = detailCheck
    if (!explicit.checked || !reason.value.trim()) throw new Error('请填写原因并明确确认取消。')
    const typed = reason.value
    try {
      await serviceWrite(
        `/services/${encodeURIComponent(current.service_id)}/cancel`,
        'POST',
        { expected_revision: current.meta.revision, reason: typed.trim() },
        v.unknown(),
        view,
      )
      check()
      await list(view)
      check()
      await load(view, current.service_id)
    } catch (caught) {
      check()
      const status = caught instanceof ApiError ? caught.status : undefined
      if (status === 409 || status === undefined || status === 0 || status >= 500)
        await load(view, current.service_id, typed)
      throw caught
    }
  }

  onSettled(() => {
    if (!scope('services:read')) return
    const view = captureView()
    const check = beginDetail()
    void (async () => {
      await list(view)
      check()
      requireCurrentView(view)
      const selected = sessionStorage.getItem(referenceKey('formal-service'))
      if (selected !== null && selected !== '') await load(view, selected)
    })().catch((error: unknown) => {
      if (!(error instanceof ViewChanged)) actionError(error, view)
    })
  })

  return (
    <Show when={scope('services:read')}>
      <Card title="正式服务记录">
        <div class="space-y-4">
          <Text>本地虚构演示</Text>
          <Field label="按服务状态查看">
            <Select
              ref={filter}
              onChange={() => {
                const view = captureView()
                void list(view).catch((error: unknown) => {
                  if (!(error instanceof ViewChanged)) actionError(error, view)
                })
              }}
            >
              <option value="">全部</option>
              <For each={Object.entries(formalServiceStates)}>
                {entry => <option value={entry[0]}>{entry[1]}</option>}
              </For>
            </Select>
          </Field>
          <div class="space-y-2">
            <Show when={loaded() && records().length === 0}>
              <EmptyState>暂无此范围内的正式服务。</EmptyState>
            </Show>
            <For each={records()}>
              {item => (
                <div class="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-950/5 py-4 dark:border-white/5">
                  <Button variant="plain" onAction={openRecord(item.service_id)}>
                    {item.service_name} ·{' '}
                    <Badge tone={statusTone(item.status)}>{formalServiceStates[item.status]}</Badge>
                  </Button>
                </div>
              )}
            </For>
            <Show when={cursor()}>{next => <Button onAction={loadNext(next())}>读取下一页</Button>}</Show>
          </div>
          <div aria-live="polite">
            <Show when={record()}>
              {item => (
                <div class="my-5 space-y-3">
                  <Subheading level={3}>{item().service_name}</Subheading>
                  <Text>服务编号 {item().service_id}</Text>
                  <p>
                    服务状态 <Badge tone={statusTone(item().status)}>{formalServiceStates[item().status]}</Badge>
                  </p>
                  <Text>
                    目录版本 {item().resource_version} · {item().provider.display_name} · mock/demo
                  </Text>
                  <Show when={own()}>
                    <p>{item().request_text}</p>
                  </Show>
                  <ul>
                    <For
                      each={(
                        [
                          ['提交', item().submitted_at],
                          ['模拟接收', item().started_at],
                          ['模拟完成', item().completed_at],
                          ['取消', item().cancelled_at],
                          ['失败', item().failed_at],
                        ] as [string, string | null][]
                      ).filter((entry): entry is [string, string] => entry[1] !== null && entry[1] !== '')}
                    >
                      {entry => (
                        <li>
                          {entry[0]} {dateText(entry[1])}
                        </li>
                      )}
                    </For>
                  </ul>
                  <For
                    each={[item().failure_reason, item().cancellation_reason, item().result_summary].filter(Boolean)}
                  >
                    {message => <p>{message}</p>}
                  </For>
                  <Show when={item().provider_response}>{response => <p>模拟答复 · {response().text}</p>}</Show>
                  <div class="flex flex-wrap gap-3">
                    <Button onAction={view => refreshRecord(view, item())}>刷新服务状态</Button>
                    <Show when={own() && item().service_kind === 'peer_support'}>
                      <Button onAction={view => resumePeer(view, item())}>核对原入组申请</Button>
                    </Show>
                  </div>
                  <Show when={scope('services:read') && scope('feedback:read')}>
                    <For each={[item()]}>{service => <ServiceFeedbackHistory service={service} />}</For>
                  </Show>
                  <Show when={own() && ['submitted', 'in_progress'].includes(item().status)}>
                    <div>
                      <Field label="取消原因">
                        <Input ref={reason} value={unsavedReason()} maxlength={500} />
                      </Field>
                      <Checkbox ref={explicit} label="我明确取消本次服务" />
                      <Button variant="danger" onAction={view => cancelRecord(view, item())}>
                        取消正式服务
                      </Button>
                    </div>
                  </Show>
                  <Show when={dispatch()}>
                    {details => (
                      <div>
                        <Subheading level={3}>模拟派发</Subheading>
                        <Text>派发任务 {item().dispatch_task_id}</Text>
                        <p>
                          {details().attempts.at(-1)?.execution_status === 'outcome_unknown' &&
                          item().started_at !== null &&
                          item().started_at !== ''
                            ? '原派发结果曾未知，后续模拟回执已登记接收。'
                            : dispatchDescription(details().task, details().attempts.at(-1))}
                        </p>
                        <For each={details().attempts}>
                          {attempt => (
                            <p class="text-sm/6 text-zinc-500 dark:text-zinc-400">
                              尝试 {attempt.attempt} ·{' '}
                              <Badge tone={statusTone(attempt.execution_status)}>
                                {labelFor(attempt.execution_status)}
                              </Badge>
                            </p>
                          )}
                        </For>
                      </div>
                    )}
                  </Show>
                  <Show when={dispatchError()}>
                    <p class="text-sm/6 text-red-600 dark:text-red-400">原派发状态暂不可核查，请刷新。</p>
                  </Show>
                </div>
              )}
            </Show>
          </div>
        </div>
      </Card>
    </Show>
  )
}
