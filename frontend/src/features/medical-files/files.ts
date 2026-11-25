import type { View } from '../../session/session'
import * as v from 'valibot'
import { all } from '../../api/api'
import { patientPath } from '../../session/session'

export interface SourceFile {
  file_id: string
  original_name: string
  media_type: string
  size_bytes: number
  meta: { created_at: string }
}

const sourceFileSchema: v.GenericSchema<unknown, SourceFile> = v.looseObject({
  file_id: v.string(),
  original_name: v.string(),
  media_type: v.string(),
  size_bytes: v.number(),
  meta: v.looseObject({ created_at: v.string() }),
})

export function listMedicalFiles(view: View): Promise<SourceFile[]> {
  return all(patientPath('/files'), sourceFileSchema, view)
}
