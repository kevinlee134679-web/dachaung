import type { RangeReader } from '../../ui/range-controls'
import type { JSX } from '@solidjs/web'
import { createSignal, For, Show } from 'solid-js'
import * as v from 'valibot'
import { api } from '../../api/api'
import { requireCurrentView } from '../../session/session'
import { Button, Card, Field, Input, Text } from '../../ui/components'
import { IssueList } from '../../ui/data-display'
import { labelFor } from '../../ui/labels'
import { RangeControls } from '../../ui/range-controls'
import { issueSchema } from '../profile/statistics'
import { pointLabels, pointRulesSchema, pointsRange } from './points-page'

const reconciliationSchema = v.looseObject({
  new_entries: v.array(v.looseObject({ rule_code: v.string(), delta: v.number() })),
  account: v.looseObject({ balance: v.number() }),
  skipped_keys: v.array(v.string()),
  source_issues: v.array(issueSchema),
})
type Reconciliation = v.InferOutput<typeof reconciliationSchema>

export function PointsConsole(): JSX.Element {
  let patient!: HTMLInputElement
  let range!: RangeReader
  const [result, setResult] = createSignal<Reconciliation>()
  return (
    <Card title="演示积分核验">
      <div class="space-y-4">
        <Text>选择患者和核验时段。系统仅按已启用规则核验实际来源。</Text>
        <Field label="核奖患者编号">
          <Input ref={patient} />
        </Field>
        <RangeControls
          ref={value => {
            range = value
          }}
        />
        <Button
          variant="primary"
          onAction={async view => {
            const id = patient.value.trim()
            if (!id) throw new Error('请填写要核验的虚构患者编号。')
            const window = pointsRange(range)
            const { rules_version } = await api('/points/rules', pointRulesSchema, 'GET', null, view)
            requireCurrentView(view)
            const value = await api(
              '/internal/points/reconcile',
              reconciliationSchema,
              'POST',
              { patient_id: id, ...window, rules_version },
              view,
            )
            requireCurrentView(view)
            setResult(value)
          }}
        >
          核验并登记正向积分
        </Button>
        <div aria-live="polite">
          <Show when={result()}>
            {value => (
              <>
                <p>
                  新增奖励 {value().new_entries.length} 笔 · 当前余额 {value().account.balance}
                </p>
                <Text>已核验过的业务 {value().skipped_keys.length} 项</Text>
                <Show when={value().new_entries.length}>
                  <ul>
                    <For each={value().new_entries}>
                      {entry => (
                        <li>
                          {pointLabels[entry.rule_code]} +{entry.delta}
                        </li>
                      )}
                    </For>
                  </ul>
                </Show>
                <Show when={value().source_issues.length}>
                  <IssueList issues={value().source_issues} />
                </Show>
              </>
            )}
          </Show>
        </div>
      </div>
    </Card>
  )
}

export function RewardDemoControls(): JSX.Element {
  let task!: HTMLInputElement
  const [result, setResult] = createSignal('')
  return (
    <Card title="兑换模拟履约">
      <div class="space-y-4">
        <Field label="兑换履约任务编号">
          <Input ref={task} />
        </Field>
        <Button
          onAction={async view => {
            const path = `/tasks/${encodeURIComponent(task.value.trim())}`
            const current = await api(
              path,
              v.looseObject({ kind: v.string(), meta: v.looseObject({ revision: v.number() }) }),
              'GET',
              null,
              view,
            )
            requireCurrentView(view)
            if (current.kind !== 'fulfill_reward') throw new Error('此处只执行已登记的兑换履约任务。')
            const execution = await api(
              `${path}/run`,
              v.looseObject({ execution_status: v.string() }),
              'POST',
              { expected_revision: current.meta.revision },
              view,
            )
            requireCurrentView(view)
            setResult(`原任务执行状态 ${labelFor(execution.execution_status)}。交付事实请在原订单中核对。`)
          }}
        >
          显式运行兑换履约任务
        </Button>
        <p>{result()}</p>
      </div>
    </Card>
  )
}
