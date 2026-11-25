import type { View } from '../../session/session'
import type { RangeReader } from '../../ui/range-controls'
import type { Statistics } from '../statistics/statistics'
import type { JSX } from '@solidjs/web'
import { createSignal, For, Show } from 'solid-js'
import * as v from 'valibot'
import { ApiError, all, api } from '../../api/api'
import { rangeQuery } from '../../api/query'
import { localDateTime } from '../../date/date'
import { notice } from '../../notice/notice'
import { readGate } from '../../session/read-gate'
import { captureView, patientPath, scope } from '../../session/session'
import { StatusBadge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { DataTable, IssueList } from '../../ui/data-display'
import { Disclosure } from '../../ui/disclosure'
import { RangeControls } from '../../ui/range-controls'
import { Subheading, Text } from '../../ui/typography'
import { feedbackProjectionSchema } from '../services/feedback/feedback'
import { CFeedbackProjection } from '../services/feedback/feedback-projection'
import { issueSchema, statisticsSchema, StatisticsView } from '../statistics/statistics'

const summarySchema = v.looseObject({
  record_overview: v.nullable(statisticsSchema),
  feedback_overview: v.looseObject({
    sources: v.array(
      v.union([
        v.looseObject({ source_module: v.literal('B'), availability: v.string(), reason: v.nullable(v.string()) }),
        v.intersect([
          v.looseObject({ source_module: v.literal('C'), reason: v.nullable(v.string()) }),
          feedbackProjectionSchema,
        ]),
      ]),
    ),
  }),
  missing_items: v.array(issueSchema),
})
type Summary = v.InferOutput<typeof summarySchema>
const matchSchema = v.looseObject({ event_id: v.string(), link_status: v.string(), reason: v.nullable(v.string()) })
type Match = v.InferOutput<typeof matchSchema>

function SummaryView(props: { summary: Summary }): JSX.Element {
  return (
    <section class="space-y-4">
      <Subheading>近期状态摘要</Subheading>
      <StatisticsView statistics={props.summary.record_overview} />
      <For each={props.summary.feedback_overview.sources}>
        {source =>
          source.source_module === 'C' ? (
            <CFeedbackProjection source={source} />
          ) : (
            <p>
              {source.source_module}反馈：
              <StatusBadge status={source.availability} />
              {source.reason != null && source.reason !== '' ? ` · ${source.reason}` : ''}
            </p>
          )
        }
      </For>
      <IssueList issues={props.summary.missing_items} />
    </section>
  )
}

export function ReportPage(): JSX.Element {
  let range!: RangeReader
  const beginRead = readGate()
  const [loading, setLoading] = createSignal('')
  const [summary, setSummary] = createSignal<Summary | null>(null)
  const [statistics, setStatistics] = createSignal<Statistics | null>(null)
  const [trend, setTrend] = createSignal<Statistics[] | null>(null)
  const [matches, setMatches] = createSignal<Match[] | null>(null)
  const [errorMessage, setErrorMessage] = createSignal('')
  const [displayed, setDisplayed] = createSignal(false)

  async function show(refresh: boolean, view: View): Promise<void> {
    const ensure = beginRead()
    const selectedRange = range.read()
    setLoading(refresh ? '正在刷新统计与摘要…' : '正在读取报告…')
    setSummary(null)
    setStatistics(null)
    setTrend(null)
    setMatches(null)
    setErrorMessage('')
    setDisplayed(false)
    try {
      const result = scope('summary:read')
        ? await api(patientPath(`/summary?${rangeQuery({ ...selectedRange })}`), summarySchema, 'GET', null, view)
        : null
      ensure()
      const cutoff = result?.record_overview?.as_of
      const counts = scope('statistics:read')
        ? await api(
            `${patientPath('/medication-statistics')}?${rangeQuery({ ...selectedRange, ...(cutoff != null && cutoff !== '' ? { as_of: cutoff } : {}) })}`,
            statisticsSchema,
            'GET',
            null,
            view,
          )
        : null
      ensure()
      const asOf = cutoff != null && cutoff !== '' ? cutoff : counts?.as_of
      const reportQuery = { ...selectedRange, ...(asOf != null && asOf !== '' ? { as_of: asOf } : {}) }
      setSummary(result)
      setStatistics(counts)
      setLoading('')
      setDisplayed(true)
      if (scope('statistics:read') && reportQuery.as_of != null && reportQuery.as_of !== '') {
        const resultTrend = await api(
          `${patientPath('/medication-trends')}?${rangeQuery({ ...reportQuery })}`,
          v.looseObject({ items: v.array(statisticsSchema) }),
          'GET',
          null,
          view,
        )
        ensure()
        setTrend(resultTrend.items)
      }
      if (scope('statistics:read') && scope('records:read')) {
        const resultMatches = await all(
          `${patientPath('/dose-matches')}?${rangeQuery({ ...reportQuery })}`,
          matchSchema,
          view,
        )
        ensure()
        setMatches(resultMatches)
      }
      ensure()
      notice(refresh ? '已刷新统计与摘要。' : '')
    } catch (error) {
      ensure()
      setLoading('')
      setErrorMessage(
        error instanceof ApiError && error.status === 409
          ? '此范围的时段窗口尚未维护，请先维护正式时段；不能将未就绪当成0计划。'
          : error instanceof Error
            ? error.message
            : String(error),
      )
      throw error
    }
  }

  async function readReport(view: View): Promise<void> {
    await show(false, view)
  }

  async function refreshReport(view: View): Promise<void> {
    await show(true, view)
  }

  return (
    <Show when={scope('statistics:read') || scope('summary:read')} fallback={<p>当前未获报告查看权限。</p>}>
      <Card title="同一窗口、同一截止时间的报告">
        <div class="space-y-6">
          <Text>报告按当前数据计算，统计、趋势和关联查询使用相同的截止时间。</Text>
          <RangeControls
            ref={reader => {
              range = reader
              const view = captureView()
              void show(false, view).catch(() => undefined)
            }}
          />
          <div class="flex flex-wrap gap-3">
            <Button onAction={readReport}>读取报告</Button>
            <Button variant="primary" onAction={refreshReport}>
              明确刷新统计与摘要
            </Button>
          </div>
          <Show when={loading()}>
            <p>{loading()}</p>
          </Show>
          <Show when={displayed()}>
            <Show
              when={summary()}
              keyed
              fallback={
                <Show when={statistics()} keyed fallback={<p>当前无可读取的统计。</p>}>
                  {value => <StatisticsView statistics={value} />}
                </Show>
              }
            >
              {value => <SummaryView summary={value} />}
            </Show>
            <Show when={trend()} keyed>
              {rows => (
                <>
                  <Subheading>按日统计（使用相同截止时间）</Subheading>
                  <DataTable
                    headers={['日期', '本人已服', '本人未服', '延期', '其他证据', '未知', '有效时段', '确认比例']}
                    rows={rows.map(row => [
                      localDateTime(row.window_start).slice(0, 10),
                      row.patient_confirmed_count,
                      row.reported_not_taken_count,
                      row.postponed_count,
                      row.unconfirmed_evidence_count,
                      row.unknown_count,
                      row.planned_dose_count,
                      row.patient_confirmation_ratio === null
                        ? '—'
                        : `${(row.patient_confirmation_ratio * 100).toFixed(1)}%`,
                    ])}
                  />
                  <Text>总比例直接使用后端汇总，不平均每日百分比。</Text>
                </>
              )}
            </Show>
            <Show when={matches()} keyed>
              {rows => (
                <Disclosure summary="关联与未匹配原因">
                  <For each={rows} fallback={<p>此窗口没有关联记录。</p>}>
                    {match => (
                      <p>
                        {match.event_id}：
                        <StatusBadge status={match.link_status} />
                        {match.reason !== null && match.reason !== '' ? `；${match.reason}` : ''}
                      </p>
                    )}
                  </For>
                </Disclosure>
              )}
            </Show>
          </Show>
          <Show when={errorMessage()}>
            <p class="text-sm/6 text-red-600 dark:text-red-400">{errorMessage()}</p>
          </Show>
        </div>
      </Card>
    </Show>
  )
}
