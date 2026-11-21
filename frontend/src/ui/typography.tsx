import type { JSX } from '@solidjs/web'
import { Show } from 'solid-js'

export function Heading(props: { children: JSX.Element }): JSX.Element {
  return <h1 class="text-2xl/8 font-semibold text-zinc-950 sm:text-xl/8 dark:text-white">{props.children}</h1>
}

export function Subheading(props: { children: JSX.Element; level?: 2 | 3 }): JSX.Element {
  return (
    <Show
      when={props.level === 3}
      fallback={<h2 class="text-base/7 font-semibold text-zinc-950 dark:text-white">{props.children}</h2>}
    >
      <h3 class="text-base/7 font-semibold text-zinc-950 dark:text-white">{props.children}</h3>
    </Show>
  )
}

export function Text(props: { children: JSX.Element; class?: string }): JSX.Element {
  return <p class={`text-sm/6 text-zinc-500 dark:text-zinc-400 ${props.class ?? ''}`}>{props.children}</p>
}
