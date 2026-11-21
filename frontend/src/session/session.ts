import type { DemoTask } from '../features/admin/demo-page'
import type { OnboardingStep } from '../features/onboarding/onboarding'
import type { Draft } from '../features/plan-drafts/drafts'
import type { Response } from '../features/questionnaire/answers'
import type { Store, StoreSetter } from 'solid-js'
import { createStore, flush } from 'solid-js'
import * as v from 'valibot'
import { api } from '../api/api'

export interface PatientAccess {
  patient: { patient_id: string; display_name: string; timezone: string }
  relationship: string
  effective_scopes: string[]
}

export interface SessionContext {
  account: { account_id: string; display_name: string; is_simulated: boolean }
  csrf_token: string
  current_patient_id: string | null
  patients: PatientAccess[]
}

const patientAccessSchema: v.GenericSchema<unknown, PatientAccess> = v.looseObject({
  patient: v.looseObject({ patient_id: v.string(), display_name: v.string(), timezone: v.string() }),
  relationship: v.string(),
  effective_scopes: v.array(v.string()),
})
const sessionContextSchema: v.GenericSchema<unknown, SessionContext> = v.looseObject({
  account: v.looseObject({ account_id: v.string(), display_name: v.string(), is_simulated: v.boolean() }),
  csrf_token: v.string(),
  current_patient_id: v.nullable(v.string()),
  patients: v.array(patientAccessSchema),
})

export type Page = 'home' | 'medication' | 'support' | 'rewards' | 'profile'
export interface View {
  readonly epoch: number
  readonly accountId: string | null
  readonly patientId: string | null
  readonly csrfToken: string | null
  readonly sessionOnly?: boolean
}

export interface SessionState {
  context: SessionContext | null
  patient: PatientAccess | null
  page: Page
  tab: string
  epoch: number
  switchingPatient: boolean
  response: Response | null
  draft: Draft | null
  demoTask: DemoTask | null
  onboarding: OnboardingStep | null
}

const sessionStore = createStore<SessionState>({
  context: null,
  patient: null,
  page: 'home',
  tab: 'overview',
  epoch: 0,
  switchingPatient: false,
  response: null,
  draft: null,
  demoTask: null,
  onboarding: null,
})
export const state: Store<SessionState> = sessionStore[0]
const setState: StoreSetter<SessionState> = sessionStore[1]

export class ViewChanged extends Error {}

export function captureView(): View {
  return Object.freeze({
    epoch: state.epoch,
    accountId: state.context?.account.account_id ?? null,
    patientId: state.patient?.patient.patient_id ?? null,
    csrfToken: state.context?.csrf_token ?? null,
  })
}

export function isCurrentView(view: View): boolean {
  const current = captureView()
  return (
    current.accountId === view.accountId &&
    current.csrfToken === view.csrfToken &&
    (view.sessionOnly === true || (current.epoch === view.epoch && current.patientId === view.patientId))
  )
}

export function requireCurrentView(view: View): void {
  if (!isCurrentView(view)) throw new ViewChanged()
}

export const scope = (code: string): boolean => !!state.patient?.effective_scopes.includes(code)
export const own = (): boolean => state.patient?.relationship === 'self'
export const isDemoAdmin = (): boolean => state.context?.account.account_id === 'demo-admin'
export const dataEnvironment = (): 'real' | 'demo' => (state.context?.account.is_simulated === false ? 'real' : 'demo')
function selected(): { context: SessionContext; patient: PatientAccess } {
  // a cleared selection means the view this caller captured is gone
  if (state.context === null || state.patient === null) throw new ViewChanged()
  return { context: state.context, patient: state.patient }
}
export function patientPath(suffix: string): string {
  return `/patients/${encodeURIComponent(selected().patient.patient.patient_id)}${suffix}`
}
export function referenceKey(type: string): string {
  const { context, patient } = selected()
  return `reference:${context.account.account_id}:${patient.patient.patient_id}:${type}`
}

export function updateSession(update: (draft: SessionState) => void): void {
  setState(update)
  flush()
}

export function resetSession(): void {
  updateSession(draft => {
    draft.epoch++
    draft.context = null
    draft.patient = null
    draft.response = null
    draft.draft = null
    draft.demoTask = null
    draft.onboarding = null
  })
}

export async function loadContext(view: View = captureView()): Promise<void> {
  const context = await api('/auth/me', sessionContextSchema, 'GET', null, view)
  requireCurrentView(view)
  updateSession(draft => {
    draft.context = context
    draft.patient = context.patients.find(item => item.patient.patient_id === context.current_patient_id) ?? null
  })
}
