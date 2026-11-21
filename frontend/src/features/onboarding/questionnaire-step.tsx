import type { View } from '../../session/session'
import type { Response } from '../questionnaire/answers'
import type { JSX } from '@solidjs/web'
import * as v from 'valibot'
import { api } from '../../api/api'
import { patientPath } from '../../session/session'
import { QuestionnairePage } from '../questionnaire/questionnaire-page'
import { resolveOnboarding } from './onboarding'

export function QuestionnaireStep(): JSX.Element {
  async function submitted(response: Response, view: View): Promise<void> {
    await api(patientPath('/profiles'), v.unknown(), 'POST', { response_id: response.response_id }, view)
    await resolveOnboarding(view)
  }
  return <QuestionnairePage onSubmitted={submitted} />
}
