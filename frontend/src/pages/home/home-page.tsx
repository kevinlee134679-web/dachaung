import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { api, ApiError } from '../../api/api'
import { rangeQuery } from '../../api/query'
import { today } from '../../date/date'
import {
  captureView,
  dataEnvironment,
  isCurrentView,
  own,
  patientPath,
  requireCurrentView,
  scope,
  state,
  ViewChanged,
} from '../../session/session'
import { navigate } from '../../shell/navigation'
import { Badge, Button, Card, Text } from '../../ui/components'
import { labelFor, statusTone } from '../../ui/labels'
import { SchedulePage } from '../medication/schedule-page'
import { statisticsSchema, StatisticsView } from '../profile/statistics'
import { HomeSupportInvitations } from '../support/home-support-invitations'
import { PeerHomeMembership } from '../support/peer-controls'
import { openServiceRecord } from '../support/service-navigation'

const actionSchema = v.looseObject({ title: v.string(), reason: v.string() })
const recommendationSchema = v.looseObject({
  primary_action: v.nullable(actionSchema),
  secondary_actions: v.array(actionSchema),
  need_status: v.picklist(['none', 'insufficient', 'needed']),
})
const serviceSchema = v.looseObject({ service_id: v.string(), service_name: v.string(), status: v.string() })
const summarySchema = v.looseObject({ record_overview: v.nullable(statisticsSchema), data_status: v.string() })
type Recommendation = v.InferOutput<typeof recommendationSchema>
type Service = v.InferOutput<typeof serviceSchema>
type Summary = v.InferOutput<typeof summarySchema>

export function HomePage(): JSX.Element {
  const [recommendation, setRecommendation] = createSignal<Recommendation | null>(null)
  const [services, setServices] = createSignal<Service[] | null>(null)
  const [recommendationError, setRecommendationError] = createSignal('')
  const [servicesError, setServicesError] = createSignal('')
  const [summary, setSummary] = createSignal<Summary | null>(null)
  const [summaryError, setSummaryError] = createSignal('')
  const [summaryUnavailable, setSummaryUnavailable] = createSignal(false)
  const serviceLabels: Record<string, string> = {
    submitted: '已提交',
    in_progress: '模拟处理中',
    completed: '模拟完成',
    cancelled: '已取消',
    failed: '处理失败',
  }
  onSettled(() => {
    const view = captureView()
    if (scope('support:read')) {
      void api(patientPath('/support-recommendations'), recommendationSchema, 'GET', null, view)
        .then(result => {
          requireCurrentView(view)
          setRecommendation(result)
        })
        .catch((error: unknown) => {
          if (!(error instanceof ViewChanged) && isCurrentView(view))
            setRecommendationError(error instanceof Error ? error.message : '')
        })
    }
    if (scope('services:read')) {
      void api(
        patientPath('/services?limit=3&order=desc'),
        v.looseObject({ items: v.array(serviceSchema) }),
        'GET',
        null,
        view,
      )
        .then(result => {
          requireCurrentView(view)
          setServices(result.items)
        })
        .catch((error: unknown) => {
          if (!(error instanceof ViewChanged) && isCurrentView(view))
            setServicesError(error instanceof Error ? error.message : '')
        })
    }
    if (scope('summary:read')) {
      const day = `${today()}T00:00:00+08:00`
      const window_end = new Date(new Date(day).getTime() + 86400000).toISOString()
      const window_start = new Date(new Date(day).getTime() - 6 * 86400000).toISOString()
      void api(
        `${patientPath('/summary')}?${rangeQuery({ window_start, window_end, data_environment: dataEnvironment() })}`,
        summarySchema,
        'GET',
        null,
        view,
      )
        .then(result => {
          requireCurrentView(view)
          setSummary(result)
        })
        .catch((error: unknown) => {
          if (!(error instanceof ViewChanged) && isCurrentView(view)) {
            setSummaryUnavailable(error instanceof ApiError && error.status === 409)
            setSummaryError(error instanceof Error ? error.message : '')
          }
        })
    }
  })
  return (
    <div class="space-y-6">
      <Card>
        <div class="space-y-4">
          <p>当前对象：{state.patient?.patient.display_name}。这里先整理你的回答、资料与安排，不评价是否足够自律。</p>
          <div class="flex flex-wrap gap-3">
            <Button
              variant="primary"
              disabled={!scope('questionnaire:assist')}
              onAction={() => navigate('profile', 'questionnaire')}
            >
              填写八题问卷
            </Button>
            <Button disabled={!scope('drafts:read')} onAction={() => navigate('medication', 'drafts')}>
              核对用药资料
            </Button>
            <Button disabled={!scope('reminder:read')} onAction={() => navigate('medication', 'reminders')}>
              设置提醒
            </Button>
            <Button
              disabled={!scope('statistics:read') && !scope('summary:read')}
              onAction={() => navigate('profile', 'report')}
            >
              查看用药报告
            </Button>
          </div>
          <Text>
            CAS、患者分类方法尚未适配。本人报告与家人、开盒等证据分别保存；提醒需显式执行，不保证关闭网页后送达。
          </Text>
          <Show when={scope('support:read')}>
            <Button variant="plain" onAction={() => navigate('support', 'social')}>
              查找社会支持
            </Button>
          </Show>
        </div>
      </Card>
      <Show when={scope('plan:read')}>
        <SchedulePage />
      </Show>
      <Show when={scope('interventions:read')}>
        <HomeSupportInvitations />
      </Show>
      <Show when={own() && scope('peer:read')}>
        <PeerHomeMembership />
      </Show>
      <Show when={scope('support:read') || scope('services:read')}>
        <section aria-label="近期支持与服务" class="space-y-6">
          <Show when={recommendation()}>
            {value => (
              <Card title="当前支持建议">
                <div class="space-y-4">
                  <Show
                    when={value().primary_action !== null || value().secondary_actions.length > 0}
                    fallback={
                      <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
                        {value().need_status === 'none'
                          ? '本次暂无支持需求。'
                          : '还没有足够的明确需求信息，你也可以主动查看支持资源。'}
                      </Text>
                    }
                  >
                    <For
                      each={[value().primary_action, ...value().secondary_actions].filter(action => action !== null)}
                    >
                      {action => (
                        <>
                          <p>{action.title}</p>
                          <Text>{action.reason}</Text>
                        </>
                      )}
                    </For>
                  </Show>
                  <Button onAction={() => navigate('support', 'social')}>查看社会支持资源</Button>
                </div>
              </Card>
            )}
          </Show>
          <Show when={recommendationError()}>
            <p class="text-sm/6 text-red-600 dark:text-red-400">{recommendationError()}</p>
          </Show>
          <Show when={services()}>
            {items => (
              <Card title="近期服务">
                <div class="space-y-4">
                  <div class="divide-y divide-zinc-950/5 dark:divide-white/5">
                    <For each={items()}>
                      {service => (
                        <div class="flex flex-wrap items-center justify-between gap-3 py-4 first:pt-0 last:pb-0">
                          <p>
                            {service.service_name} ·{' '}
                            <Badge tone={statusTone(service.status)}>{serviceLabels[service.status]}</Badge>
                          </p>
                          <Button onAction={() => openServiceRecord(service.service_id)}>查看这条服务</Button>
                        </div>
                      )}
                    </For>
                  </div>
                  <Show when={!items().length}>
                    <Text class="rounded-lg border border-dashed border-zinc-300 p-6 text-center dark:border-white/15">
                      暂无正式服务记录。
                    </Text>
                  </Show>
                  <Button onAction={() => navigate('profile', 'formal-services')}>查看全部服务记录</Button>
                </div>
              </Card>
            )}
          </Show>
          <Show when={servicesError()}>
            <p class="text-sm/6 text-red-600 dark:text-red-400">{servicesError()}</p>
          </Show>
        </section>
      </Show>
      <Show when={summary()}>
        {value => (
          <Card>
            <div class="space-y-4">
              <StatisticsView statistics={value().record_overview} title="近期记录（已保存快照）" />
              <p class="text-sm/6 text-zinc-500 dark:text-zinc-400">
                摘要状态：<Badge tone={statusTone(value().data_status)}>{labelFor(value().data_status)}</Badge>
                。刷新和来源不足详情请进入用药报告。
              </p>
            </div>
          </Card>
        )}
      </Show>
      <Show when={summaryError()}>
        <p
          class={
            summaryUnavailable()
              ? 'text-sm/6 text-zinc-500 dark:text-zinc-400'
              : 'text-sm/6 text-red-600 dark:text-red-400'
          }
        >
          {summaryUnavailable() ? '近期报告尚未准备好。请进入用药报告，在正式时段就绪后明确刷新。' : summaryError()}
        </p>
      </Show>
    </div>
  )
}
