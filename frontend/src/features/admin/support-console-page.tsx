import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api } from '../../api/api'
import { inputDateTime, localDateTime } from '../../date/date'
import { actionError } from '../../notice/notice'
import { captureView, isCurrentView, isDemoAdmin, requireCurrentView, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { confirm } from '../../ui/confirm'
import { Field, Input, Select, Textarea } from '../../ui/form'
import { Text } from '../../ui/typography'
import { PeerModerationControls } from '../peer/moderation'
import { PointsConsole, RewardDemoControls } from '../rewards/reward-controls'
import { ServiceDemoControls } from '../services/demo-controls'

interface Case {
  case_id: string
  title: string
  template_version: string
}
interface Config {
  llm_mode: string
  version_refs: { kind: string; version: string }[]
}
const caseSchema = v.looseObject({ case_id: v.string(), title: v.string(), template_version: v.string() })
const configSchema = v.looseObject({
  llm_mode: v.string(),
  version_refs: v.array(v.looseObject({ kind: v.string(), version: v.string() })),
})

export function SupportConsolePage(): JSX.Element {
  const [catalog, setCatalog] = createSignal<Case[]>([])
  const [config, setConfig] = createSignal<Config | null>(null)
  const [output, setOutput] = createSignal('')
  const [opening, setOpening] = createSignal<string | null>(null)
  let chooser!: HTMLSelectElement
  let scenario!: HTMLSelectElement
  let sessionId!: HTMLInputElement
  let runId!: HTMLInputElement
  let time!: HTMLInputElement
  onSettled(() => {
    if (!isDemoAdmin()) return
    const view = captureView()
    void Promise.all([all('/cases', caseSchema, view), api('/config/status', configSchema, 'GET', null, view)])
      .then(([cases, status]) => {
        requireCurrentView(view)
        setCatalog(cases)
        setConfig(status)
      })
      .catch((error: unknown) => {
        if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
      })
  })
  const display = (text: string) => {
    setOpening(null)
    setOutput(text)
  }
  async function checkModel(view: View, config: Config): Promise<void> {
    const result = await api(
      '/config/check-model',
      v.looseObject({ network_attempt_count: v.number() }),
      'POST',
      {
        profile_id: 'mock-single-pass',
        expected_config_version: config.version_refs.find(ref => ref.kind === 'model_config')?.version,
        allow_external_call: false,
      },
      view,
    )
    requireCurrentView(view)
    display(`探测完成 · 网络尝试 ${result.network_attempt_count} 次`)
  }
  async function readOpening(view: View): Promise<void> {
    const data = await api(
      `/cases/${encodeURIComponent(chooser.value)}`,
      v.looseObject({ opening_draft: v.string() }),
      'GET',
      null,
      view,
    )
    requireCurrentView(view)
    setOutput('')
    setOpening(data.opening_draft)
  }
  async function trigger(view: View): Promise<void> {
    const data = await api(
      '/demo/triggers',
      v.looseObject({ related_ids: v.array(v.string()) }),
      'POST',
      {
        case_id: chooser.value,
        session_id: sessionId.value || null,
        scenario: scenario.value,
        scenario_run_id: runId.value,
        occurred_at: inputDateTime(time.value),
      },
      view,
    )
    requireCurrentView(view)
    display(data.related_ids.length ? `已保存关联 ${data.related_ids.join('、')}` : '已登记场景。')
  }
  async function resetCase(view: View): Promise<void> {
    const selected = catalog().find(entry => entry.case_id === chooser.value)
    if (!selected || !(await confirm(`确认清理「${selected.title}」的虚构对话记录？`))) return
    requireCurrentView(view)
    const result = await api(
      `/cases/${encodeURIComponent(selected.case_id)}/reset`,
      v.looseObject({ affected_session_ids: v.array(v.string()) }),
      'POST',
      { case_template_version: selected.template_version, confirmed: true },
      view,
    )
    requireCurrentView(view)
    display(`已重置 ${result.affected_session_ids.length} 个会话。`)
  }
  return (
    <Show when={isDemoAdmin() && config()}>
      {current => (
        <>
          <Card title="情感支持演示控制台">
            <div class="space-y-4">
              <Text>{current().llm_mode}</Text>
              <Button onAction={view => checkModel(view, current())}>显式检查模拟模型</Button>
              <Field label="虚构案例">
                <Select ref={chooser}>
                  <For each={catalog()}>{entry => <option value={entry.case_id}>{entry.title}</option>}</For>
                </Select>
              </Field>
              <Button onAction={readOpening}>读取案例开场草稿</Button>
              <Field label="模拟场景">
                <Select ref={scenario}>
                  <option value="state_event">状态邀请</option>
                  <option value="periodic_node">周期节点</option>
                  <option value="llm_timeout">模型超时</option>
                  <option value="empty_response">空响应</option>
                  <option value="invalid_json">非法结构</option>
                  <option value="knowledge_empty">知识不足</option>
                  <option value="receipt_late">晚到回执</option>
                </Select>
              </Field>
              <Field label="限定到本案例会话（可留空）">
                <Input ref={sessionId} />
              </Field>
              <Field label="场景运行号">
                <Input ref={runId} value={crypto.randomUUID()} />
              </Field>
              <Field label="事件时间（北京时间）">
                <Input ref={time} type="datetime-local" value={localDateTime()} />
              </Field>
              <div class="flex flex-wrap gap-3">
                <Button variant="primary" onAction={trigger}>
                  执行一次模拟场景
                </Button>
                <Button
                  onAction={() => {
                    runId.value = crypto.randomUUID()
                  }}
                >
                  准备新运行号
                </Button>
                <Button variant="danger" onAction={resetCase}>
                  确认重置所选案例
                </Button>
              </div>
              <div aria-live="polite">
                <Show when={opening()} fallback={<p>{output()}</p>}>
                  {value => (
                    <Field label="开场草稿（可复制到本人对话输入框）">
                      <Textarea readonly value={value()} />
                    </Field>
                  )}
                </Show>
              </div>
            </div>
          </Card>
          <ServiceDemoControls />
          <PeerModerationControls />
          <PointsConsole />
          <RewardDemoControls />
        </>
      )}
    </Show>
  )
}
