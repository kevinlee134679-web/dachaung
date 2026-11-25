export const missedReasonLabels = {
  forgot: '忘记了',
  not_with_me: '药不在身边',
  ran_out: '药吃完了',
  unwell_or_side_effects: '身体不适或担心副作用',
  not_needed: '觉得不需要',
  other: '其他',
} as const

const statusLabels: Record<string, string> = {
  editing: '编辑中',
  pending_confirmation: '等待本人核对',
  confirmed: '已取得正式计划引用',
  returned: '需修改资料',
  active: '有效',
  revoked: '已撤销',
  expired: '已到期',
  taken: '报告已服',
  not_taken: '报告未服',
  postponed: '暂时延迟',
  unknown: '未知或待复核',
  box_opened: '观察到开盒',
  inferred_intake: '设备推测服药',
  pending_validation: '待校验',
  valid: '技术校验通过',
  needs_review: '需复核',
  processing_failed: '处理失败',
  effective: '当前有效',
  withdrawn: '已撤销证据',
  unmatched: '未匹配',
  matched: '已关联时段',
  review_required: '关联待复核',
  not_applicable: '不适用',
  pending: '待执行',
  running: '执行中',
  retry_wait: '等待安全重试',
  succeeded: '执行成功',
  completed: '执行完成',
  failed: '未能完成',
  cancelled: '已取消',
  outcome_unknown: '结果未知，须先核查',
  submitted: '已提交投递',
  delivered: '渠道回执已送达',
  not_computable: '暂不能计算',
  insufficient: '资料不足',
  available: '可用',
  not_collected: '未采集',
  unavailable: '不可用',
  restricted: '当前权限受限',
}

export function labelFor(value: string | null | undefined): string {
  return value === null || value === undefined || value === '' ? '未提供' : (statusLabels[value] ?? value)
}

export function statusTone(value: string | null | undefined): 'zinc' | 'teal' | 'amber' | 'red' {
  if (value == null) return 'zinc'
  if (
    [
      'active',
      'confirmed',
      'valid',
      'effective',
      'succeeded',
      'completed',
      'delivered',
      'available',
      'matched',
      'taken',
      'inferred_intake',
    ].includes(value)
  ) {
    return 'teal'
  }
  if (
    [
      'pending',
      'pending_confirmation',
      'pending_validation',
      'needs_review',
      'review_required',
      'retry_wait',
      'editing',
      'running',
      'postponed',
      'box_opened',
      'insufficient',
      'restricted',
    ].includes(value)
  ) {
    return 'amber'
  }
  if (['failed', 'processing_failed', 'outcome_unknown', 'returned', 'not_taken', 'unavailable'].includes(value)) {
    return 'red'
  }
  return 'zinc'
}
