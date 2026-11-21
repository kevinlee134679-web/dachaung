import type { Page } from '../session/session'
import type { JSX } from '@solidjs/web'
import { onSettled, Show } from 'solid-js'
import { DemoPage } from '../features/admin/demo-page'
import { SupportConsolePage } from '../features/admin/support-console-page'
import { DevicePage } from '../features/devices/device-page'
import { EventListPage } from '../features/dose-events/event-list-page'
import { FamilyPage } from '../features/family/family-page'
import { HomePage } from '../features/home/home-page'
import { KnowledgePage } from '../features/knowledge/knowledge-page'
import { FilePage } from '../features/medical-files/file-page'
import { MedicationPage } from '../features/medicines/medication-page'
import { PatientPage } from '../features/patient/patient-page'
import { PeerSupportPage } from '../features/peer/peer-support-page'
import { DraftPage } from '../features/plan-drafts/draft-page'
import { MedicationListForm } from '../features/plan-drafts/medication-list-form'
import { ProfilePage } from '../features/questionnaire/profile-page'
import { QuestionnairePage } from '../features/questionnaire/questionnaire-page'
import { ReminderPage } from '../features/reminders/reminder-page'
import { ReportPage } from '../features/report/report-page'
import { PointsPage } from '../features/rewards/points-page'
import { SchedulePage } from '../features/schedule/schedule-page'
import { ServiceConsentPage } from '../features/services/consent-page'
import { rememberServicePage } from '../features/services/navigation'
import { ServiceRecordsPage } from '../features/services/records-page'
import { SocialSupportPage } from '../features/support/social-support-page'
import { SupportPage } from '../features/support/support-page'
import { TaskPage } from '../features/tasks/task-page'
import { changeTab, navigate } from '../session/navigation'
import { isDemoAdmin, own, scope, state } from '../session/session'
import { Tabs } from '../ui/tabs'
import { Heading } from '../ui/typography'

const titles: Record<Page, string> = {
  home: '今天，从一件小事开始',
  medication: '用药管理',
  support: '支持服务',
  rewards: '积分权益',
  profile: '我的',
}
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

function pageTabs(): [string, string][] {
  if (state.page === 'medication') return medicationTabs
  if (state.page !== 'profile') return []
  return [
    ['overview', '个人资料'],
    ['questionnaire', '八题问卷'],
    ...(own() ? [['medication-list', '用药清单'] satisfies [string, string]] : []),
    ['assessment', '画像结果'],
    ['family', '家庭授权'],
    ...(own() ? [['service-consents', '服务授权'] satisfies [string, string]] : []),
    ...(scope('services:read') ? [['formal-services', '服务记录'] satisfies [string, string]] : []),
    ['report', '用药报告'],
    ['devices', '设备关联'],
    ...(isDemoAdmin() ? [['demo', '演示控制台'] satisfies [string, string]] : []),
  ]
}

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
    case 'medication-list':
      return <MedicationListForm />
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

export function PageContent(): JSX.Element {
  onSettled(rememberServicePage)
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
      <Show when={state.patient && pageTabs().length}>
        <Tabs aria-label="当前页面功能" items={pageTabs()} current={state.tab} onSelect={changeTab} />
      </Show>
      {tabContent()}
    </div>
  )
}
