import type { View } from '../../session/session'
import type { ServiceDraft } from './draft-data'
import type { JSX } from '@solidjs/web'
import * as v from 'valibot'
import { api, ApiError } from '../../api/api'
import { notice } from '../../notice/notice'
import { patientPath, requireCurrentView, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Checkbox } from '../../ui/form'
import { clearSubmission, serviceDraftSchema, serviceWrite } from './draft-data'
import { openServiceRecord } from './navigation'

export function Submission(props: {
  draft: ServiceDraft
  textArea: HTMLTextAreaElement
  view: View
  open: (id: string, text?: string) => Promise<void>
}): JSX.Element {
  let explicit!: HTMLInputElement
  return (
    <div>
      <Checkbox ref={explicit} label="我明确按本草稿申请模拟服务" />
      <Button
        variant="primary"
        onAction={async () => {
          if (!explicit.checked) throw new Error('请先明确确认提交正式服务。')
          if (props.textArea.value.trim() !== props.draft.request_text)
            throw new Error('请先保存修改并重新确认本次内容。')
          try {
            const value = await serviceWrite(
              patientPath('/services'),
              'POST',
              {
                service_draft_id: props.draft.service_draft_id,
                draft_revision: props.draft.draft_revision,
                confirmation_ref_id: props.draft.confirmation_ref_id,
                sharing_scope_ref_id: props.draft.sharing_scope_ref_id,
              },
              v.looseObject({ service_id: v.string() }),
              props.view,
            )
            requireCurrentView(props.view)
            openServiceRecord(value.service_id)
            notice('已登记正式服务。')
          } catch (error) {
            if (error instanceof ViewChanged) throw error
            let result: ServiceDraft
            try {
              result = await api(
                `/service-drafts/${encodeURIComponent(props.draft.service_draft_id)}`,
                serviceDraftSchema,
                'GET',
                null,
                props.view,
              )
            } catch (lookup) {
              if (
                lookup instanceof ViewChanged ||
                (lookup instanceof ApiError && (lookup.status === 403 || lookup.status === 404))
              ) {
                throw lookup
              }
              throw error
            }
            requireCurrentView(props.view)
            if (result.service_id !== null && result.service_id !== '') {
              clearSubmission(result)
              openServiceRecord(result.service_id)
              notice('从原草稿核实了已提交的服务。')
            } else {
              if (error instanceof ApiError && error.code === 'SERVICE_CONFIRMATION_REQUIRED')
                await props.open(props.draft.service_draft_id, props.textArea.value)
              throw error
            }
          }
        }}
      >
        提交正式服务
      </Button>
    </div>
  )
}
