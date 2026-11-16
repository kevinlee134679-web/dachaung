# S00 第一轮：范围、目录与维护方（draft01）

日期：2026-11-16，Asia/Shanghai。依据：总 Prompt v1.1、用户本轮指令。状态：本轮草案，未确认、未冻结；S00 部分完成，S01 未获准。

本文为首次新增的不可覆盖快照。后续评审以追加确认/更正条目或新增 draft02 保存，不回写本轮历史结论。原始研究资料、来源 Prompt 均不修改。

## 1 状态与范围

标记：**已确认**＝总 Prompt 或用户已明确决定；**建议**＝本轮提出供审阅；**待确认**＝尚需用户/维护方决定。建议被写入文档不等于获准实现。

**已确认的本期产品范围**：Windows 本地、Python/FastAPI、SQLite、原生 HTML/CSS/JavaScript，同一服务默认 127.0.0.1；O 身份/家庭授权/八主题问卷/画像/正式计划/提醒；A 文件/草稿/原始事件/清洗/五类统计/摘要/公共执行；B 可配置模型适配、共用知识、支持对话、线索、邀请和减负，先 single_pass，S06 再 STAR；C 社会支持、服务记录、匿名同辈支持、正向积分/自愿兑换及反馈；S07 完整集成验收。业务阶段1—4和编码阶段 S00—S07分开。

**本轮允许工作**：实际环境与 Git 检查；全平台能力及接口目录；公共对象关系；只对公共基础与 O 展开字段、接口卡和待确认清单；文档与追加式记录。未写应用业务代码，未安装依赖，未初始化业务数据库，未启动应用，未训练/运行研究模型，未调用付费 API。

**已确认的外部接入边界**：真实认证、真实设备云、病历自动识别、真实药师/志愿者/家庭通知、外部推送及公网部署均未接入；本期以明确标记的虚构数据和模拟依赖验证。研究模型输入映射与预处理未验证前不输出 CAS 数值。专业服务不以积分为前提；家庭共同账户、预充津贴及损失厌恶扣减不纳入本期。

**建议的文档组织**：本文件保存全平台目录与问题；`01_公共基础与O字段_draft01.md` 保存本轮字段；`02_公共基础与O接口卡_draft01.md` 保存本轮接口卡。只有原基线和明确确认成果可提交；本轮新增设计先留在本地待确认。

## 2 已确认的维护边界

| 事实/能力 | 唯一业务维护方 | 读者及边界 |
| --- | --- | --- |
| 账号、本人/家庭对象、家庭绑定与授权 | O1 | A/B/C 每次访问及执行重新检查，绑定不等于授权 |
| 问卷定义、作答、画像/分类/评估版本 | O2/O3 | C/B 引用；CAS、自报、A 确认比例和心理线索分别保存 |
| 药品资料、正式计划及版本、提醒偏好 | O4/O5 | A 保存引用和必要快照，不能另发正式计划 |
| 计划时段生成 | 待确认：建议 O 定义并发布，A1 持久化 | 生成方、多药粒度、版本替换和生效边界须 O/A 联合确认 |
| 文件、人工草稿、原始服药/指标事件 | A2/A3 | O 确认某个草稿修订；上传、提交、正式确认分开 |
| 清洗/更正、匹配、五类统计、趋势和摘要 | A4/A6/A5 | 网页/B/C 使用同一结果，不另算比例 |
| 共用数据库/迁移/身份适配/错误机制 | A0/A1 统筹，各模块提供业务定义 | 同一工程、同一连接与版本体系 |
| 任务与投递 | A7 | O 定义提醒业务，B 定义检查与干预；执行、提交、送达、展示、响应分开 |
| 模型适配、会话、消息、线索、自评、建议/邀请、模式规则 | B1/B3—B6 | 不修改处方、授权、积分，不把线索当诊断 |
| 共用知识及来源、审核/撤回、版本、检索 | B2 | O 药学页面、B 对话、C 说明复用；无审核资料不伪装为医学依据 |
| 支持资源匹配、正式服务申请、执行记录、患者反馈 | C | B 转介入口仅代理 C 创建，保存映射；A 汇总 |
| 积分规则/余额/流水/兑换/交付、同辈支持参与 | C | 程序核算，LLM 无权改余额；兑换记录与服务记录分开 |

“维护方”指模块职责；本地未找到已确认的人员分工表，不杜撰成员姓名。

## 3 公共对象关系草案

**已确认的关系**：账号可同时管理本人和多位授权患者；患者可授权多名家人。问卷评估对象始终是患者，作答者另存。O 发布正式计划，A 文件/草稿仅提供来源。一个计划时段可有多条证据，证据条数不作分母。B 会话关联输入摘要和画像版本；干预、公共任务与执行各有 ID。C 正式服务唯一创建，转介保存引用；兑换有独立流水/交付。授权撤销后缓存、任务和回调重新检查。

| 对象组 | 候选主键/引用 | 维护方 | 本轮展开程度 |
| --- | --- | --- | --- |
| Account / Patient / IdentityContext | account_id / patient_id | O | 完整字段与卡 |
| FamilyBinding / Grant | binding_id / grant_id / grant_version | O | 完整字段与卡 |
| QuestionnaireDefinition / Response / Profile | questionnaire_version / response_id / profile_id | O | 完整字段与卡；分类规则仍待确认 |
| Medication / PlanVersion / DoseSlot / ReminderPreferences | medication_id / plan_id+plan_version / dose_slot_id | O；时段生成待确认 | 完整字段与卡；A 统计接口下一批 |
| File / Draft / SourceEvent / Correction | file_id / draft_id+revision / event_id | A | 仅关系与接口目录 |
| Match / Statistics / Summary / DeviceBinding | dose_slot_id / summary_id / device_id | A | 仅关系；字段下一批 |
| Task / Execution / DeliveryReceipt | task_id / execution_id / intervention_id | A | 仅关系；状态不可与服务混用 |
| Case / Session / Message / Assessment | case_id / session_id / message_id / assessment_id | B | 仅关系与目录 |
| KnowledgeVersion / Citation | knowledge_id + version / fragment_id | B2 | 仅关系；O 读取同一事实 |
| Suggestion / Invitation / Intervention / UIModeChange | suggestion_id / invitation_id / intervention_id | B | 仅关系与目录 |
| Referral / ServiceDraft / Service / Feedback | referral_id → service_id；feedback_id | B 代理；C 正式服务 | 只给映射要求，不先定映射字段/创建时机 |
| SupportResource / PeerGroup / Membership | resource_id / group_id / membership_id | C | 仅目录 |
| PointsAccount / Ledger / Redemption / Fulfillment | points_account_id / ledger_id / redemption_id | C | 仅目录；金额/积分和退回规则待 C 批确认 |

除已确认的语义/字段外，上表对象名、标识名和实现关系均为建议，不等于已建表。A/B/C 的字段、状态及全流程事务本轮不展开。

## 4 全平台接口目录（建议，不是已实现或冻结的 API）

统一前缀候选 `/api/v1`。下表路径均相对该前缀；每一行的多个方法表示分别存在的操作。`{p}`=patient_id，`{s}`=session_id，`{id}`=对应资源 ID，计划版本为正整数。路径命名最终须分批确认。内部能力未必需要暴露 HTTP，单体服务可直接调用服务函数；标记“内”表示仅可信模块/管理入口。

### 公共基础与 O（本轮详卡）

| 卡 ID | 方法与路径 | 用途 / 页面 | 维护方 |
| --- | --- | --- | --- |
| G01 | GET /health | 运行/依赖检查；管理 | A0 |
| G02 | GET /config/status | 脱敏配置与实际能力；演示控制台 | A0，B1提供模型元信息 |
| O01 | POST /auth/demo-session | 选择已有虚构演示账号，非真实注册登录 | O1 / A身份适配 |
| O02 | GET /auth/me | 当前账号、本人及可管理患者 | O1 |
| O03 | POST /auth/logout | 退出当前会话 | O1 |
| O04 | GET /patients | 已获准管理的对象；身份选择/我的 | O1 |
| O05 | PUT /auth/current-patient | 保存上次管理对象；全局切换 | O1 |
| O06 | GET /patients/{p} | 基础资料；我的 | O1 |
| O07 | PATCH /patients/{p} | 修改基础资料；我的 | O1 |
| O08 | POST /patients/{p}/family-binding-codes | 本人生成绑定码；家庭管理 | O1 |
| O09 | POST /family-bindings/redeem | 家人使用绑定码建立关系 | O1 |
| O10 | GET /patients/{p}/family-bindings | 家庭关系及可见状态 | O1 |
| O11 | POST /family-bindings/{id}/revoke | 解除绑定并使相关授权失效 | O1 |
| O12 | PUT /family-bindings/{id}/grant | 本人精确授予/修订权限 | O1 |
| O13 | GET /patients/{p}/grants | 查询授权及历史范围 | O1 |
| O14 | POST /grants/{id}/revoke | 单独撤销授权 | O1 |
| O15 | GET /questionnaires/initial | 八主题定义、选项与版本 | O2 |
| O16 | POST /patients/{p}/questionnaire-responses | 新建问卷进度/复评或更正副本 | O2 |
| O17 | PUT /questionnaire-responses/{id}/answers | 保存某修订的作答 | O2 |
| O18 | GET /questionnaire-responses/{id} | 恢复进度/只读历史 | O2 |
| O19 | POST /questionnaire-responses/{id}/submit | 提交确定修订，不伪造 CAS | O2 |
| O20 | GET /patients/{p}/profiles/current | 当前画像及来源/不足 | O3 |
| O21 | GET /profiles/{id} | 历史画像及评估版本 | O3 |
| O22 | POST /patients/{p}/profiles | 对已提交回答作一次明确评估 | O3 |
| O23 | GET /patients/{p}/medications | 药品清单 | O4 |
| O24 | POST /patients/{p}/medications | 新增药品资料；不生成医嘱 | O4 |
| O25 | PATCH /medications/{id} | 纠正名称/备注并留修订 | O4 |
| O26 | GET /patients/{p}/plans | 正式计划版本列表 | O4 |
| O27 | GET /plans/{id}/versions/{version} | 计划完整版本/来源 | O4 |
| O28 | POST /patients/{p}/plan-confirmations | 确认 A 的草稿指定修订，发布正式计划版本 | O4，A2交接 |
| O29 | GET /patients/{p}/dose-slots | 今日/范围内正式安排 | O4；时段生成方待确认 |
| O30 | GET /patients/{p}/reminder-preferences | 提醒、作息、隐私设置 | O5 |
| O31 | PUT /patients/{p}/reminder-preferences | 自主更新配置，执行复用 A7 | O5 |

O 页面直接复用 A 的文件/草稿/服药证据/统计、B2 的知识、C 的申请接口，不另建 O 版同义接口。今日状态由 A 返回，O29 仅返回计划安排。

### A（仅目录，下一批详细展开）

| 方法与路径 | 能力 / 页面或调用方 | 维护方 |
| --- | --- | --- |
| POST /patients/{p}/files；GET /patients/{p}/files；GET /files/{id}；GET /files/{id}/content | 上传/列表/元信息/授权文件读取；用药管理 | A2 |
| POST /patients/{p}/drafts；GET /drafts/{id}；PUT /drafts/{id}；POST /drafts/{id}/submit；GET /patients/{p}/drafts | 人工录入、修订、提交确认及进度；O28取得结果 | A2 |
| POST /patients/{p}/medication-events；GET /patients/{p}/medication-events；GET /medication-events/{id} | 本人/家属原始服药报告与证据 | A2/A4 |
| POST /patients/{p}/measurements；GET /patients/{p}/measurements；GET /measurements/{id} | 指标接收/查询，缺失保留原因 | A2/A4 |
| POST /events/{id}/corrections；POST /events/{id}/withdrawals；GET /events/{id}/revisions | 更正、撤销及有效修订历史 | A4 |
| GET /events/{id}/quality；POST /events/{id}/reprocess | 质量与受控重处理（内） | A4 |
| GET /patients/{p}/device-bindings；POST /patients/{p}/device-bindings；POST /device-bindings/{id}/revoke | 设备绑定核验（维护方待确认，建议 A3，O供授权） | A3/O |
| POST /integrations/device-events | 可信设备适配入口，复用原始接收 | A3 |
| POST /demo/device-events | 固定编号模拟器（仅demo） | A3 |
| GET /patients/{p}/dose-matches；POST /dose-matches/review | 匹配依据/冲突及受控人工复核 | A6 |
| GET /patients/{p}/medication-statistics；GET /patients/{p}/medication-trends | 五类计数、比例及按日/周期趋势 | A6 |
| GET /patients/{p}/measurement-trends | 按方法/单位区分的实际指标趋势 | A4/A6 |
| GET /patients/{p}/summary；POST /patients/{p}/summary-refresh | 同一状态摘要/显式刷新 | A5 |
| POST /tasks；GET /tasks/{id}；GET /patients/{p}/tasks；POST /tasks/{id}/run；POST /tasks/{id}/cancel | 注册任务创建、查询、执行一次、取消（内） | A7 |
| GET /executions/{id}；GET /tasks/{id}/executions；POST /integrations/delivery-receipts | 执行/投递回执，不把提交当送达 | A7 |
| GET /patients/{p}/feedback-overview | 汇总B和C反馈，保留原始引用 | A5 |

### B（仅目录，A 确认后展开）

| 方法与路径 | 能力 / 页面或调用方 | 维护方 |
| --- | --- | --- |
| POST /config/check-model | 显式真实探测入口，可能付费；本轮禁止调用 | B1 |
| GET /cases；GET /cases/{id}；POST /cases/{id}/reset | 虚构案例、按案例确认重置；控制台 | B6 |
| POST /sessions；GET /sessions；GET /sessions/{s}；POST /sessions/{s}/close | 会话生命周期；AI情感支持 | B3/B6 |
| POST /sessions/{s}/messages；GET /sessions/{s}/messages；POST /messages/{id}/generation-retries | 消息持久化/历史/引用原消息重试生成 | B3 |
| GET /sessions/{s}/assessments；POST /sessions/{s}/self-reports；GET /assessments/{id} | 线索/描述性评估/患者自评 | B4 |
| GET /sessions/{s}/strategy；GET /interventions/{id} | 当前策略与决策详情 | B5 |
| POST /suggestions/{id}/response；POST /interventions/{id}/display-receipts | 建议响应与独立展示回执 | B5 |
| GET /sessions/{s}/ui-mode；PUT /sessions/{s}/ui-mode | 会话级模式读取/主动切换 | B5 |
| GET /sessions/{s}/invitations；POST /invitations/{id}/response | 邀请及接受/拒绝 | B5 |
| POST /referrals；GET /referrals/{id} | 复用 C 实际创建，返回映射；非第二份申请 | B5/C |
| POST /integrations/state-events；POST /integrations/execution-receipts；POST /integrations/referral-receipts | A状态、公共执行、C服务结果回调 | B5 |
| POST /demo/triggers | 案例事件/故障模拟；仅控制台 | B6 |
| GET /patients/{p}/intervention-feedback；GET /interventions/export | A所需反馈与受限时间范围导出 | B6 |
| GET /knowledge；GET /knowledge/{id}/versions/{version}；POST /knowledge/search | 共用资料、版本读取和检索；O/B/C共用 | B2 |
| POST /knowledge；POST /knowledge/{id}/versions；POST /knowledge/{id}/review；POST /knowledge/{id}/withdraw | 资料维护、专业审核和撤回（内；不由LLM自审） | B2 |

### C（仅目录，B 确认后展开）

| 方法与路径 | 能力 / 页面或调用方 | 维护方 |
| --- | --- | --- |
| GET /patients/{p}/support-recommendations；GET /support-resources；GET /support-resources/{id} | 匹配卡片和当前可用资源 | C1—C3/C5 |
| POST /patients/{p}/service-drafts；GET /service-drafts/{id}；PUT /service-drafts/{id} | 待确认准备，不通知第三方 | C3/C7 |
| POST /patients/{p}/services；GET /patients/{p}/services；GET /services/{id} | 唯一正式申请创建及记录 | C3/C7 |
| POST /services/{id}/cancel；POST /integrations/service-receipts；POST /demo/services/{id}/transitions | 取消、可信服务方回传、合法模拟流转 | C7 |
| POST /services/{id}/feedback；GET /services/{id}/feedback；GET /patients/{p}/support-feedback | 三维反馈，与服务完成分开 | C6 |
| GET /peer-groups；GET /peer-groups/{id}；POST /peer-groups/{id}/memberships；POST /memberships/{id}/leave | 自愿匿名同辈匹配、加入与退出 | C4 |
| GET /peer-groups/{id}/posts；POST /peer-groups/{id}/posts | 最小同辈交流；是否仅演示主题/是否上线持久聊天待确认 | C4 |
| GET /patients/{p}/points；GET /points/rules；GET /patients/{p}/points-ledger | 余额、有效规则、流水 | C4 |
| POST /internal/points/reconcile | 程序按有效行为核奖（内；不开放任意改余额） | C4 |
| GET /rewards；GET /rewards/{id}；POST /patients/{p}/redemptions；GET /patients/{p}/redemptions；GET /redemptions/{id} | 权益目录、兑换及独立记录 | C4 |
| POST /integrations/fulfillment-receipts；GET /redemptions/{id}/fulfillment；POST /redemptions/{id}/feedback | 权益交付与反馈；需要人员服务时映射C服务 | C4/C6 |

管理能力（迁移、显式初始化、启动/停止调度、生成虚构样例）建议使用 CLI，不因此增加患者侧 HTTP API。真实账号接入、回调签名协议、外部资源接入细节保留适配边界，禁止将建议路径描述成真实服务已联通。

## 5 必须分批解决的具体问题

| 编号 | 状态与待确认内容 | 建议 / 影响 / 确认批次 |
| --- | --- | --- |
| Q01 | 待确认：本轮 API 前缀、路径、类型和字段版本是否接受 | 建议 /api/v1；draft01 不作冻结版；公共/O |
| Q02 | 待确认：本地身份与会话机制 | 建议固定虚构账号+服务端Cookie会话+CSRF；不建立真实注册认证；公共/O |
| Q03 | 待确认：家庭绑定成立方式及监护例外 | 建议患者发码、家人兑换只建立关系、本人单独授权；无法表示同意的监护规则未定义，不自动放行；O |
| Q04 | 待确认：权限清单、家人能否发布计划/修改提醒/代答 | 建议分别授权，主观题未知留空；家人不能将自己的报告写为本人确认；O |
| Q05 | 待确认：八主题选项编码、程度量程、互斥和缺失提交规则 | 建议选项见字段表；允许unknown/not_applicable而非强填；O |
| Q06 | 待确认：画像分类规则、主要/复合障碍排序、维持型依据 | 分类体系已确认；阈值及Q→类型映射未确认，先描述性/证据不足；不得按单个顾虑判低依从；O |
| Q07 | 待确认：研究模型产品化的输入、训练预处理、序列化模型、验证与使用口径 | 本地找到研究脚本但未发现常见序列化模型；不运行训练，CAS保持未适配/null；O后续专项 |
| Q08 | 待确认：计划正式确认人及家人代操作的范围 | 建议患者明确核对A指定修订；有精确授权的家人是否可发布待决定；O |
| Q09 | 待确认：谁生成时段、多药计数粒度、计划版本替换/生效 | 建议O定义、A保存；建议一药品条目的一次应服作为原子时段，页面可分组；影响A分母与C核奖，必须O/A共同确认 |
| Q10 | 待确认：计划周期/按需用药/严格间隔/日历边界支持 | 本轮建议固定每日/每周；按需及复杂疗程是否本期另定；医学约束来自已确认资料，不猜补；O/A |
| Q11 | 待确认：提醒默认开启与渠道、重复上限、作息锚点偏移、隐私文本 | 建议默认关闭需设置，站内为基线，系统通知按能力/许可，未知医学约束时不移动医嘱时间；O/A |
| Q12 | 待确认：幂等键范围/保留期、在途状态/失败可否同键重试、分页/版本冲突码 | 建议在途409+Retry-After，已提交稳定重放；必须先重新鉴权；公共/A |
| Q13 | 待确认：设备绑定维护、证据窗口与匹配优先级、数据环境隔离 | 下一批A定义，不用最近时间强配；A |
| Q14 | 待确认：摘要时效/质量、周期起点与配置、授权撤销及乱序回执 | 仅登记依赖，A→B→全流程逐批确认 |
| Q15 | 待确认：B转介与C服务ID、共享同意复用、极简有效期、知识审核人、模型预算 | 不提前冻结；single_pass基线与用户操作切换已确认，STAR八尝试为建议；B/C |
| Q16 | 待确认：积分数值、连续日/周界限、兑换失败交付/积分恢复、同辈交流深度 | 总Prompt积分数值均是建议；本轮不采用为既定规则；C |
| Q17 | 待处理环境条件：Git作者身份、本机GitHub登录与可推送权限 | 非业务决定；本轮无可用Git凭据，不索取聊天令牌，不改仓库 |
| Q18 | 待处理环境条件：Python/依赖版本及兼容验证 | 现有3.14.10未验证FastAPI组合；S01再隔离安装验证并锁定，本轮不锁版本 |

## 6 确认与接续门槛

本轮先审公共/O的字段表和卡片，优先答 Q01—Q12（可以逐项确认、提出修改或保持待定）。本轮任何新建议均未冻结。公共/O确认后追加确认范围和版本，再进入A字段/卡；然后B、C、全流程。未完成必要契约确认前禁止S01；即使全部S00确认完成，仍等待用户明确指定下一编码阶段。

待确认规划仅本地保存；原基线与事实记录可按已获授权进行Git同步。同步是否成功与S00业务契约是否完成分别报告。
