import type { View } from '../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, flush, Show, untrack } from 'solid-js'
import { actionError } from '../notice/notice'
import { captureView, isCurrentView, ViewChanged } from '../session/session'

export interface ButtonProps {
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

export interface FieldProps {
  label: string
  children: JSX.Element
  description?: string
}
export function Field(props: FieldProps): JSX.Element {
  return (
    <label class="block">
      <span class="text-sm/6 font-medium text-zinc-950 dark:text-white">{props.label}</span>
      <div class="mt-2">{props.children}</div>
      <Show when={props.description}>
        <Text class="mt-2">{props.description}</Text>
      </Show>
    </label>
  )
}

const controlClass =
  'block w-full rounded-lg bg-white px-3 py-1.5 text-base/6 text-zinc-950 shadow-xs ring-1 ring-inset ring-zinc-950/10 placeholder:text-zinc-400 focus:outline-2 focus:-outline-offset-1 focus:outline-teal-600 disabled:opacity-50 sm:text-sm/6 dark:bg-white/5 dark:text-white dark:ring-white/10'

export type InputProps = JSX.InputHTMLAttributes<HTMLInputElement>
export function Input(props: InputProps): JSX.Element {
  return <input {...props} class={[`${controlClass} h-9`, props.class]} />
}

export type SelectProps = JSX.SelectHTMLAttributes<HTMLSelectElement>
export function Select(props: SelectProps): JSX.Element {
  return (
    <div class="relative grid">
      <select {...props} class={[`${controlClass} h-9 appearance-none pr-9`, props.class]} />
      <span
        aria-hidden="true"
        class="pointer-events-none absolute top-1/2 right-3 icon-[heroicons--chevron-up-down-20-solid] size-4 -translate-y-1/2 text-zinc-500 dark:text-zinc-400"
      />
    </div>
  )
}

export type TextareaProps = JSX.TextareaHTMLAttributes<HTMLTextAreaElement>
export function Textarea(props: TextareaProps): JSX.Element {
  return <textarea {...props} class={[`${controlClass} min-h-24`, props.class]} />
}

export interface CheckboxProps extends JSX.InputHTMLAttributes<HTMLInputElement> {
  label: string
}
export function Checkbox(props: CheckboxProps): JSX.Element {
  return (
    <label class="flex min-h-9 items-center gap-3 text-sm/6">
      <input
        {...props}
        type="checkbox"
        class="size-4 rounded accent-teal-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600"
      />
      <span>{props.label}</span>
    </label>
  )
}

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

export function Fieldset(props: { legend: string; children: JSX.Element }): JSX.Element {
  return (
    <fieldset class="rounded-lg p-4 ring-1 ring-zinc-950/10 dark:ring-white/10">
      <legend class="px-1 text-sm/6 font-semibold">{props.legend}</legend>
      <div class="mt-2 space-y-4">{props.children}</div>
    </fieldset>
  )
}

export type BadgeTone = 'zinc' | 'teal' | 'amber' | 'red'
export function Badge(props: { children: JSX.Element; tone?: BadgeTone }): JSX.Element {
  return (
    <span
      class={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs/5 font-medium ${props.tone === 'teal' ? 'bg-teal-500/15 text-teal-700 dark:text-teal-300' : props.tone === 'amber' ? 'bg-amber-400/20 text-amber-700 dark:text-amber-400' : props.tone === 'red' ? 'bg-red-500/15 text-red-700 dark:text-red-400' : 'bg-zinc-600/10 text-zinc-700 dark:bg-white/5 dark:text-zinc-400'}`}
    >
      {props.children}
    </span>
  )
}

export function Disclosure(props: { summary: JSX.Element; children: JSX.Element; open?: boolean }): JSX.Element {
  return (
    <details open={props.open} class="group rounded-lg ring-1 ring-zinc-950/10 dark:ring-white/10">
      <summary class="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-2.5 text-sm/6 font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600 [&::-webkit-details-marker]:hidden">
        {props.summary}
        <span
          aria-hidden="true"
          class="icon-[heroicons--chevron-down-20-solid] size-4 transition-transform duration-150 group-open:rotate-180 motion-reduce:transition-none"
        />
      </summary>
      <div class="space-y-4 border-t border-zinc-950/5 px-4 py-4 dark:border-white/10">{props.children}</div>
    </details>
  )
}
