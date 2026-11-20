import type { JSX } from '@solidjs/web'
import { For } from 'solid-js'

export function Tabs(props: {
  items: [string, string][]
  current: string
  onSelect: (key: string) => void
  'aria-label': string
}): JSX.Element {
  return (
    <nav
      aria-label={props['aria-label']}
      class="flex gap-6 overflow-x-auto border-b border-zinc-950/10 dark:border-white/10"
    >
      <For each={props.items}>
        {item => (
          <button
            type="button"
            aria-current={props.current === item[0] ? 'page' : undefined}
            onClick={() => props.onSelect(item[0])}
            class={`-mb-px border-b-2 px-1 py-3 text-sm/6 font-medium whitespace-nowrap transition-colors duration-75 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600 motion-reduce:transition-none ${props.current === item[0] ? 'border-teal-600 text-teal-700 dark:border-teal-400 dark:text-teal-300' : 'border-transparent text-zinc-500 hover:border-zinc-300 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200'}`}
          >
            {item[1]}
          </button>
        )}
      </For>
    </nav>
  )
}
