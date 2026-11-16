# B v0.2：C确认后的服务代理映射增量

2026-11-16，Asia/Shanghai。依据用户“确认C”、C_v0.1_确认清单.md及CQ13/CQ-BC01；解决B-v0.1的BU04/BCX-01中已明确部分。原B三稿及v0.1保持不变。

## 1 B23请求增量（已确认）

POST /api/v1/referrals的ReferralCreateInput新增service_draft_revision:Version，R/N、无默认，正整数，调用方引用C ServiceDraft.draft_revision，字段B-0.2。已有patient_id、session_id、resource_id、service_draft_id、confirmation_ref_id、sharing_scope_ref_id均R/N；source_suggestion_id仍O/Y，默认null；其余完整定义继承B01。新增字段不是B.meta.revision、不是A.content_revision，也不能省略后读取最新草稿。

B核验会话/建议/资源/确认/范围归属，映射C ServiceCreateInput如下：

| B输入 | C字段 | 约束 |
| --- | --- | --- |
| service_draft_id | service_draft_id | 相同患者的C草稿 |
| service_draft_revision | draft_revision | 用户核对的精确内容修订 |
| confirmation_ref_id | confirmation_ref_id | C服务确认仍有效 |
| sharing_scope_ref_id | sharing_scope_ref_id | O权威范围与确认一致且有效 |

C唯一创建Service；B只维护referral_id→service_id的代理映射。patient+草稿ID+精确修订为C业务唯一事实，直接C07与B23重复调用不能产生两份申请。相同有效确认复用，主体/范围变更重新确认。接口权限、完整Referral返回、201成功例及503未接入失败例继承B23/C07；缺少新必填字段422，旧草稿/版本冲突409，未接入仍503，不自建另一服务。

请求最小结构示例（虚构、未运行）：

```json
{
  "patient_id": "p-demo-001",
  "session_id": "session-demo-001",
  "source_suggestion_id": "suggestion-professional-demo-001",
  "resource_id": "resource-demo-001",
  "service_draft_id": "service-draft-demo-001",
  "service_draft_revision": 1,
  "confirmation_ref_id": "confirmation-demo-001",
  "sharing_scope_ref_id": "sharing-demo-001"
}
```

## 2 B27来源版本（已确认）

POST /api/v1/integrations/referral-receipts的source_version仍string R/N、无默认，值为C Service.meta.revision正整数的十进制字符串；service_id/patient_id必须等于已有可信映射。不能使用C草稿修订、request_id、时间或供应商版本替代，不作字符串字典序比较。

回执继续独立C身份、source_event_id去重、合法状态和终态不回退；同来源同号异内容冲突，未知先查C权威事实。B不能依据患者自报或一条不可信回执新增正式服务、恢复取消/过期申请或扩大共享。服务完成与患者反馈分开。

## 3 兼容与未决

本增量为已明确提出的请求必填变化；未来B23调用方必须同时升级，旧调用体不能静默补最新修订。当前没有部署应用/存量运行请求，因此无已执行数据迁移；未来如有存量，以明确记录精确C引用后迁移，不能猜测。

未来B Meta.contract_version采用B-v0.2；其他B字段/39卡、模型预算及权限不变。完整事务顺序、通知重试和断电恢复仍由全流程草案提出；BU01—BU03、BU05—BU07其余未决不自动解决，不授权S01。
