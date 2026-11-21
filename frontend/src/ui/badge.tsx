import type { JSX } from '@solidjs/web'
import { labelFor, statusTone } from './labels'

type BadgeTone = 'zinc' | 'teal' | 'amber' | 'red'
export function Badge(props: { children: JSX.Element; tone?: BadgeTone }): JSX.Element {
  return (
    <span
      class={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs/5 font-medium ${props.tone === 'teal' ? 'bg-teal-500/15 text-teal-700 dark:text-teal-300' : props.tone === 'amber' ? 'bg-amber-400/20 text-amber-700 dark:text-amber-400' : props.tone === 'red' ? 'bg-red-500/15 text-red-700 dark:text-red-400' : 'bg-zinc-600/10 text-zinc-700 dark:bg-white/5 dark:text-zinc-400'}`}
    >
      {props.children}
    </span>
  )
}

export function StatusBadge(props: { status: string | null | undefined }): JSX.Element {
  return <Badge tone={statusTone(props.status)}>{labelFor(props.status)}</Badge>
}
