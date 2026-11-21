import type { View } from '../../session/session'
import type { PeerMembership, PeerPost } from './peer'
import type { JSX } from '@solidjs/web'
import { createSignal, flush, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api, ApiError, sha } from '../../api/api'
import { actionError, notice } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import { readGate } from '../../session/read-gate'
import {
  captureView,
  isCurrentView,
  own,
  referenceKey,
  requireCurrentView,
  scope,
  ViewChanged,
} from '../../session/session'
import { Badge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { confirm } from '../../ui/confirm'
import { Field, Select, Textarea } from '../../ui/form'
import { statusTone } from '../../ui/labels'
import { EmptyState, List } from '../../ui/list'
import { Subheading, Text } from '../../ui/typography'
import { formalServiceStates } from '../services/dispatch'
import { serviceWrite } from '../services/draft-data'
import { peerMembershipSchema, peerPath, peerPostPageSchema } from './peer'
import { PeerPostItem } from './post-item'

interface PeerGroup {
  group_id: string
  title: string
  description: string
  availability: 'available' | 'unavailable' | 'unknown'
  moderator_label: string
  matching_tags: string[]
  resource_id: string
}

interface PeerService {
  service_id: string
  status: keyof typeof formalServiceStates
}

const peerGroupSchema = v.looseObject({
  group_id: v.string(),
  title: v.string(),
  description: v.string(),
  availability: v.picklist(['available', 'unavailable', 'unknown']),
  moderator_label: v.string(),
  matching_tags: v.array(v.string()),
  resource_id: v.string(),
})
const peerServiceSchema = v.looseObject({ service_id: v.string(), status: v.string() })

interface PeerDetail {
  group: PeerGroup
  membership: PeerMembership | undefined
  previouslyLeft: boolean
  service: PeerService | null
  check: () => void
}

const peerAvailability = { available: '可申请', unavailable: '暂不可申请', unknown: '可用性未知' }

function PostComposer(props: {
  group: string
  view: View
  check: () => void
  reload: () => Promise<void>
}): JSX.Element {
  let area!: HTMLTextAreaElement
  async function submit(): Promise<void> {
    const content = area.value.trim()
    if (!content) throw new Error('请填写一段短文字。')
    const fingerprint = await sha(content)
    props.check()
    const key = referenceKey(`peer-post-submission:${props.group}`)
    const pending = (): { fingerprint: string; clientId: string } | null =>
      v.parse(
        v.nullable(v.looseObject({ fingerprint: v.string(), clientId: v.string() })),
        JSON.parse(sessionStorage.getItem(key) ?? 'null'),
      )
    const known = pending()
    if (known && known.fingerprint !== fingerprint) throw new Error('原提交尚未核实，请先用原文字重试。')
    const clientId = known?.clientId ?? crypto.randomUUID()
    sessionStorage.setItem(key, JSON.stringify({ fingerprint, clientId }))
    try {
      await api(
        `${peerPath(props.group)}/posts`,
        v.unknown(),
        'POST',
        { client_post_id: clientId, content },
        props.view,
      )
      props.check()
      sessionStorage.removeItem(key)
      area.value = ''
      await props.reload()
      props.check()
      notice('文字已提交，公开状态以审核结果为准。')
    } catch (caught) {
      if (caught instanceof ViewChanged) throw caught
      props.check()
      if (
        caught instanceof ApiError &&
        caught.status < 500 &&
        !caught.pendingRecovery &&
        caught.code !== 'OPERATION_IN_PROGRESS'
      ) {
        if (pending()?.clientId === clientId) sessionStorage.removeItem(key)
      }
      if (caught instanceof ApiError && (caught.status === 403 || caught.status === 404)) await props.reload()
      throw caught
    }
  }
  return (
    <div class="space-y-4">
      <Field label="匿名短文字">
        <Textarea ref={area} rows={3} maxlength={1000} />
      </Field>
      <Button view={props.view} variant="primary" onAction={submit}>
        提交文字待审
      </Button>
    </div>
  )
}

export function PeerSupportPage(): JSX.Element {
  let groupSelect!: HTMLSelectElement
  const [groups, setGroups] = createSignal<PeerGroup[]>([])
  const [selected, setSelected] = createSignal('')
  const [ready, setReady] = createSignal(false)
  const [detail, setDetail] = createSignal<PeerDetail | null>(null)
  const [posts, setPosts] = createSignal<PeerPost[]>([])
  const [cursor, setCursor] = createSignal<string | null>(null)
  const [status, setStatus] = createSignal('')
  const [statusError, setStatusError] = createSignal(false)
  const [feedLoaded, setFeedLoaded] = createSignal(false)
  const [canCompose, setCanCompose] = createSignal(false)
  const begin = readGate()
  let feedRequest = 0
  let resume: (() => Promise<void>) | null = null
  let loadMore: ((cursor: string) => Promise<void>) | null = null
  let view: View

  function clearFeed(): void {
    feedRequest++
    setPosts([])
    setCursor(null)
    setCanCompose(false)
    setFeedLoaded(false)
    flush()
  }

  async function load(id: string): Promise<void> {
    const check = begin()
    resume = null
    loadMore = null
    clearFeed()
    setStatus('')
    setDetail(null)
    const group = await api(peerPath(id), peerGroupSchema, 'GET', null, view)
    check()
    sessionStorage.setItem(referenceKey('peer-group'), id)
    if (!own()) {
      setDetail({ group, membership: undefined, previouslyLeft: false, service: null, check })
      return
    }
    const memberships = await all('/peer-memberships/me', peerMembershipSchema, view)
    check()
    const membership = memberships.find(member => member.group_id === id && member.status !== 'left')
    let service: PeerService | null = null
    if (membership) {
      try {
        service = await api(
          `/services/${encodeURIComponent(membership.service_id)}`,
          peerServiceSchema,
          'GET',
          null,
          view,
        )
        check()
      } catch (caught) {
        check()
        if (!(caught instanceof ApiError) || (caught.status !== 404 && caught.status !== 403)) throw caught
      }
    }
    setDetail({
      group,
      membership,
      previouslyLeft: memberships.some(member => member.group_id === id && member.status === 'left'),
      service,
      check,
    })

    async function loadPosts(next: string | null = null): Promise<void> {
      check()
      const request = ++feedRequest
      if (next === null) clearFeedForRequest()
      try {
        const query = next !== null ? `?cursor=${encodeURIComponent(next)}` : ''
        const page = await api(`${peerPath(id)}/posts${query}`, peerPostPageSchema, 'GET', null, view)
        check()
        if (request !== feedRequest || document.visibilityState === 'hidden') return
        setStatus('本人可以在此组交流。')
        setStatusError(false)
        setPosts(previous => (next !== null ? [...previous, ...page.items] : page.items))
        setCursor(page.next_cursor)
        setFeedLoaded(true)
        if (next === null) setCanCompose(scope('peer:participate'))
      } catch (caught) {
        check()
        if (request !== feedRequest || document.visibilityState === 'hidden') return
        clearFeedForRequest()
        if (!(caught instanceof ApiError) || (caught.status !== 403 && caught.status !== 404)) {
          setStatus('暂无法核验小组交流权限。')
          setStatusError(true)
        } else {
          setStatus(
            membership?.status === 'pending' && service?.status === 'submitted'
              ? '正在等待模拟受理，交流尚未开放。'
              : '当前没有有效交流资格。',
          )
          setStatusError(false)
        }
      }
    }
    function clearFeedForRequest(): void {
      setPosts([])
      setCursor(null)
      setCanCompose(false)
      setFeedLoaded(false)
    }
    resume = () => loadPosts()
    loadMore = loadPosts
    await loadPosts()
  }

  function resumeFeed(): void {
    if (isCurrentView(view) && resume) {
      void resume().catch((error: unknown) => {
        if (!(error instanceof ViewChanged)) actionError(error, view)
      })
    }
  }

  onSettled(() => {
    view = captureView()
    const hide = (): void => {
      if (isCurrentView(view)) clearFeed()
    }
    const show = (event: PageTransitionEvent): void => {
      if (event.persisted) resumeFeed()
    }
    const visibility = (): void => {
      if (document.visibilityState === 'hidden') hide()
      else resumeFeed()
    }
    window.addEventListener('pagehide', hide)
    window.addEventListener('pageshow', show)
    document.addEventListener('visibilitychange', visibility)
    if (scope('peer:read')) {
      void (async () => {
        const check = begin()
        const [available, memberships] = await Promise.all([
          all('/peer-groups', peerGroupSchema, view),
          own() ? all('/peer-memberships/me', peerMembershipSchema, view) : Promise.resolve([]),
        ])
        check()
        setGroups(available)
        setReady(true)
        const first = available[0]
        if (!first) return
        const saved =
          sessionStorage.getItem(referenceKey('peer-group')) ??
          memberships.find(member => member.status !== 'left')?.group_id
        const id = available.find(group => group.group_id === saved)?.group_id ?? first.group_id
        setSelected(id)
        await load(id)
      })().catch((error: unknown) => {
        if (!(error instanceof ViewChanged)) actionError(error, view)
      })
    }
    return () => {
      begin()
      feedRequest++
      resume = null
      window.removeEventListener('pagehide', hide)
      window.removeEventListener('pageshow', show)
      document.removeEventListener('visibilitychange', visibility)
    }
  })

  async function leave(current: PeerDetail, membership: PeerMembership): Promise<void> {
    if (!(await confirm('确认自愿退出此小组？'))) return
    requireCurrentView(view)
    try {
      await serviceWrite(
        `/memberships/${encodeURIComponent(membership.membership_id)}/leave`,
        'POST',
        { expected_revision: membership.revision },
        v.unknown(),
        view,
      )
      current.check()
    } catch (error) {
      current.check()
      await load(current.group.group_id)
      throw error
    }
    clearFeed()
    await load(current.group.group_id)
    requireCurrentView(view)
    notice('已退出本组。')
  }

  return (
    <Show when={scope('peer:read')} fallback={<Text>请先获得小组介绍读取权限。</Text>}>
      <div class="space-y-6">
        <Card title="匿名同辈支持">
          <div class="space-y-4">
            <Text>虚构小组 · 自愿参与 · 短文字经模拟审核后公开。请勿填写姓名、账号、联系方式或诊疗资料。</Text>
            <Show when={ready() && groups().length === 0}>
              <EmptyState>目前没有登记的小组。</EmptyState>
            </Show>
            <Show when={groups().length > 0}>
              <Field label="同辈小组">
                <Select
                  ref={groupSelect}
                  value={selected()}
                  onChange={event => {
                    setSelected(event.currentTarget.value)
                    begin()
                    resume = null
                    clearFeed()
                    setDetail(null)
                    setStatus('')
                  }}
                >
                  <For each={groups()}>{group => <option value={group.group_id}>{group.title}</option>}</For>
                </Select>
              </Field>
              <Button onAction={() => load(groupSelect.value)}>查看小组</Button>
            </Show>
          </div>
        </Card>
        <div aria-live="polite">
          <Show when={detail()}>
            {current => (
              <Card>
                <div class="space-y-4">
                  <Subheading>{current().group.title}</Subheading>
                  <p>{current().group.description}</p>
                  <p>
                    <Badge tone={statusTone(current().group.availability)}>
                      {peerAvailability[current().group.availability]}
                    </Badge>{' '}
                    · {current().group.moderator_label}
                  </p>
                  <Text>小组主题 · {current().group.matching_tags.join('、')}</Text>
                  <Text>小组编号 {current().group.group_id}</Text>
                  <Show when={own()} fallback={<Text>当前授权允许查看小组介绍。</Text>}>
                    <Show
                      when={current().membership}
                      fallback={
                        <Show when={current().previouslyLeft}>
                          <Text>本人此前已退出此组。</Text>
                        </Show>
                      }
                    >
                      {member => (
                        <>
                          <Text>
                            本人匿名身份 {member().alias} ·{' '}
                            <Badge tone={statusTone(member().status)}>
                              {member().status === 'pending'
                                ? '等待模拟受理'
                                : member().can_participate
                                  ? '已受理'
                                  : '当前交流受限'}
                            </Badge>{' '}
                            · 修订 {member().revision}
                          </Text>
                          <Text>本人成员编号 {member().membership_id}</Text>
                        </>
                      )}
                    </Show>
                    <Show when={current().service}>
                      {service => (
                        <Text>
                          入组服务 {service().service_id} ·{' '}
                          <Badge tone={statusTone(service().status)}>{formalServiceStates[service().status]}</Badge>
                        </Text>
                      )}
                    </Show>
                    <div class="my-4 flex flex-wrap gap-3">
                      <Button onAction={() => load(current().group.group_id)}>刷新小组状态</Button>
                      <Show
                        when={
                          !current().membership &&
                          current().group.availability === 'available' &&
                          scope('services:prepare') &&
                          scope('support:read')
                        }
                      >
                        <Button
                          variant="primary"
                          onAction={() => {
                            sessionStorage.setItem(referenceKey('peer-prepare-resource'), current().group.resource_id)
                            navigate('support', 'social')
                          }}
                        >
                          准备本组申请
                        </Button>
                      </Show>
                      <Show when={current().membership}>
                        {member => (
                          <Button variant="danger" onAction={() => leave(current(), member())}>
                            退出本组
                          </Button>
                        )}
                      </Show>
                    </div>
                    <p
                      aria-live="polite"
                      class={
                        statusError()
                          ? 'text-sm/6 text-red-600 dark:text-red-400'
                          : 'text-sm/6 text-zinc-500 dark:text-zinc-400'
                      }
                    >
                      {status()}
                    </p>
                    <List>
                      <For each={posts()}>
                        {post => (
                          <li>
                            <PeerPostItem post={post} />
                          </li>
                        )}
                      </For>
                    </List>
                    <Show when={feedLoaded() && posts().length === 0}>
                      <EmptyState>当前没有可见文字。</EmptyState>
                    </Show>
                    <Show when={cursor()}>
                      {next => (
                        <Button
                          onAction={async () => {
                            current().check()
                            const loadNext = loadMore
                            if (loadNext) await loadNext(next())
                          }}
                        >
                          读取更多文字
                        </Button>
                      )}
                    </Show>
                    <Show when={canCompose() && resume} keyed>
                      {resumeFeed => (
                        <PostComposer
                          group={current().group.group_id}
                          view={view}
                          check={current().check}
                          reload={resumeFeed}
                        />
                      )}
                    </Show>
                  </Show>
                </div>
              </Card>
            )}
          </Show>
        </div>
      </div>
    </Show>
  )
}
