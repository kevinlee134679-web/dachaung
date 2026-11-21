import type { View } from '../../session/session'
import type { ServiceConsent, ServiceDraft, SupportResource } from './draft-data'
import type { JSX } from '@solidjs/web'
import { createSignal, flush, For, Show } from 'solid-js'
import { api, ApiError, sha } from '../../api/api'
import { dateText } from '../../date/date'
import { notice } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import { readGate } from '../../session/read-gate'
import { own, patientPath, referenceKey, requireCurrentView, scope, ViewChanged } from '../../session/session'
import { Badge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Checkbox, Field, Fieldset, Input, Textarea } from '../../ui/form'
import { statusLabels, statusTone } from '../../ui/labels'
import { Subheading, Text } from '../../ui/typography'
import { peerResumeFromDraft } from '../peer/peer'
import {
  clearSubmission,
  pendingServiceWrite,
  rememberServiceConsent,
  servicePurposes,
  serviceConsentSchema,
  serviceDraftSchema,
  serviceWrite,
  serviceWriteKey,
  sharedCategoryLabels,
  supportResourceSchema,
} from './draft-data'
import { openServiceRecord } from './navigation'
import { ServicePeerJoinControls } from './service-peer-join'
import { Submission } from './submission'

interface Editor {
  draft: ServiceDraft | null
  resource: SupportResource | null
  text: string
  check: () => void
}

async function reconcile(draft: ServiceDraft, view: View): Promise<void> {
  const path = `/service-drafts/${encodeURIComponent(draft.service_draft_id)}`
  const edit = pendingServiceWrite(path, 'PUT')
  if (edit?.revision !== null && edit?.revision !== undefined && draft.meta.revision > edit.revision) {
    const { resource_id, resource_version, request_text } = draft
    const hash = await sha(JSON.stringify({ resource_id, resource_version, request_text }))
    requireCurrentView(view)
    if (edit.contentHash === hash && pendingServiceWrite(path, 'PUT')?.hash === edit.hash)
      localStorage.removeItem(serviceWriteKey(path, 'PUT'))
  }
  if (!own() || draft.confirmation_ref_id === null || draft.confirmation_ref_id === '') return
  const confirmationPath = patientPath('/service-confirmations')
  const pending = pendingServiceWrite(confirmationPath, 'POST')
  if (pending?.draftId !== draft.service_draft_id || pending.revision !== draft.draft_revision) return
  const value = await api(
    `/service-confirmations/${encodeURIComponent(draft.confirmation_ref_id)}`,
    serviceConsentSchema,
    'GET',
    null,
    view,
  )
  const categories = await sha(JSON.stringify([...value.sharing_scope.data_categories].sort()))
  requireCurrentView(view)
  if (pending.selectionHash === categories && pendingServiceWrite(confirmationPath, 'POST')?.hash === pending.hash)
    localStorage.removeItem(serviceWriteKey(confirmationPath, 'POST'))
}

export interface ServicePreparation {
  prepare: (resource: SupportResource) => void
  restore: () => Promise<void>
}

export function ServiceDraftPreparation(props: {
  view: View
  ref: (preparation: ServicePreparation) => void
}): JSX.Element {
  let reference!: HTMLInputElement
  let textArea!: HTMLTextAreaElement
  let upgrade!: HTMLInputElement
  let explicit!: HTMLInputElement
  const optional = new Map<string, HTMLInputElement>()
  const begin = readGate()
  const [editor, setEditor] = createSignal<Editor | null>(null)
  const [confirmed, setConfirmed] = createSignal<ServiceConsent | null>(null)
  const [errorText, setErrorText] = createSignal('')
  function draw(draft: ServiceDraft | null, resource: SupportResource | null, text: string): void {
    const check = begin()
    setErrorText('')
    setConfirmed(null)
    optional.clear()
    setEditor({ draft, resource, text, check })
  }
  async function open(id: string, unsaved?: string): Promise<void> {
    if (!id) throw new Error('请填写草稿编号。')
    const check = begin()
    try {
      const draft = await api(`/service-drafts/${encodeURIComponent(id)}`, serviceDraftSchema, 'GET', null, props.view)
      check()
      if (draft.patient_id !== props.view.patientId) throw new Error('请先切换到草稿所属的患者。')
      localStorage.setItem(referenceKey('service-draft'), id)
      reference.value = id
      await reconcile(draft, props.view)
      check()
      let resource: SupportResource | null = null
      try {
        resource = await api(
          `/support-resources/${encodeURIComponent(draft.resource_id)}`,
          supportResourceSchema,
          'GET',
          null,
          props.view,
        )
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 404) throw error
      }
      check()
      draw(draft, resource, unsaved ?? draft.request_text)
      if (own() && draft.status === 'submitted') clearSubmission(draft)
      else if (own() && draft.confirmation_ref_id !== null && draft.confirmation_ref_id !== '')
        rememberServiceConsent(draft.confirmation_ref_id)
    } catch (error) {
      check()
      if (error instanceof ApiError && [403, 404].includes(error.status)) {
        setErrorText('')
        setEditor(null)
      }
      throw error
    }
  }
  props.ref({
    prepare(resource) {
      draw(null, resource, '')
      flush()
      textArea.focus()
    },
    async restore() {
      if (!reference.value) return
      try {
        await open(reference.value)
      } catch (error) {
        if (error instanceof ViewChanged) throw error
        setEditor(null)
        setErrorText(error instanceof Error ? error.message : '')
      }
    },
  })
  return (
    <Card title="服务草稿">
      <div class="space-y-4">
        <Text>
          {own() ? '选择资源准备问题，或输入已有草稿编号。' : '可代录获准患者的问题。共享范围由患者本人确认。'}
        </Text>
        <Field label="草稿编号">
          <Input ref={reference} value={localStorage.getItem(referenceKey('service-draft')) ?? ''} maxlength={128} />
        </Field>
        <Button onAction={() => open(reference.value.trim())}>读取草稿</Button>
        <div aria-live="polite" class="space-y-4">
          <p class="text-sm/6 text-red-600 dark:text-red-400">{errorText()}</p>
          <Show when={editor()} keyed>
            {item => (
              <Show
                when={item.draft?.status !== 'submitted'}
                fallback={
                  <Show when={item.draft} keyed>
                    {draft => (
                      <>
                        <Subheading level={3}>已提交正式服务</Subheading>
                        <p>
                          草稿编号 {draft.service_draft_id} · 内容修订 {draft.draft_revision}
                        </p>
                        <p>服务编号 {draft.service_id}</p>
                        <Show when={scope('services:read')}>
                          <Show when={draft.service_id}>
                            {serviceId => <Button onAction={() => openServiceRecord(serviceId())}>查看正式服务</Button>}
                          </Show>
                        </Show>
                        <Show when={draft.peer_group_id}>
                          {groupId => (
                            <Show when={own()}>
                              <Button onAction={() => peerResumeFromDraft({ peer_group_id: groupId() })}>
                                核对原入组申请
                              </Button>
                            </Show>
                          )}
                        </Show>
                      </>
                    )}
                  </Show>
                }
              >
                <Subheading level={3}>{(item.resource?.name ?? '') || '原目录版本'}</Subheading>
                <p>
                  {item.resource
                    ? `目录版本 ${item.resource.resource_version} · mock/demo`
                    : '原资源现已停用。草稿仍可查阅。'}
                </p>
                <Show when={item.draft}>
                  {draft => (
                    <>
                      <p>
                        已保存草稿 · 内容修订 {draft().draft_revision} · 目录版本 {draft().resource_version}
                      </p>
                      <p>草稿编号 {draft().service_draft_id}</p>
                    </>
                  )}
                </Show>
                <Show
                  when={item.draft && item.resource && item.draft.resource_version !== item.resource.resource_version}
                >
                  <Checkbox ref={upgrade} label="采用上面显示的当前目录版本" />
                </Show>
                <Field label="本次服务问题">
                  <Textarea ref={textArea} maxlength={2000} rows={4} value={item.text} />
                </Field>
                <Show when={item.resource} keyed>
                  {resource => (
                    <Button
                      variant="primary"
                      onAction={async () => {
                        const { draft, check } = item
                        if (!textArea.value.trim()) throw new Error('请填写本次服务问题。')
                        if (draft && resource.resource_version !== draft.resource_version && !upgrade.checked)
                          throw new Error('保存前请核对并选用当前目录版本。')
                        const path = draft
                          ? `/service-drafts/${encodeURIComponent(draft.service_draft_id)}`
                          : patientPath('/service-drafts')
                        const content = {
                          resource_id: resource.resource_id,
                          resource_version: resource.resource_version,
                          request_text: textArea.value.trim(),
                          ...((resource.peer_group_id ?? '') !== '' ? { peer_group_id: resource.peer_group_id } : {}),
                        }
                        const typed = textArea.value
                        try {
                          const result = await serviceWrite(
                            path,
                            draft ? 'PUT' : 'POST',
                            draft ? { expected_revision: draft.meta.revision, content } : content,
                            serviceDraftSchema,
                            props.view,
                          )
                          check()
                          await open(result.service_draft_id)
                          notice('草稿已保存。')
                        } catch (error) {
                          check()
                          if (draft && error instanceof ApiError && error.code === 'SERVICE_DRAFT_REVISION_CONFLICT')
                            await open(draft.service_draft_id, typed)
                          throw error
                        }
                      }}
                    >
                      {item.draft ? '保存草稿修改' : '保存草稿'}
                    </Button>
                  )}
                </Show>
                <Show when={own() && item.draft} keyed>
                  {draft => (
                    <Show
                      when={confirmed() !== null || Boolean(draft.confirmation_ref_id)}
                      fallback={
                        <Show when={item.resource?.resource_version === draft.resource_version && item.resource} keyed>
                          {resource => (
                            <>
                              <Subheading level={3}>本人确认共享范围</Subheading>
                              <p>
                                接收主体 {resource.provider.display_name} · 用途{' '}
                                {servicePurposes[resource.service_kind]}
                              </p>
                              <p>
                                必要类别{' '}
                                {resource.required_shared_categories
                                  .map(category => sharedCategoryLabels[category])
                                  .join('、') || '无'}
                              </p>
                              <p>有效期为首次确认后 24 小时。相同范围的有效同意沿用原截止时间。</p>
                              <Show when={resource.optional_shared_categories.length}>
                                <Fieldset legend="可选共享类别">
                                  <For each={resource.optional_shared_categories}>
                                    {category => (
                                      <Checkbox
                                        ref={element => {
                                          optional.set(category, element)
                                        }}
                                        label={sharedCategoryLabels[category]}
                                      />
                                    )}
                                  </For>
                                </Fieldset>
                              </Show>
                              <Checkbox ref={explicit} label="我已核对本次问题、接收主体和共享范围" />
                              <Button
                                variant="primary"
                                onAction={async () => {
                                  const check = item.check
                                  if (textArea.value.trim() !== draft.request_text)
                                    throw new Error('请先保存本次修改，再核对新草稿。')
                                  if (!explicit.checked) throw new Error('请先勾选本人核对。')
                                  try {
                                    const value = await serviceWrite(
                                      patientPath('/service-confirmations'),
                                      'POST',
                                      {
                                        service_draft_id: draft.service_draft_id,
                                        draft_revision: draft.draft_revision,
                                        shared_categories: [
                                          ...resource.required_shared_categories,
                                          ...resource.optional_shared_categories.filter(
                                            category => optional.get(category)?.checked ?? false,
                                          ),
                                        ].sort(),
                                        confirmed: true,
                                      },
                                      serviceConsentSchema,
                                      props.view,
                                    )
                                    check()
                                    rememberServiceConsent(value.confirmation_ref_id)
                                    setConfirmed(value)
                                    notice(
                                      value.status === 'active'
                                        ? '已记录本次共享确认。'
                                        : '已核对原提交，当前共享范围已失效。',
                                    )
                                  } catch (error) {
                                    check()
                                    if (
                                      error instanceof ApiError &&
                                      error.code === 'SHARING_CONFIRMATION_REQUIRED' &&
                                      !error.pendingRecovery
                                    ) {
                                      const latest = await api(
                                        `/service-drafts/${encodeURIComponent(draft.service_draft_id)}`,
                                        serviceDraftSchema,
                                        'GET',
                                        null,
                                        props.view,
                                      )
                                      check()
                                      if (latest.meta.revision !== draft.meta.revision)
                                        await open(draft.service_draft_id, textArea.value)
                                    }
                                    throw error
                                  }
                                }}
                              >
                                明确确认共享范围
                              </Button>
                            </>
                          )}
                        </Show>
                      }
                    >
                      <Show when={confirmed()} fallback={<p>此修订已有共享确认。</p>}>
                        {value => (
                          <>
                            <p>
                              共享确认：<Badge tone={statusTone(value().status)}>{statusLabels[value().status]}</Badge>{' '}
                              · 目录版本 {value().resource_version}
                            </p>
                            <p>
                              接收主体 {value().sharing_scope.recipient_id}（模拟） · 用途{' '}
                              {servicePurposes[value().sharing_scope.purpose_code] ??
                                value().sharing_scope.purpose_code}
                            </p>
                            <p>
                              {value()
                                .sharing_scope.data_categories.map(category => sharedCategoryLabels[category])
                                .join('、')}
                            </p>
                            <p>
                              确认于 {dateText(value().confirmed_at)}，截止于 {dateText(value().valid_until)}
                            </p>
                            <p>确认编号 {value().confirmation_ref_id}</p>
                            <p>草稿仍处于准备阶段。</p>
                          </>
                        )}
                      </Show>
                      <Button onAction={() => navigate('profile', 'service-consents')}>查看确认及历史</Button>
                      <Show when={!confirmed() || confirmed()?.status === 'active'}>
                        <Show
                          when={confirmed()}
                          keyed
                          fallback={
                            <ServicePeerJoinControls
                              draft={draft}
                              textArea={textArea}
                              view={props.view}
                              fallback={<Submission draft={draft} textArea={textArea} view={props.view} open={open} />}
                            />
                          }
                        >
                          {consent => (
                            <ServicePeerJoinControls
                              draft={{
                                ...draft,
                                confirmation_ref_id: consent.confirmation_ref_id,
                                sharing_scope_ref_id: consent.sharing_scope.sharing_scope_ref_id,
                              }}
                              textArea={textArea}
                              view={props.view}
                              fallback={
                                <Submission
                                  draft={{
                                    ...draft,
                                    confirmation_ref_id: consent.confirmation_ref_id,
                                    sharing_scope_ref_id: consent.sharing_scope.sharing_scope_ref_id,
                                  }}
                                  textArea={textArea}
                                  view={props.view}
                                  open={open}
                                />
                              }
                            />
                          )}
                        </Show>
                      </Show>
                    </Show>
                  )}
                </Show>
              </Show>
            )}
          </Show>
        </div>
      </div>
    </Card>
  )
}
