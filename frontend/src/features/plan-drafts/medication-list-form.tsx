import type { View } from '../../session/session'
import type { Draft, Entry, Medication, Plan, SourceFile } from './drafts'
import type { PreviewCandidate } from './medical-preview'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import { all, ApiError, api } from '../../api/api'
import { dateText, localDateTime, today } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import {
  captureView,
  isCurrentView,
  patientPath,
  referenceKey,
  requireCurrentView,
  scope,
  ViewChanged,
} from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Text } from '../../ui/typography'
import { doseSlotSchema } from '../dose-events/events'
import { draftSchema, medicationSchema, newEntry, planSchema, planVersionSchema } from './drafts'
import { EntryEditor } from './entry-editor'
import { MedicalPreview } from './medical-preview'
import { canManageMedicationList, openScheduleDay } from './navigation'
import { checkedSchedule } from './schedule-fields'

interface Row {
  entry: Entry
  suggestedName?: string
}

interface DraftBody {
  source_file_ids: string[]
  entries: Entry[]
}

interface PublishRequest {
  draft_id: string
  draft_revision: number
  existing_plan_id: string | null
  expected_plan_version: number | null
  effective_from: string
  confirmed: true
}

const stages = {
  save: '保存草稿',
  submit: '提交草稿',
  publish: '确认正式计划',
}
type Stage = keyof typeof stages

function manualRow(medicationId = ''): Row {
  return { entry: { ...newEntry(medicationId), start_date: today() } }
}

function draftPath(id: string): string {
  return `/drafts/${encodeURIComponent(id)}`
}

function versionPath(plan: Pick<Plan, 'plan_id' | 'plan_version'>): string {
  return `/plans/${encodeURIComponent(plan.plan_id)}/versions/${plan.plan_version}`
}

function planContent(body: DraftBody): string {
  return JSON.stringify({
    source_file_ids: body.source_file_ids,
    entries: body.entries.map(entry => ({ ...entry, draft_entry_id: undefined })),
  })
}

export function MedicationListForm(props: { onConfirmed?: (view: View) => Promise<void> }): JSX.Element {
  const [rows, setRows] = createSignal<Row[]>([manualRow()])
  const [medications, setMedications] = createSignal<Medication[]>([])
  const [loaded, setLoaded] = createSignal(false)
  const [plan, setPlan] = createSignal<Plan | null>(null)
  const [draft, setDraft] = createSignal<Draft | null>(null)
  const [busy, setBusy] = createSignal(false)
  const [status, setStatus] = createSignal('')
  const [publication, setPublication] = createSignal<{ plan: Plan; first: string | null; verified: boolean }>()
  const [sourceFiles, setSourceFiles] = createSignal<string[]>([])
  const [publishing, setPublishing] = createSignal<PublishRequest | null>(null)
  const locked = () => draft()?.status === 'pending_confirmation' || busy()
  let savedContent = ''
  let publishedContent: string | null = null
  let creating: DraftBody | null = null
  let submitting: { expected_revision: number; content_revision: number } | null = null
  let stage: Stage = 'save'

  function bodyKey(): string {
    return referenceKey('medication-list-draft')
  }

  function remember(value: Draft): void {
    setDraft(value)
    sessionStorage.setItem(bodyKey(), `draft:${value.draft_id}`)
    creating = null
  }

  function restore(value: Draft): void {
    remember(value)
    setRows(value.entries.map(entry => ({ entry: structuredClone(entry) })))
    setSourceFiles(value.source_file_ids)
    savedContent = JSON.stringify({ source_file_ids: value.source_file_ids, entries: value.entries })
  }

  function readDraft(id: string, view: View): Promise<Draft> {
    return api(draftPath(id), draftSchema, 'GET', null, view)
  }

  async function latestPlan(view: View, planId?: string): Promise<Plan | null> {
    const plans = await all(patientPath('/plans'), planSchema, view)
    return (
      plans
        .filter(item => planId === undefined || item.plan_id === planId)
        .sort((a, b) => b.effective_from.localeCompare(a.effective_from) || b.plan_version - a.plan_version)[0] ?? null
    )
  }

  async function showPublication(value: Plan, view: View): Promise<string | null> {
    setPlan(value)
    setPublication({ plan: value, first: null, verified: false })
    setStatus('')
    const day = localDateTime(value.effective_from).slice(0, 10)
    const end = new Date(Date.parse(`${day}T00:00:00+08:00`) + 31 * 86400000).toISOString()
    try {
      const query = new URLSearchParams({ window_start: new Date(value.effective_from).toISOString(), window_end: end })
      const slots = await all(`${patientPath('/dose-slots')}?${query.toString()}`, doseSlotSchema, view)
      const first =
        slots.find(
          slot =>
            slot.plan_id === value.plan_id && slot.plan_version === value.plan_version && slot.status === 'active',
        )?.scheduled_at ?? null
      setPublication({ plan: value, first, verified: true })
      return first
    } catch (error) {
      if (error instanceof ViewChanged) throw error
      return null
    }
  }

  async function recoverDraft(view: View, reference: string): Promise<Draft | null> {
    if (reference.startsWith('draft:')) {
      try {
        return await readDraft(reference.slice('draft:'.length), view)
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 404) throw error
        sessionStorage.removeItem(bodyKey())
      }
    }
    if (reference.startsWith('entry:')) {
      const drafts = await all(patientPath('/drafts'), draftSchema, view)
      const entryId = reference.slice('entry:'.length)
      return drafts.find(item => item.entries.some(entry => entry.draft_entry_id === entryId)) ?? null
    }
    return null
  }

  async function load(view: View): Promise<void> {
    const meds = await all(patientPath('/medications'), medicationSchema, view)
    const latest = await latestPlan(view)
    const reference = sessionStorage.getItem(bodyKey()) ?? ''
    const previousDraft = reference ? await recoverDraft(view, reference) : null
    setMedications(meds)
    setPlan(latest)
    if (previousDraft && previousDraft.status !== 'confirmed') {
      restore(previousDraft)
      setStatus(
        previousDraft.status === 'pending_confirmation' ? '草稿已提交，等待本人确认。' : '已恢复上次保存的草稿。',
      )
    } else if (latest) {
      const version = await api(versionPath(latest), planVersionSchema, 'GET', null, view)
      const original = await readDraft(version.source_draft_id, view)
      const restored = version.entries.map(entry => ({ entry: { ...entry, draft_entry_id: crypto.randomUUID() } }))
      setRows(restored)
      setSourceFiles(original.source_file_ids)
      publishedContent = planContent({
        source_file_ids: original.source_file_ids,
        entries: restored.map(row => row.entry),
      })
      if (previousDraft?.status === 'confirmed' && previousDraft.formal_plan) {
        const published = await api(versionPath(previousDraft.formal_plan), planVersionSchema, 'GET', null, view)
        await showPublication(published, view)
        setPlan(latest)
      }
    }
    const medicationHint = referenceKey('medication-list-medication')
    const requested = sessionStorage.getItem(medicationHint)
    sessionStorage.removeItem(medicationHint)
    if (requested !== null && meds.some(item => item.medication_id === requested)) {
      if (locked()) {
        setStatus('请先处理已提交的草稿，再添加所选药品。')
      } else if (!rows().some(row => row.entry.medication_id === requested)) {
        setRows(current =>
          current.length === 1 && current[0]?.entry.medication_id === '' && !previousDraft && !latest
            ? [manualRow(requested)]
            : [...current, manualRow(requested)],
        )
      }
    }
    if (reference.startsWith('entry:') && !previousDraft)
      setStatus('上次创建草稿的结果尚未查到。请先在病例资料中核对用药草稿，再创建新草稿。')
    requireCurrentView(view)
    setLoaded(true)
  }

  async function addMedication(view: View, name: string, notes: string | null): Promise<Medication> {
    const matches = medications().filter(item => item.name === name)
    if (matches.length === 1 && matches[0]) return matches[0]
    if (matches.length > 1) throw new Error('已有多条同名药品，请从药品列表中选择。')
    const saved = await api(patientPath('/medications'), medicationSchema, 'POST', { name, notes }, view)
    setMedications(current => [...current, saved])
    setStatus(`药品资料已保存 · ${saved.name}`)
    return saved
  }

  function applyPreview(candidate: PreviewCandidate, file: SourceFile): void {
    const matches = medications().filter(item => item.name === candidate.name)
    const entry: Entry = {
      ...newEntry(matches.length === 1 ? (matches[0]?.medication_id ?? '') : ''),
      dose_value: candidate.dose_value,
      dose_unit: candidate.dose_unit,
      schedule: candidate.schedule_kind
        ? { kind: candidate.schedule_kind, weekdays: [], times: candidate.times }
        : null,
      source_file_ids: [file.file_id],
    }
    const row: Row = { entry, suggestedName: candidate.name }
    setRows(current => {
      const first = current[0]?.entry
      return current.length === 1 &&
        first?.medication_id === '' &&
        first.dose_value === null &&
        first.dose_unit === null &&
        !first.schedule &&
        first.start_date === today() &&
        first.end_date === null &&
        first.meal_requirement === null &&
        first.medical_notes === null &&
        first.strict_timing === null &&
        first.min_interval_minutes === null &&
        !first.source_file_ids.length
        ? [row]
        : [...current, row]
    })
    setStatus('候选条目已填入清单，请核对药品并补齐日期和服药时间。')
  }

  function prepare(complete: boolean) {
    const entries = rows().map(({ entry }, index) => {
      const heading = `药品条目 ${index + 1}`
      if (!medications().some(item => item.medication_id === entry.medication_id))
        throw new Error(`${heading}：请选择已有药品，或先保存新药品资料。`)
      const draftEntry = { ...entry, schedule: checkedSchedule(entry.schedule, complete) }
      if (entry.dose_value !== null && (!/^\d+(?:\.\d+)?$/.test(entry.dose_value) || Number(entry.dose_value) <= 0))
        throw new Error(`${heading}：请填写大于零的数值剂量。`)
      if (entry.start_date !== null && entry.end_date !== null && entry.end_date < entry.start_date)
        throw new Error(`${heading}：结束日期早于开始日期。`)
      if (
        complete &&
        (entry.dose_value === null || entry.dose_unit === null || entry.start_date === null || !draftEntry.schedule)
      ) {
        throw new Error(`${heading}：请补齐每次剂量、单位、开始日期和服药时间。`)
      }
      return draftEntry
    })
    return {
      source_file_ids: [...new Set([...sourceFiles(), ...entries.flatMap(entry => entry.source_file_ids)])],
      entries,
    }
  }

  async function saveEditable(view: View, complete: boolean): Promise<Draft> {
    const body = prepare(complete)
    const snapshot = JSON.stringify(body)
    let previous = draft()
    const reference = sessionStorage.getItem(bodyKey()) ?? ''
    if (!previous && reference.startsWith('entry:')) {
      const recovered = await recoverDraft(view, reference)
      if (recovered) {
        const attempted = creating !== null
        const same =
          JSON.stringify(recovered.entries.map(entry => entry.draft_entry_id)) ===
          JSON.stringify(body.entries.map(entry => entry.draft_entry_id))
        restore(recovered)
        if (!same || !attempted) throw new Error('已找回上次保存的草稿。请核对草稿，再继续操作。')
        previous = recovered
      } else if (!creating || JSON.stringify(creating) !== snapshot) {
        throw new Error('上次创建结果尚未核实。请在病例资料中查看原草稿。')
      }
    }
    if (previous?.status === 'pending_confirmation' || previous?.status === 'confirmed') return previous
    if (previous?.status === 'editing' && savedContent === snapshot) return previous
    if (!previous && !creating) {
      const first = body.entries[0]
      if (!first) throw new Error('请添加至少一种药品。')
      creating = body
      sessionStorage.setItem(bodyKey(), `entry:${first.draft_entry_id}`)
    }
    try {
      const value = await api(
        previous ? draftPath(previous.draft_id) : patientPath('/drafts'),
        draftSchema,
        previous ? 'PUT' : 'POST',
        previous ? { ...body, expected_revision: previous.meta.revision } : body,
        view,
      )
      remember(value)
      savedContent = snapshot
      return value
    } catch (error) {
      if (
        error instanceof ApiError &&
        error.status < 500 &&
        !['OPERATION_IN_PROGRESS', 'IDEMPOTENCY_EXPIRED'].includes(error.code ?? '')
      ) {
        if (!previous) {
          sessionStorage.removeItem(bodyKey())
          creating = null
        } else if (error.status === 409) {
          setStatus('草稿已在其他页面更新。请先核对服务器修订，再决定是否重填。')
        }
      }
      throw error
    }
  }

  async function publish(view: View): Promise<void> {
    let value = draft()
    const currentPlan = plan()
    if (!value && currentPlan && publishedContent === planContent(prepare(true))) {
      await showPublication(currentPlan, view)
      setStatus('内容与已确认计划一致，沿用原安排。')
      return
    }
    if (value && (value.status === 'pending_confirmation' || submitting || publishing())) {
      stage = 'submit'
      value = await readDraft(value.draft_id, view)
      remember(value)
    }
    if (value?.status !== 'pending_confirmation' && value?.status !== 'confirmed') {
      stage = 'save'
      value = await saveEditable(view, true)
    }
    if (value.status === 'editing') {
      stage = 'submit'
      submitting = { expected_revision: value.meta.revision, content_revision: value.content_revision }
      value = await api(`${draftPath(value.draft_id)}/submit`, draftSchema, 'POST', submitting, view)
      remember(value)
      submitting = null
    }
    stage = 'publish'
    let confirmed: Plan
    if (value.status === 'confirmed' && value.formal_plan) {
      confirmed = await api(versionPath(value.formal_plan), planVersionSchema, 'GET', null, view)
    } else {
      if (value.status !== 'pending_confirmation') throw new Error('请先核对并提交当前草稿。')
      const previous = plan()
      const request: PublishRequest = publishing() ?? {
        draft_id: value.draft_id,
        draft_revision: value.content_revision,
        existing_plan_id: previous?.plan_id ?? null,
        expected_plan_version: previous?.plan_version ?? null,
        effective_from: new Date(
          Math.max(Date.now() + 60_000, previous ? Date.parse(previous.effective_from) + 1000 : 0),
        ).toISOString(),
        confirmed: true,
      }
      setPublishing(request)
      try {
        confirmed = await api(patientPath('/plan-confirmations'), planSchema, 'POST', request, view)
      } catch (error) {
        if (
          error instanceof ApiError &&
          error.status < 500 &&
          !['OPERATION_IN_PROGRESS', 'IDEMPOTENCY_EXPIRED'].includes(error.code ?? '')
        ) {
          setPublishing(null)
          const current = await readDraft(value.draft_id, view)
          remember(current)
          if (error.code === 'PLAN_VERSION_CONFLICT' && previous) setPlan(await latestPlan(view, previous.plan_id))
          if (current.status === 'returned') restore(current)
        }
        throw error
      }
    }
    const first = await showPublication(confirmed, view)
    publishedContent = planContent({ source_file_ids: value.source_file_ids, entries: value.entries })
    setSourceFiles(value.source_file_ids)
    setPublishing(null)
    submitting = null
    setDraft(null)
    savedContent = ''
    setRows(value.entries.map(entry => ({ entry: { ...entry, draft_entry_id: crypto.randomUUID() } })))
    notice('正式计划已确认。')
    if (props.onConfirmed) {
      await props.onConfirmed(view)
      if (isCurrentView(view) && first !== null) openScheduleDay(localDateTime(first).slice(0, 10))
    }
  }

  async function act(view: View, complete: boolean): Promise<void> {
    if (busy()) return
    setBusy(true)
    setStatus('')
    stage = 'save'
    try {
      if (complete) {
        await publish(view)
      } else {
        const saved = await saveEditable(view, false)
        setStatus(`草稿已保存 · 内容修订 ${saved.content_revision}。确认后才生成安排。`)
      }
    } catch (error) {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) {
        const detail = error instanceof Error ? error.message : '请核对原操作结果。'
        setStatus(`${stages[stage]}：${detail}`)
      }
      throw error
    } finally {
      setBusy(false)
    }
  }

  function copyPending(): void {
    sessionStorage.removeItem(bodyKey())
    setDraft(null)
    setPublishing(null)
    submitting = null
    setRows(current => current.map(row => ({ ...row, entry: { ...row.entry, draft_entry_id: crypto.randomUUID() } })))
    setStatus('已复制为新的编辑草稿，原提交保留在病例资料。')
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
        <Card title="用药清单">
          <div class="space-y-5">
            <Show when={publication()}>
              {result => (
                <div class="space-y-2 rounded-lg bg-teal-50 p-4 text-sm/6 dark:bg-teal-950/30" role="status">
                  <p>
                    正式计划第 {result().plan.plan_version} 版已确认 · {dateText(result().plan.effective_from)} 生效
                  </p>
                  <Show
                    when={result().first}
                    fallback={
                      <p>
                        {result().verified
                          ? '计划的首个排程窗口内没有可显示的时段。'
                          : '首个时段暂未核实，可在今日安排中查看。'}
                      </p>
                    }
                  >
                    {first => (
                      <>
                        <p>首个安排 · {dateText(first())}</p>
                        <Show when={localDateTime(first()).slice(0, 10) !== today()}>
                          <p>这份计划的首个时段不在今天。</p>
                        </Show>
                        <Button onAction={() => openScheduleDay(localDateTime(first()).slice(0, 10))}>
                          查看首个安排
                        </Button>
                      </>
                    )}
                  </Show>
                </div>
              )}
            </Show>
            <Show when={draft()?.status === 'pending_confirmation'}>
              <Text>已提交的草稿等待本人确认。若需修改内容，可复制为新草稿。</Text>
            </Show>
            <fieldset disabled={locked()} class="space-y-5 disabled:opacity-75" aria-label="编辑用药条目">
              <Show when={scope('files:read') && !locked()}>
                <MedicalPreview apply={applyPreview} />
              </Show>
              <For each={rows()}>
                {(row, index) => (
                  <EntryEditor
                    entry={row.entry}
                    index={index()}
                    meds={medications()}
                    suggestedName={row.suggestedName}
                    addMedication={scope('medication:edit') ? addMedication : undefined}
                    removable={rows().length > 1}
                    remove={() => {
                      setRows(current => current.filter(item => item !== row))
                    }}
                  />
                )}
              </For>
              <Button onAction={() => setRows(current => [...current, manualRow()])}>添加一种药</Button>
            </fieldset>
            <Show when={status()}>
              <div role="status">
                <Text>{status()}</Text>
              </div>
            </Show>
            <Show when={plan() && !publication()}>
              <Text>确认后将更新已加载的正式计划第 {plan()?.plan_version} 版。</Text>
            </Show>
            <div class="flex flex-wrap gap-3">
              <Show when={draft()?.status !== 'pending_confirmation'}>
                <Button disabled={busy()} onAction={view => act(view, false)}>
                  保存草稿
                </Button>
              </Show>
              <Show when={draft()?.status === 'pending_confirmation' && !publishing()}>
                <Button disabled={busy()} onAction={copyPending}>
                  复制为新草稿
                </Button>
              </Show>
              <Button variant="primary" disabled={busy()} onAction={view => act(view, true)}>
                确认并生成安排
              </Button>
            </div>
          </div>
        </Card>
      </Show>
    </Show>
  )
}
