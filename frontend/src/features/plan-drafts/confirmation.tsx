import type { View } from '../../session/session'
import type { Draft, Plan } from './drafts'
import type { JSX } from '@solidjs/web'
import { createMemo, For } from 'solid-js'
import { dateText } from '../../date/date'
import { notice } from '../../notice/notice'
import { requireCurrentView } from '../../session/session'
import { Button } from '../../ui/button'
import { Disclosure } from '../../ui/disclosure'
import { Checkbox, Field, Input, Select } from '../../ui/form'
import { confirmPlan } from './drafts'

export function Confirmation(props: {
  draft: Draft
  plans: Plan[]
  saved: (view: View) => Promise<void>
}): JSX.Element {
  let effective!: HTMLInputElement
  let target!: HTMLSelectElement
  let yes!: HTMLInputElement
  const uniquePlans = createMemo(() => [...new Map(props.plans.map(plan => [plan.plan_id, plan])).values()])
  async function confirm(view: View): Promise<void> {
    if (!yes.checked || !effective.value) throw new Error('请填写生效时间并明确确认资料。')
    const previous = props.plans
      .filter(plan => plan.plan_id === target.value)
      .sort((a, b) => b.plan_version - a.plan_version)[0]
    await confirmPlan(view, props.draft, previous ?? null, new Date(`${effective.value}:00+08:00`).toISOString())
    await props.saved(view)
    requireCurrentView(view)
    notice('正式计划、草稿引用和时段已共同保存。')
  }
  return (
    <Disclosure summary="核对并发布正式计划">
      <Field label="生效时间（北京时间，当前或未来）">
        <Input ref={effective} type="datetime-local" />
      </Field>
      <Field label="新计划或更新已有计划">
        <Select ref={target}>
          <option value="">建立新计划</option>
          <For each={uniquePlans()}>
            {plan => (
              <option value={plan.plan_id}>
                更新计划 · 第{plan.plan_version}版 · {dateText(plan.effective_from)}
              </option>
            )}
          </For>
        </Select>
      </Field>
      <Checkbox ref={yes} label="我已核对原资料与此修订；这不是医院或药师审核，医嘱变更需先咨询专业人员。" />
      <Button variant="primary" onAction={confirm}>
        明确确认并发布
      </Button>
    </Disclosure>
  )
}
