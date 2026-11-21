import type { View } from '../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, flush, Show, untrack } from 'solid-js'
import { actionError } from '../notice/notice'
import { captureView, isCurrentView, ViewChanged } from '../session/session'

interface ButtonProps {
  children: JSX.Element
  onAction: ((view: View) => void) | ((view: View) => Promise<unknown>)
  disabled?: boolean
  view?: View
  variant?: 'primary' | 'secondary' | 'danger' | 'plain'
  icon?: string
  class?: string
  'aria-current'?: 'page' | undefined
  'aria-label'?: string
}

export function Button(props: ButtonProps): JSX.Element {
  // deliberate creation snapshot: a control outliving its view must refuse to act
  const view = untrack(() => props.view ?? captureView())
  const [running, setRunning] = createSignal(false)
  async function click(): Promise<void> {
    if (props.disabled || running() || !isCurrentView(view)) return
    setRunning(true)
    flush()
    try {
      await props.onAction(view)
    } catch (error) {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    } finally {
      setRunning(false)
    }
  }
  return (
    <button
      type="button"
      class={`inline-flex h-9 items-center justify-center gap-2 rounded-lg px-3.5 text-sm/6 font-semibold whitespace-nowrap transition-colors duration-75 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600 disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:transition-none ${props.variant === 'primary' ? 'bg-teal-600 text-white shadow-xs hover:bg-teal-500 dark:bg-teal-500 dark:text-white dark:hover:bg-teal-400' : props.variant === 'danger' ? 'bg-red-600 text-white shadow-xs hover:bg-red-500 dark:bg-red-600 dark:text-white dark:hover:bg-red-500' : props.variant === 'plain' ? 'text-zinc-700 hover:bg-zinc-950/5 dark:text-zinc-300 dark:hover:bg-white/10' : 'bg-white text-zinc-900 shadow-xs ring-1 ring-zinc-950/10 ring-inset hover:bg-zinc-50 dark:bg-white/5 dark:text-white dark:ring-white/15 dark:hover:bg-white/10'} ${props.class ?? ''}`}
      disabled={props.disabled ? true : running()}
      aria-current={props['aria-current']}
      aria-label={props['aria-label']}
      aria-busy={running() ? 'true' : undefined}
      onClick={() => void click()}
    >
      <Show when={props.icon}>
        <span aria-hidden="true" class={`${props.icon} size-4`} />
      </Show>
      {props.children}
    </button>
  )
}
