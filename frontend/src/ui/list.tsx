import type { JSX } from '@solidjs/web'
import { Show } from 'solid-js'
import { Text } from './typography'

const listClass = 'divide-y divide-zinc-950/5 dark:divide-white/5 *:py-4 *:first:pt-0 *:last:pb-0'

export function List(props: { children: JSX.Element; ordered?: boolean; class?: string }): JSX.Element {
  return (
    <Show when={props.ordered} fallback={<ul class={[listClass, props.class]}>{props.children}</ul>}>
      <ol class={[listClass, props.class]}>{props.children}</ol>
    </Show>
  )
}

export function EmptyState(props: { children: JSX.Element }): JSX.Element {
  return (
    <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
      {props.children}
    </Text>
  )
}
