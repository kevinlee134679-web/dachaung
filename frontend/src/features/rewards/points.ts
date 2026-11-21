import type { View } from '../../session/session'
import type { RangeReader } from '../../ui/range-controls'
import * as v from 'valibot'
import { api } from '../../api/api'
import { rangeQuery } from '../../api/query'
import { requireCurrentView } from '../../session/session'

export const pointLabels: Record<string, string> = {
  daily_record: '每日有效手动记录',
  five_day_block: '连续五个合格日',
  weekly_review: '每周管理回顾',
  peer_participation: '经审核可见的同辈参与',
}

export const pointSourceLabels: Record<string, string> = {
  event: 'A 服药情况报告',
  management_review: 'C 本人管理回顾',
  peer_post: 'C 本人同辈参与',
  redemption: 'C 兑换订单',
}

export const ledgerKindLabels: Record<string, string> = {
  redemption_debit: '自愿兑换扣减',
  redemption_refund: '未交付全额退分',
}

export interface PointRules {
  rules_version: string
  rules: { rule_code: string; points: number; eligibility_description: string }[]
}

export const pointRulesSchema: v.GenericSchema<unknown, PointRules> = v.looseObject({
  rules_version: v.string(),
  rules: v.array(v.looseObject({ rule_code: v.string(), points: v.number(), eligibility_description: v.string() })),
})

export interface LedgerEntry {
  entry_kind: string
  rule_code: string | null
  delta: number
  created_at: string
  balance_after: number
  rules_version: string | null
  source_refs: { record_kind: string; module: string; version: string; recorded_at: string; record_id: string }[]
}

export interface Review {
  week_start: string
  completed_at: string
  reflection: string | null
}

export const ledgerEntrySchema: v.GenericSchema<unknown, LedgerEntry> = v.looseObject({
  entry_kind: v.string(),
  rule_code: v.nullable(v.string()),
  delta: v.number(),
  created_at: v.string(),
  balance_after: v.number(),
  rules_version: v.nullable(v.string()),
  source_refs: v.array(
    v.looseObject({
      record_kind: v.string(),
      module: v.string(),
      version: v.string(),
      recorded_at: v.string(),
      record_id: v.string(),
    }),
  ),
})

export const reviewSchema: v.GenericSchema<unknown, Review> = v.looseObject({
  week_start: v.string(),
  completed_at: v.string(),
  reflection: v.nullable(v.string()),
})

export function pointsRange(range: RangeReader): { window_start: string; window_end: string } {
  const { window_start, window_end } = range.read()
  return { window_start, window_end }
}

export function localReviewWeek(timezone: string): string {
  const today = new Intl.DateTimeFormat('sv-SE', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
  const start = new Date(`${today}T00:00:00Z`)
  start.setUTCDate(start.getUTCDate() - ((start.getUTCDay() + 6) % 7))
  return start.toISOString().slice(0, 10)
}

export async function reviewForCurrentWeek(path: string, week: string, view: View): Promise<Review | undefined> {
  const monday = new Date(`${week}T00:00:00Z`).getTime()
  const query = {
    window_start: new Date(monday - 86400000).toISOString(),
    window_end: new Date(monday + 8 * 86400000).toISOString(),
    limit: 10,
  }
  const page = await api(
    `${path}/management-reviews?${rangeQuery(query)}`,
    v.looseObject({ items: v.array(reviewSchema) }),
    'GET',
    null,
    view,
  )
  requireCurrentView(view)
  return page.items.find(item => item.week_start === week)
}
