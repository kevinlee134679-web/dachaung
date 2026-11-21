import type { View } from '../../session/session'
import type { Review } from './points'
import type { JSX } from '@solidjs/web'
import { createMemo, createSignal, onSettled, Show } from 'solid-js'
import { api, sha } from '../../api/api'
import { dateText } from '../../date/date'
import { actionError, notice } from '../../notice/notice'
import { isCurrentView, requireCurrentView, ViewChanged } from '../../session/session'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { confirm } from '../../ui/confirm'
import { Checkbox, Field, Textarea } from '../../ui/form'
import { Text } from '../../ui/typography'
import { localReviewWeek, reviewForCurrentWeek, reviewSchema } from './points'

export function ManagementReview(props: { path: string; timezone: string; view: View }): JSX.Element {
  const week = createMemo(() => localReviewWeek(props.timezone))
  const [saved, setSaved] = createSignal<Review | undefined>()
  let reflection!: HTMLTextAreaElement
  let confirmed!: HTMLInputElement
  onSettled(() => {
    void reviewForCurrentWeek(props.path, week(), props.view)
      .then(review => {
        requireCurrentView(props.view)
        setSaved(review)
      })
      .catch((error: unknown) => {
        if (!(error instanceof ViewChanged) && isCurrentView(props.view)) actionError(error, props.view)
      })
  })
  return (
    <Card title="每周管理回顾">
      <div class="space-y-4">
        <Text>当周起始日 {week()} · 演示</Text>
        <Show
          when={saved()}
          fallback={
            <div class="space-y-4">
              <Field label="回顾内容（可留空）">
                <Textarea ref={reflection} maxlength={2000} rows={3} />
              </Field>
              <Checkbox ref={confirmed} label="我已完成本周管理回顾" />
              <Button
                variant="primary"
                view={props.view}
                onAction={async view => {
                  if (!confirmed.checked) throw new Error('请本人明确确认已完成本周回顾。')
                  if (!(await confirm('确认记录本周管理回顾？'))) return
                  requireCurrentView(view)
                  const draft = {
                    week_start: week(),
                    reflection: reflection.value.trim() || null,
                    confirmed_completed: true,
                  }
                  const key = `points-review:${view.accountId}:${view.patientId}:${await sha(JSON.stringify(draft))}`
                  requireCurrentView(view)
                  let submission = sessionStorage.getItem(key)
                  if (submission === null || submission === '') {
                    submission = crypto.randomUUID()
                    sessionStorage.setItem(key, submission)
                  }
                  try {
                    const review = await api(
                      `${props.path}/management-reviews`,
                      reviewSchema,
                      'POST',
                      { client_review_id: submission, ...draft },
                      view,
                    )
                    requireCurrentView(view)
                    sessionStorage.removeItem(key)
                    setSaved(review)
                    notice('已保存回顾。积分余额会在核验入账后更新。')
                  } catch (error) {
                    if (error instanceof ViewChanged) throw error
                    const review = await reviewForCurrentWeek(props.path, week(), view)
                    requireCurrentView(view)
                    if (!review) throw error
                    sessionStorage.removeItem(key)
                    setSaved(review)
                  }
                }}
              >
                确认完成本周回顾
              </Button>
            </div>
          }
        >
          {review => (
            <div aria-live="polite">
              <p>已记录本周回顾 · {dateText(review().completed_at)}</p>
              <Show when={review().reflection}>
                <p>{review().reflection}</p>
              </Show>
            </div>
          )}
        </Show>
      </div>
    </Card>
  )
}
