import type { JSX } from '@solidjs/web'
import { QuestionnairePage } from '../questionnaire/questionnaire-page'
import { resolveOnboarding } from './onboarding'

export function QuestionnaireStep(): JSX.Element {
  return <QuestionnairePage onSubmitted={view => void resolveOnboarding(view)} />
}
