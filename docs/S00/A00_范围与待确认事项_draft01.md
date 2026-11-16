# S00 A批：范围、接口目录与具体待确认事项（draft01）

2026-11-16，Asia/Shanghai。只执行S00，不编写应用业务代码，不调用付费API。本批承接`docs/contracts/公共基础与O_v0.1_确认清单.md`；**本文新增方案均为建议、待确认，未冻结、未实现**。后续修改追加更正或新建版本，原草案不回写。

## 1 范围与依赖

覆盖A0/A1公共后端与数据维护约束、A2文件/草稿/手工证据、A3可信设备适配与固定模拟场景、A4质量/更正、A6匹配与五类统计、A5摘要、A7公共任务/执行/投递。A0的health/config继续使用已确认G01/G02，不重复新建接口；初始化、迁移、调度启停为未来显式CLI能力，本轮不生成脚本/数据库。

沿用已确认：O唯一维护身份、授权、正式计划及画像；A不发第二套计划，不重算CAS或画像；本人已服/本人未服/延迟/仅其他证据/未知五类按计划时段互斥，比例仅本人已服/有效计划时段；原始、标准化、更正和缺失分别追溯；A只运行已注册任务，B决定心理检查和干预，C创建正式社会服务和维护积分。

不展开B/C完整字段和全流程契约。摘要中的B/C内容仅保留来源模块、记录引用、服务状态和三维反馈的交接结构；未接入则说明，不填假记录。

## 2 完整接口卡目录

路径统一在/api/v1下；{p}=patient_id，{id}=对应资源ID。A01—A41卡及完整成功/失败示例见A02；字段表见A01。下表均为本批建议，不是已实现接口。

| 卡 | 方法 / 路径 | 维护方 / 用途 |
| --- | --- | --- |
| A01 | POST /patients/{p}/files | A2 上传 |
| A02 | GET /patients/{p}/files | A2 文件列表 |
| A03 | GET /files/{id} | A2 元信息 |
| A04 | GET /files/{id}/content | A2 授权内容读取，JSON封装base64 |
| A05 | POST /patients/{p}/drafts | A2 新建人工草稿 |
| A06 | GET /drafts/{id} | A2 草稿详情 |
| A07 | PUT /drafts/{id} | A2 保存完整新修订 |
| A08 | POST /drafts/{id}/submit | A2 提交确定修订，等待O确认 |
| A09 | GET /patients/{p}/drafts | A2 草稿列表 |
| A10 | POST /patients/{p}/medication-events | A2 手动服药报告 |
| A11 | GET /patients/{p}/medication-events | A2 当前有效证据列表 |
| A12 | GET /medication-events/{id} | A2/A4 精确证据详情 |
| A13 | POST /patients/{p}/measurements | A2 指标接收 |
| A14 | GET /patients/{p}/measurements | A2 指标事件列表 |
| A15 | GET /measurements/{id} | A2/A4 指标详情 |
| A16 | POST /events/{id}/corrections | A4 新更正修订 |
| A17 | POST /events/{id}/withdrawals | A4 撤销有效修订 |
| A18 | GET /events/{id}/revisions | A4 原始及修订历史 |
| A19 | GET /events/{id}/quality | A4 当前修订质量 |
| A20 | POST /events/{id}/reprocess | A4 受控重处理 |
| A21 | GET /patients/{p}/device-bindings | A3 设备关联 |
| A22 | POST /patients/{p}/device-bindings | A3 可信设备绑定（维护方待确认） |
| A23 | POST /device-bindings/{id}/revoke | A3 撤销关联 |
| A24 | POST /integrations/device-events | A3 可信设备统一接收 |
| A25 | POST /demo/device-events | A3 固定编号模拟场景 |
| A26 | GET /patients/{p}/dose-matches | A6 匹配详情/候选与原因 |
| A27 | POST /dose-matches/review | A6 受控人工复核 |
| A28 | GET /patients/{p}/medication-statistics | A6 五类统计 |
| A29 | GET /patients/{p}/medication-trends | A6 按日统计及汇总 |
| A30 | GET /patients/{p}/measurement-trends | A4/A6 实际指标趋势 |
| A31 | GET /patients/{p}/summary | A5 状态摘要 |
| A32 | POST /patients/{p}/summary-refresh | A5 显式刷新 |
| A33 | POST /tasks | A7 可信模块创建注册任务 |
| A34 | GET /tasks/{id} | A7 任务详情 |
| A35 | GET /patients/{p}/tasks | A7 授权任务列表 |
| A36 | POST /tasks/{id}/run | A7 受控执行一次 |
| A37 | POST /tasks/{id}/cancel | A7 请求取消 |
| A38 | GET /executions/{id} | A7 执行及投递结果 |
| A39 | GET /tasks/{id}/executions | A7 执行历史 |
| A40 | POST /integrations/delivery-receipts | A7 可信渠道回执 |
| A41 | GET /patients/{p}/feedback-overview | A5 B/C反馈引用汇总 |

## 3 新增权限的明确影响（待确认）

公共/O v0.1中的medication:read仅表示药品资料查看，不自动包含病历原文件、指标、B对话或C申请。**建议新增**files:read/files:write、drafts:read/drafts:write/drafts:submit、measurements:read/measurements:write、records:correct、devices:manage、statistics:read、summary:read、feedback:read、tasks:read。已有records:read/report继续用于服药证据读取/以实际身份报告。

这是对O Scope枚举的**拟议兼容增量AX-01**：若本批确认，后续新授权界面可明确授予这些代码，既有授权不自动扩权；还需在后续有效O契约版本登记增量。原有medication:read不隐含files:read，summary:read也不绕过各组成来源的权限。本人权限由服务端身份关系验证，家人/设备/服务方能力分别验证。

## 4 A1数据与对象维护草案

| 对象组 | 业务维护方 | 存储/交接原则 |
| --- | --- | --- |
| 文件及受控存储引用 | A2；A1结构 | 元信息/内容分开；物理路径只在受控内部，不返回网页 |
| 草稿及提交修订 | A2 | 计划字段复用O；O写正式结果，A仅保存PlanRef |
| 事件及不可变修订 | A2/A3接收，A4质量 | 一个来源事件仅一事实，原文和更正不覆盖；身份决定本人/家属 |
| 设备可信身份/绑定 | 建议A3维护、O授权 | body.patient_id不构成设备权限；撤销后执行/查询重新检查 |
| 质量、匹配与失效登记 | A4/A6 | 有效修订、质量和是否匹配分开；旧新时间窗都失效 |
| 统计/趋势/摘要 | A6/A5 | 五类不变；旧结果标stale而非继续冒充最新；来源状态分别说明 |
| 任务/执行/投递回执 | A7 | 三种ID/状态分别存；不把提交当送达/展示/响应 |
| O正式计划/患者/授权、B/C业务对象 | 原维护方 | A保存精确引用/必要快照，不提供可独立修改的副本 |

建议A1的内部表包含schema_versions、idempotency_receipts、change_outbox与各模块业务表；这些名称/字段尚待确认，不是本轮迁移实现。内部storage_ref和请求指纹不在患者侧JSON；跨库/外部引用须适配校验，不假定外键总可用。同库事务提交业务与幂等/失效登记；模型/渠道外部调用期间不持有SQLite长写锁。

## 5 本批具体待确认事项

| 编号 | 建议方案（本轮待确认） | 影响 / 尚未决定的部分 |
| --- | --- | --- |
| AQ01 | 采用A01—A41路径/字段；新增AX-01细分权限且旧授权不扩权 | 改动公共Scope登记，需明确确认；非凭本轮草案立即生效 |
| AQ02 | 上传仅PDF/PNG/JPEG，单文件≤10MiB；授权内容以JSON+base64返回 | 保持统一四字段响应；大小/类型/是否增补格式请确认；不做自动识别 |
| AQ03 | 草稿editing→pending_confirmation→confirmed/returned；待确认不可原地改，退回后新修订 | 只O能标正式确认；草稿修订必须映射精确正式计划版本；纯手工可无来源文件 |
| AQ04 | 手动报告由身份生成self_report/family_report；指标允许null+原因，未知单位进入needs_review | 不接受客户端is_simulated/质量/本人身份；默认指标注册仅示范中性技术单位，不设临床阈值 |
| AQ05 | 来源去重键=(患者,数据环境,来源,可信设备或报告账号,source_event_id)；同键异内容409 | 新增更正引用原事件，原来源编号不改；请求幂等保留期仍见AQ12 |
| AQ06 | A3维护设备注册/患者绑定，O提供本人确认及授权；模拟器固定场景编号 | 真实设备认证/回调签名协议未定义，真实入口依赖缺失必须拒绝 |
| AQ07 | 采用“一药品条目一次应服”原子粒度，O定义、A存储；先按明确时段引用匹配 | 自动时间窗口暂不设具体分钟数；无合法唯一候选不强配；跨时区/夏令时/回溯发布另留待定 |
| AQ08 | 统计窗口[start,end)，固定as_of；仅正式版本中已到时、未取消/未替代的有效时段进入分母；按日再汇总分子分母 | 计划新版本建议从显式生效点替换未来安排，历史已发生时段不自动重写；复杂回溯/暂停/重叠尚需专项 |
| AQ09 | 事件更正/撤销产生新修订，保留原文与原因，并登记旧新窗口重算 | 当前无法解决的矛盾归unknown/review，不静默采用最后一条；人工复核权限/证据需要明确 |
| AQ10 | 摘要时效建议15分钟；fresh/stale/insufficient，组成来源分别标可用/缺失/未接入/不可用/受限 | 15分钟是演示工程参数；依赖失败不得变空数据；组成权限不因summary:read扩张 |
| AQ11 | A7先支持执行一次和mock投递；任务最多3次尝试、间隔60秒的安全重试建议 | 结果未知不自动重发；B模型重试仍计入B统一预算；周期检查节点/调度规则待B/全流程 |
| AQ12 | 建议幂等回执至少保留7天；失败回滚可原键重试；副作用未知先查原执行 | 保留期/过期后的稳定业务唯一键与受控回执需确认；不删除旧工作记录；登录Cookie时长仍未定 |
| AQ13 | 取消/授权撤销/过期前重新校验；在途取消先记请求，待安全点确认；终态不被晚到回执回退 | 回执乱序保留审计，以合法状态机更新；真实外部未知不伪装取消成功 |
| AQ14 | 反馈只汇总B/C真实引用和明确的三维反馈；未接入不造效果 | 服务完成不等于干预有效，O画像不因反馈自动更新；完整B/C载荷后续批确认 |

## 6 状态与验收边界

建议文件saved/save_failed；草稿editing/pending_confirmation/confirmed/returned；质量pending_validation/valid/needs_review/processing_failed；匹配unmatched/matched/review_required/not_applicable；事件effective/withdrawn。统计ready/stale/not_computable与摘要fresh/stale/insufficient分别定义，不能混作C服务状态。

建议任务pending/running/retry_wait/succeeded/failed/cancelled/expired；在途取消用cancellation_requested，不伪称已取消副作用。执行与投递分别有状态，外部结果未知为outcome_unknown/unknown，必须先核查，不能盲重试。详细合法/非法转换见A02。

验收计划保留总Prompt固定案例：14时段10/14、补录11/14；9已服+1未服+1延迟+2其他+1未知=14，延迟明确结果后10/14；跨天加总1/4；跨患者、重复/并发、未知单位、撤销、迟到、更正、依赖失败与乱序回执。本轮只检查文档，不宣称这些业务用例已执行。

下一步先请用户确认AQ01—AQ14（可分组）。本批未确认之前不冻结A，也不提前展开B详细契约或进入S01。
