import { navigate } from '../../session/navigation'
import { own, referenceKey, scope, state } from '../../session/session'

export function openServiceRecord(id: string): void {
  sessionStorage.setItem(referenceKey('formal-service'), id)
  navigate('profile', 'formal-services')
}

export function rememberServicePage(): void {
  if (!state.patient) return
  const key = referenceKey('service-page')
  if (state.page === 'support' && state.tab === 'peer' && scope('peer:read')) sessionStorage.setItem(key, 'peer')
  else if (state.page === 'support' && state.tab === 'social' && scope('services:prepare') && scope('support:read'))
    sessionStorage.setItem(key, 'drafts')
  else if (state.page === 'profile' && state.tab === 'service-consents' && own())
    sessionStorage.setItem(key, 'consents')
  else if (state.page === 'profile' && state.tab === 'formal-services' && scope('services:read'))
    sessionStorage.setItem(key, 'formal-services')
  else if (state.page === 'profile' && ['authorizations', 'family'].includes(state.tab))
    sessionStorage.setItem(key, 'authorizations')
  else if (state.page === 'rewards') sessionStorage.setItem(key, 'rewards')
  else sessionStorage.removeItem(key)
}

export function restoreServicePage(): Promise<boolean> {
  return new Promise(resolve => {
    if (!state.patient) {
      resolve(false)
      return
    }
    const page = sessionStorage.getItem(referenceKey('service-page'))
    if (page === 'peer' && scope('peer:read')) {
      navigate('support', 'peer')
    } else if (page === 'drafts' && scope('services:prepare') && scope('support:read')) {
      navigate('support', 'social')
    } else if (page === 'consents' && own()) {
      navigate('profile', 'service-consents')
    } else if (page === 'formal-services' && scope('services:read')) {
      navigate('profile', 'formal-services')
    } else if (page === 'authorizations') {
      navigate('profile', 'authorizations')
    } else if (page === 'rewards') {
      navigate('rewards')
    } else {
      resolve(false)
      return
    }
    resolve(true)
  })
}
