# S00 全流程：增量字段、接口与验收（draft01）

2026-11-16，Asia/Shanghai。全部新增内容为**建议、待确认、未实现**，字段版本F-draft01。R/N=必须出现不可null，R/Y=必须出现可null，O/N=可省略但不可null，O/Y=可省略且可null。ID/Version/DateTime/Reason/Meta/Envelope/List完整复用已确认字段，不以例子替代定义。

本批没有生成应用/schema/迁移。以下内部对象是未来共用工程的持久化约束草案，不是可由浏览器任意写入的新API；不上传任何实际会话、绑定码、密钥或患者数据。

## 1 新增接口字段（FQ09，O业务/A执行）

### ReminderSnoozeInput

| 字段 | 类型 | 必填/可空 | 默认 | 格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| source_task_id | ID | R/N | 无 | 同患者、O来源、已执行且结果明确的in_app提醒任务；不接真实未知派发 | 网页引用可见提醒 |
| expected_task_revision | Version | R/N | 无 | 原任务meta.revision，旧页面不得替代当前状态 | 网页引用 |
| snooze_minutes | integer | R/N | 无 | 5—120分钟；只推迟通知，还需医嘱/下一时段/总提醒次数等限制 | 用户明确动作 |

输出不新建另一种Task，完整引用A01.Task的17字段及ReminderTaskPayload的3字段、Meta的5字段，采用确认后的相应契约版本。任务ID不当服药事件ID，不更新A服药状态。

### F-API01 稍后提醒（唯一新增候选路由）

| 项目 | 完整定义 |
| --- | --- |
| 用途/维护/页面 | 用户明确稍后收到当前通知；O5决定、A7保存执行；首页/用药提醒详情 |
| 方法/路径 | POST /api/v1/patients/{p}/reminder-snoozes |
| 身份/患者范围 | 本人或有效reminder:write家人；原任务/时段/计划/环境均属该患者，家人不扩大共享/通知范围 |
| 路径 | patient_id:ID R/N，无默认 |
| 查询 | 无；未知查询422 |
| 请求头 | Cookie/X-CSRF-Token/Idempotency-Key/Content-Type按公共完整定义；同源写请求，JSON |
| 请求体 | ReminderSnoozeInput完整3字段；未列属性422 |
| 成功返回 | HTTP 201 Envelope<Task>；自然键已有同一稍后任务可200；完整递归字段见上述引用及下例 |
| 失败 | 401未登录、403授权不足、404跨患者/不可见任务、422结构/范围错误、409 REVISION_CONFLICT或REMINDER_SNOOZE_NOT_ALLOWED、503 TASK_STORE_UNAVAILABLE；均四字段Envelope |
| 前置 | 原任务为明确结果的O in_app提醒，同slot仍正式有效且本次提醒未失效，当前配置仍允许；strict_timing未明确false或医嘱约束不满足时拒绝偏移，不猜可安全补服时间 |
| 幂等/唯一性 | 公共同键同内容/异内容/在途/过期规则；source_task_id+source_task_revision至多一个稍后子任务，不因换键反复排队；新子任务完成后再操作仍受每slot总3次上限 |
| 时效/非法行为 | 新scheduled_at=本次明确动作服务器now+snooze_minutes；必须早于原剂量scheduled_at+4小时及下一正式时段，valid_until取新通知时刻+30分钟与上述边界较早者；否则409，不静默裁剪 |
| 事务 | 核验身份/原任务修订/O偏好/slot有效性及预算→登记唯一稍后关联及次数→A新任务/回执同库提交；失败不消费次数或留半任务 |
| 来源/取消 | 只改通知安排，保留原任务/医嘱scheduled_at；payload引用原dose_slot_id和当前提醒修订。配置关闭/患者已明确处理该slot/计划替代或撤销时停止待发，不能因此推断已服 |
| 验收 | 同键/换键重复、两个并发动作、跨患者、旧修订、严格时间未知、超下一时段/4小时/3次、配置关闭、重启和回滚均实际验证后才称实现 |

请求结构示例（虚构、未运行）：

```json
{"source_task_id":"task-reminder-demo-001","expected_task_revision":2,"snooze_minutes":10}
```

成功结构示例（HTTP 201；时间固定仅用于解释，未执行）：

```json
{
  "request_id": "req-flow-snooze-001",
  "status": "success",
  "data": {
    "task_id": "task-snooze-demo-001",
    "patient_id": "p-demo-001",
    "kind": "deliver_reminder",
    "owner_module": "O",
    "owner_operation_key": "snooze:task-reminder-demo-001:2",
    "scheduled_at": "2026-11-16T00:15:00Z",
    "valid_until": "2026-11-16T00:45:00Z",
    "payload": {"dose_slot_id":"slot-demo-001","reminder_revision":1,"content_ref":"neutral-text-demo-001"},
    "intervention_id": null,
    "rule_version": "F-draft01",
    "status": "pending",
    "cancellation_requested": false,
    "attempt_count": 0,
    "max_attempts": 3,
    "next_attempt_at": null,
    "failure_reason": null,
    "meta": {
      "created_at": "2026-11-16T00:05:00Z",
      "updated_at": "2026-11-16T00:05:00Z",
      "revision": 1,
      "contract_version": "F-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{"request_id":"req-flow-snooze-002","status":"error","data":null,"error":{"code":"REMINDER_SNOOZE_NOT_ALLOWED","message":"当前提醒不满足稍后提醒的时效或次数条件，请查看原计划安排"}}
```

## 2 B19输出增量（FQ14，尚未确认）

原GET /api/v1/sessions/{s}/ui-mode仍由B5维护；页面聊天/模式栏；本人或interventions:read，患者归属/当前授权重验。路径session_id:ID R/N；query include_history:boolean O/N默认false、cursor/limit按公共规则；无体/CSRF/幂等键。完整成功Envelope<UIModeView>，失败继承B19的404及公共401/403/422/503；GET无写入/模型调用。

UIModeView原current:UIState R/N、changes:ModeChange[] R/N（默认[]）、next_cursor:string R/Y（默认null）不变；UIState与ModeChange逐字段继承B01原定义，不把本次投影写回原current。新增：

| 字段 | 类型 | 必填/可空 | 默认 | 格式/范围/语义 | 生成方/版本 |
| --- | --- | --- | --- | --- | --- |
| effective_ui_mode | string | R/N | 无 | normal/simplified；仅当current为simplified、会话active且evaluated_at<valid_until时为simplified，其余normal | B5读取时投影/F-draft01 |
| evaluated_at | DateTime | R/N | 无 | 服务器本次判断时刻，沿用demo可控时钟；不修改current.changed_at/revision | B5/F-draft01 |

过期current仍保存其原simplified/旧revision/valid_until，effective为normal；历史可能等待显式维护。B20模式写入先重验有效期/修订并执行受控状态更新，其原返回仍UIState，不偷偷改包裹类型。建议/邀请GET同样不能接受已经过期对象，write入口独立拒绝过期。

成功结构示例（HTTP 200；到期维护尚未运行，未执行）：

```json
{
  "request_id": "req-flow-mode-001",
  "status": "success",
  "data": {
    "current": {
      "session_id": "session-demo-001",
      "patient_id": "p-demo-001",
      "scope": "session",
      "ui_mode": "simplified",
      "revision": 1,
      "changed_at": "2026-11-16T00:00:00Z",
      "valid_until": "2026-11-16T02:00:00Z",
      "minimum_until": "2026-11-16T00:00:00Z",
      "last_offer_at": "2026-11-16T00:00:00Z",
      "is_simulated": true
    },
    "changes": [],
    "next_cursor": null,
    "effective_ui_mode": "normal",
    "evaluated_at": "2026-11-16T03:00:00Z"
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{"request_id":"req-flow-mode-002","status":"error","data":null,"error":{"code":"RESOURCE_NOT_FOUND","message":"当前身份无法访问该会话"}}
```

## 3 内部公共对象草案（无对外自由写入入口）

以下每行均列完整字段属性，不包含未定义任意payload。维护方A统筹，来源业务提供精确引用；均F-draft01，不是已经建立的表。状态列各自枚举，不与外部业务status混用。

### IdempotencyReceipt（FQ02）

| 字段 | 类型 | 必填/可空 | 默认 | 格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| receipt_id | ID | R/N | UUIDv4首次分配 | 内部回执ID | A0 |
| scope_hash | string | R/N | 无 | SHA256小写64十六进制，作用域见F01 | A0 |
| key_hash | string | R/N | 无 | 幂等键SHA256，不以key作为认证 | A0 |
| request_fingerprint | string | R/N | 无 | F01规范化SHA256 | A0 |
| state | string | R/N | processing | processing/committed/rejected/expired | A0 |
| resource_type | string | R/Y | null | 已注册业务对象类别，无任意类名 | 业务维护方 |
| resource_id | ID | R/Y | null | 已提交原业务引用，读取仍验权 | 业务维护方 |
| http_status | integer | R/Y | null | 100—599，提交/拒绝后非null | A0 |
| response_ref | ID | R/Y | null | 受控普通响应快照，不含敏感明文 | A0 |
| protected_response | bytes | R/Y | null | 仅OS账户保护的敏感回执密文，不出API/日志 | O身份适配 |
| sensitive_until | DateTime | R/Y | null | 绑定码5分钟/会话8小时且不超实际有效期 | O身份适配 |
| created_at | DateTime | R/N | now | 首次保留 | A0 |
| full_receipt_until | DateTime | R/N | created_at+7天 | 过期保留最小墓碑，不自动删除业务 | A0 |
| completed_at | DateTime | R/Y | null | 确定提交/拒绝时 | A0 |

唯一约束scope_hash+key_hash；不存在“清理回执就重新执行”的路径。敏感载荷不可解密不退回明文/新事实。保留期/清理动作必须遵守最终数据留存专项，当前不自行删除墓碑。

### ChangeNotice / NoticeSourceRef（FQ12）

| 对象.字段 | 类型 | 必填/可空 | 默认 | 格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| ChangeNotice.notice_id | ID | R/N | UUIDv4 | 同一变更稳定 | A共用存储 |
| ChangeNotice.source_module | string | R/N | 无 | O/A/B/C，核验受控来源 | 来源业务 |
| ChangeNotice.patient_id | ID | R/N | 无 | 精确患者 | 来源业务 |
| ChangeNotice.data_environment | string | R/N | 无 | demo/real，不混合 | 来源适配 |
| ChangeNotice.kind | string | R/N | 无 | 注册plan_published/event_revision_changed/statistics_changed/summary_changed/b_intervention_changed/c_service_changed/c_feedback_changed/points_source_changed | 来源业务 |
| ChangeNotice.source_ref | NoticeSourceRef | R/N | 无 | 单一权威事实精确引用，不包含完整健康正文 | 来源业务 |
| ChangeNotice.business_key | string | R/N | 无 | 1—200字符，来源+kind+事实/修订业务唯一 | 来源业务 |
| ChangeNotice.occurred_at | DateTime | R/N | 来源事实时间 | 不用接收时间替代 | 来源业务 |
| ChangeNotice.created_at | DateTime | R/N | now | 实际保存 | A共用存储 |
| ChangeNotice.is_simulated | boolean | R/N | 来源环境 | 不接受客户端降标 | 来源适配 |
| NoticeSourceRef.resource_type | string | R/N | 无 | 按kind注册PlanVersion/SourceEvent/Statistics/Summary/Intervention/Service/ServiceFeedback/ManagementReview/PeerPost固定类型 | 来源业务 |
| NoticeSourceRef.resource_id | ID | R/N | 无 | 实际权威事实 | 来源业务 |
| NoticeSourceRef.resource_revision | Version | R/N | 无 | 精确业务/资源修订，kind定义版本含义 | 来源业务 |

唯一(source_module,data_environment,business_key)。PlanVersion用plan_version，SourceEvent用event_revision；Statistics/Summary每次计算使用新不可变结果ID，引用修订固定1，不捏造它们不存在的meta.revision；Intervention引用下述新增内部修订；Service用meta.revision，ServiceFeedback用feedback_revision，ManagementReview用meta.revision，PeerPost用revision。points_source_changed只通知C重新按原来源核奖，不携带delta/balance；接收者再验权限，不把事件存在当授权。

| kind | 权威源类型 | 注册消费者/允许行为 |
| --- | --- | --- |
| plan_published | PlanVersion | A按O规则物化/失效统计，B/C仅失效旧证据缓存 |
| event_revision_changed | SourceEvent | A清洗/匹配/失效统计，不由消费者改源报告 |
| statistics_changed | Statistics | A刷新摘要，B/C只失效旧引用/重新读取 |
| summary_changed | Summary | B/C失效旧决策依据，后续读取仍按授权，不自动联系他人 |
| b_intervention_changed | Intervention | A汇总受限反馈，C读取获准需求，不直接申请服务 |
| c_service_changed | Service | B按既有referral映射读C状态，A汇总最小状态 |
| c_feedback_changed | ServiceFeedback | A/B读最小三维反馈，不改画像/训练 |
| points_source_changed | SourceEvent/ManagementReview/PeerPost | C按有效资格核奖，不能传金额或扩大授权 |

### BInterventionRevision（新增内部并发字段，无新增公共输出）

| 字段 | 类型 | 必填/可空 | 默认 | 格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| intervention_id | ID | R/N | 原干预 | 唯一关联B Intervention | B5 |
| revision | Version | R/N | 首次1 | 干预执行/展示/响应等实际变化同事务递增，重复回执不递增 | B5 |
| updated_at | DateTime | R/N | now | 实际保存变更时刻，和通知同事务 | B5 |

原B公共Intervention没有meta/revision，不能凭空从响应读取版本；本内部新增同样待FQ12确认后登记B增量。旧通知只用其精确修订定位当时事实，消费时再读当前权威状态，不能把旧状态覆盖新状态。

### NoticeConsumption / TaskLease / ReminderSnoozeLink

| 对象.字段 | 类型 | 必填/可空 | 默认 | 格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| NoticeConsumption.notice_id | ID | R/N | 来源通知 | 关联ChangeNotice | A共用存储 |
| NoticeConsumption.consumer | string | R/N | 无 | 该kind已注册O/A/B/C处理器 | A分发器 |
| NoticeConsumption.status | string | R/N | pending | pending/applied/ignored/failed | 接收处理器 |
| NoticeConsumption.result_ref | ID | R/Y | null | 实际目标结果或null | 接收处理器 |
| NoticeConsumption.reason | Reason | R/Y | null | ignored/failed非null，不返回正文/堆栈 | 接收处理器 |
| NoticeConsumption.updated_at | DateTime | R/N | now | 当前消费事实时间 | 接收处理器 |
| TaskLease.task_id | ID | R/N | 原任务 | 唯一任务关联 | A7 |
| TaskLease.owner_instance_id | ID | R/N | 无 | 已启动runner实例UUID | A7 |
| TaskLease.claim_token | integer | R/N | 每次领取递增 | >0，隔离旧领取者 | A7 |
| TaskLease.claimed_at | DateTime | R/N | now | 实际领取 | A7 |
| TaskLease.lease_until | DateTime | R/N | now+90秒 | 15秒续租，失权不能提交新结果 | A7 |
| TaskLease.phase | string | R/N | claimed | claimed/side_effect_started/result_saved，崩溃不能猜副作用未发生 | A7 |
| ReminderSnoozeLink.source_task_id | ID | R/N | 用户引用 | 同患者O任务 | O5/A7 |
| ReminderSnoozeLink.source_task_revision | Version | R/N | 已验证输入 | 同来源修订只一子任务 | O5/A7 |
| ReminderSnoozeLink.child_task_id | ID | R/N | 原子创建 | 不同于原任务ID | A7 |
| ReminderSnoozeLink.dose_slot_id | ID | R/N | 原任务payload | 总次数按此slot归并 | O5 |
| ReminderSnoozeLink.created_at | DateTime | R/N | now | 明确用户动作 | O5/A7 |

消费唯一notice_id+consumer，消费回执/目标变更同事务；派发尝试属于A既有任务/执行，不能因通知失败另开一套无预算重试。稍后关联唯一source_task_id+source_task_revision；预算读取同slot现有初次/重复/稍后有效派发记录，在创建新提醒事务里核验总数≤3，保留取消/失败审计，未知不自动返还次数制造重复。

### InputSnapshot（FQ07/FQ13）

| 字段 | 类型 | 必填/可空 | 默认 | 格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| snapshot_id | ID | R/N | UUIDv4 | 固定一次计算依据 | A6/A5/B |
| patient_id | ID | R/N | 已验患者 | 不跨患者 | 业务维护方 |
| data_environment | string | R/N | 无 | demo/real | 来源适配 |
| as_of | DateTime | R/N | 固定调用时钟 | 不晚于本次服务器时钟 | 业务维护方 |
| window_start | DateTime | R/N | 已验查询 | [start,end) | 业务维护方 |
| window_end | DateTime | R/N | 已验查询 | >start、≤31天 | 业务维护方 |
| source_refs | NoticeSourceRef[] | R/N | [] | 精确输入事实/修订，没有不造 | 业务维护方 |
| authorization_context_hash | string | R/N | 无 | 作用域/权限版本SHA256；仍需每次重验，不是永久许可 | O权威上下文/A保存 |
| created_at | DateTime | R/N | now | 实际计算快照保存时间 | 业务维护方 |

这是内部计算清单，完整对话/模型候选不塞入A摘要或通用通知；B已有输入快照/预算字段仍按B契约维护，不能用本表抹平模型/提示词/知识版本。

## 4 跨模块固定验收矩阵（计划，全部未运行）

每例均需隔离demo库/虚构患者甲乙、可控时钟及实际结果证据；下表“预期”不等于通过。执行阶段须记录命令、版本、输入、前后资源/计数、实际HTTP/页面及失败日志。

| 编号 | 场景/操作 | 必须验证的预期 | 所属阶段 |
| --- | --- | --- | --- |
| FT01 | 空库显式初始化、重复初始化、普通启动 | 明确幂等/拒绝，不清库、不隐式迁移/投递 | S01 |
| FT02 | 受支持旧schema追加迁移与中途失败 | 旧记录/校验和保留，失败不半升级；隔离备份可恢复 | S01/S07 |
| FT03 | demo登录同键重放、8小时边界、退出重放 | 有效同会话；过期/退出不复活；CSRF/Origin有效 | S02 |
| FT04 | 绑定码重复兑换/到期/同键重放 | 一次使用、5分钟边界；密文不可用不新建事实 | S02 |
| FT05 | 家人协助问卷、撤销授权、多标签患者切换 | 来源真实，撤销即拒绝，写目标不悄悄变更；不代发布计划/评估 | S02 |
| FT06 | 八题unknown/not_applicable/not_answered及更正 | 前两允许提交，未答阻止；新结果不覆盖原答案，不造CAS | S02 |
| FT07 | A草稿指定内容修订与O并发确认/失败 | content_revision非meta.revision；全事务发布或全回滚 | S02 |
| FT08 | 新版本恰在时段边界、多药同刻、重复补齐 | 边界归新版；每药一slot；稳定ID/无重复；历史不迁挂 | S02/S03 |
| FT09 | 未物化窗口/非本期排程/DST或回溯请求 | 明确未就绪/不支持，不伪0、不猜复杂医嘱 | S03 |
| FT10 | 两患者原始事件同号/同患者同来源异内容 | 患者隔离；合法重复一事实，异内容409；来源非客户端自报 | S03 |
| FT11 | 明确slot/无引用/多候选/跨患者复核 | 明确合法才关联；其余保留原因；复核不改来源 | S03 |
| FT12 | 14时段10本人已服，补录后11 | 旧快照10/14，新as_of 11/14，迟到不回填旧结果 | S03 |
| FT13 | 9已服+1未服+1延期+2其他+1未知 | 和=14，比例9/14；延期后本人明确已服为10/14 | S03 |
| FT14 | 矛盾/重复报告、更正撤销、零分母、跨日1/4 | 未解决矛盾unknown；一致重复不增计数；null非0；跨日加总 | S03 |
| FT15 | 指标null、未知单位、单次异常、依赖失败 | 缺失不作0，不猜单位/临床阈值；503不伪空 | S03 |
| FT16 | 提醒关闭/严格时间未知/锚点超界/稍后重复 | 不改医嘱；越界拒绝；同来源至多一子任务、slot总≤3 | S03 |
| FT17 | 停机30分钟边界/错过节点/B模式过期 | 提醒过窗不补；B仅原24h节点；effective normal且GET无写 | S03/S04/S06 |
| FT18 | 幂等同键异内容/在途/7天后/数据库回滚 | 409明确；墓碑不重复事实；回滚原键可安全恢复 | S03/S06 |
| FT19 | B消息保存后生成失败/刷新/再试原消息 | 历史恢复同一用户消息，不重复插话/新一轮预算 | S04 |
| FT20 | B超时/供应商未知/A重试/预算耗尽 | 原轮预算2或8/60秒，未知不重发，真实失败不转mock | S04/S06 |
| FT21 | 知识缺失/撤回/伪引用/提示注入 | 无审核不作医学依据，只用本次有效引用，不执行内容指令 | S04/S06 |
| FT22 | 极简主动进入/立即恢复/到期/旧任务晚到 | 明确操作、0秒可恢复，保留导航/积分/主动支持，旧任务不覆盖新选择 | S04/S06 |
| FT23 | 未确认草稿/有效同意复用/范围主体变化 | 不通知；同范围免重复同意，变更需新确认/O范围 | S05 |
| FT24 | B23/C07同时提交同草稿修订、更换幂等键 | 唯一C服务及正确B映射；缺新revision422；失败全回滚 | S05 |
| FT25 | C合法五状态/在途取消/终态晚回执/撤销 | 不伪停服、不复活；任务执行不等于服务完成/患者评价 | S05/S06 |
| FT26 | 匿名入组/退出/待审/越组/普通成员自审 | pending不公开、active限定、公开无真实ID、退出拒绝新访问 | S05 |
| FT27 | 日记录四类结局/家人记录/自动设备/重复核奖 | 参与与已服分开；日+2依资格，设备单独无奖，规则版本不重发 | S05 |
| FT28 | 连续10天/重复五日分配/后补中间日期/更正 | 最早不重叠5日块，各日只一次，不自动追回旧奖 | S05 |
| FT29 | 余额30、成本30、两笔并发/旧账户/资源版本 | 一笔成功余额0，另一冲突；无负数/半扣；必要专业服务仍免费 | S05 |
| FT30 | 未交付明确失败+重复失败/unknown/退分后晚成功 | 原扣减只全退一次；unknown不盲退重发；晚成功不复活 | S05/S06 |
| FT31 | 人员兑换与派发任务同时重试 | 只一个C服务/实际派发入口；fulfill_reward不另发一次 | S05/S06 |
| FT32 | A任务两runner竞争/租约过期/旧进程回写/崩溃 | 条件领取隔离；未知不重发；纯计算按原业务恢复；3次上限有效 | S06 |
| FT33 | 通知同号异内容/重复消费/状态缺口/源权限撤销 | 去重/冲突/查权威源；最小引用，无旧正文泄露和跨患者效果 | S06 |
| FT34 | 摘要缓存后撤销、权限不同家人、依赖不可用 | 重验底层权限、restricted/不足真实，不返旧内容/假0 | S03/S06 |
| FT35 | C关联B重置/另开演示、非demo fixture/时钟 | 有C关联拒绝；新库不覆盖旧库；真实模式禁用演示入口 | S04/S05/S07 |
| FT36 | 新隔离环境获取远程提交、安装/迁移/完整网页路径 | 无密钥mock完整、版本可定位；实际检查通过后才声称交付 | S07 |

## 5 S00出口与下一阶段门槛

本轮可核查：原来源哈希/历史前缀、153卡方法路径唯一/目录覆盖、新候选路由无冲突、上述JSON合法/字段完整、FQ及旧未决引用完整。以上均仅文档静态验证，不运行上述业务验收。

S00仍需确认F00的FQ01—FQ18及本文件新增字段/API/权限收敛；确认后新增有效全流程清单与必要模块版本，不改旧稿。真实专项的关闭边界也须明确确认；缺真实人员/协议/临床映射不伪造。

即使S00随后确认完成，仍须用户明确“执行S01”。S01仅公共工程/配置/显式库初始化迁移/身份适配骨架/基础页面与记录机制、依赖兼容验证及阶段检查，不抢先实现O/A/B/C后续业务。当前没有应用测试或付费调用。

## 6 本轮成稿修订附记（保留初始措辞，均未确认）

E-F03-01：核对发现原A Statistics/Summary和B Intervention并无公共meta.revision，不能泛称读取该字段。第3节据此补明不可变结果修订1、B内部并发对象及注册消费者；均为本轮建议。初始被替换的字段行/说明完整保留：

> | NoticeSourceRef.resource_type | string | R/N | 无 | 按kind注册PlanVersion/SourceEvent/Statistics/Summary/Intervention/Service/ServiceFeedback等固定类型 | 来源业务 |
>
> 唯一(source_module,data_environment,business_key)。每kind注册固定允许消费者及对应源类型；PlanVersion用plan_version，SourceEvent用event_revision，其他按对应meta.revision/明确版本，不混用。points_source_changed只通知C重新按原来源核奖，不携带delta/balance；接收者再验权限，不把事件存在当授权。

本轮开始前不存在本文件；没有改动原A/B/C字段表。首次评审快照以本文件全字节及13证据定位，后续变更只追加或新版本。
