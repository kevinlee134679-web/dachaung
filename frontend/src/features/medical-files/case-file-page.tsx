import type { SourceFile } from '../plan-drafts/drafts'
import type { JSX } from '@solidjs/web'
import { createSignal, Show } from 'solid-js'
import { scope, state } from '../../session/session'
import { Disclosure } from '../../ui/disclosure'
import { DraftPage } from '../plan-drafts/draft-page'
import { FilePage } from './file-page'

export function CaseFilePage(): JSX.Element {
  const [uploads, setUploads] = createSignal<SourceFile[]>([])
  const filesAllowed = () => scope('files:read') || scope('files:write')
  return (
    <div class="space-y-4">
      <Show when={filesAllowed()}>
        <Disclosure summary="上传与查看原件" lazy open={state.tab !== 'drafts'}>
          <FilePage
            onUploaded={file => {
              setUploads(current => [...current.filter(item => item.file_id !== file.file_id), file])
            }}
          />
        </Disclosure>
      </Show>
      <Show when={scope('drafts:read')}>
        <Disclosure summary="用药资料核对" lazy open={state.tab === 'drafts' || !filesAllowed()}>
          <DraftPage uploadedFiles={uploads()} />
        </Disclosure>
      </Show>
    </div>
  )
}
