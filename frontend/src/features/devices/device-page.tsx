import type { View } from '../../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { all, api } from '../../api/api'
import { actionError, notice } from '../../notice/notice'
import {
  captureView,
  isCurrentView,
  isDemoAdmin,
  own,
  patientPath,
  requireCurrentView,
  scope,
  ViewChanged,
} from '../../session/session'
import { StatusBadge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Field, Input } from '../../ui/form'
import { EmptyState, List } from '../../ui/list'
import { Text } from '../../ui/typography'

const deviceBindingSchema = v.looseObject({
  binding_id: v.string(),
  device_id: v.string(),
  status: v.string(),
  meta: v.looseObject({ revision: v.number(), is_simulated: v.boolean() }),
})
type DeviceBinding = v.InferOutput<typeof deviceBindingSchema>

export function DevicePage(): JSX.Element {
  const [bindings, setBindings] = createSignal<DeviceBinding[] | null>(null)
  let device!: HTMLInputElement
  async function load(view: View) {
    const result = await all(patientPath('/device-bindings'), deviceBindingSchema, view)
    requireCurrentView(view)
    setBindings(result)
  }
  onSettled(() => {
    if (!scope('devices:manage')) return
    const view = captureView()
    void load(view).catch((error: unknown) => {
      if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
    })
  })
  return (
    <Card title="设备关联">
      <div class="space-y-4">
        <Text>本期使用可信登记的虚构设备。有关联不表示真实设备在线，也不证明患者已经服药。</Text>
        <Show when={scope('devices:manage')} fallback={<p>当前未获设备关联查看权限。</p>}>
          <Show when={bindings()}>
            {items => (
              <>
                <List>
                  <For each={items()}>
                    {binding => (
                      <li class="flex flex-wrap items-center justify-between gap-3">
                        <p>
                          {binding.device_id} · <StatusBadge status={binding.status} /> ·{' '}
                          {binding.meta.is_simulated ? '模拟设备' : '登记设备'}
                        </p>
                        <Show when={binding.status === 'active'}>
                          <Button
                            onAction={async view => {
                              await api(
                                `/device-bindings/${encodeURIComponent(binding.binding_id)}/revoke`,
                                v.unknown(),
                                'POST',
                                { expected_revision: binding.meta.revision, reason: '用户明确撤销设备关联' },
                                view,
                              )
                              await load(view)
                              requireCurrentView(view)
                              notice('设备关联已撤销；旧来源历史仍保留，新上传须重新核验。')
                            }}
                          >
                            明确撤销此设备关联
                          </Button>
                        </Show>
                      </li>
                    )}
                  </For>
                </List>
                <Show when={!items().length}>
                  <EmptyState>尚无设备关联。</EmptyState>
                </Show>
                <Show when={own() || isDemoAdmin()}>
                  <Field label="已可信登记的设备编号">
                    <Input ref={device} />
                  </Field>
                  <Button
                    onAction={async view => {
                      await api(
                        patientPath('/device-bindings'),
                        v.unknown(),
                        'POST',
                        { device_id: device.value, confirmed: true },
                        view,
                      )
                      await load(view)
                      requireCurrentView(view)
                      notice('已保存设备关联；客户端填写编号不能创建可信设备。')
                    }}
                  >
                    明确关联此设备
                  </Button>
                </Show>
              </>
            )}
          </Show>
        </Show>
      </div>
    </Card>
  )
}
