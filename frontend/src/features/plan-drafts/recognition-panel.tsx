import type { View } from '../../session/session'
import type { SourceFile } from '../medical-files/files'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { api } from '../../api/api'
import { actionError } from '../../notice/notice'
import { captureView, isCurrentView, scope, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Disclosure } from '../../ui/disclosure'
import { Checkbox, Field, Input, Select } from '../../ui/form'
import { Text } from '../../ui/typography'
import { listMedicalFiles } from '../medical-files/files'
import { uploadMedicalFile } from '../medical-files/upload'

// PDF 上传最多 240 秒，识别对话最多 60 秒，另留 10 秒传输余量
const RECOGNITION_TIMEOUT_MS = 310_000

export interface RecognizedMedication {
  name: string
  dose_value: string | null
  dose_unit: string | null
  daily_count: number | null
  times: string[]
  duration_days: number | null
  source_text: string | null
}
const medicationSchema: v.GenericSchema<unknown, RecognizedMedication> = v.object({
  name: v.string(),
  dose_value: v.nullable(v.string()),
  dose_unit: v.nullable(v.string()),
  daily_count: v.nullable(v.number()),
  times: v.array(v.string()),
  duration_days: v.nullable(v.number()),
  source_text: v.nullable(v.string()),
})
const recognitionSchema = v.object({
  status: v.picklist(['unavailable', 'failed', 'no_candidates', 'ready']),
  medications: v.array(medicationSchema),
  allergies: v.nullable(v.string()),
  diagnosis: v.nullable(v.string()),
})

export function RecognitionPanel(props: { onApply: (meds: RecognizedMedication[]) => void }): JSX.Element {
  const [files, setFiles] = createSignal<SourceFile[]>([])
  const [selectedFile, setSelectedFile] = createSignal('')
  const [result, setResult] = createSignal<v.InferOutput<typeof recognitionSchema> | null>(null)
  const [selected, setSelected] = createSignal<number[]>([])
  let chooser!: HTMLInputElement
  async function reload(view: View): Promise<void> {
    setFiles(await listMedicalFiles(view))
  }
  async function upload(view: View): Promise<void> {
    const file = chooser.files?.[0]
    if (!file) throw new Error('请先选择文件。')
    const saved = await uploadMedicalFile(view, file)
    await reload(view)
    setSelectedFile(saved.file_id)
    chooser.value = ''
  }
  async function recognize(view: View): Promise<void> {
    const data = await api(
      `/files/${encodeURIComponent(selectedFile())}/medication-recognition`,
      recognitionSchema,
      'GET',
      null,
      view,
      RECOGNITION_TIMEOUT_MS,
    )
    setResult(data)
    setSelected(data.medications.map((_, index) => index))
  }
  onSettled(() => {
    const view = captureView()
    void reload(view).catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })
  return (
    <Disclosure summary="AI 病历识别">
      <div class="space-y-4">
        <Field label="选择病历">
          <Select
            value={selectedFile()}
            onChange={event => {
              setSelectedFile(event.currentTarget.value)
            }}
          >
            <option value="">请选择资料</option>
            <For each={files()}>{file => <option value={file.file_id}>{file.original_name}</option>}</For>
          </Select>
        </Field>
        <Show when={scope('files:write')}>
          <Field label="上传病历">
            <Input ref={chooser} type="file" accept=".pdf,.png,.jpg,.jpeg" />
          </Field>
          <Button onAction={upload}>上传资料</Button>
        </Show>
        <Button disabled={!selectedFile()} onAction={recognize}>
          AI 识别
        </Button>
        <Show when={result()}>
          {value => (
            <div class="space-y-3">
              <Show when={value().status === 'unavailable'}>
                <Text>AI 识别未配置</Text>
              </Show>
              <Show when={value().status === 'failed'}>
                <Text>识别失败，请稍后重试或手动填写</Text>
              </Show>
              <Show when={value().status === 'no_candidates'}>
                <Text>没有识别到用药信息</Text>
              </Show>
              <Show when={value().status === 'ready'}>
                <For each={value().medications}>
                  {(med, index) => (
                    <Checkbox
                      label={`${med.name} ${med.dose_value ?? ''}${med.dose_unit ?? ''} · 每日 ${med.daily_count ?? '未知'} 次 · 疗程 ${med.duration_days ?? '未知'} 天`}
                      checked={selected().includes(index())}
                      onChange={event => {
                        setSelected(current =>
                          event.currentTarget.checked
                            ? [...current, index()]
                            : current.filter(item => item !== index()),
                        )
                      }}
                    />
                  )}
                </For>
                <Text>过敏史：{value().allergies ?? '未识别'}</Text>
                <Text>诊断：{value().diagnosis ?? '未识别'}</Text>
                <Button
                  disabled={!selected().length}
                  onAction={() => props.onApply(value().medications.filter((_, index) => selected().includes(index)))}
                >
                  填入清单
                </Button>
                <Text>未写明服药时刻的，已按每日次数填入默认时间，请按医嘱核对</Text>
              </Show>
            </div>
          )}
        </Show>
      </div>
    </Disclosure>
  )
}
