import type { JSX } from '@solidjs/web'
import { Show } from 'solid-js'
import { requireCurrentView } from '../session/session'
import { Button } from '../ui/button'
import { currentNotice, notice } from './notice'

export function Notice(): JSX.Element {
  return (
    <div
      role="status"
      aria-live="polite"
      class={
        currentNotice().text
          ? `flex items-start gap-3 rounded-lg p-3 text-sm/6 ring-1 ring-inset ${currentNotice().error ? 'bg-red-50 text-red-800 ring-red-600/20 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-400/20' : 'bg-teal-50 text-teal-800 ring-teal-600/20 dark:bg-teal-500/10 dark:text-teal-300 dark:ring-teal-400/20'}`
          : ''
      }
    >
      <Show when={currentNotice().text}>
        <span
          aria-hidden="true"
          class={
            currentNotice().error
              ? 'icon-[heroicons--exclamation-circle-20-solid] size-5 shrink-0'
              : 'icon-[heroicons--check-circle-20-solid] size-5 shrink-0'
          }
        />
        <span>{currentNotice().text}</span>
      </Show>
      <Show when={currentNotice().recovery} keyed>
        {recovery => (
          <Button
            view={recovery.view}
            onAction={() => {
              const item = recovery
              requireCurrentView(item.view)
              if (localStorage.getItem(item.operation.key) !== item.operation.operation)
                throw new Error('原操作记录已变化，请重新核对原结果。')
              localStorage.removeItem(item.operation.key)
              notice('已准备新操作，表单内容已保留。请再次明确选择保存或提交；本次未发送请求。')
            }}
          >
            已核对原结果，准备新操作
          </Button>
        )}
      </Show>
    </div>
  )
}
