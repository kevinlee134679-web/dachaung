import type { View } from '../../session/session'
import * as v from 'valibot'
import { api, ApiError, sha } from '../../api/api'
import { captureView, patientPath, referenceKey, requireCurrentView } from '../../session/session'

type SharedCategory = 'support_question' | 'medication_plan' | 'medication_records' | 'profile_summary'

export const sharedCategoryLabels: Record<string, string> & Record<SharedCategory, string> = {
  support_question: '支持问题',
  medication_plan: '正式用药安排',
  medication_records: '服药记录',
  profile_summary: '画像摘要',
}
export const servicePurposes: Record<string, string> = {
  community_assistance: '社区协助',
  emotional_companionship: '情感陪伴',
  pharmacist_consultation: '药学咨询',
  peer_support: '模拟同辈入组',
}

export interface SupportResource {
  resource_id: string
  resource_version: string
  name: string
  description: string
  service_kind: string
  peer_group_id: string | null
  provider: { display_name: string; qualification_status: string }
  required_shared_categories: string[]
  optional_shared_categories: SharedCategory[]
}

export interface ServiceDraft {
  service_draft_id: string
  patient_id: string
  resource_id: string
  resource_version: string
  request_text: string
  draft_revision: number
  status: string
  confirmation_ref_id: string | null
  sharing_scope_ref_id: string | null
  service_id: string | null
  peer_group_id: string | null
  meta: { revision: number }
}

export interface ServiceConsent {
  confirmation_ref_id: string
  status: string
  resource_version: string
  confirmed_at: string
  valid_until: string
  sharing_scope: { sharing_scope_ref_id: string; recipient_id: string; purpose_code: string; data_categories: string[] }
}

export const supportResourceSchema: v.GenericSchema<unknown, SupportResource> = v.looseObject({
  resource_id: v.string(),
  resource_version: v.string(),
  name: v.string(),
  description: v.string(),
  service_kind: v.string(),
  peer_group_id: v.nullable(v.string()),
  provider: v.looseObject({ display_name: v.string(), qualification_status: v.string() }),
  required_shared_categories: v.array(v.string()),
  optional_shared_categories: v.array(
    v.picklist(['support_question', 'medication_plan', 'medication_records', 'profile_summary']),
  ),
})

export const serviceDraftSchema: v.GenericSchema<unknown, ServiceDraft> = v.looseObject({
  service_draft_id: v.string(),
  patient_id: v.string(),
  resource_id: v.string(),
  resource_version: v.string(),
  request_text: v.string(),
  draft_revision: v.number(),
  status: v.string(),
  confirmation_ref_id: v.nullable(v.string()),
  sharing_scope_ref_id: v.nullable(v.string()),
  service_id: v.nullable(v.string()),
  peer_group_id: v.nullable(v.string()),
  meta: v.looseObject({ revision: v.number() }),
})

export const serviceConsentSchema: v.GenericSchema<unknown, ServiceConsent> = v.looseObject({
  confirmation_ref_id: v.string(),
  status: v.string(),
  resource_version: v.string(),
  confirmed_at: v.string(),
  valid_until: v.string(),
  sharing_scope: v.looseObject({
    sharing_scope_ref_id: v.string(),
    recipient_id: v.string(),
    purpose_code: v.string(),
    data_categories: v.array(v.string()),
  }),
})

export interface ServiceWriteReceipt {
  hash: string
  contentHash: string | null
  selectionHash: string | null
  revision: number | null
  draftId: string | null
}

export function serviceWriteKey(path: string, method: string): string {
  const { accountId, patientId } = captureView()
  return `reference:${accountId}:${patientId ?? 'console'}:service-write:${method}:${path}`
}

export function pendingServiceWrite(path: string, method: string): ServiceWriteReceipt | null {
  return v.parse(
    v.nullable(
      v.looseObject({
        hash: v.string(),
        contentHash: v.nullable(v.string()),
        selectionHash: v.nullable(v.string()),
        revision: v.nullable(v.number()),
        draftId: v.nullable(v.string()),
      }),
    ),
    JSON.parse(localStorage.getItem(serviceWriteKey(path, method)) ?? 'null'),
  )
}

export async function serviceWrite<T>(
  path: string,
  method: string,
  body: Record<string, unknown>,
  schema: v.GenericSchema<unknown, T>,
  view: View,
): Promise<T> {
  const hash = await sha(JSON.stringify(body))
  const contentHash = body['content'] != null ? await sha(JSON.stringify(body['content'])) : null
  const selectionHash = body['shared_categories'] != null ? await sha(JSON.stringify(body['shared_categories'])) : null
  requireCurrentView(view)
  const key = serviceWriteKey(path, method)
  const pending = pendingServiceWrite(path, method)
  if (pending && pending.hash !== hash)
    throw new Error('上一次提交结果尚未核实。请用原值重试，或报出原草稿或确认编号核查。')
  localStorage.setItem(
    key,
    JSON.stringify({
      hash,
      contentHash,
      selectionHash,
      revision: body['expected_revision'] ?? body['draft_revision'] ?? null,
      draftId: body['service_draft_id'] ?? null,
    }),
  )
  try {
    const result = await api(path, schema, method, body, view)
    localStorage.removeItem(key)
    return result
  } catch (error) {
    if (
      error instanceof ApiError &&
      error.status < 500 &&
      !error.pendingRecovery &&
      error.code !== 'OPERATION_IN_PROGRESS'
    ) {
      localStorage.removeItem(key)
    }
    throw error
  }
}

export function rememberServiceConsent(identifier: string): void {
  const key = referenceKey('service-consent-history')
  const refs = (localStorage.getItem(key) ?? '').split(',').filter(Boolean)
  if (!refs.includes(identifier)) localStorage.setItem(key, [identifier, ...refs].join(','))
}

export function clearSubmission(draft: ServiceDraft): void {
  const path = patientPath('/services')
  const pending = pendingServiceWrite(path, 'POST')
  if (pending?.draftId === draft.service_draft_id && pending.revision === draft.draft_revision)
    localStorage.removeItem(serviceWriteKey(path, 'POST'))
}
