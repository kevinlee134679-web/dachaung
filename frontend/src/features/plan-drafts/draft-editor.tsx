import type { View } from '../../session/session'
import type { Editor, Medication, SourceFile } from './drafts'
import type { JSX } from '@solidjs/web'
import { createSignal, For, Show, untrack } from 'solid-js'
import * as v from 'valibot'
import { api } from '../../api/api'
import { notice } from '../../notice/notice'
import { patientPath, requireCurrentView, scope, updateSession } from '../../session/session'
import { Button } from '../../ui/button'
import { Checkbox, Fieldset } from '../../ui/form'
import { Subheading } from '../../ui/typography'
import { newEntry } from './drafts'
import { EntryEditor } from './entry-editor'
import { checkedSchedule } from './schedule-fields'

export function DraftEditor(props: {
  editor: Editor
  meds: Medication[]
  files: SourceFile[]
  saved: (view: View) => Promise<void>
}): JSX.Element {
  const initialEditor = untrack(() => props.editor)
  const [entries, setEntries] = createSignal(initialEditor.entries)
  const selectedFiles = new Set(initialEditor.draft?.source_file_ids ?? [])
  async function save(view: View): Promise<void> {
    const draft = props.editor.draft
    if (entries().some(entry => !entry.medication_id)) throw new Error('请为每个条目选择已有药品。')
    const body = {
      source_file_ids: props.files.filter(file => selectedFiles.has(file.file_id)).map(file => file.file_id),
      entries: entries().map(entry => ({ ...entry, schedule: checkedSchedule(entry.schedule) })),
      ...(draft ? { expected_revision: draft.meta.revision } : {}),
    }
    await api(
      draft ? `/drafts/${draft.draft_id}` : patientPath('/drafts'),
      v.unknown(),
      draft ? 'PUT' : 'POST',
      body,
      view,
    )
    requireCurrentView(view)
    updateSession(session => {
      session.draft = null
    })
    await props.saved(view)
    requireCurrentView(view)
    notice('草稿已保存，尚未成为正式计划。')
  }
  return (
    <div class="space-y-4">
      <Subheading>{props.editor.draft ? '修改资料草稿' : '新建资料草稿'}</Subheading>
      <Show when={props.files.length > 0}>
        <Fieldset legend="来源文件（纯手工可以不选）">
          <For each={props.files}>
            {file => (
              <Checkbox
                label={file.original_name}
                checked={selectedFiles.has(file.file_id)}
                onChange={event => {
                  if (event.currentTarget.checked) selectedFiles.add(file.file_id)
                  else selectedFiles.delete(file.file_id)
                }}
              />
            )}
          </For>
        </Fieldset>
      </Show>
      <For each={entries()}>
        {(entry, index) => (
          <EntryEditor
            entry={entry}
            index={index()}
            meds={props.meds}
            removable={entries().length > 1}
            remove={() => {
              setEntries(current => current.filter(item => item !== entry))
            }}
          />
        )}
      </For>
      <div class="flex flex-wrap gap-3">
        <Show when={props.meds[0]} keyed>
          {medication => (
            <Button
              onAction={() => {
                setEntries(current => [...current, newEntry(medication.medication_id)])
              }}
            >
              再加一种药品
            </Button>
          )}
        </Show>
        <Button variant="primary" disabled={!scope('drafts:write')} onAction={save}>
          保存草稿
        </Button>
      </div>
    </div>
  )
}
