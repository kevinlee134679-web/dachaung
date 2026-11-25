import type { View } from '../../session/session'
import * as v from 'valibot'
import { api, sha } from '../../api/api'
import { patientPath, referenceKey, requireCurrentView } from '../../session/session'

const uploadSchema = v.looseObject({ file_id: v.string(), original_name: v.string(), media_type: v.string() })

export async function uploadMedicalFile(
  view: View,
  file: File,
): Promise<{ file_id: string; original_name: string; media_type: string }> {
  if (!file.size || file.size > 10 * 1024 * 1024) throw new Error('请选择大于 0、最多 10 MiB 的资料。')
  const hash = await sha(await file.arrayBuffer())
  requireCurrentView(view)
  const ref = `upload:${referenceKey(`file:${hash}:${file.name}`)}`
  let source = localStorage.getItem(ref)
  if (source === null || source === '') {
    source = crypto.randomUUID()
    localStorage.setItem(ref, source)
  }
  const form = new FormData()
  form.append('file', file)
  form.append('source_event_id', source)
  const saved = await api(patientPath('/files'), uploadSchema, 'POST', form, view)
  localStorage.removeItem(ref)
  return saved
}
