import type { OnboardingStep } from './onboarding'
import type { JSX } from '@solidjs/web'
import { Notice } from '../../notice/notice-view'
import { Brand } from '../../ui/brand'
import { Button } from '../../ui/button'
import { Text } from '../../ui/typography'
import { MedicationStep } from './medication-step'
import { skipOnboarding } from './onboarding'
import { QuestionnaireStep } from './questionnaire-step'

export function OnboardingLayout(props: { step: OnboardingStep }): JSX.Element {
  return (
    <div class="grid min-h-dvh place-items-center p-6">
      <div class="w-full max-w-3xl space-y-6">
        <Notice />
        <Brand />
        <div class="flex items-center justify-between gap-3">
          <Text>{props.step === 'questionnaire' ? '第 1 步，共 2 步 · 填写问卷' : '第 2 步，共 2 步 · 用药清单'}</Text>
          <Button variant="plain" onAction={() => skipOnboarding(props.step)}>
            稍后再说
          </Button>
        </div>
        {props.step === 'questionnaire' ? <QuestionnaireStep /> : <MedicationStep />}
      </div>
    </div>
  )
}
