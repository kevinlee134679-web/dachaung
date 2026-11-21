import * as v from 'valibot'

export const rewardAvailability: Record<string, string> = {
  available: '可兑换',
  unavailable: '暂不可用',
  unknown: '条件待核查',
}

export const fulfillmentStatus: Record<string, string> = {
  pending: '等待模拟履约',
  in_progress: '模拟履约处理中',
  completed: '已确认模拟交付',
  failed: '已确认未交付',
  cancelled: '已确认取消且未交付',
  outcome_unknown: '交付结果未知，请先核查原订单',
}

export interface Reward {
  reward_id: string
  reward_version: string
  name: string
  description: string
  points_cost: number
  availability: string
  kind: string
  resource_id: string | null
}

export interface Order {
  redemption_id: string
  reward_name: string
  points_status: string
  points_spent: number
  status: string
  refund_ledger_id: string | null
  debit_ledger_id: string
}

export interface Delivery {
  status: string
  failure_reason: string | null
  task_id: string | null
  artifact: { text: string } | null
  service_id: string | null
}

export interface Resource {
  resource_id: string
  resource_version: string
  provider: { display_name: string }
  required_shared_categories: string[]
}

export interface Account {
  balance: number
  meta: { revision: number }
}

export interface Checkout {
  reward_id: string
  reward_version: string
  expected_account_revision: number
  confirmed: boolean
  service_draft_id?: string
  draft_revision?: number
  confirmation_ref_id?: string
  sharing_scope_ref_id?: string
}

export const rewardSchema: v.GenericSchema<unknown, Reward> = v.looseObject({
  reward_id: v.string(),
  reward_version: v.string(),
  name: v.string(),
  description: v.string(),
  points_cost: v.number(),
  availability: v.string(),
  kind: v.string(),
  resource_id: v.nullable(v.string()),
})

export const orderSchema: v.GenericSchema<unknown, Order> = v.looseObject({
  redemption_id: v.string(),
  reward_name: v.string(),
  points_status: v.string(),
  points_spent: v.number(),
  status: v.string(),
  refund_ledger_id: v.nullable(v.string()),
  debit_ledger_id: v.string(),
})

export const deliverySchema: v.GenericSchema<unknown, Delivery> = v.looseObject({
  status: v.string(),
  failure_reason: v.nullable(v.string()),
  task_id: v.nullable(v.string()),
  artifact: v.nullable(v.looseObject({ text: v.string() })),
  service_id: v.nullable(v.string()),
})

export const resourceSchema: v.GenericSchema<unknown, Resource> = v.looseObject({
  resource_id: v.string(),
  resource_version: v.string(),
  provider: v.looseObject({ display_name: v.string() }),
  required_shared_categories: v.array(v.string()),
})

export const accountSchema: v.GenericSchema<unknown, Account> = v.looseObject({
  balance: v.number(),
  meta: v.looseObject({ revision: v.number() }),
})

export interface ServiceConfirmation {
  service_draft_id: string
  draft_revision: number
  confirmation_ref_id: string
  sharing_scope_ref_id: string
}

export const checkoutSchema: v.GenericSchema<unknown, Checkout> = v.looseObject({
  reward_id: v.string(),
  reward_version: v.string(),
  expected_account_revision: v.number(),
  confirmed: v.boolean(),
  service_draft_id: v.exactOptional(v.string()),
  draft_revision: v.exactOptional(v.number()),
  confirmation_ref_id: v.exactOptional(v.string()),
  sharing_scope_ref_id: v.exactOptional(v.string()),
})

export function saveRewardText(artifact: { text: string }): void {
  const url = URL.createObjectURL(new Blob([artifact.text], { type: 'text/plain;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = '模拟管理资料.txt'
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
