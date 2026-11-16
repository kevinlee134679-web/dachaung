# B v0.3：支持强度可用状态视图（局部确认增量）

2026-11-16，Asia/Shanghai。确认依据：用户在B15支持强度状态接口草案交付后回复“确认”。本次确认F05的IM01—IM05、完整字段/接口卡及明确失效/权限/兼容规则；不等于实际方法已适配，不确认其余FQ或授权S01/应用业务编码/付费API。

契约标识`B-v0.3`，新增字段版本`B-0.3`。B-v0.1/v0.2、deferred-v0.1及各自保留事项继续有效，原来源不改写。原F05中的intensity-view-draft01/待确认文字保留为历史，当前确认范围由本文界定。

## 1 不可变来源

| 来源 | 原字节SHA256 |
| --- | --- |
| docs/S00/F05_支持强度可用状态接口增量_draft01.md | d120e0897021b31ce06018734933855a184a5246b90ea753ab222da6e6378f8f |

本来源13515字节，与18证据一致；完整字段、递归引用、3个JSON例子和8个未运行案例一并作为确认依据。总Prompt v1.1及既有公共/O/A/B/C约束不被本增量覆盖。

## 2 已确认字段及兼容变化

保留B15 GET /api/v1/sessions/{s}/strategy。StrategyView原8字段session_id/patient_id/status/current_intervention/suggestions/invitations/ui_state/generated_at不变，新增intensity_mapping:IntensityMappingView，R/N、无默认，由B5生成。完整返回共9字段，无新增URL或方法，现有153卡不增计数。

IntensityMappingView完整8字段按F05第2节类型、R/N或R/Y、默认、范围、来源纳入B-0.3：

| 字段 | 类型/必填可空 | 明确语义 |
| --- | --- | --- |
| availability | string R/N | not_configured/disabled/insufficient/evaluated/failed；必须基于实际配置/结果，不能以依赖失败猜默认 |
| support_intensity | string R/Y | evaluated时必非null且none/low/moderate/high；其他状态必须null |
| method_version | string R/Y | 1—128字符，evaluated时实际启用版本必非null，无实际方法不造版本 |
| reason | Reason R/Y | 非evaluated必须非null，不泄露受限正文或内部思维链 |
| evidence_refs | EvidenceRef[] R/N | 默认[]；只返当前可访问引用/标签，原完整定义不变 |
| evaluated_at | DateTime R/N | 真实检查/计算时刻；未配置时只表示检查能力，不声称模型执行；GET不刷新既有计算时间 |
| is_simulated | boolean R/N | 实际适配/环境来源，不以单一模型标记替代身份/渠道来源 |
| valid_until | DateTime R/Y | evaluated必非null且晚于evaluated_at；≤原计算+15分钟且不超源有效期，其他状态按原来源可为null/过期边界 |

映射视图独立于可执行Intervention；**原Intervention.support_intensity仍必填不可null、原四值不变**。none表示已评估后无需额外干预，不能拿来表达未配置。内部IntensityMappingResult仍deferred-v0.1的7字段，本增量不静默向内部对象加valid_until。

## 3 已确认接口/状态/权限行为

| 原建议 | 现在确认的具体行为 |
| --- | --- |
| IM01 | StrategyView单列必填映射视图，前后端按新B契约同步升级；B15本身无Meta，不额外塞Meta/新版本字段 |
| IM02 | 正常读到未配置/关闭/不足/已保存失败时返回200四字段成功Envelope并明确状态；必要配置/存储不可读503 STRATEGY_UNAVAILABLE，不伪装not_configured/空列表/0分 |
| IM03 | GET只读取一致性快照和投影，不运行映射/模型/预算预留/任务/恢复写入；仍有效且同方法/输入版本才evaluated，旧结果失效投影insufficient，原记录保留 |
| IM04 | evaluated必须now<valid_until；now等于边界即失效；证据/输入/方法变化使旧结果失效，不因刷新延长15分钟有效期 |
| IM05 | 只阻止依赖未就绪映射的自动动作，聊天/主动模式/主动服务继续按原授权/确认工作；不抹掉患者需求，不复活旧方法执行或覆盖历史结果 |

本人或有效interventions:read才能读B15，底层证据/当前患者/环境仍分别核验。无底层权限不返回受限引用、标签或强度，允许最小insufficient说明；current_intervention等其他字段独立核权，旧Grant不扩权。原401/403/404/422及503错误继续有效；GET无新增查询/请求体/CSRF/幂等键，不能请求覆盖方法/强度。

展示evaluated不等于执行许可；实际动作重新检查方法、证据、有效期、授权及既有B/O/A/C业务规则。配置竞争无法取得一致视图时按原卡重读一次或明确503，不拼接不同方法数据。来源/历史/三种例子与完整卡继承原F05，不把mock例子当真实方法启用。

## 4 兼容、版本与未决

新增必填输出需要消费者同步升级，不能只改后端或向旧严格schema偷偷多塞字段。未来G02/版本登记可声明B-v0.3；StrategyView没有Meta，其他带Meta的B对象按适用契约标识，不修改旧JSON/旧结果版本来伪称当时已启用。

目前没有应用部署、业务库或存量调用，未执行数据迁移。未来旧结果无映射记录时按真实配置/输入返回not_configured或insufficient，不补造已评估结果；按deferred-v0.1保留新旧输入/方法/结果。具体表/索引/类名属于后续阶段实现设计，须满足既有输入快照/独立结果/版本/历史约束；若需要改变对外字段、业务状态或权限，则另提兼容增量。

deferred-v0.1的DU01中对外视图/字段/状态/样例/兼容由本次解决，DU02—DU05及U03/BU02实际方法/阈值/验证不变。F00—F03完整全流程、稍后提醒候选接口和B19模式投影仍未确认，本增量不混入它们。8项验收尚未运行，无应用业务代码/付费调用，不授权S01。
