import type { View } from '../../session/session'
import type { RangeReader } from '../../ui/range-controls'
import type { PointRules, LedgerEntry } from './points'
import type { JSX } from '@solidjs/web'
import { createMemo, createSignal, For, Show } from 'solid-js'
import * as v from 'valibot'
import { api } from '../../api/api'
import { rangeQuery } from '../../api/query'
import { actionError } from '../../notice/notice'
import { readGate } from '../../session/read-gate'
import { isCurrentView, own, scope, state, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Disclosure } from '../../ui/disclosure'
import { EmptyState, List } from '../../ui/list'
import { RangeControls } from '../../ui/range-controls'
import { LedgerRow } from './ledger-row'
import { ManagementReview } from './management-review'
import { ledgerEntrySchema, pointLabels, pointsRange } from './points'
import { RedemptionPanel } from './redemption-panel'

export function PointsContent(props: { rules: PointRules; view: View }): JSX.Element {
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
                    <Show when={entries().length} fallback={<EmptyState>这段时间暂无积分流水。</EmptyState>}>
                      <List ordered>
                        <For each={entries()}>{entry => <LedgerRow entry={entry} />}</For>
                      </List>
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
