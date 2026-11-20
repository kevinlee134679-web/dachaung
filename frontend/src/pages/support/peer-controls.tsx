import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api, ApiError } from '../../api/api'
import { dateText } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import { readGate } from '../../session/read-gate'
import { captureView, referenceKey, requireCurrentView, ViewChanged } from '../../session/session'
import { navigate } from '../../shell/navigation'
import { Badge, Button, Card, Checkbox, Field, Input, Text } from '../../ui/components'
import { statusTone } from '../../ui/labels'
import { serviceWrite } from './service-draft-data'

export interface PeerMembership {
  group_id: string
  membership_id: string
  service_id: string
  alias: string
  status: string
  revision: number
  can_participate: boolean
}

export interface PeerPost {
  post_id: string
  author_alias: string
  moderation_status: 'pending' | 'visible' | 'hidden'
  content: string
  created_at: string
  revision: number
}

export interface PeerPage<T> {
  items: T[]
  next_cursor: string | null
}

export interface PeerJoinDraft {
  service_draft_id: string
  draft_revision: number
  confirmation_ref_id: string
  sharing_scope_ref_id: string
  peer_group_id: string
  request_text: string
}

export const peerMembershipSchema: v.GenericSchema<unknown, PeerMembership> = v.looseObject({
  group_id: v.string(),
  membership_id: v.string(),
  service_id: v.string(),
  alias: v.string(),
  status: v.string(),
  revision: v.number(),
  can_participate: v.boolean(),
})
const peerPostSchema = v.looseObject({
  post_id: v.string(),
  author_alias: v.string(),
  moderation_status: v.picklist(['pending', 'visible', 'hidden']),
  content: v.string(),
  created_at: v.string(),
  revision: v.number(),
})
export const peerPostPageSchema: v.GenericSchema<unknown, PeerPage<PeerPost>> = v.looseObject({
  items: v.array(peerPostSchema),
  next_cursor: v.nullable(v.string()),
})

const peerJoinResultSchema = v.looseObject({ group_id: v.string() })

const peerReviewStatus = { pending: '待审', visible: '已公开', hidden: '已隐藏' }

export function peerPath(group: string): string {
  return `/peer-groups/${encodeURIComponent(group)}`
}

function openPeer(group: string): void {
  sessionStorage.setItem(referenceKey('peer-group'), group)
  navigate('support', 'peer')
}

export function peerResumeFromDraft(draft: { peer_group_id: string }): void {
  openPeer(draft.peer_group_id)
}

export function PeerJoinControls(props: {
  draft: PeerJoinDraft
  textArea: HTMLTextAreaElement
  view: View
}): JSX.Element {
  let confirmed!: HTMLInputElement
  async function join(): Promise<void> {
    const draft = props.draft
    const view = props.view
    if (!confirmed.checked || props.textArea.value.trim() !== draft.request_text)
      throw new Error('请先核对已保存草稿并明确自愿加入。')
    const path = `${peerPath(draft.peer_group_id)}/memberships`
    const body = {
      service_draft_id: draft.service_draft_id,
      draft_revision: draft.draft_revision,
      confirmation_ref_id: draft.confirmation_ref_id,
      sharing_scope_ref_id: draft.sharing_scope_ref_id,
    }
    let member: { group_id: string }
    try {
      member = await serviceWrite(path, 'POST', body, peerJoinResultSchema, view)
    } catch (caught) {
      if (
        caught instanceof ViewChanged ||
        (caught instanceof ApiError && caught.status < 500 && caught.code !== 'OPERATION_IN_PROGRESS')
      ) {
        throw caught
      }
      const current = await api(
        `/service-drafts/${encodeURIComponent(draft.service_draft_id)}`,
        v.looseObject({ service_id: v.nullable(v.string()), draft_revision: v.number() }),
        'GET',
        null,
        view,
      )
      requireCurrentView(view)
      if (current.service_id === null || current.service_id === '' || current.draft_revision !== draft.draft_revision)
        throw caught
      member = await serviceWrite(path, 'POST', body, peerJoinResultSchema, view)
    }
    requireCurrentView(view)
    openPeer(member.group_id)
    notice('已登记模拟入组申请。')
  }
  return (
    <div class="space-y-4">
      <Checkbox ref={confirmed} label="我本人自愿申请加入此模拟小组" />
      <Button view={props.view} variant="primary" onAction={join}>
        提交入组申请
      </Button>
    </div>
  )
}

export function PeerPostItem(props: { post: PeerPost }): JSX.Element {
  return (
    <article class="space-y-2 py-4">
      <p class="text-sm/6 font-medium text-zinc-950 dark:text-white">
        {props.post.author_alias} ·{' '}
        <Badge tone={statusTone(props.post.moderation_status)}>{peerReviewStatus[props.post.moderation_status]}</Badge>
      </p>
      <p>{props.post.content}</p>
      <p class="text-sm/6 text-zinc-500 dark:text-zinc-400">{dateText(props.post.created_at)}</p>
    </article>
  )
}

export function PeerHomeMembership(): JSX.Element {
  const [membership, setMembership] = createSignal<PeerMembership | undefined>()
  onSettled(() => {
    const view = captureView()
    void all('/peer-memberships/me', peerMembershipSchema, view)
      .then(items => {
        requireCurrentView(view)
        setMembership(items.find(item => item.status !== 'left'))
      })
      .catch((error: unknown) => {
        if (!(error instanceof ViewChanged)) actionError(error, view)
      })
  })
  return (
    <Show when={membership()}>
      {item => <Button onAction={() => openPeer(item().group_id)}>查看我的同辈小组</Button>}
    </Show>
  )
}

function ModerationItem(props: {
  post: PeerPost
  check: () => void
  reload: (view: View) => Promise<void>
}): JSX.Element {
  let reason!: HTMLInputElement
  async function moderate(view: View, decision: string): Promise<void> {
    props.check()
    if (!reason.value.trim()) throw new Error('请填写模拟审核依据。')
    await serviceWrite(
      `/peer-posts/${encodeURIComponent(props.post.post_id)}/moderation`,
      'POST',
      { expected_revision: props.post.revision, decision, reason: reason.value.trim() },
      v.unknown(),
      view,
    )
    props.check()
    await props.reload(view)
    requireCurrentView(view)
    notice('已保存模拟审核。')
  }
  return (
    <div class="space-y-4 py-4">
      <PeerPostItem post={props.post} />
      <Field label="模拟审核说明">
        <Input ref={reason} maxlength={500} />
      </Field>
      <div class="flex flex-wrap gap-3">
        <Show when={props.post.moderation_status === 'pending'}>
          <Button variant="primary" onAction={view => moderate(view, 'visible')}>
            允许匿名公开
          </Button>
        </Show>
        <Button onAction={view => moderate(view, 'hidden')}>隐藏此文字</Button>
      </div>
    </div>
  )
}

export function PeerModerationControls(): JSX.Element {
  let group!: HTMLInputElement
  const begin = readGate()
  const [posts, setPosts] = createSignal<{ post: PeerPost; check: () => void }[]>([])
  const [cursor, setCursor] = createSignal<string | null>(null)
  const [loaded, setLoaded] = createSignal(false)
  async function load(view: View, next: string | null = null): Promise<void> {
    const current = begin()
    const id = group.value.trim()
    if (!id) throw new Error('请填写已登记的审核小组编号。')
    if (next === null) {
      setPosts([])
      setLoaded(false)
      setCursor(null)
    }
    const query = new URLSearchParams({ include_pending: 'true' })
    if (next !== null) query.set('cursor', next)
    const page = await api(`${peerPath(id)}/posts?${query}`, peerPostPageSchema, 'GET', null, view)
    current()
    setPosts(previous =>
      next !== null
        ? [...previous, ...page.items.map(post => ({ post, check: current }))]
        : page.items.map(post => ({ post, check: current })),
    )
    setCursor(page.next_cursor)
    setLoaded(true)
  }
  return (
    <Card title="模拟同辈文字审核">
      <div class="space-y-4">
        <Text>当前组授权内检查身份隐私和文字安全。</Text>
        <Field label="审核小组编号">
          <Input
            ref={group}
            maxlength={128}
            onInput={() => {
              begin()
              setPosts([])
              setCursor(null)
              setLoaded(false)
            }}
          />
        </Field>
        <Button onAction={view => load(view)}>读取本组审核队列</Button>
        <div aria-live="polite">
          <For each={posts()}>{item => <ModerationItem post={item.post} check={item.check} reload={load} />}</For>
          <Show when={loaded() && posts().length === 0}>
            <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
              该组暂无待审或公开文字。
            </Text>
          </Show>
          <Show when={cursor()}>
            {next => <Button onAction={view => load(view, next())}>读取下一页审核队列</Button>}
          </Show>
        </div>
      </div>
    </Card>
  )
}
