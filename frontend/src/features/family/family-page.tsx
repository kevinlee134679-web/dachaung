import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api } from '../../api/api'
import { dateText, inputDateTime, localDateTime } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import { readGate } from '../../session/read-gate'
import {
  captureView,
  isCurrentView,
  loadContext,
  own,
  patientPath,
  requireCurrentView,
  state,
  ViewChanged,
} from '../../session/session'
import { StatusBadge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Disclosure } from '../../ui/disclosure'
import { Checkbox, Field, Input } from '../../ui/form'
import { EmptyState, List } from '../../ui/list'
import { Text } from '../../ui/typography'

const accounts: Record<string, string> = {
  'demo-patient-a': '演示患者甲',
  'demo-patient-b': '演示患者乙',
  'demo-family': '演示家人（也可管理自己）',
  'demo-admin': '演示管理员',
}

const grantOptions: [string, string][] = [
  ['patient:read', '基础资料查看'],
  ['patient:edit', '基础资料编辑'],
  ['questionnaire:read', '问卷读取'],
  ['questionnaire:assist', '协助问卷'],
  ['profile:read', '画像摘要'],
  ['medication:read', '药品资料查看'],
  ['medication:edit', '药品资料编辑'],
  ['plan:read', '正式安排查看'],
  ['reminder:read', '提醒查看'],
  ['reminder:write', '提醒编辑'],
  ['notify:receive', '接收相关通知'],
  ['files:read', '病历文件读取'],
  ['files:write', '病历文件上传'],
  ['drafts:read', '草稿查看'],
  ['drafts:write', '草稿编辑'],
  ['drafts:submit', '提交草稿供患者核对'],
  ['records:read', '服药证据查看'],
  ['records:report', '报告服药情况'],
  ['records:correct', '更正自己的报告'],
  ['devices:manage', '设备关联查看与撤销'],
  ['statistics:read', '五类用药统计'],
  ['summary:read', '近期状态摘要'],
  ['feedback:read', '获准来源的反馈概况'],
  ['dialogue:read', '支持对话历史（只读）'],
  ['support:read', '社会支持目录和候选（只读）'],
  ['services:prepare', '协助准备服务草稿'],
  ['services:read', '查看正式服务状态'],
  ['peer:read', '查看同辈小组介绍'],
  ['tasks:read', '提醒与执行状态'],
]

const bindingSchema = v.looseObject({
  binding_id: v.string(),
  family_account_id: v.string(),
  status: v.string(),
  meta: v.looseObject({ revision: v.number() }),
})
type Binding = v.InferOutput<typeof bindingSchema>

const grantSchema = v.looseObject({
  grant_id: v.string(),
  binding_id: v.string(),
  status: v.string(),
  scopes: v.array(v.string()),
  valid_until: v.nullable(v.string()),
  meta: v.looseObject({ revision: v.number() }),
})
type Grant = v.InferOutput<typeof grantSchema>

function BindingItem(props: { binding: Binding; grant: Grant | undefined; reload: (view: View) => Promise<void> }) {
  let deadline!: HTMLInputElement
  let deadlineEdited = false
  const checks = new Map<string, HTMLInputElement>()

  async function finish(view: View, message: string): Promise<void> {
    requireCurrentView(view)
    await loadContext(view)
    requireCurrentView(view)
    await props.reload(view)
    requireCurrentView(view)
    notice(message)
  }

  return (
    <li class="space-y-4">
      <strong>{accounts[props.binding.family_account_id] ?? '已关联家人'}</strong>
      <p>
        关系：
        <StatusBadge status={props.binding.status} />
      </p>
      <Show when={props.grant} fallback={<Text>尚未授予健康资料权限</Text>}>
        {grant => (
          <p class="text-sm/6 text-zinc-500 dark:text-zinc-400">
            授权：
            <StatusBadge status={grant().status} />，
            {grant()
              .scopes.map(scope => grantOptions.find(option => option[0] === scope)?.[1] ?? scope)
              .join('、') || '没有健康权限'}
          </p>
        )}
      </Show>
      <Show when={own() && props.binding.status === 'active'}>
        <Disclosure summary="编辑精确授权范围">
          <Field label="授权截止时间（北京时间，留空表示无预设截止）">
            <Input
              ref={deadline}
              type="datetime-local"
              value={
                props.grant?.valid_until != null && props.grant.valid_until !== ''
                  ? localDateTime(props.grant.valid_until)
                  : ''
              }
              onInput={() => {
                deadlineEdited = true
              }}
              onChange={() => {
                deadlineEdited = true
              }}
            />
          </Field>
          <For each={grantOptions}>
            {option => (
              <Checkbox
                ref={node => {
                  checks.set(option[0], node)
                }}
                label={option[1]}
                checked={props.grant?.status === 'active' && props.grant.scopes.includes(option[0])}
              />
            )}
          </For>
          <Text>
            家人获准后可查看支持对话历史。发言、切换模式和响应邀请由患者本人操作。家人不能发布正式计划或主动生成患者画像。授权范围不会自动随功能增加。
          </Text>
          <Button
            variant="primary"
            onAction={async view => {
              const shown = new Set(grantOptions.map(option => option[0]))
              const keep = props.grant?.status === 'active' ? props.grant.scopes.filter(scope => !shown.has(scope)) : []
              await api(
                `/family-bindings/${props.binding.binding_id}/grant`,
                v.unknown(),
                'PUT',
                {
                  expected_revision: props.grant?.meta.revision ?? 0,
                  scopes: [
                    ...keep,
                    ...Array.from(checks)
                      .filter(([, checkbox]) => checkbox.checked)
                      .map(([scope]) => scope),
                  ],
                  valid_until: deadlineEdited
                    ? deadline.value
                      ? inputDateTime(deadline.value)
                      : null
                    : (props.grant?.valid_until ?? null),
                  confirmed: true,
                },
                view,
              )
              await finish(view, '授权范围已保存。')
            }}
          >
            明确确认并保存授权
          </Button>
        </Disclosure>
        <Show when={props.grant?.status === 'active' && props.grant} keyed>
          {grant => (
            <Button
              variant="danger"
              onAction={async view => {
                await api(
                  `/grants/${grant.grant_id}/revoke`,
                  v.unknown(),
                  'POST',
                  {
                    expected_revision: grant.meta.revision,
                    reason: '患者在家庭管理页面主动撤销',
                  },
                  view,
                )
                await finish(view, '授权已撤销，关系仍保留。')
              }}
            >
              撤销这条授权
            </Button>
          )}
        </Show>
      </Show>
      <Show when={props.binding.status === 'active'}>
        <Button
          class="ml-2"
          variant="danger"
          onAction={async view => {
            await api(
              `/family-bindings/${props.binding.binding_id}/revoke`,
              v.unknown(),
              'POST',
              {
                expected_revision: props.binding.meta.revision,
                reason: '当前账号在家庭页面主动解除关系',
              },
              view,
            )
            await finish(view, '关系已解除，原授权不再可用。')
          }}
        >
          {own() ? '解除这条家庭关系' : '退出这条家庭关系'}
        </Button>
      </Show>
    </li>
  )
}

export function FamilyPage(): JSX.Element {
  let code!: HTMLInputElement
  const [bindingCode, setBindingCode] = createSignal('')
  const [items, setItems] = createSignal<{ binding: Binding; grant: Grant | undefined }[] | null>(null)
  const startRead = readGate()

  async function reload(view: View): Promise<void> {
    requireCurrentView(view)
    const check = startRead()
    const [bindings, grants] = await Promise.all([
      all(patientPath('/family-bindings'), bindingSchema, view),
      all(patientPath('/grants'), grantSchema, view),
    ])
    check()
    setItems(
      bindings.map(binding => ({
        binding,
        grant: grants.filter(grant => grant.binding_id === binding.binding_id).at(-1),
      })),
    )
  }

  onSettled(() => {
    if (!state.patient) return
    const view = captureView()
    void reload(view).catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })

  return (
    <div class="space-y-6">
      <Card title="帮助家人">
        <div class="space-y-4">
          <p>绑定只建立关系，不会自动取得健康资料权限。患者需要另行明确授权。</p>
          <Field label="患者提供的限时绑定码">
            <Input ref={code} />
          </Field>
          <Button
            variant="primary"
            onAction={async view => {
              await api('/family-bindings/redeem', v.unknown(), 'POST', { binding_code: code.value }, view)
              requireCurrentView(view)
              await loadContext(view)
              requireCurrentView({ ...view, sessionOnly: true })
              navigate('profile', 'family')
              notice('家庭关系已建立，请由患者选择具体授权范围。')
            }}
          >
            兑换绑定码
          </Button>
        </div>
      </Card>
      <Show when={state.patient}>
        <Show when={own()}>
          <Card title="邀请家人">
            <div class="space-y-4">
              <Button
                onAction={async view => {
                  const result = await api(
                    patientPath('/family-binding-codes'),
                    v.looseObject({ binding_code: v.string(), expires_at: v.string() }),
                    'POST',
                    {},
                    view,
                  )
                  requireCurrentView(view)
                  setBindingCode(`${result.binding_code}（截止 ${dateText(result.expires_at)}，仅一次使用）`)
                }}
              >
                生成一次性绑定码
              </Button>
              <p>{bindingCode()}</p>
            </div>
          </Card>
        </Show>
        <Show when={items()}>
          {entries => (
            <Card title="家庭关系与授权">
              <Show when={entries().length === 0}>
                <EmptyState>当前没有家庭关系。</EmptyState>
              </Show>
              <List>
                <For each={entries()}>
                  {entry => <BindingItem binding={entry.binding} grant={entry.grant} reload={reload} />}
                </For>
              </List>
            </Card>
          )}
        </Show>
      </Show>
    </div>
  )
}
