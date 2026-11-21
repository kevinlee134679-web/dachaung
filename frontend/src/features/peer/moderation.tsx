import type { View } from '../../session/session'
import type { PeerPost } from './peer'
import type { JSX } from '@solidjs/web'
import { createSignal, For, Show } from 'solid-js'
import * as v from 'valibot'
import { api } from '../../api/api'
import { notice } from '../../notice/notice'
import { readGate } from '../../session/read-gate'
import { requireCurrentView } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Field, Input } from '../../ui/form'
import { EmptyState } from '../../ui/list'
import { Text } from '../../ui/typography'
import { serviceWrite } from '../services/draft-data'
import { peerPath, peerPostPageSchema } from './peer'
import { PeerPostItem } from './post-item'

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
      <div class="py-4">
        <PeerPostItem post={props.post} />
      </div>
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
            <EmptyState>该组暂无待审或公开文字。</EmptyState>
          </Show>
          <Show when={cursor()}>
            {next => <Button onAction={view => load(view, next())}>读取下一页审核队列</Button>}
          </Show>
        </div>
      </div>
    </Card>
  )
}
