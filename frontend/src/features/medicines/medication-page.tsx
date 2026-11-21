import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api } from '../../api/api'
import { actionError, notice } from '../../notice/notice'
import { captureView, isCurrentView, patientPath, requireCurrentView, scope, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Field, Input, Textarea } from '../../ui/form'
import { EmptyState, List } from '../../ui/list'
import { Text } from '../../ui/typography'

const medicationSchema = v.looseObject({
  medication_id: v.string(),
  name: v.string(),
  notes: v.nullable(v.string()),
  meta: v.looseObject({ revision: v.number() }),
})
type Medication = v.InferOutput<typeof medicationSchema>

export function MedicationPage(): JSX.Element {
  const [medications, setMedications] = createSignal<Medication[] | null>(null)
  const [editing, setEditing] = createSignal<Medication | null>(null)
  let name!: HTMLInputElement
  let notes!: HTMLTextAreaElement

  async function load(view: View): Promise<void> {
    const result = await all(patientPath('/medications'), medicationSchema, view)
    requireCurrentView(view)
    setMedications(result)
  }

  function edit(medication: Medication | null): void {
    setEditing(medication)
    name.value = medication?.name ?? ''
    notes.value = medication?.notes ?? ''
  }

  async function save(view: View): Promise<void> {
    const medication = editing()
    const body = {
      name: name.value,
      notes: notes.value || null,
      ...(medication ? { expected_revision: medication.meta.revision } : {}),
    }
    await api(
      medication ? `/medications/${medication.medication_id}` : patientPath('/medications'),
      v.unknown(),
      medication ? 'PATCH' : 'POST',
      body,
      view,
    )
    await load(view)
    requireCurrentView(view)
    edit(null)
    notice('药品资料已保存。')
  }

  onSettled(() => {
    if (!scope('medication:read')) return
    const view = captureView()
    void load(view).catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })

  return (
    <Show when={scope('medication:read')} fallback={<p>当前未获药品资料查看权限。</p>}>
      <div class="space-y-6">
        <Show when={scope('medication:edit')}>
          <Card title={editing() ? '纠正药品资料' : '添加药品资料'}>
            <div class="space-y-4">
              <Field label="药品名称（按原资料核对）">
                <Input ref={name} />
              </Field>
              <Field label="资料备注（可空）">
                <Textarea ref={notes} />
              </Field>
              <Text>名称和备注不改变处方剂量或频次；正式安排需要另行提交草稿并核对。</Text>
              <Button variant="primary" onAction={save}>
                保存药品资料
              </Button>
            </div>
          </Card>
        </Show>
        <Card title="已有药品">
          <Show when={medications()}>
            {items => (
              <>
                <Show when={!items().length}>
                  <EmptyState>还没有药品资料。</EmptyState>
                </Show>
                <List>
                  <For each={items()}>
                    {medication => (
                      <li class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <strong class="text-sm/6 font-medium">{medication.name}</strong>
                          <Text>
                            {medication.notes === null || medication.notes === '' ? '没有备注' : medication.notes}
                          </Text>
                        </div>
                        <Button disabled={!scope('medication:edit')} onAction={() => edit(medication)}>
                          编辑资料
                        </Button>
                      </li>
                    )}
                  </For>
                </List>
              </>
            )}
          </Show>
        </Card>
      </div>
    </Show>
  )
}
