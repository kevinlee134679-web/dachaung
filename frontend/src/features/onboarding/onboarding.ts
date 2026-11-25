import type { View } from '../../session/session'
import * as v from 'valibot'
import { all, ApiError, api } from '../../api/api'
import {
  captureView,
  isDemoAdmin,
  own,
  patientPath,
  referenceKey,
  requireCurrentView,
  scope,
  updateSession,
} from '../../session/session'

export type OnboardingStep = 'questionnaire' | 'medication'

export async function resolveOnboarding(view: View = captureView()): Promise<boolean> {
  let step: OnboardingStep | null = null
  if (own() && !isDemoAdmin()) {
    const skipped = (sessionStorage.getItem(referenceKey('onboarding-skipped')) ?? '').split(',')
    if (scope('profile:read') && !skipped.includes('questionnaire')) {
      try {
        await api(patientPath('/profiles/current'), v.unknown(), 'GET', null, view)
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 404 || error.code !== 'PROFILE_NOT_AVAILABLE') throw error
        step = 'questionnaire'
      }
    }
    if (step === null && scope('plan:read') && !skipped.includes('medication')) {
      const plans = await all(patientPath('/plans'), v.unknown(), view)
      if (plans.length === 0) step = 'medication'
    }
  }
  requireCurrentView(view)
  updateSession(draft => {
    draft.onboarding = step
  })
  return step !== null
}

export async function skipOnboarding(step: OnboardingStep): Promise<void> {
  const key = referenceKey('onboarding-skipped')
  const skipped = (sessionStorage.getItem(key) ?? '').split(',').filter(Boolean)
  sessionStorage.setItem(key, [...skipped, step].join(','))
  await resolveOnboarding()
}
