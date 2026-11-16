# S00 B批：完整字段草案（draft01）

2026-11-16，Asia/Shanghai。字段版本B-draft01；**新增类型/状态/默认/参数/权限均待确认，未实现**。公共/O与A已确认部分按各确认清单和排除项继承。旧资料只引用，不覆盖。

## 1 类型与请求规则

R/N必须出现不接受null；R/Y必须出现可null；O/N可省略不可传null；O/Y可省略可传null。输出全部R；请求只含对应Input，禁止客户端填写服务端身份、审核人、mode、实际流水线、病例归属、模型地址/密钥或执行结果。各表逐字段版本均B-draft01，生成方按标题/行定义；无=无默认。

继承公共ID、Version、DateTime、Text、ShortText、Reason、Meta、VersionRef、List<T>与Envelope<T>。外部别名PlanRef、Issue、Execution、FeedbackSource完整引用A01_字段_draft01.md及A-v0.1确认范围；不另起相同语义。UserText=1—4000字符；ReplyText=1—2000字符；KnowledgeText=1—20000字符；均仅安全文本，不执行HTML/指令。涉及费用、临床阈值、模型真实能力无推断默认。

每张卡继承公共Cookie/CSRF/Idempotency-Key；可信集成用独立服务身份/签名适配，不用body自报。参数格式兼容由后端白名单配置，不在患者请求中开放任意生成参数。POST检索仍要求登录/CSRF，检索快照及引用再次检查撤回/适用状态；不能重放撤回资料作为新事实依据。

| 查询/路径字段 | 类型 | 必填/可空 | 默认 | 约束/生成方 |
| --- | --- | --- | --- | --- |
| path.s/path.id | ID | R/N | 无 | 对应卡资源ID，后端查患者/案例/会话归属 |
| path.version | string | R/N | 无 | 精确知识内容版本，不能浮动最新替代 |
| cursor / limit | string / integer | O/N | 首批 / 20 | 公共分页上限100，绑定账号/患者/筛选 |
| patient_id（会话列表/导出/检索等） | ID | 按卡R/N | 无 | 明确患者范围，不能用家属账号替代 |
| case_id（会话列表） | ID | O/N | 不筛选 | 只当前可访问虚构案例 |
| client_message_id（历史恢复） | ID | O/N | 不筛选 | 定位原提交，不能绕过患者权限 |
| include_history（模式读取） | boolean | O/N | false | true时changes分页，false时空数组，不写状态 |
| status（邀请列表） | string | O/N | 不筛选 | 邀请自己的状态枚举 |
| window_start / window_end（导出/反馈） | DateTime | R/N | 无 | [start,end)，建议≤31天 |
| include_unreviewed（知识列表） | boolean | O/N | false | 仅知识管理者可true，患者不能取未审核医学事实 |
| kind（知识列表） | string | O/N | 不筛选 | communication/medical/service_information |
| session_id（旧引用读取） | ID | O/Y | null | 撤回版本需曾被本患者该会话真实引用或管理权限 |
| format（导出） | string | O/N | json | 本批仅JSON保持Envelope；不偷换原始CSV下载 |

本批不定义医学危险阈值/有效量表评分；score暂留null，若后来启用方法需独立确认。所有模式/邀请/策略/材料的有效期由后端时间校验，GET不产生状态写入、调度或模型调用。

## 2 对象逐字段表

### CaseDefinition（维护方：B6；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| case_id | ID | R/N | 无 | 公共类型定义 | B6 |
| patient_id | ID | R/N | 无 | 关联O虚构患者，不是账号ID | B6 |
| title | ShortText | R/N | 无 | 公共类型定义 | B6 |
| focus | string | R/N | 无 | low_mood/anxiety_concerns/treatment_fatigue | B6 |
| template_version | string | R/N | 无 | 公共类型定义 | B6 |
| opening_draft | UserText | R/N | 无 | 仅输入草稿，不是已发送用户话或模型回复 | B6 |
| is_simulated | boolean | R/N | 无 | 本期案例必须true | B6 |

### CaseResetInput（维护方：演示管理→B6；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| case_template_version | string | R/N | 无 | 当前模板版本 | 操作者引用 |
| confirmed | boolean | R/N | 无 | 必须true，仅当前案例 | 操作者 |

### ResetResult（维护方：B6；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| reset_id | ID | R/N | 无 | 公共类型定义 | B6 |
| case_id | ID | R/N | 无 | 公共类型定义 | B6 |
| affected_session_ids | ID[] | R/N | 无 | 仅本案例B记录 | B6 |
| cancelled_task_ids | ID[] | R/N | 无 | A确认已取消的本案例待执行任务 | B6 |
| reset_at | DateTime | R/N | 无 | 公共类型定义 | B6 |
| preserved_template_version | string | R/N | 无 | 公共类型定义 | B6 |
| is_simulated | boolean | R/N | 无 | true；真实环境拒绝 | B6 |

### SessionCreateInput（维护方：患者→B3；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| patient_id | ID | R/N | 无 | 来自本人/有效范围 | 用户引用 |
| case_id | ID | O/Y | null | 虚构演示案例；自由会话可null | 调用方 |
| entry_source | string | O/N | user | user/accepted_invitation | 调用方 |
| invitation_id | ID | O/Y | null | accepted_invitation时必有、同患者且已接受 | 调用方 |

### Session（维护方：B3/B6；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| session_id | ID | R/N | 无 | 公共类型定义 | B3/B6 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B3/B6 |
| case_id | ID | R/Y | null | 公共类型定义 | B3/B6 |
| status | string | R/N | 无 | active/closed | B3/B6 |
| entry_source | string | R/N | 无 | user/accepted_invitation | B3/B6 |
| invitation_id | ID | R/Y | null | 公共类型定义 | B3/B6 |
| turn_count | integer | R/N | 无 | ≥0，已保存用户轮数；失败生成也不重复插话 | B3/B6 |
| ui_mode | string | R/N | 无 | normal/simplified，投影当前模式事实 | B3/B6 |
| opened_at | DateTime | R/N | 无 | 公共类型定义 | B3/B6 |
| closed_at | DateTime | R/Y | null | 公共类型定义 | B3/B6 |
| meta | Meta | R/N | 无 | 公共类型定义 | B3/B6 |

### SessionCloseInput（维护方：患者→B6；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | Session.meta.revision | 用户引用 |
| reason | Reason | O/Y | null | 主动关闭原因可空 | 调用方 |

### SummaryRef（维护方：A快照引用，B只读；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| summary_id | ID | R/N | 无 | 公共类型定义 | A快照引用，B只读 |
| window_start | DateTime | R/N | 无 | 公共类型定义 | A快照引用，B只读 |
| window_end | DateTime | R/N | 无 | 公共类型定义 | A快照引用，B只读 |
| generated_at | DateTime | R/N | 无 | 公共类型定义 | A快照引用，B只读 |
| valid_until | DateTime | R/N | 无 | 公共类型定义 | A快照引用，B只读 |
| data_status | string | R/N | 无 | fresh/stale/insufficient；继承A，不重算 | A快照引用，B只读 |
| schema_version | string | R/N | 无 | 公共类型定义 | A快照引用，B只读 |

### InputSnapshot（维护方：B3；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| snapshot_id | ID | R/N | 无 | 公共类型定义 | B3 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B3 |
| session_id | ID | R/N | 无 | 公共类型定义 | B3 |
| user_message_id | ID | R/N | 无 | 公共类型定义 | B3 |
| history_message_ids | ID[] | R/N | 无 | 默认最多20条，精确输入范围 | B3 |
| profile_id | ID | R/Y | null | O画像精确不可变结果 | B3 |
| plan_refs | PlanRef[] | R/N | 无 | O正式版本；可空列表 | B3 |
| summary_ref | SummaryRef | R/Y | null | A未可用则null，不造评分 | B3 |
| retrieval_id | ID | R/Y | null | 本次检索集合引用，纯倾听可无 | B3 |
| version_refs | VersionRef[] | R/N | 无 | 规则/提示词/知识/模型/评估等实际版本 | B3 |
| missing_items | Issue[] | R/N | 无 | 缺失/过期/不可用分别记录 | B3 |
| captured_at | DateTime | R/N | 无 | 公共类型定义 | B3 |

### GenerationBudget（维护方：B1/B3编排；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| max_network_attempts | integer | R/N | 无 | single_pass=2；star建议8，含所有子步骤/重试 | B1/B3编排 |
| used_network_attempts | integer | R/N | 无 | ≥0，不超过max；发起前持久化预留 | B1/B3编排 |
| max_candidates | integer | R/N | 无 | single_pass=1；star建议≤2 | B1/B3编排 |
| max_output_tokens | integer | R/Y | null | 建议1024，仅服务支持时配置，不能强传不支持参数 | B1/B3编排 |
| deadline_at | DateTime | R/N | 无 | 建议整轮开始+60秒；A重试不重置 | B1/B3编排 |

### TokenUsage（维护方：B1；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| input_tokens | integer | R/Y | null | ≥0，供应商不提供则null | B1 |
| output_tokens | integer | R/Y | null | ≥0，不编造用量 | B1 |
| total_tokens | integer | R/Y | null | ≥0，确知时才填 | B1 |
| source | string | R/N | 无 | reported/estimated/unavailable；估计不当账单 | B1 |
| missing_reason | Reason | R/Y | null | unavailable时必须说明；mock无真实用量 | B1 |

### ModelCall（维护方：B1；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| call_id | ID | R/N | 无 | 公共类型定义 | B1 |
| generation_id | ID | R/N | 无 | 公共类型定义 | B1 |
| stage | string | R/N | 无 | single_pass/state/topic/strategy/candidate/select/fallback/probe | B1 |
| attempt_number | integer | R/N | 无 | ≥1，逻辑尝试序号 | B1 |
| network_attempt_number | integer | R/Y | null | 真实网络尝试≥1；mock=null | B1 |
| mode | string | R/N | 无 | mock/real，实际适配来源 | B1 |
| provider_label | ShortText | R/N | 无 | 后端配置脱敏标识，不含地址/密钥 | B1 |
| model_label | ShortText | R/N | 无 | 公共类型定义 | B1 |
| provider_model_version | string | R/Y | null | 未提供稳定版本则null，不声称严格复现 | B1 |
| model_config_version | string | R/N | 无 | 公共类型定义 | B1 |
| status | string | R/N | 无 | succeeded/failed/outcome_unknown | B1 |
| usage | TokenUsage | R/N | 无 | 公共类型定义 | B1 |
| elapsed_ms | integer | R/N | 无 | ≥0，毫秒 | B1 |
| error_code | ShortText | R/Y | null | 公共类型定义 | B1 |
| started_at | DateTime | R/N | 无 | 公共类型定义 | B1 |
| finished_at | DateTime | R/N | 无 | 公共类型定义 | B1 |

### Generation（维护方：B3；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| generation_id | ID | R/N | 无 | 公共类型定义 | B3 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B3 |
| session_id | ID | R/N | 无 | 公共类型定义 | B3 |
| user_message_id | ID | R/N | 无 | 已有稳定用户消息 | B3 |
| status | string | R/N | 无 | accepted/running/completed/failed/cancelled/outcome_unknown | B3 |
| mode | string | R/N | 无 | 实际mock/real | B3 |
| requested_pipeline | string | R/N | 无 | single_pass/star | B3 |
| actual_pipeline | string | R/N | 无 | single_pass/star；不隐式mock降级 | B3 |
| fallback_reason | Reason | R/Y | null | 仅预配置允许且预算内降阶 | B3 |
| input_snapshot | InputSnapshot | R/N | 无 | 公共类型定义 | B3 |
| budget | GenerationBudget | R/N | 无 | 公共类型定义 | B3 |
| calls | ModelCall[] | R/N | 无 | 含失败/重试；无模型思维链 | B3 |
| error_code | ShortText | R/Y | null | 公共类型定义 | B3 |
| started_at | DateTime | R/N | 无 | 公共类型定义 | B3 |
| finished_at | DateTime | R/Y | null | 公共类型定义 | B3 |
| is_simulated | boolean | R/N | 无 | 生成来源标记；不掩盖A数据/渠道各自来源 | B3 |

### MessageInput（维护方：患者→B3；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| client_message_id | ID | R/N | 无 | 客户端稳定操作号，独立服务端message_id | 网页 |
| content | UserText | R/N | 无 | 1—4000字符，安全当文本，不执行系统指令 | 患者 |
| expected_turn_count | integer | R/N | 无 | ≥0，当前会话轮数，处理多标签并发 | 网页引用 |

### Message（维护方：B3/B6；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| message_id | ID | R/N | 无 | 公共类型定义 | B3/B6 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B3/B6 |
| session_id | ID | R/N | 无 | 公共类型定义 | B3/B6 |
| client_message_id | ID | R/Y | null | user必有，assistant=null | B3/B6 |
| role | string | R/N | 无 | user/assistant；服务端生成 | B3/B6 |
| content | UserText | R/N | 无 | 患者原话不可覆盖；assistant受ReplyText上限 | B3/B6 |
| author_account_id | ID | R/Y | null | 实际患者账号；assistant=null | B3/B6 |
| source_message_id | ID | R/Y | null | assistant指向原user，user=null | B3/B6 |
| generation_id | ID | R/Y | null | 公共类型定义 | B3/B6 |
| generation_status | string | R/N | 无 | not_applicable/accepted/running/completed/failed/cancelled/outcome_unknown | B3/B6 |
| created_at | DateTime | R/N | 无 | 公共类型定义 | B3/B6 |
| is_simulated | boolean | R/N | 无 | 实际虚构案例/来源标记，不由客户端决定 | B3/B6 |

### DifficultyCue（维护方：B4模型线索经后端验证；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| category | string | R/N | 无 | low_mood/anxiety_concerns/treatment_fatigue/routine_barriers | B4模型线索经后端验证 |
| label | ShortText | R/N | 无 | 非诊断性线索 | B4模型线索经后端验证 |
| evidence | Text | R/N | 无 | 必须是输入范围内患者原文片段 | B4模型线索经后端验证 |
| source_message_id | ID | R/N | 无 | 本人user消息，不能引助手/其他患者/范围外消息 | B4模型线索经后端验证 |

### Readiness（维护方：B3描述性推断；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| state | string | R/N | 无 | not_considering/ambivalent/preparing/acting/maintaining；后两类为项目扩展 | B3描述性推断 |
| evidence | Text | R/N | 无 | 真实患者原文 | B3描述性推断 |
| source_message_id | ID | R/N | 无 | 同会话、本次输入范围；未知时整个对象null | B3描述性推断 |

### SuggestedAction（维护方：B3候选，B5校验；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| type | string | R/N | 无 | small_step/offer_simplified_mode/offer_professional_support | B3候选，B5校验 |
| description | Text | R/N | 无 | 候选建议不是已执行动作 | B3候选，B5校验 |

### KnowledgeCitation（维护方：B2集合→B3校验；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| retrieval_id | ID | R/N | 无 | 公共类型定义 | B2集合→B3校验 |
| knowledge_id | ID | R/N | 无 | 公共类型定义 | B2集合→B3校验 |
| version | string | R/N | 无 | 公共类型定义 | B2集合→B3校验 |
| fragment_id | ID | R/N | 无 | 公共类型定义 | B2集合→B3校验 |
| source_locator | string | R/N | 无 | 实际逻辑来源定位，非服务器路径 | B2集合→B3校验 |
| quote | Text | R/N | 无 | 本次返回片段的真实文本 | B2集合→B3校验 |
| review_status_at_use | string | R/N | 无 | 作医学依据必须reviewed，不能模型自报审核 | B2集合→B3校验 |

### DialogueOutput（维护方：B3统一业务输出；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| assistant_reply | ReplyText | R/N | 无 | 1—2000字符；患者可见，不含内部思维链 | B3统一业务输出 |
| support_focus | string | R/N | 无 | listening/clarifying/exploring/action_support/closing | B3统一业务输出 |
| difficulty_cues | DifficultyCue[] | R/N | 无 | 可空；无证据条目剔除并记录降阶原因 | B3统一业务输出 |
| communication_strategy | string[] | R/N | 无 | reflection/affirmation/open_question/autonomy_support/permission_based_advice/summary；建议每轮1—2项 | B3统一业务输出 |
| suggested_action | SuggestedAction | R/Y | null | 无建议null | B3统一业务输出 |
| knowledge_citations | KnowledgeCitation[] | R/N | 无 | 只来自本次有效集合；倾听可空 | B3统一业务输出 |
| change_readiness | Readiness | R/Y | null | 未知null，不造概率 | B3统一业务输出 |

### GenerationResult（维护方：B3非流式输出；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| user_message | Message | R/N | 无 | 公共类型定义 | B3非流式输出 |
| assistant_message | Message | R/N | 无 | 成功必须有真实校验后助手结果 | B3非流式输出 |
| generation | Generation | R/N | 无 | 公共类型定义 | B3非流式输出 |
| business_output | DialogueOutput | R/N | 无 | 公共类型定义 | B3非流式输出 |
| intervention_id | ID | R/Y | null | 无决策可null | B3非流式输出 |
| suggestion_ids | ID[] | R/N | 无 | 后端实际创建且校验的建议 | B3非流式输出 |

### GenerationRetryInput（维护方：患者→B3；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| generation_id | ID | R/N | 无 | 精确失败/已知可重试生成，引用原消息 | 网页引用 |
| expected_turn_count | integer | R/N | 无 | 当前会话轮数；旧页不覆盖新轮 | 网页引用 |

### SelfReportItem（维护方：患者明确自评；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| dimension | string | R/N | 无 | concerns/necessity/burden/routine/support_need | 患者明确自评 |
| description | Text | R/N | 无 | 患者自述，不是临时量表分数 | 患者 |
| source_message_id | ID | O/Y | null | 可引用本人原消息，不能引他人 | 调用方 |

### SelfReportInput（维护方：患者→B4；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| client_report_id | ID | R/N | 无 | 稳定提交号 | 网页 |
| items | SelfReportItem[] | R/N | 无 | 至少1条，无score字段 | 患者 |

### Assessment（维护方：B4；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| assessment_id | ID | R/N | 无 | 公共类型定义 | B4 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B4 |
| session_id | ID | R/N | 无 | 公共类型定义 | B4 |
| kind | string | R/N | 无 | model_cues/self_report/context_summary | B4 |
| source_message_ids | ID[] | R/N | 无 | 可核对原话来源 | B4 |
| cues | DifficultyCue[] | R/N | 无 | 公共类型定义 | B4 |
| self_report_items | SelfReportItem[] | R/N | 无 | 公共类型定义 | B4 |
| score | number | R/Y | null | 本期方法未确认一律null，不混合跨源分数 | B4 |
| scoring_method_version | string | R/Y | null | 未确认null | B4 |
| score_missing_reason | Reason | R/Y | null | 无评分方法明确说明 | B4 |
| observed_at | DateTime | R/N | 无 | 公共类型定义 | B4 |
| valid_until | DateTime | R/Y | null | 历史线索不永久当当前状态 | B4 |
| version_refs | VersionRef[] | R/N | 无 | 公共类型定义 | B4 |
| meta | Meta | R/N | 无 | 公共类型定义 | B4 |

### EvidenceRef（维护方：B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| source_type | string | R/N | 无 | message/summary/profile/self_report/service | B5 |
| record_id | ID | R/N | 无 | 公共类型定义 | B5 |
| version | string | R/Y | null | 可定位时填写 | B5 |
| label | ShortText | R/N | 无 | 可核对业务依据，非模型内部推理 | B5 |

### Intervention（维护方：B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| intervention_id | ID | R/N | 无 | 公共类型定义 | B5 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B5 |
| session_id | ID | R/Y | null | 背景触发可尚无会话 | B5 |
| trigger_type | string | R/N | 无 | user/periodic/state_event | B5 |
| trigger_ref | ID | R/N | 无 | 消息/检查节点/状态事件 | B5 |
| should_intervene | boolean | R/N | 无 | 允许false | B5 |
| support_type | string | R/N | 无 | none/listening/practical/knowledge/professional_support/interaction_relief | B5 |
| support_intensity | string | R/N | 无 | none/low/moderate/high；非临床风险等级 | B5 |
| interaction_burden | string | R/N | 无 | minimal/low/standard，独立于支持强度 | B5 |
| channel_suggestion | string | R/Y | null | mock/in_app/none；真实渠道未接入 | B5 |
| decision_reason | Text | R/N | 无 | 证据与规则摘要，不含思维链 | B5 |
| evidence_refs | EvidenceRef[] | R/N | 无 | 公共类型定义 | B5 |
| input_snapshot_id | ID | R/N | 无 | 公共类型定义 | B5 |
| rule_version | string | R/N | 无 | 公共类型定义 | B5 |
| version_refs | VersionRef[] | R/N | 无 | 公共类型定义 | B5 |
| decided_at | DateTime | R/N | 无 | 公共类型定义 | B5 |
| valid_until | DateTime | R/N | 无 | 建议最多15分钟且不超证据有效期 | B5 |
| execution_status | string | R/N | 无 | not_required/pending/submitted/delivered/failed/cancelled/expired/outcome_unknown | B5 |
| execution_ids | ID[] | R/N | 无 | A执行引用，不冒充干预ID | B5 |
| displayed_at | DateTime | R/Y | null | 首次有效网页展示，提交/送达不能填此字段 | B5 |
| response_ids | ID[] | R/N | 无 | 实际建议/患者响应引用 | B5 |
| is_simulated | boolean | R/N | 无 | 公共类型定义 | B5 |

### Suggestion（维护方：B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| suggestion_id | ID | R/N | 无 | 公共类型定义 | B5 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B5 |
| session_id | ID | R/N | 无 | 公共类型定义 | B5 |
| intervention_id | ID | R/N | 无 | 公共类型定义 | B5 |
| type | string | R/N | 无 | small_step/offer_simplified_mode/offer_professional_support | B5 |
| description | Text | R/N | 无 | 公共类型定义 | B5 |
| status | string | R/N | 无 | pending/accepted/declined/cancelled/expired | B5 |
| created_at | DateTime | R/N | 无 | 公共类型定义 | B5 |
| valid_until | DateTime | R/N | 无 | 公共类型定义 | B5 |
| response_id | ID | R/Y | null | 公共类型定义 | B5 |
| rule_version | string | R/N | 无 | 公共类型定义 | B5 |
| is_simulated | boolean | R/N | 无 | 公共类型定义 | B5 |

### SuggestionResponseInput（维护方：患者→B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| choice | string | R/N | 无 | accepted/declined/cancelled | 患者 |
| expected_status | string | R/N | 无 | pending，防止相反响应覆盖 | 网页引用 |

### SuggestionResponse（维护方：B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| response_id | ID | R/N | 无 | 公共类型定义 | B5 |
| suggestion_id | ID | R/N | 无 | 公共类型定义 | B5 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B5 |
| choice | string | R/N | 无 | accepted/declined/cancelled | B5 |
| responded_at | DateTime | R/N | 无 | 公共类型定义 | B5 |
| mode_change_id | ID | R/Y | null | 接受极简时同事务改变模式；无额外同意弹窗 | B5 |
| referral_id | ID | R/Y | null | 仅表达专业支持意愿不创建C申请，通常null | B5 |
| is_simulated | boolean | R/N | 无 | 公共类型定义 | B5 |

### DisplayReceiptInput（维护方：网页真实展示→B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| client_receipt_id | ID | R/N | 无 | 稳定展示事件号 | 网页 |
| displayed_at | DateTime | R/N | 无 | 浏览器实际展示时刻，服务器校验合理偏差 | 网页 |

### DisplayReceipt（维护方：B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| receipt_id | ID | R/N | 无 | 公共类型定义 | B5 |
| intervention_id | ID | R/N | 无 | 公共类型定义 | B5 |
| client_receipt_id | ID | R/N | 无 | 公共类型定义 | B5 |
| displayed_at | DateTime | R/N | 无 | 公共类型定义 | B5 |
| received_at | DateTime | R/N | 无 | 公共类型定义 | B5 |
| is_simulated | boolean | R/N | 无 | 实际会话/渠道来源 | B5 |

### UIState（维护方：B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| session_id | ID | R/N | 无 | 公共类型定义 | B5 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B5 |
| scope | string | R/N | 无 | session，患者级跨会话未启用 | B5 |
| ui_mode | string | R/N | 无 | normal/simplified | B5 |
| revision | Version | R/N | 无 | 公共类型定义 | B5 |
| changed_at | DateTime | R/N | 无 | 公共类型定义 | B5 |
| valid_until | DateTime | R/Y | null | simplified建议2小时；normal=null | B5 |
| minimum_until | DateTime | R/Y | null | 建议最短0秒，绝不阻止用户恢复 | B5 |
| last_offer_at | DateTime | R/Y | null | 用于建议间隔24小时，不伪称跨会话模式 | B5 |
| is_simulated | boolean | R/N | 无 | 公共类型定义 | B5 |

### ModeChange（维护方：B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| mode_change_id | ID | R/N | 无 | 公共类型定义 | B5 |
| session_id | ID | R/N | 无 | 公共类型定义 | B5 |
| from_mode | string | R/N | 无 | normal/simplified | B5 |
| to_mode | string | R/N | 无 | normal/simplified；重复选择当前模式不产生事件 | B5 |
| source | string | R/N | 无 | user/accepted_suggestion/expiry/session_closed | B5 |
| source_suggestion_id | ID | R/Y | null | 公共类型定义 | B5 |
| changed_at | DateTime | R/N | 无 | 公共类型定义 | B5 |
| resulting_revision | Version | R/N | 无 | 公共类型定义 | B5 |
| is_simulated | boolean | R/N | 无 | 公共类型定义 | B5 |

### UIModeView（维护方：B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| current | UIState | R/N | 无 | 公共类型定义 | B5 |
| changes | ModeChange[] | R/N | 无 | 仅查询明确include_history时分页返回 | B5 |
| next_cursor | string | R/Y | null | 没有下一页null | B5 |

### UIModePutInput（维护方：患者→B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| ui_mode | string | R/N | 无 | normal/simplified | 患者 |
| expected_revision | Version | R/N | 无 | 当前UI状态修订 | 网页 |
| confirmed | boolean | R/N | 无 | 明确用户动作必须true | 患者 |
| source_suggestion_id | ID | O/Y | null | 如已接受建议引用；不重复索要确认 | 调用方 |

### BExpiryTaskPayload（维护方：B5→A7拟议注册增量；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| session_id | ID | R/N | 无 | 对应会话 | B5→A7拟议注册增量 |
| target_kind | string | R/N | 无 | ui_mode/invitation/suggestion，均只注册B受控处理器 | B5→A7拟议注册增量 |
| target_id | ID | R/N | 无 | 公共类型定义 | B5→A7拟议注册增量 |
| expected_revision | Version | R/N | 无 | 防旧到期任务撤回新状态 | B5→A7拟议注册增量 |

### Invitation（维护方：B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| invitation_id | ID | R/N | 无 | 公共类型定义 | B5 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B5 |
| session_id | ID | R/Y | null | 背景邀请可尚无会话 | B5 |
| trigger_type | string | R/N | 无 | periodic/state_event | B5 |
| trigger_ref | ID | R/N | 无 | 同周期节点/同状态事件稳定引用 | B5 |
| status | string | R/N | 无 | pending/accepted/declined/expired/cancelled | B5 |
| title | ShortText | R/N | 无 | 公共类型定义 | B5 |
| description | Text | R/N | 无 | 低负担邀请，不代患者发言 | B5 |
| created_at | DateTime | R/N | 无 | 公共类型定义 | B5 |
| valid_until | DateTime | R/N | 无 | 建议24小时 | B5 |
| displayed_at | DateTime | R/Y | null | 独立展示记录 | B5 |
| resolved_session_id | ID | R/Y | null | 接受后绑定/新建唯一会话，未进入可null | B5 |
| rule_version | string | R/N | 无 | 公共类型定义 | B5 |
| is_simulated | boolean | R/N | 无 | 公共类型定义 | B5 |

### InvitationResponseInput（维护方：患者→B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| choice | string | R/N | 无 | accepted/declined | 患者 |
| expected_status | string | R/N | 无 | pending | 网页引用 |
| session_id | ID | O/Y | null | 可绑定本人已有active会话；null则B05后续创建 | 调用方 |

### InvitationResponse（维护方：B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| response_id | ID | R/N | 无 | 公共类型定义 | B5 |
| invitation_id | ID | R/N | 无 | 公共类型定义 | B5 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B5 |
| choice | string | R/N | 无 | accepted/declined | B5 |
| session_id | ID | R/Y | null | 已绑定则返回；未进入null，不假造会话 | B5 |
| responded_at | DateTime | R/N | 无 | 公共类型定义 | B5 |
| is_simulated | boolean | R/N | 无 | 公共类型定义 | B5 |

### ReferralCreateInput（维护方：患者确认后→B5代理C；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| patient_id | ID | R/N | 无 | 患者实际权限 | 用户引用 |
| session_id | ID | R/N | 无 | 本患者会话 | 网页引用 |
| source_suggestion_id | ID | O/Y | null | 可为已接受专业支持建议 | 调用方 |
| resource_id | ID | R/N | 无 | C可用资源，字段需C批联合确认 | C引用 |
| service_draft_id | ID | R/N | 无 | C待确认准备记录 | C引用 |
| confirmation_ref_id | ID | R/N | 无 | C已有有效服务确认，不是网页布尔伪确认 | C引用 |
| sharing_scope_ref_id | ID | R/N | 无 | 相同服务及共享范围可复用 | C/O引用 |

### Referral（维护方：B5代理状态，C正式服务；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| referral_id | ID | R/N | 无 | B衔接记录，不是实际申请ID | B5代理状态，C正式服务 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B5代理状态，C正式服务 |
| session_id | ID | R/N | 无 | 公共类型定义 | B5代理状态，C正式服务 |
| source_suggestion_id | ID | R/Y | null | 公共类型定义 | B5代理状态，C正式服务 |
| proxy_status | string | R/N | 无 | pending/linked/failed/result_unknown | B5代理状态，C正式服务 |
| service_id | ID | R/Y | null | C实际创建成功后才非空 | B5代理状态，C正式服务 |
| service_status | string | R/Y | null | submitted/in_progress/completed/cancelled/failed；service_id=null时必须null | B5代理状态，C正式服务 |
| confirmation_ref_id | ID | R/N | 无 | 公共类型定义 | B5代理状态，C正式服务 |
| sharing_scope_ref_id | ID | R/N | 无 | 公共类型定义 | B5代理状态，C正式服务 |
| failure_reason | Reason | R/Y | null | 公共类型定义 | B5代理状态，C正式服务 |
| meta | Meta | R/N | 无 | 公共类型定义 | B5代理状态，C正式服务 |

### StateEventInput（维护方：A/可信模块→B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| source_event_id | ID | R/N | 无 | 可信来源稳定号 | 来源服务 |
| patient_id | ID | R/N | 无 | 公共类型定义 | A/可信模块→B5 |
| event_type | string | R/N | 无 | summary_updated/plan_changed/consent_revoked | A/可信模块→B5 |
| summary_ref | SummaryRef | R/Y | null | 非摘要事件可null | A/可信模块→B5 |
| occurred_at | DateTime | R/N | 无 | 公共类型定义 | A/可信模块→B5 |
| rule_version | string | R/N | 无 | 业务来源规则 | A/可信模块→B5 |

### ExecutionReceiptInput（维护方：A7→B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| source_event_id | ID | R/N | 无 | 公共类型定义 | A7→B5 |
| patient_id | ID | R/N | 无 | 公共类型定义 | A7→B5 |
| task_id | ID | R/N | 无 | 公共类型定义 | A7→B5 |
| execution_id | ID | R/N | 无 | 公共类型定义 | A7→B5 |
| intervention_id | ID | R/N | 无 | 必须与A原记录一致 | A7→B5 |
| occurred_at | DateTime | R/N | 无 | 公共类型定义 | A7→B5 |
| execution | Execution | R/N | 无 | 完整复用A-v0.1；不可body越权篡改 | A7→B5 |

### ReferralReceiptInput（维护方：C→B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| source_event_id | ID | R/N | 无 | 公共类型定义 | C→B5 |
| patient_id | ID | R/N | 无 | 公共类型定义 | C→B5 |
| referral_id | ID | R/N | 无 | 公共类型定义 | C→B5 |
| service_id | ID | R/N | 无 | 必须等于B已映射的C事实 | C→B5 |
| service_status | string | R/N | 无 | C五状态；终态不回退 | C→B5 |
| occurred_at | DateTime | R/N | 无 | 公共类型定义 | C→B5 |
| source_version | string | R/N | 无 | C真实状态版本；格式C批联合确认 | C→B5 |

### IntegrationAck（维护方：B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| integration_event_id | ID | R/N | 无 | 公共类型定义 | B5 |
| source_event_id | ID | R/N | 无 | 公共类型定义 | B5 |
| applied | boolean | R/N | 无 | 乱序/失效可以false，审计保留 | B5 |
| ignore_reason | Reason | R/Y | null | 公共类型定义 | B5 |
| related_ids | ID[] | R/N | 无 | 公共类型定义 | B5 |
| received_at | DateTime | R/N | 无 | 公共类型定义 | B5 |
| is_simulated | boolean | R/N | 无 | 可信适配来源，非body自报 | B5 |

### DemoTriggerInput（维护方：演示管理→B6；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| case_id | ID | R/N | 无 | 公共类型定义 | 演示管理→B6 |
| session_id | ID | O/Y | null | 如指定必须属于本案例 | 调用方 |
| scenario | string | R/N | 无 | state_event/periodic_node/llm_timeout/empty_response/invalid_json/knowledge_empty/star_mid_failure/receipt_late | 演示管理→B6 |
| scenario_run_id | ID | R/N | 无 | 固定重放编号 | 演示管理→B6 |
| occurred_at | DateTime | R/N | 无 | 可控演示时刻 | 演示管理→B6 |

### DemoTriggerResult（维护方：B6；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| trigger_id | ID | R/N | 无 | 公共类型定义 | B6 |
| case_id | ID | R/N | 无 | 公共类型定义 | B6 |
| scenario | string | R/N | 无 | 公共类型定义 | B6 |
| related_ids | ID[] | R/N | 无 | 真实创建/配置的本例模拟记录 | B6 |
| is_simulated | boolean | R/N | 无 | 必须true | B6 |

### InterventionExport（维护方：B6；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| export_id | ID | R/N | 无 | 公共类型定义 | B6 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B6 |
| window_start | DateTime | R/N | 无 | 公共类型定义 | B6 |
| window_end | DateTime | R/N | 无 | ≤31天 | B6 |
| items | Intervention[] | R/N | 无 | 默认仅元信息/证据引用，不整段原话 | B6 |
| next_cursor | string | R/Y | null | 公共类型定义 | B6 |
| generated_at | DateTime | R/N | 无 | 公共类型定义 | B6 |
| is_simulated | boolean | R/N | 无 | 公共类型定义 | B6 |

### KnowledgeRecord（维护方：B2；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| knowledge_id | ID | R/N | 无 | 公共类型定义 | B2 |
| version | string | R/N | 无 | 不可变内容版本；审核/撤回另外留历史 | B2 |
| kind | string | R/N | 无 | communication/medical/service_information | B2 |
| title | ShortText | R/N | 无 | 公共类型定义 | B2 |
| body | KnowledgeText | R/N | 无 | 1—20000字符；外部文本当资料，不执行指令 | B2 |
| source_locator | string | R/N | 无 | 1—2000字符、实际逻辑来源/URL，不含密钥与服务器物理路径 | B2 |
| applicability_tags | string[] | R/N | 无 | 明确适用范围，不猜病种/医嘱 | B2 |
| language | string | R/N | 无 | 本期zh-CN | B2 |
| review_status | string | R/N | 无 | draft/pending_review/reviewed/withdrawn | B2 |
| effective_from | DateTime | R/N | 无 | 公共类型定义 | B2 |
| effective_until | DateTime | R/Y | null | 公共类型定义 | B2 |
| reviewed_by | ID | R/Y | null | 真实受控审核者；未审核null，不伪造 | B2 |
| reviewed_at | DateTime | R/Y | null | 公共类型定义 | B2 |
| review_note | Text | R/Y | null | 公共类型定义 | B2 |
| meta | Meta | R/N | 无 | 公共类型定义 | B2 |

### KnowledgeCreateInput（维护方：资料维护→B2；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| kind | string | R/N | 无 | communication/medical/service_information | 维护者 |
| title | ShortText | R/N | 无 | 真实标题 | 维护者 |
| body | KnowledgeText | R/N | 无 | 原资料内容 | 维护者 |
| source_locator | string | R/N | 无 | 实际来源定位 | 维护者 |
| applicability_tags | string[] | R/N | 无 | 明确适用标签 | 维护者 |
| language | string | O/N | zh-CN | 后续语言需明确资料 | 调用方 |
| effective_from | DateTime | R/N | 无 | 公共类型定义 | 资料维护→B2 |
| effective_until | DateTime | O/Y | null | 公共类型定义 | 调用方 |

### KnowledgeVersionInput（维护方：资料维护→B2；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_current_version | string | R/N | 无 | 防覆盖并发版本 | 维护者引用 |
| content | KnowledgeCreateInput | R/N | 无 | 新内容版本，不继承旧审核状态 | 维护者 |

### KnowledgeReviewInput（维护方：合格审核者→B2；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| version | string | R/N | 无 | 精确内容版本 | 审核者引用 |
| expected_revision | Version | R/N | 无 | 元信息并发版本 | 审核者引用 |
| decision | string | R/N | 无 | approve/reject；approve资格由后端验证 | 审核者 |
| note | Text | R/N | 无 | 真实审核说明 | 审核者 |

### KnowledgeWithdrawInput（维护方：资料维护→B2；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| version | string | R/N | 无 | 公共类型定义 | 资料维护→B2 |
| expected_revision | Version | R/N | 无 | 公共类型定义 | 资料维护→B2 |
| reason | Reason | R/N | 无 | 撤回原因 | 资料维护→B2 |

### KnowledgeSearchInput（维护方：O/B/C可信用途→B2；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| patient_id | ID | R/N | 无 | 患者范围最小化，无病例原文 | 调用方引用 |
| query | Text | R/N | 无 | 检索需求，不是执行指令 | 调用方 |
| applicability_tags | string[] | R/N | 无 | 明确适用条件 | 调用方 |
| limit | integer | O/N | 5 | 1—10片段 | 调用方 |
| purpose | string | O/N | medical_support | medical_support/communication/service_explanation | 调用方 |

### KnowledgeSnippet（维护方：B2检索快照；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| fragment_id | ID | R/N | 无 | 公共类型定义 | B2检索快照 |
| knowledge_id | ID | R/N | 无 | 公共类型定义 | B2检索快照 |
| version | string | R/N | 无 | 公共类型定义 | B2检索快照 |
| text | Text | R/N | 无 | ≤2000字符可核对片段 | B2检索快照 |
| source_locator | string | R/N | 无 | 公共类型定义 | B2检索快照 |
| kind | string | R/N | 无 | communication/medical/service_information | B2检索快照 |
| review_status_at_retrieval | string | R/N | 无 | 患者医学用途只允许reviewed | B2检索快照 |
| effective_from | DateTime | R/N | 无 | 公共类型定义 | B2检索快照 |
| effective_until | DateTime | R/Y | null | 公共类型定义 | B2检索快照 |

### RetrievalSet（维护方：B2；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| retrieval_id | ID | R/N | 无 | 公共类型定义 | B2 |
| patient_id | ID | R/N | 无 | 公共类型定义 | B2 |
| status | string | R/N | 无 | matched/knowledge_insufficient/conflicting | B2 |
| snippets | KnowledgeSnippet[] | R/N | 无 | 真实本次集合，无结果[]但必须说明不足 | B2 |
| reason | Reason | R/Y | null | 不足/冲突必须说明 | B2 |
| retrieved_at | DateTime | R/N | 无 | 公共类型定义 | B2 |
| knowledge_version_refs | VersionRef[] | R/N | 无 | 公共类型定义 | B2 |
| is_simulated | boolean | R/N | 无 | 公共类型定义 | B2 |

### ModelProbeInput（维护方：管理明确动作→B1；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| profile_id | ID | R/N | 无 | 后端预登记配置，不传URL或密钥 | 管理者 |
| expected_config_version | string | R/N | 无 | 配置快照版本 | 管理者引用 |
| allow_external_call | boolean | R/N | 无 | mock可false；real必须明确true，本轮仍禁止调用 | 管理者 |

### ModelProbeResult（维护方：B1；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| probe_id | ID | R/N | 无 | 公共类型定义 | B1 |
| profile_id | ID | R/N | 无 | 公共类型定义 | B1 |
| mode | string | R/N | 无 | mock/real | B1 |
| model_label | ShortText | R/N | 无 | 公共类型定义 | B1 |
| model_config_version | string | R/N | 无 | 公共类型定义 | B1 |
| status | string | R/N | 无 | available；配置/连接失败用HTTP失败Envelope | B1 |
| network_attempt_count | integer | R/N | 无 | ≥0；mock=0；探测建议最多1 | B1 |
| elapsed_ms | integer | R/N | 无 | ≥0 | B1 |
| usage | TokenUsage | R/N | 无 | 公共类型定义 | B1 |
| checked_at | DateTime | R/N | 无 | 公共类型定义 | B1 |

### ModelProfileInput（维护方：白名单管理→B1；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| profile_id | ID | R/N | 无 | 后端已登记配置 | 管理者 |
| expected_config_version | string | R/N | 无 | 当前全局活动配置版本 | 管理者引用 |
| confirmed | boolean | R/N | 无 | 必须true；只是选择，不执行付费探测 | 管理者 |

### ModelProfileSelection（维护方：B1；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| profile_id | ID | R/N | 无 | 公共类型定义 | B1 |
| previous_profile_id | ID | R/Y | null | 公共类型定义 | B1 |
| mode | string | R/N | 无 | mock/real | B1 |
| requested_pipeline | string | R/N | 无 | single_pass/star | B1 |
| model_config_version | string | R/N | 无 | 公共类型定义 | B1 |
| configuration_status | string | R/N | 无 | ready/misconfigured；缺依赖拒绝激活real | B1 |
| selected_at | DateTime | R/N | 无 | 公共类型定义 | B1 |

## 3 跨模块约束与未决细节

1. client_message_id为提交来源号；message_id为服务端消息；generation_id为生成操作；call_id为一次模型调用元信息；request_id/Idempotency-Key各自独立。先保存患者user消息和生成占位，再锁定输入快照/预算账本，释放写锁后调用供应商；同键在途不重复调用。成功校验后才发布助手消息/建议。
2. 生成失败时可能已保存用户消息，HTTP失败Envelope仍data=null/error有值；网页用原client_message_id查询B10恢复message_id/generation_status，再由B11引用原消息重试。不得插入第二条用户话或重置预算。provider超时结果未知记outcome_unknown；没有可靠查询/去重能力时不自动再付费调用。
3. 全轮预算先预留真实网络尝试，底层重试和STAR子步骤共用。建议single_pass≤2、STAR≤8、候选≤2、总60秒；mock可有逻辑调用但network_attempts=0，用量未知为null+原因，不当0账单。真实失败不切mock；STAR降single_pass仅预配置允许且在剩余预算内，记actual/fallback。
4. 本轮定义的是来源和校验结构，不调用模型、不复制CAMI代码。准备程度/候选选择为项目适配，不能宣称全为原方法或临床有效；不保存/展示内部思维链。
5. 线索和Readiness的原文必须在InputSnapshot真实patient user消息范围内；跨患者/助手/范围外引用拒绝，不能用拒绝帮助作为心理病理证据。A设备/行为仅上下文，B不重算五类比例/CAS。
6. 资料内容版本不可覆盖；review_status/审核动作另留审计。没有实际合格审核者不填reviewed_by/at、不用AI自评代审核。撤回后不进新检索，旧会话可查看引用时版本及现撤回状态。知识不足不补造医学结论。
7. 接受极简建议本身是明确操作，B17可以同事务记录response+ModeChange，避免再问同一确认；直接B20切换也走同一服务。重复选择当前模式不新增变更；small_step接受不等于已服；接受专业帮助只表意愿，仍由C核对服务和共享范围后创建实际申请。
8. Invitation可尚无session。首页用B39读取患者邀请；B22接受可关联已有active会话，或由B05用已接受邀请建立唯一会话，不自动生成患者消息。周期建议+7/+28天和24小时窗口仍待确认，缺enrollment_at不伪设起点。
9. expire_b_state为BX-03对A注册任务的新增建议；payload只交给注册B处理器，target_kind包括ui_mode/invitation/suggestion。模式到期恢复写ModeChange，建议/邀请到期留状态审计，旧expected_revision不能覆盖新用户选择。后续须A兼容增量登记，GET不得代替写入执行器。
10. Intervention.execution_status为B业务投影；A.Execution.execution_status与delivery_status分别映射。A completed+submitted仅B submitted，不是delivered/displayed/accepted；无送达保持未知。DisplayReceipt独立记录网页实际展示。
11. BCX-01的resource/service_draft/confirmation/sharing引用名和C来源版本为拟议交接，C批要联合确认。B service_id必须是C实际返回，未授权/未确认/未接入不伪创建；同服务同共享范围已有有效确认复用，范围变更再取得相应确认。
12. 演示重置只当前虚构案例B数据和经A确认取消的待执行引用；模板/配置/其他案例/O授权计划/A原始事实/工作记录不删。若关联C服务/积分等未定义清理契约，返回409阻止重置，不造孤儿资源。
13. BX-01的对话/评估/模式/知识/导出权限为待确认增量；原家庭授权不扩大。B30默认只导出决策与来源引用，不含整段患者原话/内部候选；研究使用和训练授权分开。
14. 配置选择B38只选后端登记profile；激活real缺依赖拒绝，不退mock；选择不探测。B01真实探测需要明确allow_external_call且应说明费用，独立最大1次尝试；本轮任何“确认”都不越过用户禁止付费调用的限制。

以上新增内容均待B批确认；具体时效/阈值/真实协议/同意映射仍以B00 BQ及前置未决项管理。没有实现表、迁移、API或模型调用。


## 4 只读策略投影及共享输入/输出补充

SelfReportItem.source_message_id在输入可省略或null；在Assessment输出中规范化为必须出现、可null。知识列表/版本示例若review_status不是reviewed，仅指管理预览，不能作为患者医学依据。

### StrategyView（维护方：B5；字段版本B-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| session_id | ID | R/N | 无 | 当前会话 | B5 |
| patient_id | ID | R/N | 无 | 实际患者 | B5 |
| status | string | R/N | 无 | active/none/expired，过期不执行旧建议 | B5 |
| current_intervention | Intervention | R/Y | null | 当前有效决策，未就绪可空 | B5 |
| suggestions | Suggestion[] | R/N | [] | 当前有效建议，历史原记录保留 | B5 |
| invitations | Invitation[] | R/N | [] | 本会话邀请；背景邀请用B39 | B5 |
| ui_state | UIState | R/N | 无 | 同一模式事实投影 | B5 |
| generated_at | DateTime | R/N | 无 | 只读投影时刻，不发起模型 | B5 |

## 5 到期并发和离线未决补充

Invitation与Suggestion的受控存储行另有内部revision（Version，必填、不可null、默认1，由B5生成，状态变化递增，字段版本B-draft01），不作为当前API JSON的新增输出字段；BExpiryTaskPayload.expected_revision对这两类引用该内部修订，对ui_mode引用公开UIState.revision。业务状态和内部修订同事务保存，旧到期任务只能审计/忽略，不能覆盖新状态。

长时间关闭应用/停调度后的到期补偿与catch-up窗口未在本批给出数值，属于BQ16待全流程调度确认。GET不承担写入恢复；到期事实未执行落库前，不得把旧simplified当仍有效或伪称恢复已完成，应明确过期/待恢复，并保留用户立即恢复入口。
