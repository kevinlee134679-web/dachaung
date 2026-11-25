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
import { CaseFilePage } from '../features/medical-files/case-file-page'
import { MedicationPage } from '../features/medicines/medication-page'
import { PatientPage } from '../features/patient/patient-page'
import { PeerSupportPage } from '../features/peer/peer-support-page'
import { MedicationListForm } from '../features/plan-drafts/medication-list-form'
import { canManageMedicationList, rememberMedicationPage } from '../features/plan-drafts/navigation'
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
import { Disclosure } from '../ui/disclosure'
import { Tabs } from '../ui/tabs'
import { Heading } from '../ui/typography'

const titles: Record<Page, string> = {
  home: '今天，从一件小事开始',
  medication: '用药管理',
  knowledge: '药学知识',
  support: '支持服务',
  rewards: '积分权益',
  profile: '我的',
}
const medicationTabs: [string, string][] = [
  ['overview', '今日安排'],
  ['medication-list', '用药清单'],
  ['records', '服药记录'],
  ['case-files', '病例资料'],
  ['reminders', '提醒设置'],
  ['measurements', '指标记录'],
  ['executions', '提醒与执行'],
]

function canOpenCaseFiles(): boolean {
  return scope('files:read') || scope('files:write') || scope('drafts:read')
}

function activeTab(): string {
  const { page, tab } = state
  if (page === 'medication' && ['files', 'drafts'].includes(tab)) return 'case-files'
  if (page === 'profile' && ['questionnaire', 'assessment'].includes(tab)) return 'adherence'
  if (page === 'profile' && ['family', 'service-consents', 'formal-services'].includes(tab)) return 'authorizations'
  return tab
}

function pageTabs(): [string, string][] {
  if (state.page === 'medication') {
    return medicationTabs.filter(
      ([key]) =>
        (key !== 'medication-list' || canManageMedicationList()) && (key !== 'case-files' || canOpenCaseFiles()),
    )
  }
  if (state.page !== 'profile') return []
  return [
    ['overview', '个人资料'],
    ...(scope('profile:read') || scope('questionnaire:assist')
      ? [['adherence', '依从性类型'] satisfies [string, string]]
      : []),
    ...(scope('medication:read') ? [['meds', '药品资料'] satisfies [string, string]] : []),
    ['authorizations', '授权与服务'],
    ['report', '用药报告'],
    ['devices', '设备关联'],
    ...(isDemoAdmin() ? [['demo', '演示控制台'] satisfies [string, string]] : []),
  ]
}

function AdherencePage(): JSX.Element {
  return (
    <div class="space-y-4">
      <Show when={scope('profile:read')}>
        <ProfilePage />
      </Show>
      <Show when={scope('questionnaire:assist')}>
        <Disclosure summary="评估问卷" lazy open={state.tab === 'questionnaire' || !scope('profile:read')}>
          <QuestionnairePage />
        </Disclosure>
      </Show>
    </div>
  )
}

function AuthorizationsPage(): JSX.Element {
  return (
    <div class="space-y-4">
      <Disclosure summary="家庭授权" lazy open={state.tab === 'family'}>
        <FamilyPage />
      </Disclosure>
      <Show when={own()}>
        <Disclosure summary="服务授权" lazy open={state.tab === 'service-consents'}>
          <ServiceConsentPage />
        </Disclosure>
      </Show>
      <Show when={scope('services:read')}>
        <Disclosure summary="服务记录" lazy open={state.tab === 'formal-services'}>
          <ServiceRecordsPage />
        </Disclosure>
      </Show>
    </div>
  )
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
  if (state.page === 'knowledge') return <KnowledgePage />
  if (state.page === 'medication') {
    switch (activeTab()) {
      case 'medication-list':
        return <MedicationListForm />
      case 'case-files':
        return <CaseFilePage />
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
  switch (activeTab()) {
    case 'adherence':
      return <AdherencePage />
    case 'meds':
      return <MedicationPage />
    case 'authorizations':
      return <AuthorizationsPage />
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
  onSettled(rememberMedicationPage)
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
        <Tabs aria-label="当前页面功能" items={pageTabs()} current={activeTab()} onSelect={changeTab} />
      </Show>
      {tabContent()}
    </div>
  )
}
