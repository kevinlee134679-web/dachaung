export const evidenceLabels: Record<string, string> = {
  self_report: '本人报告',
  family_report: '家人报告（不计入本人已服）',
  box_opening: '开盒证据（不证明已服）',
  device_inference: '设备推断（不证明已服）',
}

export const taskLabels: Record<string, string> = {
  refresh_statistics: '更新统计',
  refresh_summary: '更新摘要',
  deliver_reminder: '应用内提醒',
  check_in_node: 'B检查（未接入）',
  deliver_intervention: 'B投递（未接入）',
}
