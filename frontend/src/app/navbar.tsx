import type { Page } from '../session/session'
import type { JSX } from '@solidjs/web'
import { For } from 'solid-js'
import { navigate } from '../session/navigation'
import { state } from '../session/session'

const pages: { page: Page; label: string; icon: string }[] = [
  { page: 'home', label: '首页', icon: 'icon-[heroicons--home]' },
  { page: 'medication', label: '用药管理', icon: 'icon-[heroicons--clipboard-document-list]' },
  { page: 'support', label: '支持服务', icon: 'icon-[heroicons--chat-bubble-left-right]' },
  { page: 'rewards', label: '积分权益', icon: 'icon-[heroicons--gift]' },
  { page: 'profile', label: '我的', icon: 'icon-[heroicons--user-circle]' },
]

export function Navbar(): JSX.Element {
  return (
    <nav aria-label="主要导航" class="flex w-full lg:flex-col lg:gap-1">
      <For each={pages}>
        {item => (
          <button
            type="button"
            disabled={state.switchingPatient}
            aria-current={state.page === item.page ? 'page' : undefined}
            onClick={() => navigate(item.page)}
            class={`inline-flex h-auto min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-none px-1 py-2 text-xs font-semibold whitespace-nowrap transition-colors duration-75 hover:bg-zinc-950/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600 disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:transition-none lg:h-9 lg:w-full lg:flex-none lg:flex-row lg:justify-start lg:gap-3 lg:rounded-lg lg:px-2 lg:py-0 lg:text-sm lg:font-medium dark:hover:bg-white/10 ${state.page === item.page ? 'text-teal-600 lg:bg-zinc-950/5 lg:text-zinc-950 dark:text-teal-400 lg:dark:bg-white/10 lg:dark:text-white' : 'text-zinc-600 hover:text-zinc-950 dark:text-zinc-400 dark:hover:text-white'}`}
          >
            <span
              aria-hidden="true"
              class={`${item.icon} size-6 lg:size-5 ${state.page === item.page ? 'lg:text-teal-600 lg:dark:text-teal-400' : ''}`}
            />
            {item.label}
          </button>
        )}
      </For>
    </nav>
  )
}
