import type { View } from '../../session/session'
import type { RangeReader } from '../../ui/range-controls'
import type { JSX } from '@solidjs/web'
import { createMemo, createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { api, sha } from '../../api/api'
import { rangeQuery } from '../../api/query'
import { dateText } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import { readGate } from '../../session/read-gate'
import { captureView, isCurrentView, own, requireCurrentView, scope, state, ViewChanged } from '../../session/session'
import { Button, Card, Checkbox, Disclosure, Field, Text, Textarea } from '../../ui/components'
import { confirm } from '../../ui/confirm'
import { RangeControls } from '../../ui/range-controls'
import { RedemptionPanel } from './redemption-panel'

export const pointLabels: Record<string, string> = {
  daily_record: '每日有效手动记录',
  five_day_block: '连续五个合格日',
  weekly_review: '每周管理回顾',
  peer_participation: '经审核可见的同辈参与',
}

const pointSourceLabels: Record<string, string> = {
  event: 'A 服药情况报告',
  management_review: 'C 本人管理回顾',
  peer_post: 'C 本人同辈参与',
  redemption: 'C 兑换订单',
}
const ledgerKindLabels: Record<string, string> = {
  redemption_debit: '自愿兑换扣减',
  redemption_refund: '未交付全额退分',
}

export interface PointRules {
  rules_version: string
  rules: { rule_code: string; points: number; eligibility_description: string }[]
}

export const pointRulesSchema: v.GenericSchema<unknown, PointRules> = v.looseObject({
  rules_version: v.string(),
  rules: v.array(v.looseObject({ rule_code: v.string(), points: v.number(), eligibility_description: v.string() })),
})
const ledgerEntrySchema = v.looseObject({
  entry_kind: v.string(),
  rule_code: v.nullable(v.string()),
  delta: v.number(),
  created_at: v.string(),
  balance_after: v.number(),
  rules_version: v.nullable(v.string()),
  source_refs: v.array(
    v.looseObject({
      record_kind: v.string(),
      module: v.string(),
      version: v.string(),
      recorded_at: v.string(),
      record_id: v.string(),
    }),
  ),
})
type LedgerEntry = v.InferOutput<typeof ledgerEntrySchema>
const reviewSchema = v.looseObject({
  week_start: v.string(),
  completed_at: v.string(),
  reflection: v.nullable(v.string()),
})
type Review = v.InferOutput<typeof reviewSchema>

export function pointsRange(range: RangeReader): { window_start: string; window_end: string } {
  const { window_start, window_end } = range.read()
  return { window_start, window_end }
}

function localReviewWeek(timezone: string, now = new Date()): string {
  const today = new Intl.DateTimeFormat('sv-SE', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now)
  const start = new Date(`${today}T00:00:00Z`)
  start.setUTCDate(start.getUTCDate() - ((start.getUTCDay() + 6) % 7))
  return start.toISOString().slice(0, 10)
}

async function reviewForCurrentWeek(path: string, week: string, view: View): Promise<Review | undefined> {
  const monday = new Date(`${week}T00:00:00Z`).getTime()
  const query = {
    window_start: new Date(monday - 86400000).toISOString(),
    window_end: new Date(monday + 8 * 86400000).toISOString(),
    limit: 10,
  }
  const page = await api(
    `${path}/management-reviews?${rangeQuery(query)}`,
    v.looseObject({ items: v.array(reviewSchema) }),
    'GET',
    null,
    view,
  )
  requireCurrentView(view)
  return page.items.find(item => item.week_start === week)
}

function ManagementReview(props: { path: string; timezone: string; view: View }): JSX.Element {
  const week = createMemo(() => localReviewWeek(props.timezone))
  const [saved, setSaved] = createSignal<Review | undefined>()
  let reflection!: HTMLTextAreaElement
  let confirmed!: HTMLInputElement
  onSettled(() => {
    void reviewForCurrentWeek(props.path, week(), props.view)
      .then(review => {
        requireCurrentView(props.view)
        setSaved(review)
      })
      .catch((error: unknown) => {
        if (!(error instanceof ViewChanged) && isCurrentView(props.view)) actionError(error, props.view)
      })
  })
  return (
    <Card title="每周管理回顾">
      <div class="space-y-4">
        <Text>当周起始日 {week()} · 演示</Text>
        <Show
          when={saved()}
          fallback={
            <div class="space-y-4">
              <Field label="回顾内容（可留空）">
                <Textarea ref={reflection} maxlength={2000} rows={3} />
              </Field>
              <Checkbox ref={confirmed} label="我已完成本周管理回顾" />
              <Button
                variant="primary"
                view={props.view}
                onAction={async view => {
                  if (!confirmed.checked) throw new Error('请本人明确确认已完成本周回顾。')
                  if (!(await confirm('确认记录本周管理回顾？'))) return
                  requireCurrentView(view)
                  const draft = {
                    week_start: week(),
                    reflection: reflection.value.trim() || null,
                    confirmed_completed: true,
                  }
                  const key = `points-review:${view.accountId}:${view.patientId}:${await sha(JSON.stringify(draft))}`
                  requireCurrentView(view)
                  let submission = sessionStorage.getItem(key)
                  if (submission === null || submission === '') {
                    submission = crypto.randomUUID()
                    sessionStorage.setItem(key, submission)
                  }
                  try {
                    const review = await api(
                      `${props.path}/management-reviews`,
                      reviewSchema,
                      'POST',
                      { client_review_id: submission, ...draft },
                      view,
                    )
                    requireCurrentView(view)
                    sessionStorage.removeItem(key)
                    setSaved(review)
                    notice('已保存回顾。积分余额会在核验入账后更新。')
                  } catch (error) {
                    if (error instanceof ViewChanged) throw error
                    const review = await reviewForCurrentWeek(props.path, week(), view)
                    requireCurrentView(view)
                    if (!review) throw error
                    sessionStorage.removeItem(key)
                    setSaved(review)
                  }
                }}
              >
                确认完成本周回顾
              </Button>
            </div>
          }
        >
          {review => (
            <div aria-live="polite">
              <p>已记录本周回顾 · {dateText(review().completed_at)}</p>
              <Show when={review().reflection}>
                <p>{review().reflection}</p>
              </Show>
            </div>
          )}
        </Show>
      </div>
    </Card>
  )
}

function LedgerRow(props: { entry: LedgerEntry }): JSX.Element {
  return (
    <li class="space-y-3 py-4 first:pt-0 last:pb-0">
      <strong>
        {props.entry.delta > 0 ? '+' : ''}
        {props.entry.delta} · {ledgerKindLabels[props.entry.entry_kind] ?? pointLabels[props.entry.rule_code ?? '']}
      </strong>
      <Text>
        {dateText(props.entry.created_at)} · 入账后 {props.entry.balance_after} 积分
        {props.entry.rules_version != null && props.entry.rules_version !== '' ? ` · ${props.entry.rules_version}` : ''}
      </Text>
      <Disclosure summary="来源与版本">
        <Show when={props.entry.source_refs.length} fallback={<Text>当前权限下来源详情不可用。</Text>}>
          <ul>
            <For each={props.entry.source_refs}>
              {ref => (
                <li>
                  {pointSourceLabels[ref.record_kind] ?? ref.module} · 版本 {ref.version} · {dateText(ref.recorded_at)}
                  <div class="text-sm/6 text-zinc-500 dark:text-zinc-400">{ref.record_id}</div>
                </li>
              )}
            </For>
          </ul>
        </Show>
      </Disclosure>
    </li>
  )
}

function PointsContent(props: { rules: PointRules; view: View }): JSX.Element {
  const canRead = createMemo(() => props.view.patientId !== null && props.view.patientId !== '' && scope('points:read'))
  const path = createMemo(() => `/patients/${encodeURIComponent(props.view.patientId ?? '')}`)
  const [balance, setBalance] = createSignal('正在读取当前余额…')
  const [entries, setEntries] = createSignal<LedgerEntry[]>([])
  const [cursor, setCursor] = createSignal<string | null>(null)
  const [historyError, setHistoryError] = createSignal('')
  const [loaded, setLoaded] = createSignal(false)
  const beginRead = readGate()
  let range!: RangeReader
  let currentWindow: { window_start: string; window_end: string }
  async function loadLedger(
    view: View,
    window: { window_start: string; window_end: string },
    next: string | null = null,
  ): Promise<void> {
    const current = beginRead()
    try {
      const [account, page] = await Promise.all([
        api(`${path()}/points`, v.looseObject({ balance: v.number() }), 'GET', null, view),
        api(
          `${path()}/points-ledger?${rangeQuery({ ...window, cursor: next, limit: 20 })}`,
          v.looseObject({ items: v.array(ledgerEntrySchema), next_cursor: v.nullable(v.string()) }),
          'GET',
          null,
          view,
        ),
      ])
      current()
      setBalance(`可用积分 ${account.balance}`)
      setEntries(previous => (next !== null ? [...previous, ...page.items] : page.items))
      setCursor(page.next_cursor)
      setHistoryError('')
      setLoaded(true)
    } catch (error) {
      current()
      setBalance('余额暂不可显示')
      setHistoryError(error instanceof Error ? error.message : '')
      setLoaded(true)
    }
  }
  return (
    <div class="space-y-6">
      <Card title="演示积分">
        <div class="space-y-4">
          <Show when={canRead()}>
            <p class="text-2xl font-semibold text-zinc-950 tabular-nums dark:text-white">{balance()}</p>
          </Show>
          <Disclosure summary={<>积分规则 · {props.rules.rules_version}</>}>
            <ul>
              <For each={props.rules.rules}>
                {rule => (
                  <li>
                    {pointLabels[rule.rule_code]} +{rule.points} · {rule.eligibility_description}
                  </li>
                )}
              </For>
            </ul>
            <p>漏服、医嘱暂停或退出同辈支持不会扣除已有积分。必要专业支持不设积分门槛。</p>
          </Disclosure>
          <Show when={canRead()} fallback={<p>当前身份没有该患者的积分读取权限。</p>}>
            <RangeControls
              ref={value => {
                range = value
                currentWindow = pointsRange(value)
                void loadLedger(props.view, currentWindow).catch((error: unknown) => {
                  if (!(error instanceof ViewChanged) && isCurrentView(props.view)) actionError(error, props.view)
                })
              }}
            />
            <Button
              view={props.view}
              onAction={view => {
                currentWindow = pointsRange(range)
                return loadLedger(view, currentWindow)
              }}
            >
              刷新积分余额和历史
            </Button>
            <div aria-live="polite">
              <Show
                when={historyError()}
                fallback={
                  <Show when={loaded()}>
                    <Show
                      when={entries().length}
                      fallback={
                        <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
                          这段时间暂无积分流水。
                        </Text>
                      }
                    >
                      <ol class="divide-y divide-zinc-950/5 dark:divide-white/5">
                        <For each={entries()}>{entry => <LedgerRow entry={entry} />}</For>
                      </ol>
                    </Show>
                    <Show when={cursor()}>
                      {next => (
                        <Button view={props.view} onAction={view => loadLedger(view, currentWindow, next())}>
                          查看更多流水
                        </Button>
                      )}
                    </Show>
                  </Show>
                }
              >
                <p class="text-sm/6 text-red-600 dark:text-red-400">{historyError()}</p>
              </Show>
            </div>
          </Show>
        </div>
      </Card>
      <Show when={canRead() && own() && state.patient}>
        {patient => <ManagementReview path={path()} timezone={patient().patient.timezone} view={props.view} />}
      </Show>
      <Show when={canRead()}>
        <RedemptionPanel path={path()} view={props.view} />
      </Show>
    </div>
  )
}

export function PointsPage(): JSX.Element {
  const [rules, setRules] = createSignal<PointRules>()
  onSettled(() => {
    const view = captureView()
    void api('/points/rules', pointRulesSchema, 'GET', null, view)
      .then(value => {
        requireCurrentView(view)
        setRules(value)
      })
      .catch((error: unknown) => {
        if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
      })
  })
  return <Show when={rules()}>{value => <PointsContent rules={value()} view={captureView()} />}</Show>
}
