import type { Page } from '../session/session'
import { canManageMedicationList } from '../features/plan-drafts/medication-list'
import { isDemoAdmin, scope } from '../session/session'

export function pageTabs(page: Page): [string, string][] {
  if (page === 'medication') {
    return [
      ['overview', '今日用药情况'],
      ...(canManageMedicationList() ? [['medication-list', '用药清单'] satisfies [string, string]] : []),
      ...(scope('files:read') || scope('files:write') || scope('drafts:read')
        ? [['case-files', '病例资料'] satisfies [string, string]]
        : []),
      ['reminders', '提醒设置'],
    ]
  }
  if (page === 'support')
    return [['overview', '支持对话'], ...(scope('peer:read') ? [['peer', '匿名同辈'] satisfies [string, string]] : [])]
  if (page !== 'profile') return [['overview', '']]
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
