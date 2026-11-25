import type { View } from '../../session/session'
import type { SourceFile } from './files'
import type { JSX } from '@solidjs/web'
import { createSignal, onSettled, Show } from 'solid-js'
import { actionError } from '../../notice/notice'
import { captureView, isCurrentView, scope, ViewChanged } from '../../session/session'
import { Disclosure } from '../../ui/disclosure'
import { DraftPage } from '../plan-drafts/draft-page'
import { FilePage } from './file-page'
import { listMedicalFiles } from './files'

export function CaseFilePage(): JSX.Element {
  const [files, setFiles] = createSignal<SourceFile[]>([])
  async function reload(view: View): Promise<void> {
    setFiles(await listMedicalFiles(view))
  }
  onSettled(() => {
    if (!scope('files:read')) return
    const view = captureView()
    void reload(view).catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })
  const filesAllowed = () => scope('files:read') || scope('files:write')
  return (
    <div class="space-y-4">
      <Show when={filesAllowed()}>
        <Disclosure summary="上传与查看原件" lazy open>
          <FilePage files={files()} reload={reload} />
        </Disclosure>
      </Show>
      <Show when={scope('drafts:read')}>
        <Disclosure summary="用药资料核对" lazy open={!filesAllowed()}>
          <DraftPage files={files()} reload={reload} />
        </Disclosure>
      </Show>
    </div>
  )
}
