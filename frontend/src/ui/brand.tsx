import type { JSX } from '@solidjs/web'

export function Brand(): JSX.Element {
  return (
    <div class="flex items-center gap-3">
      <span
        aria-hidden="true"
        class="flex size-8 items-center justify-center rounded-lg bg-teal-600 text-white dark:bg-teal-600 dark:text-white"
      >
        <span class="icon-[heroicons--heart] size-5" />
      </span>
      <span class="font-semibold">用药支持</span>
    </div>
  )
}
