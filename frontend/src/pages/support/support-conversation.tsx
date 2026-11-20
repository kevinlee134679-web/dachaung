import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api, ApiError, sha } from '../../api/api'
import { dateText } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import {
  captureView,
  isCurrentView,
  own,
  referenceKey,
  requireCurrentView,
  scope,
  ViewChanged,
} from '../../session/session'
import { navigate } from '../../shell/navigation'
import { Badge, Button, Card, Disclosure, Field, Select, Subheading, Text, Textarea } from '../../ui/components'
import { statusTone } from '../../ui/labels'
import { refreshSupport } from './home-support-invitations'

export interface SupportSession {
  session_id: string
  status: 'active' | 'closed'
  ui_mode: 'normal' | 'simplified'
  turn_count: number
  opened_at: string
  meta: { revision: number }
}
export const supportSessionSchema: v.GenericSchema<unknown, SupportSession> = v.looseObject({
  session_id: v.string(),
  status: v.picklist(['active', 'closed']),
  ui_mode: v.picklist(['normal', 'simplified']),
  turn_count: v.number(),
  opened_at: v.string(),
  meta: v.looseObject({ revision: v.number() }),
})
interface Message {
  role: 'user' | 'assistant'
  content: string
  generation_status:
    | 'accepted'
    | 'running'
    | 'failed'
    | 'outcome_unknown'
    | 'cancelled'
    | 'completed'
    | 'not_applicable'
  message_id: string
  generation_id: string
}
const messageSchema: v.GenericSchema<unknown, Message> = v.looseObject({
  role: v.picklist(['user', 'assistant']),
  content: v.string(),
  generation_status: v.picklist([
    'accepted',
    'running',
    'failed',
    'outcome_unknown',
    'cancelled',
    'completed',
    'not_applicable',
  ]),
  message_id: v.string(),
  generation_id: v.string(),
})
const cueSchema = v.looseObject({ label: v.string(), evidence: v.string() })
const assessmentSchema = v.looseObject({
  kind: v.picklist(['model_cues', 'self_report']),
  observed_at: v.string(),
  self_report_items: v.array(v.looseObject({ description: v.string() })),
  cues: v.array(cueSchema),
})
const modeSchema = v.looseObject({
  effective_ui_mode: v.picklist(['normal', 'simplified']),
  current: v.looseObject({ revision: v.number() }),
})
const outputSchema = v.looseObject({
  business_output: v.looseObject({
    communication_strategy: v.array(
      v.picklist([
        'reflection',
        'affirmation',
        'open_question',
        'autonomy_support',
        'permission_based_advice',
        'summary',
      ]),
    ),
    difficulty_cues: v.array(cueSchema),
    knowledge_citations: v.array(v.looseObject({ knowledge_id: v.string(), version: v.string(), quote: v.string() })),
    suggested_action: v.nullable(v.looseObject({ description: v.string() })),
  }),
  generation: v.looseObject({
    mode: v.picklist(['mock', 'real']),
    actual_pipeline: v.picklist(['single_pass', 'star']),
    session_id: v.string(),
    input_snapshot: v.looseObject({ missing_items: v.array(v.looseObject({ message: v.string() })) }),
  }),
})
const pendingSchema = v.looseObject({
  id: v.string(),
  hash: v.string(),
  turn: v.number(),
  rejected: v.exactOptional(v.boolean()),
})
type Assessment = v.InferOutput<typeof assessmentSchema>
type Mode = v.InferOutput<typeof modeSchema>
type Output = v.InferOutput<typeof outputSchema>
type Pending = v.InferOutput<typeof pendingSchema>
interface RefreshState {
  accountId: string | null
  patientId: string | null
  sessionId: string
  draft?: string
  output?: Output
  message?: string
}
let pendingRefresh: RefreshState | null = null
const generationState: Record<string, string> = {
  accepted: '等待生成',
  running: '生成中',
  failed: '生成失败',
  outcome_unknown: '结果未知，先核查原消息',
  cancelled: '生成已取消',
}
const assessmentSource: Record<string, string> = {
  model_cues: '模型线索',
  self_report: '本人自评',
  context_summary: '上下文摘要',
}
function supportPath(session: SupportSession, suffix = ''): string {
  return `/sessions/${encodeURIComponent(session.session_id)}${suffix}`
}

export function SupportMessage(props: { session: SupportSession; message: Message; canWrite: boolean }): JSX.Element {
  async function retry(view: View): Promise<void> {
    const data = await api(
      `/messages/${encodeURIComponent(props.message.message_id)}/generation-retries`,
      outputSchema,
      'POST',
      { generation_id: props.message.generation_id, expected_turn_count: props.session.turn_count },
      view,
    )
    requireCurrentView(view)
    pendingRefresh = {
      accountId: view.accountId,
      patientId: view.patientId,
      sessionId: props.session.session_id,
      output: data,
    }
    refreshSupport(view)
  }
  return (
    <article class={`flex ${props.message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div
        class={`max-w-[85%] space-y-2 rounded-xl px-4 py-3 text-sm/6 ${props.message.role === 'user' ? 'bg-teal-50 text-teal-950 dark:bg-teal-500/15 dark:text-teal-100' : 'bg-zinc-100 text-zinc-950 dark:bg-white/5 dark:text-white'}`}
      >
        <small class="font-medium">{props.message.role === 'user' ? '本人' : 'AI 支持助手'}</small>
        <p class="whitespace-pre-wrap">{props.message.content}</p>
        <Show when={props.message.role === 'user' && generationState[props.message.generation_status]}>
          <Badge tone={statusTone(props.message.generation_status)}>
            {generationState[props.message.generation_status]}
          </Badge>
          <Show when={props.canWrite && props.message.generation_status === 'failed'}>
            <Button onAction={retry}>重试原消息</Button>
          </Show>
        </Show>
      </div>
    </article>
  )
}

function OutputDetails(props: { output: Output }): JSX.Element {
  const [documents, setDocuments] = createSignal<
    Record<string, { title: string; review_status: string; body: string; source_locator: string }>
  >({})
  async function readDocument(
    view: View,
    citation: Output['business_output']['knowledge_citations'][number],
  ): Promise<void> {
    const key = `${citation.knowledge_id}:${citation.version}`
    const doc = await api(
      `/knowledge/${encodeURIComponent(citation.knowledge_id)}/versions/${encodeURIComponent(citation.version)}?session_id=${encodeURIComponent(props.output.generation.session_id)}`,
      v.looseObject({ title: v.string(), review_status: v.string(), body: v.string(), source_locator: v.string() }),
      'GET',
      null,
      view,
    )
    requireCurrentView(view)
    setDocuments(previous => ({ ...previous, [key]: doc }))
  }
  return (
    <Disclosure summary="本轮来源与沟通说明">
      <p>
        实际来源 {props.output.generation.mode} / {props.output.generation.actual_pipeline}
      </p>
      <p>策略 {props.output.business_output.communication_strategy.join('、')}</p>
      <For each={props.output.business_output.difficulty_cues}>
        {cue => (
          <p>
            {cue.label} · {cue.evidence}
          </p>
        )}
      </For>
      <For each={props.output.business_output.knowledge_citations}>
        {citation => (
          <div>
            <p>{citation.quote}</p>
            <Button onAction={view => readDocument(view, citation)}>查看所引资料版本</Button>
            <Show when={documents()[`${citation.knowledge_id}:${citation.version}`]}>
              {doc => (
                <>
                  <p>
                    {doc().title} · <Badge tone={statusTone(doc().review_status)}>{doc().review_status}</Badge>
                  </p>
                  <p>{doc().body}</p>
                  <p>{doc().source_locator}</p>
                </>
              )}
            </Show>
          </div>
        )}
      </For>
      <Show when={props.output.business_output.suggested_action}>
        {action => <p>沟通建议 · {action().description}</p>}
      </Show>
      <For each={props.output.generation.input_snapshot.missing_items}>{issue => <Text>{issue.message}</Text>}</For>
    </Disclosure>
  )
}

export function SupportConversation(props: { session: SupportSession }): JSX.Element {
  const [mode, setMode] = createSignal<Mode | null>(null)
  const [messages, setMessages] = createSignal<Message[]>([])
  const [assessments, setAssessments] = createSignal<Assessment[]>([])
  const [loaded, setLoaded] = createSignal(false)
  const [pendingVisible, setPendingVisible] = createSignal(false)
  const [output, setOutput] = createSignal<Output | null>(null)
  let editor!: HTMLTextAreaElement
  let dimension!: HTMLSelectElement
  let description!: HTMLTextAreaElement
  const reportId = crypto.randomUUID()
  const canWrite = () => own() && props.session.status === 'active'
  const simplified = () => (mode()?.effective_ui_mode ?? props.session.ui_mode) === 'simplified'
  const key = () => referenceKey(`support-pending:${props.session.session_id}`)
  const readPending = (): Pending | null =>
    v.parse(v.nullable(pendingSchema), JSON.parse(sessionStorage.getItem(key()) ?? 'null'))
  const clearPending = (pending: Pending) => {
    if (readPending()?.id === pending.id) sessionStorage.removeItem(key())
  }
  function reload(view: View, extra: Omit<RefreshState, 'accountId' | 'patientId' | 'sessionId'> = {}): void {
    requireCurrentView(view)
    pendingRefresh = {
      accountId: view.accountId,
      patientId: view.patientId,
      sessionId: props.session.session_id,
      ...extra,
    }
    refreshSupport(view)
  }
  onSettled(() => {
    const view = captureView()
    void (async () => {
      const currentMode = scope('interventions:read')
        ? await api(supportPath(props.session, '/ui-mode'), modeSchema, 'GET', null, view)
        : null
      const thread = await all(supportPath(props.session, '/messages'), messageSchema, view)
      const records =
        (currentMode?.effective_ui_mode ?? props.session.ui_mode) !== 'simplified' && scope('assessment:read')
          ? await all(supportPath(props.session, '/assessments'), assessmentSchema, view)
          : []
      requireCurrentView(view)
      setMode(currentMode)
      setMessages(thread)
      setAssessments(records)
      setPendingVisible(!!readPending())
      if (
        pendingRefresh &&
        pendingRefresh.accountId === view.accountId &&
        pendingRefresh.patientId === view.patientId &&
        pendingRefresh.sessionId === props.session.session_id
      ) {
        const saved = pendingRefresh
        pendingRefresh = null
        if (saved.output && scope('interventions:read')) setOutput(saved.output)
        setLoaded(true)
        if (saved.draft !== undefined) {
          const draft = saved.draft
          onSettled(() => {
            if (isCurrentView(view) && editor.value === '') {
              editor.value = draft
              if (saved.message !== undefined) notice(saved.message)
            }
          })
        } else if (saved.message !== undefined) {
          notice(saved.message)
        }
      } else {
        pendingRefresh = null
        setLoaded(true)
      }
    })().catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })
  async function recover(view: View): Promise<void> {
    const pending = readPending()
    if (!pending) return
    let result: { items: Message[] }
    try {
      result = await api(
        supportPath(props.session, `/messages?client_message_id=${encodeURIComponent(pending.id)}`),
        v.looseObject({ items: v.array(messageSchema) }),
        'GET',
        null,
        view,
      )
    } catch (error) {
      if (
        !pending.rejected ||
        !(error instanceof ApiError) ||
        error.status !== 404 ||
        error.code !== 'RESOURCE_NOT_FOUND'
      ) {
        throw error
      }
      requireCurrentView(view)
      const draft = editor.value
      clearPending(pending)
      reload(view, { draft, message: '会话已更新。请核对最新记录后再次点击发送。' })
      return
    }
    requireCurrentView(view)
    const message = result.items[0]
    if (!message) return
    const status = message.generation_status
    if (!['accepted', 'running'].includes(status)) clearPending(pending)
    reload(view, { message: generationState[status] ?? '已核对原消息。' })
  }
  async function send(view: View): Promise<void> {
    const content = editor.value
    if (!content.trim()) throw new Error('请先填写消息。')
    const hash = await sha(content)
    requireCurrentView(view)
    const old = readPending()
    if (old?.rejected) return recover(view)
    if (old && old.hash !== hash) throw new Error('上一条结果尚未核对。请核查原消息，或使用相同原文重试。')
    const pending = old ?? { id: crypto.randomUUID(), hash, turn: props.session.turn_count }
    sessionStorage.setItem(key(), JSON.stringify(pending))
    let data: Output
    try {
      data = await api(
        supportPath(props.session, '/messages'),
        outputSchema,
        'POST',
        { client_message_id: pending.id, expected_turn_count: pending.turn, content },
        view,
      )
    } catch (error) {
      if (error instanceof ViewChanged) throw error
      requireCurrentView(view)
      if (
        error instanceof ApiError &&
        error.status === 409 &&
        error.code === 'SESSION_REVISION_CONFLICT' &&
        readPending()?.id === pending.id
      ) {
        sessionStorage.setItem(key(), JSON.stringify({ ...pending, rejected: true }))
      }
      try {
        await recover(view)
      } catch (lookup) {
        if (lookup instanceof ViewChanged) throw lookup
        if (isCurrentView(view)) setPendingVisible(true)
        throw error
      }
      return
    }
    clearPending(pending)
    reload(view, { output: data })
  }
  async function toggleMode(view: View, mode: Mode): Promise<void> {
    await api(
      supportPath(props.session, '/ui-mode'),
      v.unknown(),
      'PUT',
      {
        ui_mode: simplified() ? 'normal' : 'simplified',
        expected_revision: mode.current.revision,
        confirmed: true,
        source_suggestion_id: null,
      },
      view,
    )
    refreshSupport(view)
  }
  async function close(view: View): Promise<void> {
    await api(
      supportPath(props.session, '/close'),
      v.unknown(),
      'POST',
      { expected_revision: props.session.meta.revision },
      view,
    )
    refreshSupport(view)
  }
  async function saveAssessment(view: View): Promise<void> {
    await api(
      supportPath(props.session, '/self-reports'),
      v.unknown(),
      'POST',
      {
        client_report_id: reportId,
        items: [{ dimension: dimension.value, description: description.value, source_message_id: null }],
      },
      view,
    )
    reload(view, { message: '已保存自评。' })
  }
  return (
    <Show when={loaded()}>
      <Card>
        <div class="space-y-6">
          <div>
            <Subheading>{simplified() ? '极简对话' : '支持对话'}</Subheading>
            <Text>本地模拟对话</Text>
          </div>
          <div class="flex flex-wrap gap-3">
            <Show when={canWrite() && mode()}>
              {value => (
                <Button onAction={view => toggleMode(view, value())}>
                  {simplified() ? '恢复普通模式' : '使用极简模式'}
                </Button>
              )}
            </Show>
            <Show when={scope('plan:read')}>
              <Button onAction={() => navigate('medication')}>今日用药确认</Button>
            </Show>
            <Show when={canWrite()}>
              <Button onAction={close}>结束会话</Button>
            </Show>
          </div>
          <div aria-label="对话历史" class="space-y-4">
            <For
              each={messages()}
              fallback={
                <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
                  可以从你现在最想说的一件事开始。
                </Text>
              }
            >
              {message => <SupportMessage session={props.session} message={message} canWrite={canWrite()} />}
            </For>
          </div>
          <Show when={!simplified() && scope('assessment:read')}>
            <Disclosure summary="自评与沟通线索">
              <Text>这里记录你的描述及可核对的线索。评分方法尚未接入。</Text>
              <For each={assessments()}>
                {record => (
                  <>
                    <Text>
                      {assessmentSource[record.kind]} · {dateText(record.observed_at)}
                    </Text>
                    <For each={record.self_report_items}>{item => <p>{item.description}</p>}</For>
                    <For each={record.cues}>
                      {cue => (
                        <p>
                          {cue.label} · {cue.evidence}
                        </p>
                      )}
                    </For>
                  </>
                )}
              </For>
              <Show when={canWrite() && scope('assessment:write')}>
                <Field label="自评主题">
                  <Select ref={dimension}>
                    <option value="concerns">顾虑</option>
                    <option value="necessity">必要性感知</option>
                    <option value="burden">负担</option>
                    <option value="routine">作息</option>
                    <option value="support_need">支持需求</option>
                  </Select>
                </Field>
                <Field label="你的描述">
                  <Textarea ref={description} maxlength={2000} rows={2} />
                </Field>
                <Button onAction={saveAssessment}>保存自评</Button>
              </Show>
            </Disclosure>
          </Show>
          <Show when={!simplified() && output()}>{value => <OutputDetails output={value()} />}</Show>
          <Show when={canWrite()}>
            <div class="space-y-4 border-t border-zinc-950/5 pt-4 dark:border-white/10">
              <Show when={pendingVisible()}>
                <Button onAction={recover}>核查原消息</Button>
              </Show>
              <Field label="你想说的话">
                <Textarea
                  ref={editor}
                  maxlength={4000}
                  rows={3}
                  placeholder="写下想说的话"
                  data-support-session={props.session.session_id}
                />
              </Field>
              <Button variant="primary" onAction={send}>
                发送
              </Button>
            </div>
          </Show>
        </div>
      </Card>
    </Show>
  )
}
