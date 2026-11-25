import type { View } from '../../session/session'
import type { SourceFile } from './drafts'
import type { JSX } from '@solidjs/web'
import { createSignal, For, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api } from '../../api/api'
import { patientPath, requireCurrentView, scope } from '../../session/session'
import { Button } from '../../ui/button'
import { Disclosure } from '../../ui/disclosure'
import { Field, Input, Select } from '../../ui/form'
import { Text } from '../../ui/typography'
import { uploadMedicalFile } from '../medical-files/upload'
import { sourceFileSchema } from './drafts'

export interface PreviewCandidate {
  name: string
  dose_value: string | null
  dose_unit: string | null
  frequency_text: string | null
  schedule_kind: 'daily' | null
  times: string[]
  page: number
  source_excerpt: string
}

const candidateSchema: v.GenericSchema<unknown, PreviewCandidate> = v.object({
  name: v.string(),
  dose_value: v.nullable(v.string()),
  dose_unit: v.nullable(v.string()),
  frequency_text: v.nullable(v.string()),
  schedule_kind: v.nullable(v.literal('daily')),
  times: v.array(v.string()),
  page: v.number(),
  source_excerpt: v.string(),
})
const previewSchema = v.object({
  status: v.picklist(['ready', 'unsupported', 'unreadable', 'no_candidates', 'no_text']),
  candidates: v.array(candidateSchema),
  partial: v.boolean(),
})
const messages = {
  ready: '逐项核对原件，再将候选条目填入清单。',
  unsupported: '可复制文字的 PDF 支持预填。图片请对照原件手动录入。',
  unreadable: '无法读出此 PDF。请查看原件后手动录入。',
  no_candidates: 'PDF 中没有找到可识别的用药字段。请查看原件后手动录入。',
  no_text: 'PDF 没有可读取的文字层。请查看原件后手动录入。',
}

export function MedicalPreview(props: { apply: (candidate: PreviewCandidate, file: SourceFile) => void }): JSX.Element {
  const [files, setFiles] = createSignal<SourceFile[] | null>(null)
  const [result, setResult] = createSignal<{ file: SourceFile; preview: v.InferOutput<typeof previewSchema> } | null>(
    null,
  )
  const [applied, setApplied] = createSignal<Set<PreviewCandidate>>(new Set())
  const [saved, setSaved] = createSignal('')
  let chooser!: HTMLInputElement
  let existing!: HTMLSelectElement

  async function load(view: View): Promise<void> {
    const data = await all(patientPath('/files'), sourceFileSchema, view)
    setFiles(data.filter(file => file.media_type === 'application/pdf'))
  }

  async function preview(file: SourceFile, view: View): Promise<void> {
    setResult(null)
    setApplied(new Set<PreviewCandidate>())
    const response = await api(
      `/files/${encodeURIComponent(file.file_id)}/medication-preview`,
      previewSchema,
      'GET',
      null,
      view,
    )
    setResult({ file, preview: response })
  }

  async function upload(view: View): Promise<void> {
    const file = chooser.files?.[0]
    if (file?.type !== 'application/pdf') throw new Error('请选择一份可复制文字的 PDF。')
    const uploaded = await uploadMedicalFile(view, file)
    requireCurrentView(view)
    chooser.value = ''
    setSaved(`原件已保存 · ${uploaded.original_name}`)
    setFiles(current => [uploaded, ...(current ?? []).filter(item => item.file_id !== uploaded.file_id)])
    await preview(uploaded, view)
  }

  return (
    <Disclosure summary="从病历或处方 PDF 预填">
      <Text>从文字 PDF 提取标明的药名、每次剂量、频次和时刻。请使用虚构演示资料。</Text>
      <Show when={scope('files:write')}>
        <Field label="病历或处方 PDF">
          <Input ref={chooser} type="file" accept="application/pdf,.pdf" />
        </Field>
        <Button onAction={upload}>上传并提取候选</Button>
      </Show>
      <Show when={!files()}>
        <Button onAction={load}>查找已上传的 PDF</Button>
      </Show>
      <Show when={files()}>
        {available => (
          <div class="space-y-2">
            <Field label="已上传的 PDF">
              <Select ref={existing}>
                <option value="">请选择</option>
                <For each={available()}>{file => <option value={file.file_id}>{file.original_name}</option>}</For>
              </Select>
            </Field>
            <Button
              onAction={async view => {
                const file = available().find(item => item.file_id === existing.value)
                if (!file) throw new Error('请先选择原件。')
                await preview(file, view)
              }}
            >
              提取所选 PDF 的候选
            </Button>
          </div>
        )}
      </Show>
      <Show when={saved()}>
        <div role="status">
          <Text>{saved()}</Text>
        </div>
      </Show>
      <Show when={result()} keyed>
        {value => (
          <div class="space-y-3" aria-live="polite">
            <Text>
              {value.file.original_name} · {messages[value.preview.status]}
            </Text>
            <Show when={value.preview.partial}>
              <Text>仅提取了本文件的一部分，请核对完整原件。</Text>
            </Show>
            <For each={value.preview.candidates}>
              {candidate => (
                <div class="space-y-2 rounded-lg border border-zinc-200 p-3 dark:border-white/10">
                  <Text>
                    第 {candidate.page} 页 · {candidate.name}
                  </Text>
                  <pre class="font-sans text-sm whitespace-pre-wrap">{candidate.source_excerpt}</pre>
                  <Show when={!candidate.times.length}>
                    <Text>具体时刻待核对，请在清单中选择。</Text>
                  </Show>
                  <Button
                    disabled={applied().has(candidate)}
                    onAction={() => {
                      props.apply(candidate, value.file)
                      setApplied(current => new Set([...current, candidate]))
                    }}
                  >
                    {applied().has(candidate) ? '已填入清单' : `核对后填入 ${candidate.name}`}
                  </Button>
                </div>
              )}
            </For>
          </div>
        )}
      </Show>
    </Disclosure>
  )
}
