import { navigate } from '../../session/navigation'
import { own, referenceKey, scope, state } from '../../session/session'

export function canManageMedicationList(): boolean {
  return own() && ['medication:read', 'drafts:read', 'drafts:write', 'drafts:submit', 'plan:read'].every(scope)
}

export function openMedicationList(medicationId: string): void {
  sessionStorage.setItem(referenceKey('medication-list-medication'), medicationId)
  navigate('medication', 'medication-list')
}

export function openScheduleDay(day: string): void {
  sessionStorage.setItem(referenceKey('schedule-day'), day)
  navigate('medication')
}

const medicationViews = {
  'medication-list': { page: 'medication', tab: 'medication-list', allowed: canManageMedicationList },
  'medication-overview': { page: 'medication', tab: 'overview', allowed: () => scope('plan:read') },
  'medication-records': {
    page: 'medication',
    tab: 'records',
    allowed: () => scope('records:read') || scope('records:report'),
  },
  'profile-meds': { page: 'profile', tab: 'meds', allowed: () => scope('medication:read') },
  'case-files': {
    page: 'medication',
    tab: 'case-files',
    allowed: () => scope('files:read') || scope('files:write') || scope('drafts:read'),
  },
  knowledge: { page: 'knowledge', tab: 'overview', allowed: () => scope('knowledge:read') },
  adherence: {
    page: 'profile',
    tab: 'adherence',
    allowed: () => scope('profile:read') || scope('questionnaire:assist'),
  },
} as const

export function rememberMedicationPage(): void {
  if (!state.patient) return
  const key = referenceKey('medication-page')
  const current = Object.entries(medicationViews).find(
    ([, route]) => state.page === route.page && state.tab === route.tab && route.allowed(),
  )
  if (current) sessionStorage.setItem(key, current[0])
  else sessionStorage.removeItem(key)
}

export function restoreMedicationPage(): boolean {
  if (!state.patient) return false
  const key = sessionStorage.getItem(referenceKey('medication-page'))
  const previous = Object.entries(medicationViews).find(([name]) => name === key)?.[1]
  if (!previous?.allowed()) return false
  navigate(previous.page, previous.tab)
  return true
}
