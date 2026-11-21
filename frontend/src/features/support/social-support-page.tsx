import type { Issue } from '../../ui/data-display'
import type { SupportResource } from '../services/draft-data'
import type { ServicePreparation } from '../services/draft-preparation'
import type { JSX } from '@solidjs/web'
import { createSignal, flush, For, onSettled, Show, untrack } from 'solid-js'
import * as v from 'valibot'
import { api } from '../../api/api'
import { actionError } from '../../notice/notice'
import { navigate } from '../../session/navigation'
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
import { IssueList } from '../../ui/data-display'
import { Field, Select } from '../../ui/form'
import { statusTone } from '../../ui/labels'
import { EmptyState, List } from '../../ui/list'
import { Subheading, Text } from '../../ui/typography'
import { sharedCategoryLabels, supportResourceSchema } from '../services/draft-data'
import { ServiceDraftPreparation } from '../services/draft-preparation'

interface ResourcePage {
  items: SupportResource[]
  next_cursor: string | null
}
interface SourceRef {
  module: string
  record_kind: string
  record_id: string
  version: string
}
interface MatchAction {
  resource_id: string
  title: string
  reason: string
}
interface Recommendation {
  source_refs: SourceRef[]
  need_status: string
  primary_action: MatchAction | null
  secondary_actions: MatchAction[]
  missing_items: Issue[]
}
const matchActionSchema = v.looseObject({ resource_id: v.string(), title: v.string(), reason: v.string() })
const recommendationSchema: v.GenericSchema<unknown, Recommendation> = v.looseObject({
  source_refs: v.array(
    v.looseObject({ module: v.string(), record_kind: v.string(), record_id: v.string(), version: v.string() }),
  ),
  need_status: v.string(),
  primary_action: v.nullable(matchActionSchema),
  secondary_actions: v.array(matchActionSchema),
  missing_items: v.array(v.looseObject({ message: v.string(), code: v.string() })),
})
const qualificationLabels: Record<string, string> = { not_required: '无需专业资质', not_verified: '资质未核验' }

export function SocialSupportPage(): JSX.Element {
  const view = untrack(captureView)
  const startMatch = readGate(),
    startDetail = readGate(),
    startDirectory = readGate()
  const [need, setNeed] = createSignal('')
  const [match, setMatch] = createSignal<Recommendation | null>(null)
  const [loading, setLoading] = createSignal(false)
  const [detail, setDetail] = createSignal<SupportResource | null>(null)
  const [directory, setDirectory] = createSignal<ResourcePage | null>(null)
  const [cursor, setCursor] = createSignal<string | null>(null)
  let detailSection!: HTMLElement
  let preparation: ServicePreparation | undefined
  function clearDetail(): void {
    startDetail()
    setDetail(null)
  }
  async function openDetail(id: string, version?: string): Promise<void> {
    clearDetail()
    const check = startDetail()
    const doc = await api(`/support-resources/${encodeURIComponent(id)}`, supportResourceSchema, 'GET', null, view)
    check()
    if (version !== undefined && version !== '' && doc.resource_version !== version)
      throw new Error('资源版本已更新，请刷新目录或重新匹配。')
    setDetail(doc)
    flush()
    detailSection.focus()
  }
  async function load(next: string | null = null): Promise<void> {
    const check = startDirectory()
    const page = await api(
      `/support-resources${next !== null && next !== '' ? `?cursor=${encodeURIComponent(next)}` : ''}`,
      v.looseObject({ items: v.array(supportResourceSchema), next_cursor: v.nullable(v.string()) }),
      'GET',
      null,
      view,
    )
    check()
    setCursor(next)
    setDirectory(page)
  }
  onSettled(() => {
    if (!scope('support:read')) return
    void (async () => {
      await Promise.all([load(), preparation?.restore()])
      requireCurrentView(view)
      const peerResource = sessionStorage.getItem(referenceKey('peer-prepare-resource'))
      if (peerResource !== null && peerResource !== '' && own()) {
        sessionStorage.removeItem(referenceKey('peer-prepare-resource'))
        await openDetail(peerResource)
      }
    })().catch((error: unknown) => {
      if (!(error instanceof ViewChanged)) actionError(error, view)
    })
  })
  const refs = () =>
    match()?.source_refs.filter(ref => ref.module === 'C' && ref.record_kind === 'support_resource') ?? []
  const actions = () =>
    [match()?.primary_action, ...(match()?.secondary_actions ?? [])].filter((action): action is MatchAction => !!action)
  const profile = () => match()?.source_refs.find(ref => ref.module === 'O' && ref.record_kind === 'profile')
  return (
    <Show when={scope('support:read')} fallback={<p>请先选择本人或获准查看社会支持的对象。</p>}>
      <Card title="社会支持">
        <div class="space-y-4">
          <Text>这里展示虚构资源和匹配依据。查看目录与匹配均不会提交申请或共享资料。</Text>
          <Show when={scope('profile:read')} fallback={<Text>当前授权不含画像读取。</Text>}>
            <Button onAction={() => navigate('profile', 'assessment')}>查看已登记画像</Button>
          </Show>
          <Field label="本次支持需求">
            <Select
              value={need()}
              onChange={event => {
                setNeed(event.currentTarget.value)
                startMatch()
                clearDetail()
                setMatch(null)
                setLoading(false)
              }}
            >
              <option value="">使用已有明确需求</option>
              <option value="practical">实际生活协助</option>
              <option value="emotional">情感陪伴</option>
              <option value="professional">药学咨询</option>
              <option value="none">暂不需要支持</option>
            </Select>
          </Field>
          <Button
            variant="primary"
            onAction={async () => {
              const check = startMatch()
              clearDetail()
              setMatch(null)
              setLoading(true)
              try {
                const data = await api(
                  patientPath('/support-recommendations') + (need() ? `?need=${encodeURIComponent(need())}` : ''),
                  recommendationSchema,
                  'GET',
                  null,
                  view,
                )
                check()
                setMatch(data)
                setLoading(false)
              } catch (error) {
                check()
                setLoading(false)
                throw error
              }
            }}
          >
            查看匹配
          </Button>
          <div aria-live="polite" class="space-y-4">
            <Show when={loading()}>
              <p>正在匹配…</p>
            </Show>
            <Show when={match()}>
              {data => (
                <>
                  <Subheading level={3}>匹配结果</Subheading>
                  <Show when={profile()}>
                    {value => (
                      <p>
                        O 画像 {value().record_id} · 修订 {value().version}
                      </p>
                    )}
                  </Show>
                  <Show when={data().need_status === 'none'}>
                    <p>本次暂不需要支持。</p>
                  </Show>
                  <Show when={data().need_status === 'insufficient'}>
                    <p>当前信息不足，无法确定资源。</p>
                  </Show>
                  <List>
                    <For each={actions()}>
                      {action => (
                        <Show when={refs().find(item => item.record_id === action.resource_id)} keyed>
                          {ref => (
                            <li class="space-y-2">
                              <p class="text-sm/6 font-medium">{action.title}</p>
                              <Text>{action.reason}</Text>
                              <Text>版本 {ref.version} · mock/demo</Text>
                              <Button onAction={() => openDetail(ref.record_id, ref.version)}>查看候选详情</Button>
                            </li>
                          )}
                        </Show>
                      )}
                    </For>
                  </List>
                  <Show
                    when={refs().filter(ref => !actions().some(action => action.resource_id === ref.record_id)).length}
                  >
                    <p>同级候选按资源编号展示。</p>
                    <ul>
                      <For each={refs().filter(ref => !actions().some(action => action.resource_id === ref.record_id))}>
                        {ref => (
                          <li>
                            <Button onAction={() => openDetail(ref.record_id, ref.version)}>
                              {ref.record_id} · {ref.version}
                            </Button>
                          </li>
                        )}
                      </For>
                    </ul>
                  </Show>
                  <Show when={data().missing_items.length}>
                    <IssueList issues={data().missing_items} />
                  </Show>
                </>
              )}
            </Show>
          </div>
        </div>
      </Card>
      <section ref={detailSection} aria-label="资源详情" aria-live="polite" hidden={!detail()} tabindex={-1}>
        <Show when={detail()}>
          {doc => (
            <Card>
              <div class="space-y-4">
                <Subheading>{doc().name}</Subheading>
                <Text>{doc().description}</Text>
                <Text>版本 {doc().resource_version} · mock/demo</Text>
                <p>
                  {doc().provider.display_name} ·{' '}
                  <Badge tone={statusTone(doc().provider.qualification_status)}>
                    {qualificationLabels[doc().provider.qualification_status]}
                  </Badge>
                </p>
                <p>
                  潜在的必要共享类别　
                  {doc()
                    .required_shared_categories.map(name => sharedCategoryLabels[name])
                    .join('、') || '无'}
                </p>
                <p>
                  潜在的可选共享类别　
                  {doc()
                    .optional_shared_categories.map(name => sharedCategoryLabels[name])
                    .join('、') || '无'}
                </p>
                <Show when={scope('services:prepare') && ((doc().peer_group_id ?? '') === '' || own())}>
                  <Show when={preparation} keyed>
                    {value => (
                      <Button variant="primary" onAction={() => value.prepare(doc())}>
                        {(doc().peer_group_id ?? '') !== '' ? '准备入组草稿' : '准备服务问题'}
                      </Button>
                    )}
                  </Show>
                </Show>
              </div>
            </Card>
          )}
        </Show>
      </section>
      <Show when={scope('services:prepare')}>
        <ServiceDraftPreparation
          view={view}
          ref={value => {
            preparation = value
          }}
        />
      </Show>
      <Card title="可用资源">
        <Show when={directory()}>
          {page => (
            <div class="space-y-4">
              <Show when={!page().items.length}>
                <EmptyState>当前没有可用的虚构资源。</EmptyState>
              </Show>
              <List>
                <For each={page().items}>
                  {doc => (
                    <li class="space-y-2 sm:flex sm:items-center sm:justify-between sm:gap-4 sm:space-y-0">
                      <div>
                        <p class="text-sm/6 font-medium">{doc.name}</p>
                        <Text>版本 {doc.resource_version} · mock/demo</Text>
                      </div>
                      <Button onAction={() => openDetail(doc.resource_id, doc.resource_version)}>查看资源详情</Button>
                    </li>
                  )}
                </For>
              </List>
              <Show when={page().next_cursor}>
                <Button onAction={() => load(page().next_cursor)}>下一页资源</Button>
              </Show>
              <Show when={cursor()}>
                <Button onAction={() => load()}>返回资源首页</Button>
              </Show>
            </div>
          )}
        </Show>
      </Card>
    </Show>
  )
}
