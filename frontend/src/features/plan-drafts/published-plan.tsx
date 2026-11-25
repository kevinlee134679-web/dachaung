import type { Plan } from './drafts'
import type { JSX } from '@solidjs/web'
import { dateText, localDateTime } from '../../date/date'
import { Button } from '../../ui/button'
import { Text } from '../../ui/typography'
import { openScheduleDay } from '../schedule/schedule-page'

export function PublishedPlan(props: { plan: Plan }): JSX.Element {
  return (
    <div class="space-y-2">
      <Text>
        正式计划第 {props.plan.plan_version} 版 · {dateText(props.plan.effective_from)} 生效
      </Text>
      <Button onAction={() => openScheduleDay(localDateTime(props.plan.effective_from).slice(0, 10))}>查看安排</Button>
    </div>
  )
}
