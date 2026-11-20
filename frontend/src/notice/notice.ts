import type { PendingRecovery } from '../api/api'
import type { View } from '../session/session'
import type { Accessor, Setter } from 'solid-js'
import { createSignal, flush } from 'solid-js'
import { ApiError } from '../api/api'
import { isCurrentView } from '../session/session'

export interface NoticeState {
  text: string
  error: boolean
  recovery?: { operation: PendingRecovery; view: View }
}
const noticeSignal = createSignal<NoticeState>({ text: '', error: false })
export const currentNotice: Accessor<NoticeState> = noticeSignal[0]
const setCurrentNotice: Setter<NoticeState> = noticeSignal[1]

export function notice(text: string, error = false): void {
  setCurrentNotice({ text, error })
  flush()
}

export function actionError(error: unknown, view: View): void {
  const recovery = error instanceof ApiError ? error.pendingRecovery : undefined
  const message = error instanceof Error ? error.message : ''
  setCurrentNotice({
    text: message !== '' ? message : '操作未完成，请核查原结果后重试。',
    error: true,
    ...(recovery && isCurrentView(view) ? { recovery: { operation: recovery, view } } : {}),
  })
  flush()
}
