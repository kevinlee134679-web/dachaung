import type { JSX } from '@solidjs/web'
import { Show } from 'solid-js'
import { captureView, state } from '../session/session'
import { Button } from '../ui/button'
import { Text } from '../ui/typography'

export function HealthFooter(props: {
  ready: boolean
  message: string
  checking: boolean
  onRecheck: () => Promise<void>
}): JSX.Element {
  return (
    <footer class="space-y-2">
      <div class="flex items-center gap-2">
        <span
          aria-hidden="true"
          class={`size-1.5 rounded-full ${props.ready ? 'bg-teal-500 dark:bg-teal-400' : 'bg-amber-500 dark:bg-amber-400'}`}
        />
        <Text class="text-xs">{props.message}</Text>
        <Show when={state.context?.csrf_token} keyed>
          <Button
            view={{ ...captureView(), sessionOnly: true }}
            variant="plain"
            disabled={props.checking}
            onAction={props.onRecheck}
            class="!h-auto !px-1 py-1 !text-xs"
          >
            重新检查
          </Button>
        </Show>
      </div>
      <Text class="text-xs">
        演示资料不用于实际服药。涉及医嘱变更，请咨询医生或药师。对话、人员服务和外部通知均为模拟。
      </Text>
    </footer>
  )
}
