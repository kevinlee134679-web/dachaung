import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show, untrack } from 'solid-js'
import * as v from 'valibot'
import { ApiError, api } from '../../api/api'
import { dateText } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import { readGate } from '../../session/read-gate'
import { captureView, own, referenceKey, ViewChanged } from '../../session/session'
import { StatusBadge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Checkbox, Field, Input } from '../../ui/form'
import { Text } from '../../ui/typography'
import {
  rememberServiceConsent,
  servicePurposes,
  serviceWrite,
  serviceWriteKey,
  sharedCategoryLabels,
} from './draft-data'

interface ServiceConsent {
  status: string
  resource_version: string
  sharing_scope: { recipient_id: string; purpose_code: string; data_categories: string[] }
  confirmed_at: string
  valid_until: string
  confirmation_ref_id: string
  meta: { revision: number }
}

const serviceConsentSchema = v.looseObject({
  status: v.string(),
  resource_version: v.string(),
  sharing_scope: v.looseObject({
    recipient_id: v.string(),
    purpose_code: v.string(),
    data_categories: v.array(v.string()),
  }),
  confirmed_at: v.string(),
  valid_until: v.string(),
  confirmation_ref_id: v.string(),
  meta: v.looseObject({ revision: v.number() }),
})

export function ServiceConsentPage(): JSX.Element {
  const view = untrack(captureView)
  const isOwner = untrack(own)
  const begin = readGate()
  const [refs, setRefs] = createSignal<string[]>([])
  const [consent, setConsent] = createSignal<ServiceConsent | null>(null)
  const [unsavedReason, setUnsavedReason] = createSignal('')
  let reference!: HTMLInputElement
  let reason!: HTMLInputElement
  let explicit!: HTMLInputElement

  async function load(id: string, savedReason = ''): Promise<void> {
    if (!id) throw new Error('请填写确认编号。')
    const check = begin()
    setConsent(null)
    const result = await api(
      `/service-confirmations/${encodeURIComponent(id)}`,
      serviceConsentSchema,
      'GET',
      null,
      view,
    )
    check()
    setRefs(previous => (previous.includes(id) ? previous : [...previous, id]))
    rememberServiceConsent(id)
    localStorage.setItem(referenceKey('service-consent'), id)
    if (result.status === 'revoked')
      localStorage.removeItem(serviceWriteKey(`/service-confirmations/${encodeURIComponent(id)}/revoke`, 'POST'))
    setUnsavedReason(savedReason)
    setConsent(result)
  }

  async function revoke(value: ServiceConsent): Promise<void> {
    if (!explicit.checked || !reason.value.trim()) throw new Error('请填写原因并明确勾选撤销。')
    const check = begin()
    const savedReason = reason.value
    try {
      const result = await serviceWrite(
        `/service-confirmations/${encodeURIComponent(value.confirmation_ref_id)}/revoke`,
        'POST',
        { expected_revision: value.meta.revision, reason: savedReason.trim() },
        serviceConsentSchema,
        view,
      )
      check()
      setUnsavedReason('')
      setConsent(result)
      notice('共享范围已撤销。')
    } catch (error) {
      check()
      if (error instanceof ApiError && error.code === 'CONFIRMATION_REVISION_CONFLICT')
        await load(value.confirmation_ref_id, savedReason)
      throw error
    }
  }

  onSettled(() => {
    if (!isOwner) return
    const stored = (localStorage.getItem(referenceKey('service-consent-history')) ?? '').split(',').filter(Boolean)
    setRefs(stored)
    const saved = localStorage.getItem(referenceKey('service-consent'))
    const last = saved != null && saved !== '' ? saved : stored[0]
    if (last != null && last !== '') {
      reference.value = last
      void load(last).catch((error: unknown) => {
        if (!(error instanceof ViewChanged)) actionError(error, view)
      })
    }
  })

  return (
    <Show when={isOwner}>
      <Card title="服务授权">
        <div class="space-y-4">
          <p>可查看本浏览器记录的共享确认，或输入已知确认编号。</p>
          <div class="flex flex-wrap gap-2">
            <For each={refs()}>
              {id => (
                <Button
                  onAction={async () => {
                    reference.value = id
                    return load(id)
                  }}
                >
                  {id}
                </Button>
              )}
            </For>
          </div>
          <Field label="确认编号">
            <Input ref={reference} maxlength={128} />
          </Field>
          <Button onAction={async () => load(reference.value.trim())}>读取确认</Button>
          <div aria-live="polite">
            <Show when={consent()} keyed>
              {value => (
                <>
                  <div class="space-y-2 border-y border-zinc-950/5 py-4 dark:border-white/5">
                    <p class="font-medium">
                      共享确认：
                      <StatusBadge status={value.status} /> · 目录版本 {value.resource_version}
                    </p>
                    <p>
                      接收主体 {value.sharing_scope.recipient_id}（模拟） · 用途{' '}
                      {servicePurposes[value.sharing_scope.purpose_code] != null &&
                      servicePurposes[value.sharing_scope.purpose_code] !== ''
                        ? servicePurposes[value.sharing_scope.purpose_code]
                        : value.sharing_scope.purpose_code}
                    </p>
                    <p>
                      {value.sharing_scope.data_categories.map(category => sharedCategoryLabels[category]).join('、')}
                    </p>
                    <Text>
                      确认于 {dateText(value.confirmed_at)}，截止于 {dateText(value.valid_until)}
                    </Text>
                    <Text>确认编号 {value.confirmation_ref_id}</Text>
                  </div>
                  <Show when={value.status !== 'revoked'}>
                    <Field label="撤销原因">
                      <Input ref={reason} maxlength={500} value={unsavedReason()} />
                    </Field>
                    <Checkbox ref={explicit} label="明确撤销此共享范围" />
                    <Button variant="danger" onAction={async () => revoke(value)}>
                      撤销共享授权
                    </Button>
                  </Show>
                </>
              )}
            </Show>
          </div>
        </div>
      </Card>
    </Show>
  )
}
