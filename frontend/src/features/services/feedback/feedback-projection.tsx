import type { FeedbackProjection } from './feedback'
import type { JSX } from '@solidjs/web'
import { For, Show } from 'solid-js'
import { dateText } from '../../../date/date'
import { navigate } from '../../../session/navigation'
import { referenceKey, scope } from '../../../session/session'
import { Badge, StatusBadge } from '../../../ui/badge'
import { Button } from '../../../ui/button'
import { statusTone } from '../../../ui/labels'
import { Text } from '../../../ui/typography'
import { formalServiceStates } from '../dispatch'
import { feedbackDimensions } from './feedback'

export function CFeedbackProjection(props: { source: FeedbackProjection }): JSX.Element {
  return (
    <div class="space-y-4">
      <p class="font-medium">
        C 社会支持反馈 · <StatusBadge status={props.source.availability} />
      </p>
      <Show when={props.source.reason}>
        <Text>{props.source.reason}</Text>
      </Show>
      <For each={props.source.records}>
        {record => (
          <div class="space-y-2 border-t border-zinc-950/5 py-4 dark:border-white/5">
            <p>
              服务状态{' '}
              <Badge tone={statusTone(record.service_status)}>{formalServiceStates[record.service_status]}</Badge> ·
              来源修订 {record.source_version}
            </p>
            <Text>
              {dateText(record.recorded_at)} · {record.is_simulated ? '模拟' : '已登记'}
            </Text>
            <For each={feedbackDimensions}>
              {([key, label]) => (
                <Show when={record[key] !== null}>
                  <p>
                    {label} · {record[key]}
                  </p>
                </Show>
              )}
            </For>
            <Show when={scope('services:read')}>
              <Button
                onAction={() => {
                  sessionStorage.setItem(referenceKey('formal-service'), record.record_id)
                  navigate('profile', 'formal-services')
                }}
              >
                查看该服务及反馈历史
              </Button>
            </Show>
          </div>
        )}
      </For>
    </div>
  )
}
