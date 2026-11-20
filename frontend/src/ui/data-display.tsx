import type { JSX } from '@solidjs/web'
import { For } from 'solid-js'

export type Issue = string | { message?: string | null; reason?: string | null; code?: string | null }

export function IssueList(props: { issues: Issue[] | null | undefined }): JSX.Element {
  return (
    <ul class="space-y-1 text-sm/6 text-amber-700 dark:text-amber-400">
      <For each={props.issues ?? []}>
        {issue => (
          <li>
            <span aria-hidden="true" class="mr-2 icon-[heroicons--exclamation-triangle-20-solid] size-4" />
            {typeof issue === 'string'
              ? issue
              : ([issue.message, issue.reason, issue.code].find(
                  value => value !== null && value !== undefined && value !== '',
                ) ?? Object.prototype.toString.call(issue))}
          </li>
        )}
      </For>
    </ul>
  )
}

export interface DataTableProps {
  headers: JSX.Element[]
  rows: JSX.Element[][]
}

export function DataTable(props: DataTableProps): JSX.Element {
  return (
    <div class="-mx-4 overflow-x-auto sm:mx-0" tabindex="0">
      <table class="min-w-full text-left text-sm/6">
        <thead>
          <tr>
            <For each={props.headers}>
              {header => (
                <th
                  scope="col"
                  class="border-b border-zinc-950/10 px-4 py-2 font-medium text-zinc-500 dark:border-white/10 dark:text-zinc-400"
                >
                  {header}
                </th>
              )}
            </For>
          </tr>
        </thead>
        <tbody>
          <For each={props.rows}>
            {row => (
              <tr>
                <For each={row}>
                  {value => <td class="border-b border-zinc-950/5 px-4 py-3 dark:border-white/5">{value ?? '—'}</td>}
                </For>
              </tr>
            )}
          </For>
        </tbody>
      </table>
    </div>
  )
}
