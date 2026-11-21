import * as v from 'valibot'
import { labelFor } from '../../ui/labels'

export const formalServiceStates: Record<string, string> = {
  submitted: '已提交',
  in_progress: '模拟处理中',
  completed: '模拟完成',
  cancelled: '已取消',
  failed: '处理失败',
}

export interface DispatchTask {
  status: string
  kind: string
  meta: { revision: number }
}

export interface DispatchAttempt {
  attempt: number
  execution_status: string
  delivery_status: string
}

export const dispatchTaskSchema: v.GenericSchema<unknown, DispatchTask> = v.looseObject({
  status: v.string(),
  kind: v.string(),
  meta: v.looseObject({ revision: v.number() }),
})
export const dispatchAttemptSchema: v.GenericSchema<unknown, DispatchAttempt> = v.looseObject({
  attempt: v.number(),
  execution_status: v.string(),
  delivery_status: v.string(),
})

export function dispatchDescription(task: DispatchTask, attempt: DispatchAttempt | undefined): string {
  if (attempt?.execution_status === 'outcome_unknown') return '原派发结果未知，请核对原任务及后续回执。'
  if (task.status === 'succeeded' && attempt?.delivery_status === 'submitted')
    return '模拟派发已登记，服务状态请见上方。'
  const labels: Record<string, string> = {
    pending: '等待模拟派发',
    retry_wait: '模拟派发明确失败，等待安全重试',
    running: '模拟派发待核实',
    cancelled: '原派发已停止',
    expired: '派发授权已过期',
    failed: '模拟派发失败',
  }
  const label = labels[task.status]
  return label !== undefined && label !== '' ? label : labelFor(task.status)
}
