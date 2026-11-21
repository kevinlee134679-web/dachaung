import type { JSX } from '@solidjs/web'
import { Show } from 'solid-js'
import { Text } from './typography'

interface FieldProps {
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

type InputProps = JSX.InputHTMLAttributes<HTMLInputElement>
export function Input(props: InputProps): JSX.Element {
  return <input {...props} class={[`${controlClass} h-9`, props.class]} />
}

type SelectProps = JSX.SelectHTMLAttributes<HTMLSelectElement>
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

type TextareaProps = JSX.TextareaHTMLAttributes<HTMLTextAreaElement>
export function Textarea(props: TextareaProps): JSX.Element {
  return <textarea {...props} class={[`${controlClass} min-h-24`, props.class]} />
}

interface CheckboxProps extends JSX.InputHTMLAttributes<HTMLInputElement> {
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

export function Fieldset(props: { legend: string; children: JSX.Element }): JSX.Element {
  return (
    <fieldset class="rounded-lg p-4 ring-1 ring-zinc-950/10 dark:ring-white/10">
      <legend class="px-1 text-sm/6 font-semibold">{props.legend}</legend>
      <div class="mt-2 space-y-4">{props.children}</div>
    </fieldset>
  )
}
