import type { View } from '../../session/session'
import type { SourceFile } from '../medical-files/files'
import type { DraftData, Editor, Draft, Medication } from './drafts'
import type { JSX } from '@solidjs/web'
import { createSignal, flush, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api } from '../../api/api'
import { dateText } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import { readGate } from '../../session/read-gate'
import {
  captureView,
  isCurrentView,
  own,
  patientPath,
  requireCurrentView,
  scope,
  state,
  updateSession,
  ViewChanged,
} from '../../session/session'
import { StatusBadge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { EmptyState, List } from '../../ui/list'
import { Subheading, Text } from '../../ui/typography'
import { Confirmation } from './confirmation'
import { DraftEditor } from './draft-editor'
import { draftSchema, medicationSchema, planSchema, newEntry } from './drafts'

export function DraftPage(props: { files: SourceFile[]; reload: (view: View) => Promise<void> }): JSX.Element {
  const [data, setData] = createSignal<DraftData | null>(null)
  const [editor, setEditor] = createSignal<Editor | null>(null)
  const nextRead = readGate()
  async function load(view: View): Promise<DraftData> {
    const check = nextRead()
    const drafts = await all(patientPath('/drafts'), draftSchema, view)
    const meds = scope('medication:read') ? await all(patientPath('/medications'), medicationSchema, view) : []
    const plans = meds.length && scope('plan:read') ? await all(patientPath('/plans'), planSchema, view) : []
    check()
    const result = { drafts, meds, files: props.files, plans }
    setData(result)
    flush()
    return result
  }
  async function saved(view: View): Promise<void> {
    requireCurrentView(view)
    setEditor(null)
    await load(view)
  }
  function edit(draft: Draft | null, firstMedication: Medication): void {
    updateSession(session => {
      session.draft = draft
    })
    const entries = structuredClone(draft?.entries ?? [])
    setEditor({ draft, entries: entries.length ? entries : [newEntry(firstMedication.medication_id)] })
  }
  async function submit(draft: Draft, view: View): Promise<void> {
    await api(
      `/drafts/${draft.draft_id}/submit`,
      v.unknown(),
      'POST',
      { expected_revision: draft.meta.revision, content_revision: draft.content_revision },
      view,
    )
    await saved(view)
    requireCurrentView(view)
    notice('已提交此内容修订，等待患者本人核对。')
  }
  onSettled(() => {
    if (!scope('drafts:read')) return
    const view = captureView()
    void load(view)
      .then(current => {
        requireCurrentView(view)
        const draft = state.draft
        const firstMedication = current.meds[0]
        if (draft && firstMedication && scope('drafts:write') && ['editing', 'returned'].includes(draft.status)) {
          edit(draft, firstMedication)
        }
      })
      .catch((error: unknown) => {
        if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
      })
  })
  return (
    <Show when={scope('drafts:read')} fallback={<Text>当前未获草稿查看权限。</Text>}>
      <Show when={data()}>
        {current => (
          <Card>
            <div class="space-y-6">
              <Text>人工录成草稿，核对后提交，再由患者本人确认正式计划。文件保存、草稿提交和正式确认是不同结果。</Text>
              <Show
                when={current().meds.length > 0}
                fallback={
                  <Button variant="primary" onAction={() => navigate('profile', 'meds')}>
                    先添加药品资料
                  </Button>
                }
              >
                <Show when={scope('drafts:write')}>
                  <Show when={current().meds[0]} keyed>
                    {medication => <Button onAction={() => edit(null, medication)}>新建人工资料草稿</Button>}
                  </Show>
                </Show>
                <Show when={editor()} keyed>
                  {value => <DraftEditor editor={value} meds={current().meds} files={props.files} saved={saved} />}
                </Show>
                <Subheading>草稿与核对进度</Subheading>
                <Show when={current().drafts.length > 0} fallback={<EmptyState>还没有资料草稿。</EmptyState>}>
                  <List>
                    <For each={current().drafts}>
                      {draft => (
                        <li class="space-y-4">
                          <div class="flex flex-wrap items-center gap-2 text-sm/6 font-medium">
                            <StatusBadge status={draft.status} /> · {draft.entries.length} 个条目
                          </div>
                          <Text>
                            内容修订 {draft.content_revision} · {dateText(draft.meta.updated_at)}
                          </Text>
                          <For each={draft.entries}>
                            {entry => (
                              <p class="text-sm/6">
                                {current().meds.find(med => med.medication_id === entry.medication_id)?.name ??
                                  '药品资料'}
                                ：{entry.dose_value ?? '剂量未录入'} {entry.dose_unit ?? '单位未录入'}；
                                {entry.schedule && entry.schedule.times.length > 0
                                  ? entry.schedule.times.join('、')
                                  : '时间待核对'}
                              </p>
                            )}
                          </For>
                          <Show when={draft.return_reason}>
                            <p class="text-sm/6 text-red-600 dark:text-red-400">{draft.return_reason}</p>
                          </Show>
                          <Show when={['editing', 'returned'].includes(draft.status)}>
                            <div class="flex flex-wrap gap-3 sm:justify-end">
                              <Show when={current().meds[0]} keyed>
                                {medication => (
                                  <Button disabled={!scope('drafts:write')} onAction={() => edit(draft, medication)}>
                                    修改草稿
                                  </Button>
                                )}
                              </Show>
                              <Button disabled={!scope('drafts:submit')} onAction={async view => submit(draft, view)}>
                                提交本修订供本人核对
                              </Button>
                            </div>
                          </Show>
                          <Show when={draft.status === 'pending_confirmation' && own()}>
                            <Confirmation draft={draft} plans={current().plans} saved={saved} />
                          </Show>
                          <Show when={draft.formal_plan}>
                            <Text>正式计划第 {draft.formal_plan?.plan_version} 版已保存；可在“今日安排”中查看。</Text>
                          </Show>
                        </li>
                      )}
                    </For>
                  </List>
                </Show>
              </Show>
            </div>
          </Card>
        )}
      </Show>
    </Show>
  )
}
