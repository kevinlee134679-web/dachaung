import type { View } from '../../session/session'
import type { SourceFile } from './files'
import type { JSX } from '@solidjs/web'
import { For, Show } from 'solid-js'
import * as v from 'valibot'
import { api } from '../../api/api'
import { dateText } from '../../date/date'
import { notice } from '../../notice/notice'
import { requireCurrentView, scope } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Field, Input } from '../../ui/form'
import { EmptyState, List } from '../../ui/list'
import { Text } from '../../ui/typography'
import { uploadMedicalFile } from './upload'

export function FilePage(props: { files: SourceFile[]; reload: (view: View) => Promise<void> }): JSX.Element {
  let chooser!: HTMLInputElement

  async function upload(view: View): Promise<void> {
    const file = chooser.files?.[0]
    if (!file) throw new Error('请先选择文件。')
    await uploadMedicalFile(view, file)
    if (scope('files:read')) {
      await props.reload(view)
    }
    requireCurrentView(view)
    chooser.value = ''
    notice('原始资料已保存，尚未识别或确认计划。')
  }

  async function download(file: SourceFile, view: View): Promise<void> {
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
          <Show when={props.files}>
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
