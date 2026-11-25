import type { View } from '../../session/session'
import type { SourceFile } from '../plan-drafts/drafts'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api } from '../../api/api'
import { dateText } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import { captureView, isCurrentView, patientPath, requireCurrentView, scope, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Field, Input } from '../../ui/form'
import { EmptyState, List } from '../../ui/list'
import { Text } from '../../ui/typography'
import { uploadMedicalFile } from './upload'

const savedFileSchema = v.looseObject({
  file_id: v.string(),
  original_name: v.string(),
  size_bytes: v.number(),
  meta: v.looseObject({ created_at: v.string() }),
})
type SavedFile = v.InferOutput<typeof savedFileSchema>

export function FilePage(props: { onUploaded: (file: SourceFile) => void }): JSX.Element {
  let chooser!: HTMLInputElement
  const [files, setFiles] = createSignal<SavedFile[] | null>(null)

  async function load(view: View): Promise<void> {
    const result = await all(patientPath('/files'), savedFileSchema, view)
    requireCurrentView(view)
    setFiles(result)
  }

  async function upload(view: View): Promise<void> {
    const file = chooser.files?.[0]
    if (!file) throw new Error('请先选择文件。')
    const uploaded = await uploadMedicalFile(view, file)
    if (scope('files:read')) {
      props.onUploaded(uploaded)
      await load(view)
    }
    requireCurrentView(view)
    chooser.value = ''
    notice('原始资料已保存，尚未识别或确认计划。')
  }

  async function download(file: SavedFile, view: View): Promise<void> {
    const data = await api(
      `/files/${file.file_id}/content`,
      v.looseObject({ content_base64: v.string(), media_type: v.string() }),
      'GET',
      null,
      view,
    )
    const bytes = Uint8Array.from(atob(data.content_base64), character => character.charCodeAt(0))
    const url = URL.createObjectURL(new Blob([bytes], { type: data.media_type }))
    const link = document.createElement('a')
    link.href = url
    link.download = file.original_name
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 5000)
  }

  onSettled(() => {
    if (!scope('files:read')) return
    const view = captureView()
    void load(view).catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })

  return (
    <div class="space-y-6">
      <Show when={scope('files:write')}>
        <Card title="保存原始资料">
          <div class="space-y-4">
            <Text>支持PDF、PNG、JPEG，最多10MiB。保存不代表已识别医嘱或确认计划。</Text>
            <Field label="选择文件">
              <Input ref={chooser} type="file" accept=".pdf,.png,.jpg,.jpeg" aria-label="选择虚构病历文件" />
            </Field>
            <Button variant="primary" onAction={upload}>
              上传资料
            </Button>
          </div>
        </Card>
      </Show>
      <Show
        when={scope('files:read')}
        fallback={
          <Card>
            <p>当前未获原始病历读取权限。</p>
          </Card>
        }
      >
        <Card title="已保存资料">
          <Show when={files()}>
            {items => (
              <>
                <Show when={!items().length}>
                  <EmptyState>还没有上传资料。</EmptyState>
                </Show>
                <List>
                  <For each={items()}>
                    {file => (
                      <li class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <strong class="text-sm/6 font-medium">{file.original_name}</strong>
                          <Text>
                            {Math.ceil(file.size_bytes / 1024)} KB · {dateText(file.meta.created_at)} · 原文件已保存
                          </Text>
                        </div>
                        <Button onAction={download.bind(null, file)}>下载核对原件</Button>
                      </li>
                    )}
                  </For>
                </List>
              </>
            )}
          </Show>
        </Card>
      </Show>
    </div>
  )
}
