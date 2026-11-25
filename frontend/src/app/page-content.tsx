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
import { AdherencePage } from '../features/questionnaire/adherence-page'
import { ReminderPage } from '../features/reminders/reminder-page'
import { ReportPage } from '../features/report/report-page'
import { SchedulePage } from '../features/schedule/schedule-page'
import { AuthorizationsPage } from '../features/services/authorizations-page'
import { SupportPage } from '../features/support/support-page'
import { TaskPage } from '../features/tasks/task-page'
import { changeTab, navigate, rememberPage } from '../session/navigation'
import { isDemoAdmin, scope, state } from '../session/session'
import { Tabs } from '../ui/tabs'
import { Heading, Subheading } from '../ui/typography'
import { pageTabs } from './pages'

const titles: Record<Page, string> = {
  home: '今天，从一件小事开始',
  medication: '用药管理',
  knowledge: '药学知识',
  support: '支持服务',
  profile: '我的',
}
function tabContent(): JSX.Element {
  if (state.page === 'support') {
    return state.tab === 'peer' ? <PeerSupportPage /> : <SupportPage />
  }
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
    switch (state.tab) {
      case 'medication-list':
        return <MedicationListForm />
      case 'case-files':
        return <CaseFilePage />
      case 'reminders':
        return (
          <>
            <ReminderPage />
            <Subheading>提醒执行记录</Subheading>
            <TaskPage />
          </>
        )
      default:
        return (
          <>
            <SchedulePage />
            <Subheading>服药记录</Subheading>
            <EventListPage />
          </>
        )
    }
  }
  switch (state.tab) {
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
  onSettled(rememberPage)
  return (
    <div class="space-y-6">
      <Heading>{titles[state.page]}</Heading>
      <Show when={state.page === 'support' && (scope('support:read') || scope('peer:read'))}>
        <Tabs
          aria-label="支持服务功能"
          items={[
            ['overview', '支持对话'],
            ...(scope('peer:read') ? [['peer', '匿名同辈'] satisfies [string, string]] : []),
          ]}
          current={state.tab === 'peer' ? 'peer' : 'overview'}
          onSelect={key => navigate('support', key === 'overview' ? undefined : key)}
        />
      </Show>
      <Show when={state.patient && (state.page === 'medication' || state.page === 'profile')}>
        <Tabs aria-label="当前页面功能" items={pageTabs(state.page)} current={state.tab} onSelect={changeTab} />
      </Show>
      {tabContent()}
    </div>
  )
}
