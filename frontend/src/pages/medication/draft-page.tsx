import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createMemo, createSignal, flush, For, onSettled, Show, untrack } from 'solid-js'
import * as v from 'valibot'
import { all, api } from '../../api/api'
import { copyValue } from '../../data/copy'
import { dateText } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
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
import { navigate } from '../../shell/navigation'
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Disclosure,
  Field,
  Fieldset,
  Input,
  Select,
  Subheading,
  Text,
} from '../../ui/components'
import { labelFor, statusTone } from '../../ui/labels'

export interface Draft {
  draft_id: string
  status: string
  source_file_ids: string[]
  entries: Entry[]
  content_revision: number
  meta: { revision: number; updated_at: string }
  return_reason: string | null
  formal_plan: { plan_version: number } | null
}
interface DraftData {
  drafts: Draft[]
  meds: Medication[]
  files: SourceFile[]
  plans: Plan[]
}
interface Editor {
  draft: Draft | null
  entries: Entry[]
}
interface Entry {
  draft_entry_id: string
  medication_id: string
  dose_value: string | null
  dose_unit: string | null
  start_date: string | null
  end_date: string | null
  schedule: { kind: string; times: string[]; weekdays: number[] } | null
  meal_requirement: string | null
  medical_notes: string | null
  strict_timing: boolean | null
  min_interval_minutes: number | null
  source_file_ids: string[]
}

const medicationSchema = v.looseObject({ medication_id: v.string(), name: v.string() })
const sourceFileSchema = v.looseObject({ file_id: v.string(), original_name: v.string() })
const entrySchema = v.looseObject({
  draft_entry_id: v.string(),
  medication_id: v.string(),
  dose_value: v.nullable(v.string()),
  dose_unit: v.nullable(v.string()),
  start_date: v.nullable(v.string()),
  end_date: v.nullable(v.string()),
  schedule: v.nullable(
    v.looseObject({ kind: v.picklist(['daily', 'weekly']), times: v.array(v.string()), weekdays: v.array(v.number()) }),
  ),
  meal_requirement: v.nullable(v.string()),
  medical_notes: v.nullable(v.string()),
  strict_timing: v.nullable(v.boolean()),
  min_interval_minutes: v.nullable(v.number()),
  source_file_ids: v.array(v.string()),
})
const draftSchema = v.looseObject({
  draft_id: v.string(),
  status: v.picklist(['editing', 'pending_confirmation', 'confirmed', 'returned']),
  source_file_ids: v.array(v.string()),
  entries: v.array(entrySchema),
  content_revision: v.number(),
  meta: v.looseObject({ revision: v.number(), updated_at: v.string() }),
  return_reason: v.nullable(v.string()),
  formal_plan: v.nullable(v.looseObject({ plan_version: v.number() })),
})
const planSchema = v.looseObject({ plan_id: v.string(), plan_version: v.number(), effective_from: v.string() })
type Medication = v.InferOutput<typeof medicationSchema>
type SourceFile = v.InferOutput<typeof sourceFileSchema>
type Plan = v.InferOutput<typeof planSchema>

function newEntry(medicationId: string): Entry {
  return {
    draft_entry_id: crypto.randomUUID(),
    medication_id: medicationId,
    dose_value: null,
    dose_unit: null,
    start_date: null,
    end_date: null,
    schedule: null,
    meal_requirement: null,
    medical_notes: null,
    strict_timing: null,
    min_interval_minutes: null,
    source_file_ids: [],
  }
}

function EntryEditor(props: {
  entry: Entry
  index: number
  meds: Medication[]
  removable: boolean
  remove: () => void
}) {
  let kind!: HTMLSelectElement
  let times!: HTMLInputElement
  const weekdays: HTMLInputElement[] = []
  const entry = untrack(() => props.entry)
  const selectedWeekdays = entry.schedule?.weekdays ?? []
  function updateSchedule(): void {
    entry.schedule = times.value
      ? {
          kind: kind.value,
          times: times.value
            .split(/[,，]/)
            .map(value => value.trim())
            .filter(Boolean),
          weekdays:
            kind.value === 'daily' ? [] : weekdays.flatMap((input, index) => (input.checked ? [index + 1] : [])),
        }
      : null
  }
  return (
    <Fieldset legend={`药品条目 ${props.index + 1}`}>
      <div class="grid gap-4 md:grid-cols-2">
        <Field label="药品资料">
          <Select
            value={entry.medication_id}
            onChange={event => {
              entry.medication_id = event.currentTarget.value
            }}
          >
            <For each={props.meds}>{med => <option value={med.medication_id}>{med.name}</option>}</For>
          </Select>
        </Field>
        <Field label="每次剂量（原资料数值）">
          <Input
            value={entry.dose_value ?? ''}
            onInput={event => {
              entry.dose_value = event.currentTarget.value || null
            }}
          />
        </Field>
        <Field label="剂量单位（原资料）">
          <Input
            value={entry.dose_unit ?? ''}
            onInput={event => {
              entry.dose_unit = event.currentTarget.value || null
            }}
          />
        </Field>
        <Field label="开始日期">
          <Input
            type="date"
            value={entry.start_date ?? ''}
            onInput={event => {
              entry.start_date = event.currentTarget.value || null
            }}
          />
        </Field>
        <Field label="结束日期（未知可空）">
          <Input
            type="date"
            value={entry.end_date ?? ''}
            onInput={event => {
              entry.end_date = event.currentTarget.value || null
            }}
          />
        </Field>
        <Field label="固定频次">
          <Select ref={kind} value={entry.schedule?.kind ?? 'daily'} onChange={updateSchedule}>
            <option value="daily">每天</option>
            <option value="weekly">每周指定日期</option>
          </Select>
        </Field>
        <Field label="每天时刻（HH:mm，多个用逗号分隔）">
          <Input ref={times} value={entry.schedule?.times.join(',') ?? ''} onInput={updateSchedule} />
        </Field>
        <div>
          <span class="text-sm/6 font-medium text-zinc-950 dark:text-white">每周日期（每天安排不勾选）</span>
          <div class="flex flex-wrap gap-3">
            <For each={['一', '二', '三', '四', '五', '六', '日']}>
              {(day, index) => (
                <Checkbox
                  ref={element => {
                    weekdays[index()] = element
                  }}
                  label={day}
                  checked={selectedWeekdays.includes(index() + 1)}
                  onChange={updateSchedule}
                />
              )}
            </For>
          </div>
        </div>
        <Field label="餐前、餐后等要求（未知可空）">
          <Input
            value={entry.meal_requirement ?? ''}
            onInput={event => {
              entry.meal_requirement = event.currentTarget.value || null
            }}
          />
        </Field>
        <Field label="特殊医嘱原文（未知可空）">
          <Input
            value={entry.medical_notes ?? ''}
            onInput={event => {
              entry.medical_notes = event.currentTarget.value || null
            }}
          />
        </Field>
        <Field label="是否明确严格时间要求">
          <Select
            value={entry.strict_timing === null ? '' : String(entry.strict_timing)}
            onChange={event => {
              entry.strict_timing = event.currentTarget.value === '' ? null : event.currentTarget.value === 'true'
            }}
          >
            <option value="">未知</option>
            <option value="true">是</option>
            <option value="false">原资料明确无严格时间要求</option>
          </Select>
        </Field>
        <Field label="原医嘱最小间隔（分钟，未知可空）">
          <Input
            type="number"
            value={entry.min_interval_minutes ?? ''}
            onInput={event => {
              entry.min_interval_minutes = event.currentTarget.value ? Number(event.currentTarget.value) : null
            }}
          />
        </Field>
      </div>
      <Button variant="plain" disabled={!props.removable} onAction={props.remove}>
        移除此条目
      </Button>
    </Fieldset>
  )
}

function DraftEditor(props: {
  editor: Editor
  meds: Medication[]
  files: SourceFile[]
  saved: (view: View) => Promise<void>
}) {
  const initialEditor = untrack(() => props.editor)
  const [entries, setEntries] = createSignal(initialEditor.entries)
  const selectedFiles = new Set(initialEditor.draft?.source_file_ids ?? [])
  async function save(view: View): Promise<void> {
    const draft = props.editor.draft
    const body = {
      source_file_ids: props.files.filter(file => selectedFiles.has(file.file_id)).map(file => file.file_id),
      entries: entries(),
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

function Confirmation(props: { draft: Draft; plans: Plan[]; saved: (view: View) => Promise<void> }) {
  let effective!: HTMLInputElement
  let target!: HTMLSelectElement
  let yes!: HTMLInputElement
  const uniquePlans = createMemo(() => [...new Map(props.plans.map(plan => [plan.plan_id, plan])).values()])
  async function confirm(view: View): Promise<void> {
    if (!yes.checked || !effective.value) throw new Error('请填写生效时间并明确确认资料。')
    const previous = props.plans
      .filter(plan => plan.plan_id === target.value)
      .sort((a, b) => b.plan_version - a.plan_version)[0]
    await api(
      patientPath('/plan-confirmations'),
      v.unknown(),
      'POST',
      {
        draft_id: props.draft.draft_id,
        draft_revision: props.draft.content_revision,
        existing_plan_id: target.value || null,
        expected_plan_version: previous?.plan_version ?? null,
        effective_from: new Date(`${effective.value}:00+08:00`).toISOString(),
        confirmed: true,
      },
      view,
    )
    await props.saved(view)
    requireCurrentView(view)
    notice('正式计划、草稿引用和时段已共同保存。')
  }
  return (
    <Disclosure summary="核对并发布正式计划">
      <Field label="生效时间（北京时间，当前或未来）">
        <Input ref={effective} type="datetime-local" />
      </Field>
      <Field label="新计划或更新已有计划">
        <Select ref={target}>
          <option value="">建立新计划</option>
          <For each={uniquePlans()}>
            {plan => (
              <option value={plan.plan_id}>
                更新计划 · 第{plan.plan_version}版 · {dateText(plan.effective_from)}
              </option>
            )}
          </For>
        </Select>
      </Field>
      <Checkbox ref={yes} label="我已核对原资料与此修订；这不是医院或药师审核，医嘱变更需先咨询专业人员。" />
      <Button variant="primary" onAction={confirm}>
        明确确认并发布
      </Button>
    </Disclosure>
  )
}

export function DraftPage(): JSX.Element {
  const [data, setData] = createSignal<DraftData | null>(null)
  const [editor, setEditor] = createSignal<Editor | null>(null)
  const nextRead = readGate()
  async function load(view: View): Promise<DraftData> {
    const check = nextRead()
    const drafts = await all(patientPath('/drafts'), draftSchema, view)
    const meds = scope('medication:read') ? await all(patientPath('/medications'), medicationSchema, view) : []
    const files = scope('files:read') ? await all(patientPath('/files'), sourceFileSchema, view) : []
    const plans = meds.length && scope('plan:read') ? await all(patientPath('/plans'), planSchema, view) : []
    check()
    const result = { drafts, meds, files, plans }
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
    const entries = copyValue(draft?.entries ?? [])
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
                  <Button variant="primary" onAction={() => navigate('medication', 'meds')}>
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
                  {value => <DraftEditor editor={value} meds={current().meds} files={current().files} saved={saved} />}
                </Show>
                <Subheading>草稿与核对进度</Subheading>
                <Show
                  when={current().drafts.length > 0}
                  fallback={
                    <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
                      还没有资料草稿。
                    </Text>
                  }
                >
                  <ul class="divide-y divide-zinc-950/5 dark:divide-white/5">
                    <For each={current().drafts}>
                      {draft => (
                        <li class="space-y-4 py-4 first:pt-0 last:pb-0">
                          <div class="flex flex-wrap items-center gap-2 text-sm/6 font-medium">
                            <Badge tone={statusTone(draft.status)}>{labelFor(draft.status)}</Badge> ·{' '}
                            {draft.entries.length} 个条目
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
                  </ul>
                </Show>
              </Show>
            </div>
          </Card>
        )}
      </Show>
    </Show>
  )
}
