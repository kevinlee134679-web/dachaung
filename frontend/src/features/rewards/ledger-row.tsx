import type { LedgerEntry } from './points'
import type { JSX } from '@solidjs/web'
import { For, Show } from 'solid-js'
import { dateText } from '../../date/date'
import { Disclosure } from '../../ui/disclosure'
import { Text } from '../../ui/typography'
import { ledgerKindLabels, pointLabels, pointSourceLabels } from './points'

export function LedgerRow(props: { entry: LedgerEntry }): JSX.Element {
  return (
    <li class="space-y-3">
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
