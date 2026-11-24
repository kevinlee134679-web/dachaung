import type { View } from '../../session/session'
import * as v from 'valibot'
import { api } from '../../api/api'
import { patientPath } from '../../session/session'

export async function generateProfile(responseId: string, view: View): Promise<void> {
  await api(patientPath('/profiles'), v.unknown(), 'POST', { response_id: responseId }, view)
}
