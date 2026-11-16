# A v0.2：B确认后的注册到期任务增量

2026-11-16，Asia/Shanghai。依据B_v0.1_确认清单.md及原B00/B01/B02不可变来源。A-v0.1保持有效，本文追加BX-03，不修改旧任务事实、旧迁移或原稿。

## 已确认增量

TaskKind新增expire_b_state；owner_module为B。TaskPayload增加BExpiryTaskPayload：session_id为ID、target_kind为ui_mode/invitation/suggestion、target_id为ID、expected_revision为正整数Version，均必填不可null，无调用方默认，字段B-0.1，由B5受控服务提供。仅调用注册B到期处理器，不能传任意命令/函数/URL。

UI目标的修订来自UIState.revision；邀请/建议来自B受控存储行内部revision（默认1，状态变化递增，不因此给既有JSON新增必填输出）。业务去重按患者/目标种类/目标ID/预期修订固定；旧任务不能覆盖后来用户选择，重复执行不产生多个ModeChange或失效事件。

复用A既有任务领取、3次/60秒安全重试、有效期/取消/授权重检、未知结果核查及持久化审计。到期状态和B历史由B处理器维护，A不独立改变模式/邀请事实；GET仅查询，不承担写入或另启调度。

未来A Meta.contract_version可标A-v0.2；原五种注册能力和O/A/B来源含义不变，C来源/能力尚未加入。具体长时间离线补偿/catch-up窗口按BU05待全流程确认，不凭本条造参数；没有实现任务或数据库。
