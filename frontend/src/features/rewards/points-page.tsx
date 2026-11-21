import type { PointRules } from './points'
import type { JSX } from '@solidjs/web'
import { createSignal, onSettled, Show } from 'solid-js'
import { api } from '../../api/api'
import { actionError } from '../../notice/notice'
import { captureView, isCurrentView, requireCurrentView, ViewChanged } from '../../session/session'
import { pointRulesSchema } from './points'
import { PointsContent } from './points-content'

export function PointsPage(): JSX.Element {
  const [rules, setRules] = createSignal<PointRules>()
  onSettled(() => {
    const view = captureView()
    void api('/points/rules', pointRulesSchema, 'GET', null, view)
      .then(value => {
        requireCurrentView(view)
        setRules(value)
      })
      .catch((error: unknown) => {
        if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
      })
  })
  return <Show when={rules()}>{value => <PointsContent rules={value()} view={captureView()} />}</Show>
}
