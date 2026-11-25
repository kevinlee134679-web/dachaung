import type { JSX } from '@solidjs/web'
import { createSignal, Show, untrack } from 'solid-js'

export function Disclosure(props: {
  summary: JSX.Element
  children: JSX.Element
  open?: boolean
  lazy?: boolean
}): JSX.Element {
  const [activated, activate] = createSignal(untrack(() => props.open === true))
  return (
    <details
      open={props.open}
      class="group rounded-lg ring-1 ring-zinc-950/10 dark:ring-white/10"
      onToggle={event => {
        if (props.lazy && event.currentTarget.open) activate(true)
      }}
    >
      <summary class="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-2.5 text-sm/6 font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600 [&::-webkit-details-marker]:hidden">
        {props.summary}
        <span
          aria-hidden="true"
          class="icon-[heroicons--chevron-down-20-solid] size-4 transition-transform duration-150 group-open:rotate-180 motion-reduce:transition-none"
        />
      </summary>
      <Show when={!props.lazy || activated()}>
        <div class="space-y-4 border-t border-zinc-950/5 px-4 py-4 dark:border-white/10">{props.children}</div>
      </Show>
    </details>
  )
}
