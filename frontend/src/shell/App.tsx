import type { Page } from '../session/session'
import type { JSX } from '@solidjs/web'
import { createSignal, For, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { api } from '../api/api'
import { actionError, notice } from '../notice/notice'
import { Notice } from '../notice/notice-view'
import { LoginPage } from '../pages/auth/login-page'
import { HomePage } from '../pages/home/home-page'
import { DraftPage } from '../pages/medication/draft-page'
import { EventListPage } from '../pages/medication/event-list-page'
import { FilePage } from '../pages/medication/file-page'
import { KnowledgePage } from '../pages/medication/knowledge-page'
import { MedicationPage } from '../pages/medication/medication-page'
import { ReminderPage } from '../pages/medication/reminder-page'
import { SchedulePage } from '../pages/medication/schedule-page'
import { TaskPage } from '../pages/medication/task-page'
import { DemoPage } from '../pages/profile/demo-page'
import { DevicePage } from '../pages/profile/device-page'
import { FamilyPage } from '../pages/profile/family-page'
import { PatientPage } from '../pages/profile/patient-page'
import { ProfilePage } from '../pages/profile/profile-page'
import { QuestionnairePage } from '../pages/profile/questionnaire-page'
import { ReportPage } from '../pages/profile/report-page'
import { ServiceConsentPage } from '../pages/profile/service-consent-page'
import { ServiceRecordsPage } from '../pages/profile/service-records-page'
import { PointsPage } from '../pages/rewards/points-page'
import { PeerSupportPage } from '../pages/support/peer-support-page'
import { rememberServicePage, restoreServicePage } from '../pages/support/service-navigation'
import { SocialSupportPage } from '../pages/support/social-support-page'
import { SupportConsolePage } from '../pages/support/support-console-page'
import { SupportPage } from '../pages/support/support-page'
import {
  captureView,
  isCurrentView,
  isDemoAdmin,
  loadContext,
  own,
  requireCurrentView,
  resetSession,
  scope,
  state,
  updateSession,
  ViewChanged,
} from '../session/session'
import { Badge, Button, Heading, Select, Text } from '../ui/components'
import { Tabs } from '../ui/tabs'
import { changeTab, navigate } from './navigation'

const titles: Record<Page, string> = {
  home: '今天，从一件小事开始',
  medication: '用药管理',
  support: '支持服务',
  rewards: '积分权益',
  profile: '我的',
}
const healthEnvelopeSchema = v.looseObject({ status: v.string() })
const pages: [Page, string, string][] = [
  ['home', '首页', 'icon-[heroicons--home]'],
  ['medication', '用药管理', 'icon-[heroicons--clipboard-document-list]'],
  ['support', '支持服务', 'icon-[heroicons--chat-bubble-left-right]'],
  ['rewards', '积分权益', 'icon-[heroicons--gift]'],
  ['profile', '我的', 'icon-[heroicons--user-circle]'],
]
const medicationTabs: [string, string][] = [
  ['overview', '今日安排'],
  ['meds', '药品资料'],
  ['files', '病历资料'],
  ['drafts', '资料核对'],
  ['reminders', '提醒设置'],
  ['records', '服药记录'],
  ['measurements', '指标记录'],
  ['executions', '提醒与执行'],
  ['knowledge', '药学知识'],
]

function tabContent(): JSX.Element {
  if (state.page === 'support') {
    return state.tab === 'social' ? <SocialSupportPage /> : state.tab === 'peer' ? <PeerSupportPage /> : <SupportPage />
  }
  if (state.page === 'rewards') return <PointsPage />
  if (!state.patient) {
    return state.page === 'profile' && isDemoAdmin() ? (
      <SupportConsolePage />
    ) : (
      <>
        <p>请先在上方选择本人或已获授权的照护对象。</p>
        {state.page === 'profile' && <FamilyPage />}
      </>
    )
  }
  if (state.page === 'home') return <HomePage />
  if (state.page === 'medication') {
    switch (state.tab) {
      case 'meds':
        return <MedicationPage />
      case 'files':
        return <FilePage />
      case 'drafts':
        return <DraftPage />
      case 'reminders':
        return <ReminderPage />
      case 'records':
      case 'measurements':
        return <EventListPage />
      case 'executions':
        return <TaskPage />
      case 'knowledge':
        return <KnowledgePage />
      default:
        return <SchedulePage />
    }
  }
  switch (state.tab) {
    case 'questionnaire':
      return <QuestionnairePage />
    case 'assessment':
      return <ProfilePage />
    case 'family':
      return <FamilyPage />
    case 'service-consents':
      return <ServiceConsentPage />
    case 'formal-services':
      return <ServiceRecordsPage />
    case 'report':
      return <ReportPage />
    case 'devices':
      return <DevicePage />
    case 'demo':
      return <DemoPage />
    default:
      return <PatientPage />
  }
}

function PageContent(): JSX.Element {
  onSettled(rememberServicePage)
  const tabs = (): [string, string][] =>
    state.page === 'medication'
      ? medicationTabs
      : state.page === 'profile'
        ? [
            ['overview', '个人资料'],
            ['questionnaire', '八题问卷'],
            ['assessment', '画像结果'],
            ['family', '家庭授权'],
            ...(own() ? [['service-consents', '服务授权'] satisfies [string, string]] : []),
            ...(scope('services:read') ? [['formal-services', '服务记录'] satisfies [string, string]] : []),
            ['report', '用药报告'],
            ['devices', '设备关联'],
            ...(isDemoAdmin() ? [['demo', '演示控制台'] satisfies [string, string]] : []),
          ]
        : []
  return (
    <div class="space-y-6">
      <Heading>{titles[state.page]}</Heading>
      <Show when={state.page === 'support' && (scope('support:read') || scope('peer:read'))}>
        <Tabs
          aria-label="支持服务功能"
          items={[
            ['overview', '支持对话'],
            ...(scope('support:read') ? [['social', '社会支持'] satisfies [string, string]] : []),
            ...(scope('peer:read') ? [['peer', '匿名同辈'] satisfies [string, string]] : []),
          ]}
          current={['social', 'peer'].includes(state.tab) ? state.tab : 'overview'}
          onSelect={key => navigate('support', key === 'overview' ? undefined : key)}
        />
      </Show>
      <Show when={state.patient && tabs().length}>
        <Tabs aria-label="当前页面功能" items={tabs()} current={state.tab} onSelect={changeTab} />
      </Show>
      {tabContent()}
    </div>
  )
}

function Identity(): JSX.Element {
  async function switchPatient(event: Event & { currentTarget: HTMLSelectElement }): Promise<void> {
    const picker = event.currentTarget
    const selected = picker.value
    if (!selected || state.switchingPatient) return
    updateSession(draft => {
      draft.switchingPatient = true
      draft.epoch++
      draft.response = null
      draft.draft = null
    })
    const transition = captureView()
    try {
      await api('/auth/current-patient', v.unknown(), 'PUT', { patient_id: selected }, transition)
      await loadContext(transition)
      notice('已切换对象，旧表单已清除。')
    } catch (error) {
      if (!(error instanceof ViewChanged) && state.epoch === transition.epoch && isCurrentView(transition))
        actionError(error, transition)
      picker.value = state.patient?.patient.patient_id ?? ''
    } finally {
      updateSession(draft => {
        draft.switchingPatient = false
      })
    }
  }
  return (
    <div class="flex min-w-0 items-center justify-end gap-2">
      <Show when={state.context}>
        <p class="hidden text-sm/6 font-semibold sm:block">{state.context?.account.display_name}</p>
        <Show when={state.context?.patients.length}>
          <label class="max-w-40 min-w-0">
            <span class="sr-only">正在管理</span>
            <Select
              aria-label="当前管理对象"
              value={state.patient?.patient.patient_id ?? ''}
              disabled={state.switchingPatient}
              onChange={event => void switchPatient(event)}
            >
              <option value="">请选择管理对象</option>
              <For each={state.context?.patients}>
                {item => (
                  <option value={item.patient.patient_id}>
                    {item.patient.display_name} · {item.relationship === 'self' ? '本人' : '家庭协助'}
                  </option>
                )}
              </For>
            </Select>
          </label>
        </Show>
        <Button
          view={{ ...captureView(), sessionOnly: true }}
          variant="plain"
          icon="icon-[heroicons--arrow-right-start-on-rectangle]"
          class="!px-2"
          onAction={async view => {
            await api('/auth/logout', v.unknown(), 'POST', {}, view)
            requireCurrentView(view)
            resetSession()
            notice('当前会话已退出。')
          }}
        >
          <span class="sr-only sm:not-sr-only">退出</span>
        </Button>
      </Show>
    </div>
  )
}

function Brand(): JSX.Element {
  return (
    <div class="flex items-center gap-3">
      <span
        aria-hidden="true"
        class="flex size-8 items-center justify-center rounded-lg bg-teal-600 text-white dark:bg-teal-600 dark:text-white"
      >
        <span class="icon-[heroicons--heart] size-5" />
      </span>
      <span class="font-semibold">用药支持</span>
    </div>
  )
}

function Navigation(): JSX.Element {
  return (
    <nav aria-label="主要导航" class="flex w-full lg:flex-col lg:gap-1">
      <For each={pages}>
        {page => (
          <Button
            view={{ ...captureView(), sessionOnly: true }}
            disabled={state.switchingPatient}
            aria-current={state.page === page[0] ? 'page' : undefined}
            variant="plain"
            onAction={() => navigate(page[0])}
            class={`!h-auto min-w-0 flex-1 flex-col !gap-1 !rounded-none !px-1 py-2 !text-xs lg:!h-9 lg:w-full lg:flex-none lg:flex-row lg:!justify-start lg:!gap-3 lg:!rounded-lg lg:!px-2 lg:!py-0 lg:!text-sm lg:!font-medium ${state.page === page[0] ? '!text-teal-600 lg:bg-zinc-950/5 lg:!text-zinc-950 dark:!text-teal-400 lg:dark:bg-white/10 lg:dark:!text-white' : '!text-zinc-600 hover:!text-zinc-950 dark:!text-zinc-400 dark:hover:!text-white'}`}
          >
            <span
              aria-hidden="true"
              class={`${page[2]} size-6 lg:size-5 ${state.page === page[0] ? 'lg:text-teal-600 lg:dark:text-teal-400' : ''}`}
            />
            {page[1]}
          </Button>
        )}
      </For>
    </nav>
  )
}

export function App(): JSX.Element {
  const [health, setHealth] = createSignal('正在检查基础服务…')
  const [checking, setChecking] = createSignal(false)
  const [ready, setReady] = createSignal(false)
  const [serviceReady, setServiceReady] = createSignal(false)
  async function checkHealth(): Promise<void> {
    setChecking(true)
    try {
      const response = await fetch('/api/v1/health', { cache: 'no-store' })
      const result = v.parse(healthEnvelopeSchema, await response.json())
      setServiceReady(response.ok && result.status === 'success')
      setHealth(
        response.ok && result.status === 'success'
          ? '基础存储已就绪；功能以各页面实际状态为准。'
          : '基础服务尚未就绪，请查看初始化或迁移说明。',
      )
    } catch {
      setServiceReady(false)
      setHealth('无法连接本地服务，请确认已启动后重新检查。')
    } finally {
      setChecking(false)
    }
  }
  onSettled(() => {
    void (async () => {
      await checkHealth()
      try {
        await loadContext()
      } catch {
        resetSession()
      }
      await restoreServicePage()
      setReady(true)
    })()
  })
  return (
    <Show
      when={ready()}
      fallback={
        <div class="grid min-h-dvh place-items-center">
          <Text>
            <span
              aria-hidden="true"
              class="mr-2 icon-[heroicons--arrow-path] size-4 animate-spin motion-reduce:animate-none"
            />
            正在读取本地状态…
          </Text>
        </div>
      }
    >
      <Show
        when={state.context}
        fallback={
          <div class="grid min-h-dvh place-items-center p-6">
            <div class="w-full max-w-md space-y-6">
              <Notice />
              <LoginPage />
            </div>
          </div>
        }
      >
        <Show when={state.context?.csrf_token} keyed>
          <aside class="fixed inset-x-0 bottom-0 z-20 border-t border-zinc-950/5 bg-white pb-[env(safe-area-inset-bottom)] lg:inset-y-0 lg:right-auto lg:flex lg:w-64 lg:flex-col lg:gap-6 lg:border-t-0 lg:border-r lg:p-4 dark:border-white/10 dark:bg-zinc-900">
            <div class="hidden items-center justify-between gap-2 lg:flex">
              <Brand />
              <Badge>虚构演示</Badge>
            </div>
            <Navigation />
          </aside>
          <header class="sticky top-0 z-10 flex h-14 items-center justify-between gap-3 border-b border-zinc-950/5 bg-white/80 px-4 backdrop-blur lg:ml-64 lg:justify-end lg:px-10 dark:border-white/10 dark:bg-zinc-900/80">
            <div class="lg:hidden">
              <Brand />
            </div>
            <Identity />
          </header>
        </Show>
        <div class="lg:pl-64">
          <main class="mx-auto max-w-5xl space-y-6 px-4 py-6 pb-24 sm:px-6 lg:px-10 lg:py-10 lg:pb-8">
            <Notice />
            <Show
              when={state.switchingPatient}
              fallback={
                <Show when={state.epoch + 1} keyed>
                  <PageContent />
                </Show>
              }
            >
              <Text>
                <span
                  aria-hidden="true"
                  class="mr-2 icon-[heroicons--arrow-path] size-4 animate-spin motion-reduce:animate-none"
                />
                正在切换管理对象…
              </Text>
            </Show>
            <footer class="space-y-2">
              <div class="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  class={`size-1.5 rounded-full ${serviceReady() ? 'bg-teal-500 dark:bg-teal-400' : 'bg-amber-500 dark:bg-amber-400'}`}
                />
                <Text class="text-xs">{health()}</Text>
                <Show when={state.context?.csrf_token} keyed>
                  <Button
                    view={{ ...captureView(), sessionOnly: true }}
                    variant="plain"
                    disabled={checking()}
                    onAction={checkHealth}
                    class="!h-auto !px-1 py-1 !text-xs"
                  >
                    重新检查
                  </Button>
                </Show>
              </div>
              <Text class="text-xs">
                演示资料不用于实际服药。涉及医嘱变更，请咨询医生或药师；未接入真实模型、人员或外部通知。
              </Text>
            </footer>
          </main>
        </div>
      </Show>
    </Show>
  )
}
