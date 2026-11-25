import { navigate } from '../../session/navigation'
import { own, referenceKey, scope, state } from '../../session/session'

export function rememberServicePage(): void {
  if (!state.patient) return
  const key = referenceKey('service-page')
  if (state.page === 'support' && state.tab === 'peer' && scope('peer:read')) sessionStorage.setItem(key, 'peer')
  else if (state.page === 'profile' && state.tab === 'service-consents' && own())
    sessionStorage.setItem(key, 'consents')
  else if (state.page === 'profile' && state.tab === 'formal-services' && scope('services:read'))
    sessionStorage.setItem(key, 'formal-services')
  else if (state.page === 'profile' && ['authorizations', 'family'].includes(state.tab))
    sessionStorage.setItem(key, 'authorizations')
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
    } else if (page === 'consents' && own()) {
      navigate('profile', 'service-consents')
    } else if (page === 'formal-services' && scope('services:read')) {
      navigate('profile', 'formal-services')
    } else if (page === 'authorizations') {
      navigate('profile', 'authorizations')
    } else {
      resolve(false)
      return
    }
    resolve(true)
  })
}
