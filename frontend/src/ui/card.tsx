import type { JSX } from '@solidjs/web'
import { Show } from 'solid-js'
import { Subheading } from './typography'

export function Card(props: {
  children: JSX.Element
  title?: string
  actions?: JSX.Element
  'aria-label'?: string
}): JSX.Element {
  return (
    <section
      aria-label={props['aria-label']}
      class="rounded-xl bg-white p-4 shadow-xs ring-1 ring-zinc-950/5 sm:p-6 dark:bg-zinc-900 dark:ring-white/10"
    >
      <Show when={props.title != null || props.actions != null}>
        <div class="mb-4 flex items-center justify-between gap-4">
          <Show when={props.title}>
            <Subheading>{props.title}</Subheading>
          </Show>
          {props.actions}
        </div>
      </Show>
      {props.children}
    </section>
  )
}
