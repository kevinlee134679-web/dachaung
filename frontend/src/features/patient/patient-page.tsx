import type { JSX } from '@solidjs/web'
import { createSignal, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { api } from '../../api/api'
import { actionError, notice } from '../../notice/notice'
import {
  captureView,
  isCurrentView,
  loadContext,
  patientPath,
  requireCurrentView,
  scope,
  ViewChanged,
} from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Field, Input } from '../../ui/form'
import { Text } from '../../ui/typography'

const patientSchema = v.looseObject({
  display_name: v.string(),
  timezone: v.string(),
  meta: v.looseObject({ revision: v.number() }),
})
type Patient = v.InferOutput<typeof patientSchema>

export function PatientPage(): JSX.Element {
  const [patient, setPatient] = createSignal<Patient | null>(null)
  let name!: HTMLInputElement
  let timezone!: HTMLInputElement
  onSettled(() => {
    if (!scope('patient:read')) return
    const view = captureView()
    void api(patientPath(''), patientSchema, 'GET', null, view)
      .then(result => {
        requireCurrentView(view)
        setPatient(result)
      })
      .catch((error: unknown) => {
        if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
      })
  })
  return (
    <Show when={scope('patient:read')} fallback={<p>当前未获基础资料查看权限。</p>}>
      <Show when={patient()}>
        {value => (
          <Card>
            <div class="space-y-4">
              <Field label="显示名称">
                <Input ref={name} value={value().display_name} />
              </Field>
              <Field label="显示时区（IANA标识）">
                <Input ref={timezone} value={value().timezone} />
              </Field>
              <Text>显示时区只影响展示，不平移已经确认的计划。正式计划按北京时间核对。</Text>
              <Button
                variant="primary"
                disabled={!scope('patient:edit')}
                onAction={async view => {
                  await api(
                    patientPath(''),
                    v.unknown(),
                    'PATCH',
                    { expected_revision: value().meta.revision, display_name: name.value, timezone: timezone.value },
                    view,
                  )
                  await loadContext(view)
                  const result = await api(patientPath(''), patientSchema, 'GET', null, view)
                  requireCurrentView(view)
                  setPatient(result)
                  notice('基础资料已保存。')
                }}
              >
                保存基础资料
              </Button>
            </div>
          </Card>
        )}
      </Show>
    </Show>
  )
}
