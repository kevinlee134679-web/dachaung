import type { View } from '../../session/session'
import type { Entry } from './drafts'
import type { MedicationList } from './medication-list'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import { today } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import { captureView, isCurrentView, referenceKey, requireCurrentView, scope, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Text } from '../../ui/typography'
import { draftBody, isBlank, newEntry } from './drafts'
import { EntryEditor } from './entry-editor'
import {
  canManageMedicationList,
  entryFromRecognition,
  loadMedicationList,
  saveMedicationList,
} from './medication-list'
import { PublishedPlan } from './published-plan'
import { RecognitionPanel } from './recognition-panel'

export function MedicationListForm(props: { onConfirmed?: (view: View) => Promise<void> }): JSX.Element {
  const [rows, setRows] = createSignal<Entry[]>([])
  const [loaded, setLoaded] = createSignal<MedicationList | null>(null)
  const [busy, setBusy] = createSignal(false)
  let loadedBody = ''
  async function load(view: View): Promise<void> {
    const value = await loadMedicationList(view)
    requireCurrentView(view)
    loadedBody = JSON.stringify(draftBody(value.entries, false))
    const requested = sessionStorage.getItem(referenceKey('medication-list-medication'))
    sessionStorage.removeItem(referenceKey('medication-list-medication'))
    if (
      requested !== null &&
      requested !== '' &&
      value.meds.some(med => med.medication_id === requested) &&
      !value.entries.some(entry => entry.medication_id === requested)
    ) {
      const entry = { ...newEntry(requested), start_date: today() }
      value.entries =
        value.entries.length === 1 && value.entries[0] && isBlank(value.entries[0])
          ? [entry]
          : [...value.entries, entry]
    }
    setRows(value.entries)
    setLoaded(value)
  }
  async function save(view: View, value: MedicationList): Promise<void> {
    setBusy(true)
    try {
      await saveMedicationList(view, value, rows())
      notice('用药清单已生效，今日用药情况已更新')
      await props.onConfirmed?.(view)
      await load(view)
    } finally {
      setBusy(false)
    }
  }
  onSettled(() => {
    if (!canManageMedicationList()) return
    const view = captureView()
    void load(view).catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })
  return (
    <Show when={canManageMedicationList()} fallback={<Text>当前未获用药清单管理权限。</Text>}>
      <Show when={loaded()} fallback={<Text>正在读取药品资料与用药计划…</Text>}>
        {value => (
          <Card title="用药清单">
            <div class="space-y-5">
              <Show when={value().plan}>{plan => <PublishedPlan plan={plan()} />}</Show>
              <Show when={scope('files:read')}>
                <RecognitionPanel
                  onApply={meds => {
                    const entries = meds.map(med => entryFromRecognition(med, value().meds, today()))
                    setRows(current =>
                      current.length === 1 && current[0] && isBlank(current[0]) ? entries : [...current, ...entries],
                    )
                  }}
                />
              </Show>
              <fieldset
                disabled={busy()}
                class="space-y-5 disabled:opacity-75"
                aria-label="编辑用药条目"
                onInput={() => {
                  setRows(current => [...current])
                }}
                onChange={() => {
                  setRows(current => [...current])
                }}
              >
                <For each={rows()}>
                  {(entry, index) => (
                    <EntryEditor
                      entry={entry}
                      index={index()}
                      meds={value().meds}
                      allowNew={scope('medication:edit')}
                      removable={rows().length > 1}
                      remove={() => {
                        setRows(current => current.filter(item => item !== entry))
                      }}
                    />
                  )}
                </For>
                <Button onAction={() => setRows(current => [...current, { ...newEntry(''), start_date: today() }])}>
                  添加一种药
                </Button>
              </fieldset>
              <Button
                variant="primary"
                disabled={busy() || JSON.stringify(draftBody(rows(), false)) === loadedBody}
                onAction={view => save(view, value())}
              >
                保存并生效
              </Button>
            </div>
          </Card>
        )}
      </Show>
    </Show>
  )
}
