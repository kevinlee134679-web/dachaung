import type { JSX } from '@solidjs/web'
import { createSignal, flush, Show } from 'solid-js'
import { state } from '../session/session'
import { Button } from './button'
import { Text } from './typography'

const [message, setMessage] = createSignal('')
let dialog!: HTMLDialogElement
let resolveConfirmation!: (confirmed: boolean) => void

export function confirm(text: string): Promise<boolean> {
  const { promise, resolve } = Promise.withResolvers<boolean>()
  resolveConfirmation = resolve
  setMessage(text)
  flush()
  dialog.showModal()
  return promise
}

export function ConfirmHost(): JSX.Element {
  function finish(confirmed: boolean): void {
    dialog.close()
    resolveConfirmation(confirmed)
  }

  return (
    <dialog
      ref={dialog}
      aria-label="确认操作"
      class="m-auto w-[calc(100%-2rem)] max-w-md rounded-xl bg-white p-6 text-zinc-950 shadow-xl backdrop:bg-zinc-950/50 dark:bg-zinc-900 dark:text-white"
      onCancel={event => {
        event.preventDefault()
        finish(false)
      }}
    >
      <Text>{message()}</Text>
      <Show when={state.epoch + 1} keyed>
        <div class="mt-6 flex justify-end gap-3">
          <Button onAction={() => finish(false)}>取消</Button>
          <Button variant="primary" onAction={() => finish(true)}>
            确认
          </Button>
        </div>
      </Show>
    </dialog>
  )
}
