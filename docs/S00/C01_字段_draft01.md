# S00 C批：完整字段草案（draft01）

2026-11-16，Asia/Shanghai。版本C-draft01；**新增字段/枚举/默认/参数/权限均建议待确认，未实现**。完整输入/输出逐字段定义如下，示例不能代替本表。原总约束与公共/O/A/B有效确认及排除项继续适用，不重算CAS/五类统计，不新建平行授权或知识事实。

## 1 字段、类型、公共请求

R/N必须出现不可null；R/Y必须出现可null；O/N可省略不可null；O/Y可省略也可null。输出全部R；对应Input才可请求，未列字段422。各表字段版本均C-draft01，生成方以表头/行列为准，无=无默认，null/[]配合R/O解释。共用ID/Version/DateTime/LocalDate/Text/ShortText/Reason/Meta/Envelope/List与Issue/FeedbackSource等外部别名完整引用前置字段及确认清单。PeerText=1—1000字符纯文字；积分为整数，不是货币价格。

POST/PUT业务写入继承Cookie、X-CSRF-Token、Idempotency-Key与JSON；可信服务/交付回调和内部核奖需独立身份，不能body自报provider/owner/患者/余额/审核权限。真实依赖未接入则拒绝，demo适配只能虚构来源。回调最小OperationAck不向第三方回传患者余额/未授权健康内容。

| 路径/查询字段 | 类型 | 必填/可空 | 默认 | 约束/生成方 |
| --- | --- | --- | --- | --- |
| path.p/path.id | ID | R/N | 无 | 对应卡实际患者/资源/服务/成员/兑换，后端对象权限检查 |
| cursor / limit | string / integer | O/N | 首批 / 20 | 公共分页上限100，绑定患者/账号/筛选 |
| need（推荐） | string | O/N | 仅现有上下文 | practical/emotional/professional/none，仅主动表达不改O画像 |
| channel（资源列表） | string | O/N | support | support/rewards，必要专业资源永不因积分隐藏 |
| status（服务列表） | string | O/N | 不筛选 | C五状态；草稿不混入 |
| window_start/window_end（反馈/流水/回顾） | DateTime | 按卡R/N | 无 | [start,end)，建议≤31天；患者时区显示 |
| rules_version（规则读取） | string | O/N | 当前启用 | 精确旧规则可追溯，未启用不伪发布 |
| include_pending（帖子读取） | boolean | O/N | false | 仅受控本组审核者可true，本人可看自己的pending |
| group_id（小组列表） | ID | O/N | 不筛选 | 不允许借组ID查询其他成员健康记录 |

资源、服务确认的语义指纹只绑定确定主体/资源版本/服务用途/共享类别，不把一次草稿当永久同意；O权威有效性每次重查。申请唯一键是患者+service_draft_id+draft_revision；新申请需要新草稿，但相同有效范围的确认可复用。共享/临床/点数具体新政策均等C确认。

## 2 对象逐字段定义

### SourceRef（维护方：原模块事实，C引用；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| module | string | R/N | 无 | O/A/B/C | 原模块事实，C引用 |
| record_kind | ShortText | R/N | 无 | profile/summary/message/event/service/review/post/ledger等实际种类 | 原模块事实，C引用 |
| record_id | ID | R/N | 无 | 按公共类型定义 | 原模块事实，C引用 |
| version | string | R/Y | null | 可定位版本；未知null附上游限制 | 原模块事实，C引用 |
| recorded_at | DateTime | R/N | 无 | 按公共类型定义 | 原模块事实，C引用 |

### ProviderSummary（维护方：C资源登记；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| provider_id | ID | R/N | 无 | 受控服务主体 | C资源登记 |
| provider_type | string | R/N | 无 | family/volunteer/pharmacist | C资源登记 |
| display_name | ShortText | R/N | 无 | 演示必须标模拟，不伪造真实人员 | C资源登记 |
| qualification_status | string | R/N | 无 | not_required/not_verified/verified；真实专业答复须可核验资质 | C资源登记 |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | C资源登记 |

### SupportResource（维护方：C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| resource_id | ID | R/N | 无 | 按公共类型定义 | C |
| resource_version | string | R/N | 无 | 内容/主体/共享要求的明确版本 | C |
| service_kind | string | R/N | 无 | medication_access/peer_support/emotional_companionship/pharmacist_consultation/follow_up/community_assistance | C |
| name | ShortText | R/N | 无 | 按公共类型定义 | C |
| description | Text | R/N | 无 | 按公共类型定义 | C |
| provider | ProviderSummary | R/N | 无 | 按公共类型定义 | C |
| availability | string | R/N | 无 | available/unavailable/unknown；模拟不冒充真实容量 | C |
| access_mode | string | R/N | 无 | support_free/reward_only；必要服务必须support_free | C |
| is_essential | boolean | R/N | 无 | 必要医疗/药学不设积分门槛 | C |
| required_shared_categories | string[] | R/N | 无 | support_question/medication_plan/medication_records/profile_summary，仅最小必要 | C |
| optional_shared_categories | string[] | R/N | 无 | 只能从允许范围选，不自动全选 | C |
| peer_group_id | ID | R/Y | null | peer_support时关联目标组 | C |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | C |

### SupportAction（维护方：C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| resource_id | ID | R/N | 无 | 按公共类型定义 | C |
| provider_type | string | R/N | 无 | 引用资源主体 | C |
| action_type | string | R/N | 无 | medication_access/peer_support/companionship/pharmacist_consultation/follow_up/community_assistance | C |
| reason | Text | R/N | 无 | 来自实际输入的业务说明 | C |
| title | ShortText | R/N | 无 | 按公共类型定义 | C |
| page_entry | string | R/N | 无 | 固定平台导航项，不是任意外部URL | C |
| requires_confirmation | boolean | R/N | 无 | 涉及正式申请/第三方共享true | C |

### SupportRecommendation（维护方：C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C |
| profile_id | ID | R/Y | null | 只引用O，不重算分类 | C |
| primary_profile_type | string | R/Y | null | O原分类；未知null | C |
| additional_profile_types | string[] | R/N | 无 | O原复合障碍 | C |
| need_status | string | R/N | 无 | needed/none/insufficient | C |
| main_need | string | R/N | 无 | practical/emotional/professional/none/unknown | C |
| primary_action | SupportAction | R/Y | null | 最多1；none/insufficient不造行动 | C |
| secondary_actions | SupportAction[] | R/N | 无 | 最多2 | C |
| source_refs | SourceRef[] | R/N | 无 | 按公共类型定义 | C |
| missing_items | Issue[] | R/N | 无 | 按公共类型定义 | C |
| generated_at | DateTime | R/N | 无 | 按公共类型定义 | C |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | C |

### ServiceDraftInput（维护方：本人/获准家人→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| resource_id | ID | R/N | 无 | 实际可访问资源 | 用户引用 |
| resource_version | string | R/N | 无 | 核对的资源版本 | 用户引用 |
| request_text | Text | R/N | 无 | 患者主动提供问题，不填模型擅自推测 | 用户 |
| peer_group_id | ID | O/Y | null | 仅peer_support时同资源组 | 调用方 |
| source_suggestion_id | ID | O/Y | null | B同患者真实建议；不能凭建议冒充确认 | 调用方 |

### ServiceDraftPutInput（维护方：本人/获准家人→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | 资源meta.revision | 网页引用 |
| content | ServiceDraftInput | R/N | 无 | 全量内容快照，不改患者 | 用户 |

### ServiceDraft（维护方：C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| service_draft_id | ID | R/N | 无 | 按公共类型定义 | C |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C |
| draft_revision | Version | R/N | 无 | 仅内容修订；提交/指针状态变化不偷换内容号 | C |
| resource_id | ID | R/N | 无 | 按公共类型定义 | C |
| resource_version | string | R/N | 无 | 按公共类型定义 | C |
| request_text | Text | R/N | 无 | 按公共类型定义 | C |
| peer_group_id | ID | R/Y | null | 按公共类型定义 | C |
| source_suggestion_id | ID | R/Y | null | 按公共类型定义 | C |
| status | string | R/N | 无 | preparing/submitted/abandoned；均非服务五状态 | C |
| confirmation_ref_id | ID | R/Y | null | 关联有效服务确认，不是已申请 | C |
| sharing_scope_ref_id | ID | R/Y | null | O权威共享范围 | C |
| service_id | ID | R/Y | null | C正式创建后才有 | C |
| meta | Meta | R/N | 无 | 按公共类型定义 | C |

### SharingScopeRef（维护方：O唯一维护，C只读引用；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| sharing_scope_ref_id | ID | R/N | 无 | 按公共类型定义 | O唯一维护，C只读引用 |
| scope_version | Version | R/N | 无 | 按公共类型定义 | O唯一维护，C只读引用 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | O唯一维护，C只读引用 |
| recipient_id | ID | R/N | 无 | 来自资源受控provider，不让客户端随意指定 | O唯一维护，C只读引用 |
| recipient_type | string | R/N | 无 | family/volunteer/pharmacist | O唯一维护，C只读引用 |
| purpose_code | string | R/N | 无 | 明确service_kind用途 | O唯一维护，C只读引用 |
| data_categories | string[] | R/N | 无 | 可见、必要且经患者明确选择 | O唯一维护，C只读引用 |
| related_grant_ids | ID[] | R/N | 无 | O校验适用家庭/服务授权引用，不自动扩旧Grant | O唯一维护，C只读引用 |
| status | string | R/N | 无 | active/revoked/expired | O唯一维护，C只读引用 |
| confirmed_at | DateTime | R/N | 无 | 真实患者动作服务器记录 | O唯一维护，C只读引用 |
| valid_until | DateTime | R/N | 无 | 建议24小时；工程演示参数 | O唯一维护，C只读引用 |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | O唯一维护，C只读引用 |

### ServiceConfirmationInput（维护方：本人→C/O同一确认动作；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| service_draft_id | ID | R/N | 无 | 当前准备记录 | 患者引用 |
| draft_revision | Version | R/N | 无 | 用户核对的精确内容号 | 患者引用 |
| shared_categories | string[] | R/N | 无 | 必须含资源必要类别，只能是资源允许集合 | 患者选择 |
| confirmed | boolean | R/N | 无 | 明确动作true；仍需O验证，非网页自报授权 | 患者 |
| existing_confirmation_ref_id | ID | O/Y | null | 相同服务/主体/范围有效确认可复用 | 调用方 |

### ServiceConfirmation（维护方：C服务同意，O共享事实；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| confirmation_ref_id | ID | R/N | 无 | 按公共类型定义 | C服务同意，O共享事实 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C服务同意，O共享事实 |
| resource_id | ID | R/N | 无 | 按公共类型定义 | C服务同意，O共享事实 |
| resource_version | string | R/N | 无 | 按公共类型定义 | C服务同意，O共享事实 |
| provider_id | ID | R/N | 无 | 按公共类型定义 | C服务同意，O共享事实 |
| service_kind | string | R/N | 无 | 按公共类型定义 | C服务同意，O共享事实 |
| descriptor_hash | string | R/N | 无 | SHA256；固定服务/主体/用途/类别，不含一次申请意图 | C服务同意，O共享事实 |
| origin_draft_id | ID | R/N | 无 | 最初确认核对的草稿，允许同范围后续复用 | C服务同意，O共享事实 |
| origin_draft_revision | Version | R/N | 无 | 按公共类型定义 | C服务同意，O共享事实 |
| sharing_scope | SharingScopeRef | R/N | 无 | O权威当前有效引用/必要快照，不是C可独改副本 | C服务同意，O共享事实 |
| status | string | R/N | 无 | active/revoked/expired，取C确认与O授权有效性交集 | C服务同意，O共享事实 |
| confirmed_at | DateTime | R/N | 无 | 按公共类型定义 | C服务同意，O共享事实 |
| valid_until | DateTime | R/N | 无 | 建议24小时 | C服务同意，O共享事实 |
| meta | Meta | R/N | 无 | 按公共类型定义 | C服务同意，O共享事实 |

### ServiceCreateInput（维护方：本人或B代理→C唯一创建；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| service_draft_id | ID | R/N | 无 | 按公共类型定义 | 本人或B代理→C唯一创建 |
| draft_revision | Version | R/N | 无 | 必须精确，不取最新 | 本人或B代理→C唯一创建 |
| confirmation_ref_id | ID | R/N | 无 | 相同服务/主体/范围有效且本人确认 | 本人或B代理→C唯一创建 |
| sharing_scope_ref_id | ID | R/N | 无 | 与确认引用的O范围一致且有效 | 本人或B代理→C唯一创建 |

### ProviderResponse（维护方：C，实际来源经可信服务适配验证；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| provider_id | ID | R/N | 无 | 按公共类型定义 | C，实际来源经可信服务适配验证 |
| origin | string | R/N | 无 | authenticated_provider/mock_example；未核验资格不能作真实药师答复 | C，实际来源经可信服务适配验证 |
| text | Text | R/N | 无 | 安全文本，不执行HTML，不直接改O计划 | C，实际来源经可信服务适配验证 |
| recorded_at | DateTime | R/N | 无 | 按公共类型定义 | C，实际来源经可信服务适配验证 |
| source_refs | SourceRef[] | R/N | 无 | 实际资料/服务答复依据，可空并标来源局限 | C，实际来源经可信服务适配验证 |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | C，实际来源经可信服务适配验证 |

### Service（维护方：C唯一正式事实；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| service_id | ID | R/N | 无 | 按公共类型定义 | C唯一正式事实 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C唯一正式事实 |
| service_draft_id | ID | R/N | 无 | 按公共类型定义 | C唯一正式事实 |
| draft_revision | Version | R/N | 无 | 按公共类型定义 | C唯一正式事实 |
| resource_id | ID | R/N | 无 | 按公共类型定义 | C唯一正式事实 |
| resource_version | string | R/N | 无 | 按公共类型定义 | C唯一正式事实 |
| service_name | ShortText | R/N | 无 | 按公共类型定义 | C唯一正式事实 |
| service_kind | string | R/N | 无 | 按公共类型定义 | C唯一正式事实 |
| provider | ProviderSummary | R/N | 无 | 按公共类型定义 | C唯一正式事实 |
| request_text | Text | R/N | 无 | 按查看人权限裁剪，不对其他组员/服务方泄露额外健康信息 | C唯一正式事实 |
| status | string | R/N | 无 | submitted/in_progress/completed/cancelled/failed（已确认） | C唯一正式事实 |
| submitted_at | DateTime | R/N | 无 | 按公共类型定义 | C唯一正式事实 |
| started_at | DateTime | R/Y | null | 按公共类型定义 | C唯一正式事实 |
| completed_at | DateTime | R/Y | null | 按公共类型定义 | C唯一正式事实 |
| cancelled_at | DateTime | R/Y | null | 按公共类型定义 | C唯一正式事实 |
| failed_at | DateTime | R/Y | null | 按公共类型定义 | C唯一正式事实 |
| failure_reason | Reason | R/Y | null | failed必有 | C唯一正式事实 |
| cancellation_requested | boolean | R/N | 无 | 默认false；在途请求不假称已取消 | C唯一正式事实 |
| cancellation_reason | Reason | R/Y | null | 按公共类型定义 | C唯一正式事实 |
| confirmation_ref_id | ID | R/N | 无 | 按公共类型定义 | C唯一正式事实 |
| sharing_scope_ref_id | ID | R/N | 无 | 按公共类型定义 | C唯一正式事实 |
| source_suggestion_id | ID | R/Y | null | 按公共类型定义 | C唯一正式事实 |
| source_referral_id | ID | R/Y | null | 仅可信B内部调用来源；用户不能自报创建 | C唯一正式事实 |
| redemption_id | ID | R/Y | null | 仅C兑换事务创建的人员服务有此引用 | C唯一正式事实 |
| dispatch_task_id | ID | R/Y | null | A注册C能力执行引用 | C唯一正式事实 |
| result_summary | Text | R/Y | null | completed需实际完成说明；模拟显式标 | C唯一正式事实 |
| provider_response | ProviderResponse | R/Y | null | 按公共类型定义 | C唯一正式事实 |
| meta | Meta | R/N | 无 | revision为服务来源版本，B source_version用其十进制字符串 | C唯一正式事实 |

### ServiceCancelInput（维护方：本人→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | 服务当前修订 | 本人→C |
| reason | Reason | R/N | 无 | 取消原因 | 本人→C |

### ServiceReceiptInput（维护方：可信服务方→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| provider_event_id | ID | R/N | 无 | 可信主体内稳定编号 | 可信服务方→C |
| service_id | ID | R/N | 无 | 按公共类型定义 | 可信服务方→C |
| expected_revision | Version | R/N | 无 | 并发/乱序校验 | 可信服务方→C |
| status | string | R/N | 无 | in_progress/completed/cancelled/failed | 可信服务方→C |
| occurred_at | DateTime | R/N | 无 | 按公共类型定义 | 可信服务方→C |
| result_summary | Text | R/Y | null | completed必须提供 | 可信服务方→C |
| failure_reason | Reason | R/Y | null | failed必须提供 | 可信服务方→C |
| response_text | Text | R/Y | null | 可信答复或模拟文本；不是LLM自报药师 | 可信服务方→C |

### OperationAck（维护方：C可信回调最小返回；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| operation_id | ID | R/N | 无 | 按公共类型定义 | C可信回调最小返回 |
| resource_id | ID | R/N | 无 | 按公共类型定义 | C可信回调最小返回 |
| applied | boolean | R/N | 无 | 重复/晚到/非法回退可false，审计保留 | C可信回调最小返回 |
| ignore_reason | Reason | R/Y | null | 按公共类型定义 | C可信回调最小返回 |
| received_at | DateTime | R/N | 无 | 按公共类型定义 | C可信回调最小返回 |
| is_simulated | boolean | R/N | 无 | 后端适配决定；不向外部回传患者余额/完整健康内容 | C可信回调最小返回 |

### DemoTransitionInput（维护方：演示管理→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | 按公共类型定义 | 演示管理→C |
| target_status | string | R/N | 无 | 仅合法in_progress/completed/cancelled/failed | 演示管理→C |
| reason | Text | R/N | 无 | 清楚标模拟操作 | 演示管理→C |

### ServiceFeedbackInput（维护方：患者→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| client_feedback_id | ID | R/N | 无 | 稳定操作号 | 患者→C |
| expected_feedback_revision | integer | R/N | 无 | ≥0，首次0；更正匹配当前反馈修订 | 患者→C |
| participation | string | R/N | 无 | provided/declined/unable；拒绝不是负面疗效 | 患者→C |
| support_needs | Text | R/Y | null | 需求变化；provided时至少一维实际内容 | 患者→C |
| support_acceptance | Text | R/Y | null | 接受程度/继续意愿 | 患者→C |
| intervention_effectiveness | Text | R/Y | null | 执行结果/主观改善描述，不冒充因果疗效 | 患者→C |
| willing_to_continue | boolean | R/Y | null | 未知null，不强迫接受 | 患者→C |
| missing_reason | Reason | R/Y | null | declined/unable或维度缺失说明 | 患者→C |

### ServiceFeedback（维护方：C患者反馈；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| feedback_id | ID | R/N | 无 | 按公共类型定义 | C患者反馈 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C患者反馈 |
| service_id | ID | R/N | 无 | 按公共类型定义 | C患者反馈 |
| feedback_revision | Version | R/N | 无 | 按公共类型定义 | C患者反馈 |
| supersedes_feedback_id | ID | R/Y | null | 更正追加新事实，不覆盖旧意见 | C患者反馈 |
| participation | string | R/N | 无 | provided/declined/unable | C患者反馈 |
| support_needs | Text | R/Y | null | 按公共类型定义 | C患者反馈 |
| support_acceptance | Text | R/Y | null | 按公共类型定义 | C患者反馈 |
| intervention_effectiveness | Text | R/Y | null | 按公共类型定义 | C患者反馈 |
| willing_to_continue | boolean | R/Y | null | 按公共类型定义 | C患者反馈 |
| missing_reason | Reason | R/Y | null | 按公共类型定义 | C患者反馈 |
| recorded_at | DateTime | R/N | 无 | 按公共类型定义 | C患者反馈 |
| meta | Meta | R/N | 无 | 按公共类型定义 | C患者反馈 |

### PeerGroup（维护方：C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| group_id | ID | R/N | 无 | 按公共类型定义 | C |
| resource_id | ID | R/N | 无 | 入组对应C资源/申请 | C |
| title | ShortText | R/N | 无 | 按公共类型定义 | C |
| description | Text | R/N | 无 | 按公共类型定义 | C |
| matching_tags | string[] | R/N | 无 | 组级主题，如同演示病种/阶段/作息，不公开患者标签 | C |
| moderator_label | ShortText | R/N | 无 | 演示志愿者引导，不冒充真实专业人员 | C |
| availability | string | R/N | 无 | available/unavailable/unknown | C |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | C |

### MembershipCreateInput（维护方：本人→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| service_draft_id | ID | R/N | 无 | peer_support资源且目标group匹配 | 本人→C |
| draft_revision | Version | R/N | 无 | 按公共类型定义 | 本人→C |
| confirmation_ref_id | ID | R/N | 无 | 按公共类型定义 | 本人→C |
| sharing_scope_ref_id | ID | R/N | 无 | 按公共类型定义 | 本人→C |

### Membership（维护方：C本人私有视图；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| membership_id | ID | R/N | 无 | 按公共类型定义 | C本人私有视图 |
| patient_id | ID | R/N | 无 | 仅本人/受控业务可见，不进入其他成员帖子 | C本人私有视图 |
| group_id | ID | R/N | 无 | 按公共类型定义 | C本人私有视图 |
| service_id | ID | R/N | 无 | 复用唯一C入组申请，不建第二份 | C本人私有视图 |
| alias | ShortText | R/N | 无 | 组内随机匿名昵称，不由真实姓名派生 | C本人私有视图 |
| status | string | R/N | 无 | pending/active/left | C本人私有视图 |
| joined_at | DateTime | R/N | 无 | 按公共类型定义 | C本人私有视图 |
| activated_at | DateTime | R/Y | null | 服务实际受理后才能交流 | C本人私有视图 |
| left_at | DateTime | R/Y | null | 按公共类型定义 | C本人私有视图 |
| leave_reason | Reason | R/Y | null | 按公共类型定义 | C本人私有视图 |
| meta | Meta | R/N | 无 | 按公共类型定义 | C本人私有视图 |

### MembershipLeaveInput（维护方：本人→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | 按公共类型定义 | 本人→C |
| reason | Reason | O/Y | null | 不强制解释退出 | 调用方 |

### PeerPostInput（维护方：活跃成员→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| client_post_id | ID | R/N | 无 | 稳定提交号 | 活跃成员→C |
| content | PeerText | R/N | 无 | 1—1000字，纯文字，不含附件/即时外链 | 本人 |

### PeerPost（维护方：C组员可见视图；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| post_id | ID | R/N | 无 | 按公共类型定义 | C组员可见视图 |
| group_id | ID | R/N | 无 | 按公共类型定义 | C组员可见视图 |
| author_alias | ShortText | R/N | 无 | 无真实patient/account/membership ID | C组员可见视图 |
| content | PeerText | R/N | 无 | 按公共类型定义 | C组员可见视图 |
| moderation_status | string | R/N | 无 | pending/visible/hidden；非本人/审核者只返回visible | C组员可见视图 |
| created_at | DateTime | R/N | 无 | 按公共类型定义 | C组员可见视图 |
| moderated_at | DateTime | R/Y | null | 按公共类型定义 | C组员可见视图 |
| revision | Version | R/N | 无 | 按公共类型定义 | C组员可见视图 |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | C组员可见视图 |

### PostModerationInput（维护方：受控志愿者/管理→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | 按公共类型定义 | 受控志愿者/管理→C |
| decision | string | R/N | 无 | visible/hidden | 受控志愿者/管理→C |
| reason | Reason | R/N | 无 | 真实审核说明；不能冒充专业医疗建议审核 | 受控志愿者/管理→C |

### PointsRule（维护方：C注册程序规则；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| rule_code | string | R/N | 无 | daily_record/five_day_block/weekly_review/peer_participation | C注册程序规则 |
| points | integer | R/N | 无 | 建议分别2/5/3/2，正整数 | C注册程序规则 |
| period | string | R/N | 无 | day/five_day_block/week | C注册程序规则 |
| max_awards_per_period | integer | R/N | 无 | 1 | C注册程序规则 |
| eligibility_description | Text | R/N | 无 | 实际来源和参与条件，不按LLM印象给分 | C注册程序规则 |

### PointsRules（维护方：C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| rules_version | string | R/N | 无 | 按公共类型定义 | C |
| timezone_source | string | R/N | 无 | patient，使用患者本地计划日 | C |
| week_start_day | integer | R/N | 无 | 建议1=周一，按ISO周 | C |
| rules | PointsRule[] | R/N | 无 | 4类已登记规则；未确认数值不实际核奖 | C |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | C |

### PointsAccount（维护方：C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| points_account_id | ID | R/N | 无 | 按公共类型定义 | C |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C |
| balance | integer | R/N | 无 | ≥0，可用整数积分；程序/事务维护 | C |
| meta | Meta | R/N | 无 | 账户变更乐观并发，GET不创建账户 | C |

### LedgerEntry（维护方：C不可变流水；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| ledger_id | ID | R/N | 无 | 按公共类型定义 | C不可变流水 |
| points_account_id | ID | R/N | 无 | 按公共类型定义 | C不可变流水 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C不可变流水 |
| entry_kind | string | R/N | 无 | award/redemption_debit/redemption_refund | C不可变流水 |
| delta | integer | R/N | 无 | award/refund>0，debit<0；不是医学行为处罚 | C不可变流水 |
| balance_after | integer | R/N | 无 | ≥0 | C不可变流水 |
| business_key | string | R/N | 无 | 1—200字符，稳定业务去重，不因规则版本更新重新发奖 | C不可变流水 |
| rule_code | string | R/Y | null | 奖励规则；兑换扣减/退分null | C不可变流水 |
| rules_version | string | R/Y | null | 奖励按当时规则，不能事后改历史 | C不可变流水 |
| source_refs | SourceRef[] | R/N | 无 | 实际记录/回顾/可见参与等可核对来源 | C不可变流水 |
| redemption_id | ID | R/Y | null | 兑换/退分关联 | C不可变流水 |
| reverses_ledger_id | ID | R/Y | null | 退款只指向原扣减，最多一次全额 | C不可变流水 |
| created_at | DateTime | R/N | 无 | 按公共类型定义 | C不可变流水 |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | C不可变流水 |

### AwardDateAllocation（维护方：C连续奖励分配内部证据；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| allocation_id | ID | R/N | 无 | 按公共类型定义 | C连续奖励分配内部证据 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C连续奖励分配内部证据 |
| rule_code | string | R/N | 无 | five_day_block | C连续奖励分配内部证据 |
| local_date | LocalDate | R/N | 无 | 每位患者每规则每自然日最多分配一次 | C连续奖励分配内部证据 |
| ledger_id | ID | R/N | 无 | 连续5日块的奖励流水 | C连续奖励分配内部证据 |
| rules_version | string | R/N | 无 | 按公共类型定义 | C连续奖励分配内部证据 |
| assigned_at | DateTime | R/N | 无 | 按公共类型定义 | C连续奖励分配内部证据 |

### PointsReconcileInput（维护方：可信程序/受控演示→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| patient_id | ID | R/N | 无 | 按公共类型定义 | 可信程序/受控演示→C |
| window_start | DateTime | R/N | 无 | 按公共类型定义 | 可信程序/受控演示→C |
| window_end | DateTime | R/N | 无 | 按公共类型定义 | 可信程序/受控演示→C |
| rules_version | string | R/N | 无 | 已确认启用的规则；不能传delta/balance | 可信程序/受控演示→C |

### PointsReconcileResult（维护方：C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C |
| window_start | DateTime | R/N | 无 | 按公共类型定义 | C |
| window_end | DateTime | R/N | 无 | 按公共类型定义 | C |
| account | PointsAccount | R/N | 无 | 按公共类型定义 | C |
| new_entries | LedgerEntry[] | R/N | 无 | 只真正新增的奖励 | C |
| new_allocations | AwardDateAllocation[] | R/N | 无 | 五天块每日期唯一 | C |
| skipped_keys | string[] | R/N | 无 | 已核过/不重复的业务键 | C |
| source_issues | Issue[] | R/N | 无 | 不足/未接入/失效来源 | C |
| rules_version | string | R/N | 无 | 按公共类型定义 | C |

### ManagementReviewInput（维护方：患者明确完成→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| client_review_id | ID | R/N | 无 | 按公共类型定义 | 患者明确完成→C |
| week_start | LocalDate | R/N | 无 | 建议当前患者本地ISO周一，拒绝未来或任意冒充旧周 | 患者明确完成→C |
| reflection | Text | O/Y | null | 低负担描述，不是心理量表 | 调用方 |
| confirmed_completed | boolean | R/N | 无 | 必须true，明确完成当前周回顾 | 患者明确完成→C |

### ManagementReview（维护方：C管理参与；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| review_id | ID | R/N | 无 | 按公共类型定义 | C管理参与 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C管理参与 |
| week_start | LocalDate | R/N | 无 | 按公共类型定义 | C管理参与 |
| reflection | Text | R/Y | null | 按公共类型定义 | C管理参与 |
| completed_at | DateTime | R/N | 无 | 按公共类型定义 | C管理参与 |
| rules_version | string | R/N | 无 | 按公共类型定义 | C管理参与 |
| meta | Meta | R/N | 无 | 按公共类型定义 | C管理参与 |

### Reward（维护方：C自愿额外权益；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| reward_id | ID | R/N | 无 | 按公共类型定义 | C自愿额外权益 |
| reward_version | string | R/N | 无 | 按公共类型定义 | C自愿额外权益 |
| name | ShortText | R/N | 无 | 按公共类型定义 | C自愿额外权益 |
| description | Text | R/N | 无 | 按公共类型定义 | C自愿额外权益 |
| points_cost | integer | R/N | 无 | 建议30/40/50/60/80之一，>0 | C自愿额外权益 |
| kind | string | R/N | 无 | digital_content/service_appointment | C自愿额外权益 |
| availability | string | R/N | 无 | available/unavailable/unknown | C自愿额外权益 |
| resource_id | ID | R/Y | null | 人员服务需reward_only资源；数字内容null | C自愿额外权益 |
| is_essential | boolean | R/N | 无 | 本期可兑额外权益false，必要医疗不放积分门槛 | C自愿额外权益 |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | C自愿额外权益 |

### RedemptionInput（维护方：本人→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| reward_id | ID | R/N | 无 | 按公共类型定义 | 本人→C |
| reward_version | string | R/N | 无 | 用户看见的价格/项目版本 | 本人→C |
| expected_account_revision | Version | R/N | 无 | 避免多标签并发覆盖 | 本人→C |
| confirmed | boolean | R/N | 无 | 自愿兑换true | 本人→C |
| service_draft_id | ID | O/Y | null | 人员预约必有，数字内容null/省略 | 调用方 |
| draft_revision | Version | O/Y | null | 人员预约对应精确草稿 | 调用方 |
| confirmation_ref_id | ID | O/Y | null | 需要共享给人员时必有 | 调用方 |
| sharing_scope_ref_id | ID | O/Y | null | O有效范围，与服务确认一致 | 调用方 |

### Redemption（维护方：C独立兑换记录；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| redemption_id | ID | R/N | 无 | 按公共类型定义 | C独立兑换记录 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C独立兑换记录 |
| reward_id | ID | R/N | 无 | 按公共类型定义 | C独立兑换记录 |
| reward_version | string | R/N | 无 | 按公共类型定义 | C独立兑换记录 |
| reward_name | ShortText | R/N | 无 | 按公共类型定义 | C独立兑换记录 |
| points_spent | integer | R/N | 无 | >0，创建时成本快照 | C独立兑换记录 |
| status | string | R/N | 无 | submitted/fulfilling/completed/failed，非C服务状态 | C独立兑换记录 |
| points_status | string | R/N | 无 | debited/refunded，和交付状态分开 | C独立兑换记录 |
| debit_ledger_id | ID | R/N | 无 | 按公共类型定义 | C独立兑换记录 |
| refund_ledger_id | ID | R/Y | null | 明确失败未交付才一次全额，结果未知不盲退 | C独立兑换记录 |
| balance_after_debit | integer | R/N | 无 | ≥0，历史扣减后的余额快照不是永远当前余额 | C独立兑换记录 |
| fulfillment_id | ID | R/N | 无 | 按公共类型定义 | C独立兑换记录 |
| service_id | ID | R/Y | null | 人员预约创建的唯一C服务，数字内容null | C独立兑换记录 |
| redeemed_at | DateTime | R/N | 无 | 按公共类型定义 | C独立兑换记录 |
| meta | Meta | R/N | 无 | 按公共类型定义 | C独立兑换记录 |

### DigitalArtifact（维护方：C按已确认资料生成；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| artifact_id | ID | R/N | 无 | 按公共类型定义 | C按已确认资料生成 |
| title | ShortText | R/N | 无 | 按公共类型定义 | C按已确认资料生成 |
| media_type | string | R/N | 无 | text/plain，首版可保存管理文本 | C按已确认资料生成 |
| text | Text | R/N | 无 | 管理清单/记录卡，不能生成个体化改药补服指令 | C按已确认资料生成 |
| source_refs | SourceRef[] | R/N | 无 | 实际计划/知识版本，未知不编造 | C按已确认资料生成 |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | C按已确认资料生成 |

### Fulfillment（维护方：C交付事实；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| fulfillment_id | ID | R/N | 无 | 按公共类型定义 | C交付事实 |
| redemption_id | ID | R/N | 无 | 按公共类型定义 | C交付事实 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C交付事实 |
| kind | string | R/N | 无 | digital_content/service_appointment | C交付事实 |
| status | string | R/N | 无 | pending/in_progress/completed/failed/cancelled/outcome_unknown | C交付事实 |
| service_id | ID | R/Y | null | 人员预约必须对应唯一C服务 | C交付事实 |
| artifact | DigitalArtifact | R/Y | null | 数字交付完成时实际内容，未完成null | C交付事实 |
| failure_reason | Reason | R/Y | null | failed/cancelled/unknown明确原因 | C交付事实 |
| task_id | ID | R/Y | null | A注册C交付任务引用 | C交付事实 |
| updated_at | DateTime | R/N | 无 | 按公共类型定义 | C交付事实 |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | C交付事实 |

### FulfillmentReceiptInput（维护方：可信交付方→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| provider_event_id | ID | R/N | 无 | 按公共类型定义 | 可信交付方→C |
| fulfillment_id | ID | R/N | 无 | 按公共类型定义 | 可信交付方→C |
| status | string | R/N | 无 | in_progress/completed/failed/cancelled/outcome_unknown | 可信交付方→C |
| occurred_at | DateTime | R/N | 无 | 按公共类型定义 | 可信交付方→C |
| result_ref | ID | R/Y | null | 实际产物或已完成C服务引用，不接任意URL/HTML | 可信交付方→C |
| failure_reason | Reason | R/Y | null | 失败/未知时必有 | 可信交付方→C |

### RedemptionFeedbackInput（维护方：本人→C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| client_feedback_id | ID | R/N | 无 | 按公共类型定义 | 本人→C |
| participation | string | R/N | 无 | provided/declined/unable | 本人→C |
| experience | Text | O/Y | null | 自愿额外权益体验，不是疗效分数 | 调用方 |
| service_feedback_id | ID | O/Y | null | 同一实际服务已反馈可引用，免重复问同一内容 | 调用方 |

### RedemptionFeedback（维护方：C；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| feedback_id | ID | R/N | 无 | 按公共类型定义 | C |
| patient_id | ID | R/N | 无 | 按公共类型定义 | C |
| redemption_id | ID | R/N | 无 | 按公共类型定义 | C |
| participation | string | R/N | 无 | provided/declined/unable | C |
| experience | Text | R/Y | null | 按公共类型定义 | C |
| service_feedback_id | ID | R/Y | null | 按公共类型定义 | C |
| recorded_at | DateTime | R/N | 无 | 按公共类型定义 | C |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | C |

### ServiceDispatchTaskPayload（维护方：C→A拟议注册；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| service_id | ID | R/N | 无 | 按公共类型定义 | C→A拟议注册 |
| service_revision | Version | R/N | 无 | 按公共类型定义 | C→A拟议注册 |
| confirmation_ref_id | ID | R/N | 无 | 按公共类型定义 | C→A拟议注册 |
| sharing_scope_ref_id | ID | R/N | 无 | 执行前再验O有效授权，消息只取获准范围 | C→A拟议注册 |

### RewardFulfillmentTaskPayload（维护方：C→A拟议注册；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| redemption_id | ID | R/N | 无 | 按公共类型定义 | C→A拟议注册 |
| fulfillment_id | ID | R/N | 无 | 按公共类型定义 | C→A拟议注册 |
| reward_id | ID | R/N | 无 | 按公共类型定义 | C→A拟议注册 |
| reward_version | string | R/N | 无 | 按公共类型定义 | C→A拟议注册 |

### ProfileFixtureInput（维护方：演示管理→O适配，C仅入口；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| profile_fixture_id | ID | R/N | 无 | 后端已登记虚构画像+问卷来源，不传任意标签/CAS | 演示管理→O适配，C仅入口 |
| expected_profile_id | ID | R/N | 无 | 当前O画像，防旧场景覆盖 | 演示管理→O适配，C仅入口 |
| confirmed | boolean | R/N | 无 | 明确切换true，非demo拒绝 | 演示管理→O适配，C仅入口 |

### ProfileFixtureResult（维护方：O唯一模拟画像事实；字段版本C-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/单位/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| patient_id | ID | R/N | 无 | 按公共类型定义 | O唯一模拟画像事实 |
| profile_fixture_id | ID | R/N | 无 | 按公共类型定义 | O唯一模拟画像事实 |
| profile_id | ID | R/N | 无 | O返回的真实模拟结果ID，旧画像不删除 | O唯一模拟画像事实 |
| is_simulated | boolean | R/N | 无 | 必须true，不产生真实CAS预测 | O唯一模拟画像事实 |

## 3 业务唯一性、来源与事务（本批待确认细化）

1. C34同一动作调用O权威授权服务取得SharingScopeRef，C只保存确认和引用；必须核对家庭关系/适用授权与患者真实动作，不把confirmed=true当任意共享许可。范围、主体、用途变更重新确认；缺O依赖拒绝。撤销从O阻止后续共享，不暗中恢复。
2. ServiceDraft.draft_revision是精确内容号；meta.revision还可反映关联/提交等变化。C07同库事务核验精确内容/资源/确认/O授权→唯一Service submitted→草稿链接→去重/失效/待派发登记；失败回滚，不通知第三方。B23由同一服务复用，不能自行维护第二份正式申请。
3. CQ-BC01拟议B23增加必填service_draft_revision。该部分原BCX-01留待C联合确认，现明确防止浮动“最新”内容；对调用方有请求字段影响，确认C后另登记B增量，不修改B原稿。
4. ProviderResponse必须源自可信服务方/资格或mock_example；LLM不能以药师身份回传、改O计划。C11回执只合法推进已确认五状态，C12只模拟合法转换；结果/理由/发生/接收及来源版本保存。B source_version=Service.meta.revision的十进制字符串，状态版本不凭AI生成。
5. submitted/in_progress的患者取消，demo可明确合法cancelled；真实已派发/在途只能先cancellation_requested，待可靠结果确认。完成/取消/失败不回退；晚到回执审计，不假称第三方已停。授权撤销后的结果不可恢复共享动作。
6. 三维反馈、愿不愿继续和服务完成独立；declined/unable保留原因，不当负面评分。反馈更正新增feedback_revision/supersedes，原意见不覆盖；更正是否影响下轮策略由原维护方处理，不自动改画像/训练。
7. Membership最初pending且关联唯一C服务，实际受理才active；入组服务completed不自动退出小组。pending/active可left，退出立即停止后续组访问/发帖；正式服务生命周期仍独立留存，不能借退组回退服务终态。其他成员只获PeerPost匿名视图，无真实账号/患者/成员ID。
8. 帖子先pending，受控志愿者/管理身份再visible/hidden；患者不能自行设审核结果。纯文本安全展示、不即时外链/附件；身份/病药隐私风险提示与最小文本检查不能被声称为绝对匿名保证。实际运营人员未提供时只演示，不伪称真实社区值守。
9. 日参与奖励+2：至少一条匹配已到时正式时段且质量valid的手动记录，实际来源可本人或已授权家人，taken/not_taken/postponed/unknown如实记录均不代表吞服验证；设备自动数据不单独发奖。归属患者当地计划日，按唯一patient/rule_code/day键一次，不因规则版本变重发。
10. 连续5日+5：选择5个相邻合格本地日，每日最多分配一个five_day_block奖励。AwardDateAllocation唯一(patient,rule_code,local_date)，按最早可用连续未分配5日成块；旧已分配日期不因补录/更正重复分配，每5日块最多一条奖励。来源后来更正/撤销不自动扣回已获积分，保留标注、不再发相同奖励。
11. 周一至周一为患者本地ISO周，周回顾+3只当前周明确完成一次；小组参与+2须该周本人有实际visible帖子/活动来源（首版只文字帖），不是仅推荐/入组/读消息。反复提交/审核回调不重复发奖，家人/自动模型不能代造本人参与。
12. 核奖从A有效证据及C真实回顾/可见帖子读取，客户端不能传分值/余额。账户与奖励流水、业务键及分配日期同事务；余额始终等于有效不可变流水之和，原流水不编辑。GET账户不静默初始化，需显式虚构数据/初始化建立。
13. 兑换在同库事务校验资源版本/自愿动作/账户修订与足额余额，原子写扣减+兑换+交付+必要人员服务及业务去重。数字内容不需第三方共享确认；人员预约必须C草稿与O共享确认，reward_only资源不能绕过兑换从C07直接免费创建；必要支持资源support_free仍独立可申请。
14. 明确未交付且failed/cancelled时一次全额退分，唯一refund:<redemption_id>指向原扣减；失败状态、退分流水和余额更新同事务。outcome_unknown先核查，不盲重发/退分。已交付后争议/部分履约/人工异常修正尚未定义，不自动扣回或二次发货；晚到成功不复活已终止/退分单。
15. service_appointment交付只映射原C服务：completed依据该服务真实完成；failed/cancelled据同一C权威事实，不能C31独立伪造第二份服务完成。数字内容才依据实际artifact。回执只OperationAck，外部方看不到患者点数余额。
16. CX-A01拟加dispatch_service/fulfill_reward与owner_module=C，载荷见本表，仅注册C处理器。A投递submitted不是C服务in_progress/completed；执行前重验确认/共享/取消/有效期，沿用A安全预算，不另建调度。具体真实机构/SLA/库存/支付/配送未接入。
17. C40由O受控fixture适配选择预登记虚构问卷/画像结果，旧O结果保留、CAS仍null；不得由C计算/写任意画像或改研究数据。非demo、任意label/CAS参数、跨患者fixture都拒绝；该O新增接口需C确认后再登记。
18. 所有示例及工程参数是C草案，未实际发奖/扣分/创建服务/交付。医学知识仍用B2；临床阈值/专业机构/审核/真实联系人不编造。

## 4 保留事项

C00 CQ01—CQ16需用户确认；真实第三方授权协议/签名/资质与隐私留存、权益争议/异常人工点数修正、实际社群运营、长期离线补偿、O/A/B未决仍不冻结。C确认后还需全流程联合契约，不进入S01。

