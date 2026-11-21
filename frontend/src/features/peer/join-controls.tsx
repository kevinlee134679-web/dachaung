import type { View } from '../../session/session'
import type { PeerJoinDraft } from './peer'
import type { JSX } from '@solidjs/web'
import * as v from 'valibot'
import { api, ApiError } from '../../api/api'
import { notice } from '../../notice/notice'
import { requireCurrentView, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Checkbox } from '../../ui/form'
import { serviceWrite } from '../services/draft-data'
import { openPeer, peerPath } from './peer'

const peerJoinResultSchema = v.looseObject({ group_id: v.string() })

export function PeerJoinControls(props: {
  draft: PeerJoinDraft
  textArea: HTMLTextAreaElement
  view: View
}): JSX.Element {
  let confirmed!: HTMLInputElement
  async function join(): Promise<void> {
    const draft = props.draft
    const view = props.view
    if (!confirmed.checked || props.textArea.value.trim() !== draft.request_text)
      throw new Error('请先核对已保存草稿并明确自愿加入。')
    const path = `${peerPath(draft.peer_group_id)}/memberships`
    const body = {
      service_draft_id: draft.service_draft_id,
      draft_revision: draft.draft_revision,
      confirmation_ref_id: draft.confirmation_ref_id,
      sharing_scope_ref_id: draft.sharing_scope_ref_id,
    }
    let member: { group_id: string }
    try {
      member = await serviceWrite(path, 'POST', body, peerJoinResultSchema, view)
    } catch (caught) {
      if (
        caught instanceof ViewChanged ||
        (caught instanceof ApiError && caught.status < 500 && caught.code !== 'OPERATION_IN_PROGRESS')
      ) {
        throw caught
      }
      const current = await api(
        `/service-drafts/${encodeURIComponent(draft.service_draft_id)}`,
        v.looseObject({ service_id: v.nullable(v.string()), draft_revision: v.number() }),
        'GET',
        null,
        view,
      )
      requireCurrentView(view)
      if (current.service_id === null || current.service_id === '' || current.draft_revision !== draft.draft_revision)
        throw caught
      member = await serviceWrite(path, 'POST', body, peerJoinResultSchema, view)
    }
    requireCurrentView(view)
    openPeer(member.group_id)
    notice('已登记模拟入组申请。')
  }
  return (
    <div class="space-y-4">
      <Checkbox ref={confirmed} label="我本人自愿申请加入此模拟小组" />
      <Button view={props.view} variant="primary" onAction={join}>
        提交入组申请
      </Button>
    </div>
  )
}
