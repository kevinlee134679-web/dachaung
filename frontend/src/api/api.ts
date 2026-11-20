import type { View } from '../session/session'
import * as v from 'valibot'
import { notice } from '../notice/notice'
import { captureView, requireCurrentView, resetSession, state } from '../session/session'

const envelopeSchema = v.looseObject({
  request_id: v.string(),
  status: v.picklist(['success', 'error']),
  data: v.nonOptional(v.unknown()),
  error: v.nullable(v.looseObject({ code: v.string(), message: v.string() })),
})
const errorEnvelopeSchema = v.looseObject({
  error: v.optional(v.nullable(v.looseObject({ code: v.string(), message: v.string() }))),
})

export interface PendingRecovery {
  readonly key: string
  readonly operation: string
}
export class ApiError extends Error {
  status: number
  code: string | undefined
  pendingRecovery: PendingRecovery | undefined

  constructor(message: string, status: number, code?: string, pendingRecovery?: PendingRecovery) {
    super(message)
    this.status = status
    this.code = code
    this.pendingRecovery = pendingRecovery
  }
}

class ApiContractError extends Error {
  path: string
  issues: v.BaseIssue<unknown>[]

  constructor(path: string, issues: v.BaseIssue<unknown>[]) {
    super('服务返回的数据与前端约定不一致，结果请以原资源为准。')
    this.path = path
    this.issues = issues
  }
}

export async function sha(text: string | ArrayBuffer): Promise<string> {
  const raw = typeof text === 'string' ? new TextEncoder().encode(text) : text
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', raw))]
    .map(value => value.toString(16).padStart(2, '0'))
    .join('')
}

export async function api<T>(
  path: string,
  schema: v.GenericSchema<unknown, T>,
  method = 'GET',
  body: unknown = null,
  view: View = captureView(),
): Promise<T> {
  requireCurrentView(view)
  const headers: Record<string, string> = {}
  const options: RequestInit = { method, headers, credentials: 'same-origin', cache: 'no-store' }
  let pending: string | null = null
  let operation: string | null = null
  if (method !== 'GET') {
    let semantic: string
    if (body instanceof FormData) {
      options.body = body
      const file = body.get('file')
      if (!(file instanceof File)) throw new TypeError('Missing file')
      const source = body.get('source_event_id')
      semantic =
        (typeof source === 'string' || source === null ? String(source) : Object.prototype.toString.call(source)) +
        file.name +
        (await sha(await file.arrayBuffer()))
    } else {
      headers['Content-Type'] = 'application/json'
      semantic = JSON.stringify(body ?? {})
      options.body = semantic
    }
    const bodyHash = await sha(semantic)
    requireCurrentView(view)
    pending = `pending:${view.accountId ?? 'anonymous'}:${method}:${path}:${bodyHash}`
    operation = localStorage.getItem(pending)
    if (operation === null || operation === '') {
      operation = crypto.randomUUID()
      localStorage.setItem(pending, operation)
    }
    headers['Idempotency-Key'] = operation
    if (view.csrfToken !== null && view.csrfToken !== '') headers['X-CSRF-Token'] = view.csrfToken
  }
  requireCurrentView(view)
  const controller = new AbortController()
  options.signal = controller.signal
  const timer = setTimeout(() => controller.abort(), 15000)
  try {
    const response = await fetch(`/api/v1${path}`, options)
    const json: unknown = await response.json()
    const envelope = v.safeParse(envelopeSchema, json)
    requireCurrentView(view)
    if (!envelope.success && response.ok) throw new ApiContractError(path, envelope.issues)
    if (!response.ok || !envelope.success || envelope.output.status !== 'success') {
      const errorEnvelope = envelope.success ? undefined : v.safeParse(errorEnvelopeSchema, json)
      const failure = envelope.success
        ? envelope.output.error
        : errorEnvelope?.success
          ? errorEnvelope.output.error
          : undefined
      const expired = ['IDEMPOTENCY_EXPIRED', 'SENSITIVE_RECEIPT_EXPIRED'].includes(failure?.code ?? '')
      if (pending !== null && response.status < 500 && failure?.code !== 'OPERATION_IN_PROGRESS' && !expired)
        localStorage.removeItem(pending)
      if (response.status === 401 && state.context) {
        resetSession()
        notice('当前会话已失效，请重新进入演示。', true)
      }
      const error = new ApiError(
        expired
          ? '原操作回执已过期。请先核对原资源；已确认结果后，选择“已核对原结果，准备新操作”。'
          : (failure?.message ?? '操作未完成，请重新检查。'),
        response.status,
        failure?.code,
        expired && pending !== null && operation !== null ? Object.freeze({ key: pending, operation }) : undefined,
      )
      throw error
    }
    if (pending !== null) localStorage.removeItem(pending)
    const data = v.safeParse(schema, envelope.output.data)
    if (!data.success) throw new ApiContractError(path, data.issues)
    return data.output
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError')
      throw new Error('等待超时，结果尚未核实。请先刷新原资源；重试会沿用同一操作键。')
    throw error
  } finally {
    clearTimeout(timer)
  }
}

export async function all<T>(
  path: string,
  item: v.GenericSchema<unknown, T>,
  view: View = captureView(),
): Promise<T[]> {
  const items: T[] = []
  const pageSchema = v.looseObject({ items: v.array(item), next_cursor: v.nullable(v.string()) })
  let cursor: string | null = null
  do {
    const data: { items: T[]; next_cursor: string | null } = await api(
      `${path}${path.includes('?') ? '&' : '?'}limit=100${cursor !== null && cursor !== '' ? `&cursor=${encodeURIComponent(cursor)}` : ''}`,
      pageSchema,
      'GET',
      null,
      view,
    )
    items.push(...data.items)
    cursor = data.next_cursor
  } while (cursor !== null && cursor !== '')
  return items
}
