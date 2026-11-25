import { updateSession } from '../src/session/session'

export interface SuccessResponse {
  ok: boolean
  status: number
  json: () => Promise<{ request_id: string; status: string; data: unknown; error: null }>
}

export function success(data: unknown): SuccessResponse {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ request_id: 'test', status: 'success', data, error: null }),
  }
}

export function failure(
  status: number,
  code: string,
  message: string,
): {
  ok: boolean
  status: number
  json: () => Promise<{ request_id: string; status: string; data: null; error: { code: string; message: string } }>
} {
  return {
    ok: false,
    status,
    json: () => Promise.resolve({ request_id: 'test', status: 'error', data: null, error: { code, message } }),
  }
}

export function pageOf(items: unknown[]): { items: unknown[]; next_cursor: null } {
  return { items, next_cursor: null }
}

export function choose({
  patient = 'pa',
  account = 'account-a',
  relationship = 'self',
  scopes = [],
}: { patient?: string; account?: string; relationship?: string; scopes?: string[] } = {}): void {
  const access = {
    patient: { patient_id: patient, display_name: patient, timezone: 'Asia/Shanghai' },
    relationship,
    effective_scopes: scopes,
  }
  updateSession(draft => {
    draft.context = {
      account: { account_id: account, display_name: account, is_simulated: true },
      csrf_token: `csrf-${account}`,
      current_patient_id: patient,
      patients: [access],
    }
    draft.patient = access
  })
}
