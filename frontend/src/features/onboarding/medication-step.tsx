import type { JSX } from '@solidjs/web'
import { Text } from '../../ui/typography'
import { MedicationListForm } from '../plan-drafts/medication-list-form'
import { resolveOnboarding } from './onboarding'

export function MedicationStep(): JSX.Element {
  return (
    <div class="space-y-4">
      <Text>填写现在使用的药品，方便查看每日安排。</Text>
      <MedicationListForm
        onConfirmed={async view => {
          await resolveOnboarding(view)
        }}
      />
      <Text>病历资料可以稍后在用药管理中保存。</Text>
    </div>
  )
}
