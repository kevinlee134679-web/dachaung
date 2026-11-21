import type { Issue } from '../../ui/data-display'
import type { JSX } from '@solidjs/web'
import * as v from 'valibot'
import { dateText } from '../../date/date'
import { IssueList } from '../../ui/data-display'
import { Subheading, Text } from '../../ui/typography'

export const issueSchema: v.GenericSchema<unknown, Issue> = v.union([
  v.string(),
  v.looseObject({
    message: v.exactOptional(v.nullable(v.string())),
    reason: v.exactOptional(v.nullable(v.string())),
    code: v.exactOptional(v.nullable(v.string())),
  }),
])

export interface Statistics {
  window_start: string
  window_end: string
  as_of: string
  patient_confirmed_count: number
  reported_not_taken_count: number
  postponed_count: number
  unconfirmed_evidence_count: number
  unknown_count: number
  planned_dose_count: number
  patient_confirmation_ratio: number | null
  is_simulated: boolean
  issues: Issue[]
}

export const statisticsSchema: v.GenericSchema<unknown, Statistics> = v.looseObject({
  window_start: v.string(),
  window_end: v.string(),
  as_of: v.string(),
  patient_confirmed_count: v.number(),
  reported_not_taken_count: v.number(),
  postponed_count: v.number(),
  unconfirmed_evidence_count: v.number(),
  unknown_count: v.number(),
  planned_dose_count: v.number(),
  patient_confirmation_ratio: v.nullable(v.number()),
  is_simulated: v.boolean(),
  issues: v.array(issueSchema),
})

export function StatisticsView(props: { statistics: Statistics | null | undefined; title?: string }): JSX.Element {
  return (
    <section class="space-y-4">
      <Subheading>{props.title ?? '五类用药记录'}</Subheading>
      {props.statistics ? (
        <>
          <Text>
            {dateText(props.statistics.window_start)} 至 {dateText(props.statistics.window_end)}（结束不含）；数据截止{' '}
            {dateText(props.statistics.as_of)}。
          </Text>
          <p>{props.statistics.is_simulated ? '演示数据' : '实际来源数据'}</p>
          <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm/6">
            <dt>本人确认已服</dt>
            <dd>{props.statistics.patient_confirmed_count}</dd>
            <dt>本人报告未服</dt>
            <dd>{props.statistics.reported_not_taken_count}</dd>
            <dt>暂时延迟</dt>
            <dd>{props.statistics.postponed_count}</dd>
            <dt>仅其他证据</dt>
            <dd>{props.statistics.unconfirmed_evidence_count}</dd>
            <dt>未知或待复核</dt>
            <dd>{props.statistics.unknown_count}</dd>
          </dl>
          <p>
            有效已到时计划时段：{props.statistics.planned_dose_count}；本人确认比例：
            {props.statistics.patient_confirmation_ratio === null
              ? '暂不能计算'
              : `${(props.statistics.patient_confirmation_ratio * 100).toFixed(1)}%`}
            。
          </p>
          <Text>比例按后端本人已服/有效时段结果展示，不代表客观吞服率或CAS。家人、开盒、推断均不冒充本人已服。</Text>
          <IssueList issues={props.statistics.issues} />
        </>
      ) : (
        <p>当前没有可用统计，请查看来源不足说明。</p>
      )}
    </section>
  )
}
