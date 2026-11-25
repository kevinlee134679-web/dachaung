import type { View } from '../../session/session'
import * as v from 'valibot'
import { api, ApiError, sha } from '../../api/api'
import { captureView, referenceKey, requireCurrentView } from '../../session/session'

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

interface ServiceWriteReceipt {
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

function pendingServiceWrite(path: string, method: string): ServiceWriteReceipt | null {
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
