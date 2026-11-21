import type { View } from '../../session/session'
import type { Message, SupportSession } from './conversation'
import type { JSX } from '@solidjs/web'
import { Show } from 'solid-js'
import { api } from '../../api/api'
import { requireCurrentView } from '../../session/session'
import { Badge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { statusTone } from '../../ui/labels'
import { generationState, outputSchema, pendingRefresh } from './conversation'
import { refreshSupport } from './invitations'

export function SupportMessage(props: { session: SupportSession; message: Message; canWrite: boolean }): JSX.Element {
  async function retry(view: View): Promise<void> {
    const data = await api(
      `/messages/${encodeURIComponent(props.message.message_id)}/generation-retries`,
      outputSchema,
      'POST',
      { generation_id: props.message.generation_id, expected_turn_count: props.session.turn_count },
      view,
    )
    requireCurrentView(view)
    pendingRefresh.current = {
      accountId: view.accountId,
      patientId: view.patientId,
      sessionId: props.session.session_id,
      output: data,
    }
    refreshSupport(view)
  }
  return (
    <article class={`flex ${props.message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div
        class={`max-w-[85%] space-y-2 rounded-xl px-4 py-3 text-sm/6 ${props.message.role === 'user' ? 'bg-teal-50 text-teal-950 dark:bg-teal-500/15 dark:text-teal-100' : 'bg-zinc-100 text-zinc-950 dark:bg-white/5 dark:text-white'}`}
      >
        <small class="font-medium">{props.message.role === 'user' ? '本人' : 'AI 支持助手'}</small>
        <p class="whitespace-pre-wrap">{props.message.content}</p>
        <Show when={props.message.role === 'user' && generationState[props.message.generation_status]}>
          <Badge tone={statusTone(props.message.generation_status)}>
            {generationState[props.message.generation_status]}
          </Badge>
          <Show when={props.canWrite && props.message.generation_status === 'failed'}>
            <Button onAction={retry}>重试原消息</Button>
          </Show>
        </Show>
      </div>
    </article>
  )
}
