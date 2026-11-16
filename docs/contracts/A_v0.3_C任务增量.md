# A v0.3：C确认后的公共任务增量

2026-11-16，Asia/Shanghai。依据用户“确认C”、C_v0.1_确认清单.md及CQ14/CX-A01。A-v0.1/v0.2继续有效，追加注册能力，不改旧任务或迁移。

## 1 枚举与维护方

TaskCreateInput.owner_module、Task.owner_module新增C，仅可信C服务可提供。TaskKind新增dispatch_service、fulfill_reward，分别调用C的服务派发/权益交付处理器；共用A持久化任务、领取、执行、回执与取消机制，不建第二套调度，不接受任意函数、命令、URL或模型指令。

## 2 已确认载荷

以下均必填不可null，无调用方默认，字段版本C-0.1，由可信C业务提供，A按kind验证；公共ID/Version类型继续沿用。

| 载荷 | 字段 | 类型 | 语义 |
| --- | --- | --- | --- |
| ServiceDispatchTaskPayload | service_id | ID | C唯一正式服务 |
| ServiceDispatchTaskPayload | service_revision | Version | C服务精确资源修订 |
| ServiceDispatchTaskPayload | confirmation_ref_id | ID | C有效服务确认 |
| ServiceDispatchTaskPayload | sharing_scope_ref_id | ID | O权威范围，执行前再次核验 |
| RewardFulfillmentTaskPayload | redemption_id | ID | C独立兑换 |
| RewardFulfillmentTaskPayload | fulfillment_id | ID | 该兑换的交付事实 |
| RewardFulfillmentTaskPayload | reward_id | ID | 实际权益 |
| RewardFulfillmentTaskPayload | reward_version | string | 兑换时精确目录版本，不取浮动当前价 |

患者/环境/关联服务必须与任务一致。去重仍用已确认owner_module+owner_operation_key和业务唯一事实，不能靠更换任务ID重复申请、扣分、退分或交付。服务状态由C维护，A succeeded仅说明注册处理器本次完成，不代表服务完成/患者收到。

## 3 执行限制与版本

复用A最多3次、可安全重试间隔60秒、未知先核查、执行前重验授权/取消/有效期、终态晚回执不复活等既有规则。C处理器按C唯一服务/兑换状态执行；过期确认不自动续签，真实服务/渠道未接入拒绝，不冒充模拟成功。

精确任务时效、离线补偿、同库事件通知及领取细节留全流程草案，不在本登记增加未提出的数值。积分核奖先沿用C显式入口/有效来源触发，不因此新建任意改余额任务。

未来A Meta.contract_version采用A-v0.3；原任务/载荷兼容保留。没有应用/任务实现或数据库迁移，不授权S01。
