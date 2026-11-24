import type { View } from '../../session/session'
import type { Response } from '../questionnaire/answers'
import type { JSX } from '@solidjs/web'
import { generateProfile } from '../questionnaire/profile'
import { QuestionnairePage } from '../questionnaire/questionnaire-page'
import { resolveOnboarding } from './onboarding'

export function QuestionnaireStep(): JSX.Element {
  async function submitted(response: Response, view: View): Promise<void> {
    await generateProfile(response.response_id, view)
    await resolveOnboarding(view)
  }
  return <QuestionnairePage onSubmitted={submitted} />
}
