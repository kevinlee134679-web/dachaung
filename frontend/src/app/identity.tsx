import type { JSX } from '@solidjs/web'
import { For, Show } from 'solid-js'
import * as v from 'valibot'
import { api } from '../api/api'
import { actionError, notice } from '../notice/notice'
import {
  captureView,
  isCurrentView,
  loadContext,
  requireCurrentView,
  resetSession,
  state,
  updateSession,
  ViewChanged,
} from '../session/session'
import { Button } from '../ui/button'
import { Select } from '../ui/form'

export function Identity(): JSX.Element {
  async function switchPatient(event: Event & { currentTarget: HTMLSelectElement }): Promise<void> {
    const picker = event.currentTarget
    const selected = picker.value
    if (!selected || state.switchingPatient) return
    updateSession(draft => {
      draft.switchingPatient = true
      draft.epoch++
      draft.response = null
      draft.draft = null
    })
    const transition = captureView()
    try {
      await api('/auth/current-patient', v.unknown(), 'PUT', { patient_id: selected }, transition)
      await loadContext(transition)
      notice('已切换对象，旧表单已清除。')
    } catch (error) {
      if (!(error instanceof ViewChanged) && state.epoch === transition.epoch && isCurrentView(transition))
        actionError(error, transition)
      picker.value = state.patient?.patient.patient_id ?? ''
    } finally {
      updateSession(draft => {
        draft.switchingPatient = false
      })
    }
  }
  return (
    <div class="flex min-w-0 items-center justify-end gap-2">
      <Show when={state.context}>
        <p class="hidden text-sm/6 font-semibold sm:block">{state.context?.account.display_name}</p>
        <Show when={state.context?.patients.length}>
          <label class="max-w-40 min-w-0">
            <span class="sr-only">正在管理</span>
            <Select
              aria-label="当前管理对象"
              value={state.patient?.patient.patient_id ?? ''}
              disabled={state.switchingPatient}
              onChange={event => void switchPatient(event)}
            >
              <option value="">请选择管理对象</option>
              <For each={state.context?.patients}>
                {item => (
                  <option value={item.patient.patient_id}>
                    {item.patient.display_name} · {item.relationship === 'self' ? '本人' : '家庭协助'}
                  </option>
                )}
              </For>
            </Select>
          </label>
        </Show>
        <Button
          view={{ ...captureView(), sessionOnly: true }}
          variant="plain"
          icon="icon-[heroicons--arrow-right-start-on-rectangle]"
          class="!px-2"
          onAction={async view => {
            await api('/auth/logout', v.unknown(), 'POST', {}, view)
            requireCurrentView(view)
            resetSession()
            notice('当前会话已退出。')
          }}
        >
          <span class="sr-only sm:not-sr-only">退出</span>
        </Button>
      </Show>
    </div>
  )
}
