import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all } from '../../api/api'
import { actionError } from '../../notice/notice'
import { captureView, isCurrentView, requireCurrentView, scope, ViewChanged } from '../../session/session'
import { Card, Text } from '../../ui/components'

const knowledgeItemSchema = v.looseObject({ title: v.string(), body: v.string(), source_locator: v.string() })
type KnowledgeItem = v.InferOutput<typeof knowledgeItemSchema>

export function KnowledgePage(): JSX.Element {
  const [items, setItems] = createSignal<KnowledgeItem[] | null>(null)
  onSettled(() => {
    if (!scope('knowledge:read')) return
    const view = captureView()
    void all('/knowledge?kind=medical', knowledgeItemSchema, view)
      .then(result => {
        requireCurrentView(view)
        setItems(result)
      })
      .catch((error: unknown) => {
        if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
      })
  })
  return (
    <Show when={scope('knowledge:read')} fallback={<p>当前对象的知识查看权限未开启。</p>}>
      <Show when={items()}>
        {list => (
          <Show
            when={list().length}
            fallback={
              <Card>
                <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
                  目前没有适用的审核药学资料。用药问题请向实际医生或药师核实。
                </Text>
              </Card>
            }
          >
            <div class="space-y-6">
              <For each={list()}>
                {item => (
                  <Card title={item.title}>
                    <div class="space-y-2">
                      <p class="text-sm/6">{item.body}</p>
                      <Text>{item.source_locator}</Text>
                    </div>
                  </Card>
                )}
              </For>
            </div>
          </Show>
        )}
      </Show>
    </Show>
  )
}
