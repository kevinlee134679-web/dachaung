import type { JSX } from '@solidjs/web'
import { Show } from 'solid-js'
import { own, scope } from '../../session/session'
import { Disclosure } from '../../ui/disclosure'
import { FamilyPage } from '../family/family-page'
import { ServiceConsentPage } from './consent-page'
import { ServiceRecordsPage } from './records-page'

export function AuthorizationsPage(): JSX.Element {
  return (
    <div class="space-y-4">
      <Disclosure summary="家庭授权" lazy open>
        <FamilyPage />
      </Disclosure>
      <Show when={own()}>
        <Disclosure summary="服务授权" lazy>
          <ServiceConsentPage />
        </Disclosure>
      </Show>
      <Show when={scope('services:read')}>
        <Disclosure summary="服务记录" lazy>
          <ServiceRecordsPage />
        </Disclosure>
      </Show>
    </div>
  )
}
