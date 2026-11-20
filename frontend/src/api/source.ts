import type { View } from '../session/session'
import type * as v from 'valibot'
import { requireCurrentView } from '../session/session'
import { api, sha } from './api'

export async function submitSource<T>(
  path: string,
  kind: string,
  body: object,
  schema: v.GenericSchema<unknown, T>,
  view: View,
): Promise<T> {
  const hash = await sha(JSON.stringify(body))
  requireCurrentView(view)
  const reference = `source:${view.accountId}:${view.patientId}:${kind}:${hash}`
  let source = localStorage.getItem(reference)
  if (source === null || source === '') {
    source = crypto.randomUUID()
    localStorage.setItem(reference, source)
  }
  const result = await api(path, schema, 'POST', { source_event_id: source, ...body }, view)
  requireCurrentView(view)
  return result
}
