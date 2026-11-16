# S00 A批：完整字段草案（draft01）

2026-11-16，Asia/Shanghai；版本A-draft01。**所有新增字段/类型/枚举/默认/状态/规则均为建议、待确认；未建表、未实现接口**。公共基础与O的已确认部分引用docs/contracts/公共基础与O_v0.1_确认清单.md及其不可变来源；未决排除项继续有效。

## 1 统一类型、字段规则与请求位置

逐字段表中的R/N=必须出现且不可null，R/Y=必须出现但可null，O/N=可省略但传入不可null，O/Y=可省略也可null。输出字段全部R；请求体只含对应Input表，未列字段422，不能从输出对象照抄服务端属性。类型ID/Version/DateTime/LocalDate/Timezone/Text/ShortText/Reason/Meta/Schedule/List<T>/Envelope<T>完整复用公共/O确认来源；不改变其定义。所有本节及以下对象字段版本均A-draft01，各表默认维护/生成方在标题列明，行内生成方优先；“无”无默认，“null/[]”须结合R/O判断是否能省略。

number必须有限，拒绝NaN/Infinity，不自动截断成正常值。string decimal来自O计划，不与指标number混用。EventPayload按event_kind判别：medication=EvidencePayload，measurement=MeasurementPayload；更正不得改event_kind。Availability为available/not_collected/not_integrated/unavailable/restricted；确实无记录用not_collected，依赖失败用unavailable，不伪装[]成功。

TaskKind候选：refresh_statistics/refresh_summary/deliver_reminder/check_in_node/deliver_intervention；TaskPayload依次为WindowTaskPayload（前两种）、ReminderTaskPayload、CheckinTaskPayload、InterventionTaskPayload。任务参数只作已注册业务输入，不接受任意Python/命令/URL执行。

已登录网页写入继承Cookie/CSRF/Idempotency-Key；上传Content-Type为multipart/form-data，其他JSON。可信设备/模块/渠道走独立适配身份，不能拿body自报role/module/device/patient代替认证；签名协议未提供时真实入口拒绝，demo仅可虚构数据。GET无CSRF/幂等键，均先查患者权限。新权限AX-01见A00，尚未生效。

| 公共查询字段 | 类型 | 必填/可空 | 默认 | 格式/范围/生成方 |
| --- | --- | --- | --- | --- |
| patient_id（路径p） | ID | R/N | 无 | 客户端引用，服务端核验实际患者 |
| 资源id（路径） | ID | R/N | 无 | 对应卡中的file/draft/event/binding/task/execution ID，查归属 |
| cursor / limit | opaque string / integer | O/N | 首批 / 20 | 继承公共上限100，游标绑定账号/患者/筛选 |
| window_start / window_end | DateTime | R/N，对范围查询 | 无 | [start,end)，end>start，建议≤31天；客户端指定 |
| as_of | DateTime | O/N | 请求接收时服务器当前时间 | 统计固定cutoff；不能让普通患者用未来as_of伪造已到时 |
| data_environment | string | R/N，对事件/统计/摘要等 | 无 | demo/real，显式选择且后端检查环境；不允许隐式混算 |
| state（事件列表） | string | O/N | effective | effective/withdrawn/all；历史查看需同等权限 |
| status（草稿/任务列表） | string | O/N | 不筛选 | 对应对象枚举，不能混用服务状态 |
| metric_code（指标列表/趋势） | ShortText | 趋势R/N、列表O/N | 列表不筛选 | 注册指标；未知代码不猜单位 |
| unit / method_code（指标趋势） | string / ShortText | unit R/N、method_code O/Y | 无 / null | 明确可比组，null表示方法未知组而非合并所有方法 |
| plan_id（匹配查询） | ID | O/N | 不筛选 | 仅当前患者计划 |
| event_kind（修订以外的通用筛选） | string | O/N | 卡片固定种类 | medication/measurement，专用路由不接受另类 |

所有卡片未列查询字段不接受。本轮不新增通用编辑原事件的PUT；更正/撤销必须走独立修订接口。

## 2 对象逐字段定义

### PlanRef（维护方：O引用，A只读；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| plan_id | ID | R/N | 无 | 按公共类型定义 | O引用，A只读 |
| plan_version | Version | R/N | 无 | 按公共类型定义 | O引用，A只读 |

### Issue（维护方：A4/A6/A5；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| code | ShortText | R/N | 无 | 稳定原因码 | A4/A6/A5 |
| message | Text | R/N | 无 | 可读脱敏说明 | A4/A6/A5 |
| field | ShortText | R/Y | null | 如unit；不定位字段时null | A4/A6/A5 |

### File（维护方：A2；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| file_id | ID | R/N | 无 | 服务器生成 | A2 |
| patient_id | ID | R/N | 无 | 路径及授权决定 | A2 |
| source_event_id | ID | R/N | 无 | 本次上传稳定来源编号 | 调用方 |
| original_name | ShortText | R/N | 无 | 只显示，不作服务器路径 | A2 |
| media_type | string | R/N | 无 | application/pdf/image/png/image/jpeg（本批建议） | A2 |
| size_bytes | integer | R/N | 无 | 1—10485760字节 | A2 |
| sha256 | string | R/N | 无 | 64位小写十六进制，原内容摘要 | A2 |
| status | string | R/N | 无 | saved/save_failed；saved才可读内容 | A2 |
| source | string | R/N | 无 | manual_upload，不表示已OCR | A2 |
| meta | Meta | R/N | 无 | 按公共类型定义 | A2 |

### FileUploadInput（维护方：网页→A2；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| file | binary | R/N | 无 | multipart/form-data单文件，类型/大小检查 | 用户 |
| source_event_id | ID | R/N | 无 | 稳定来源编号，不是request_id | 用户 |

### FileContent（维护方：A2；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| file_id | ID | R/N | 无 | 按公共类型定义 | A2 |
| media_type | string | R/N | 无 | 与已保存文件一致 | A2 |
| content_encoding | string | R/N | 无 | base64 | A2 |
| content_base64 | string | R/N | 无 | 原文件内容base64；读取权限先验证 | A2 |
| sha256 | string | R/N | 无 | 解码后原字节SHA256 | A2 |

### DraftEntry（维护方：A2录入，正式字段语义归O4；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| draft_entry_id | ID | R/N | 无 | 草稿临时行键，网页稳定生成，非正式plan_entry_id | 网页 |
| medication_id | ID | R/N | 无 | 引用同患者O药品资料 | 网页引用 |
| dose_value | string | R/Y | null | 正十进制定点字符串；未录入null | 人工录入 |
| dose_unit | string | R/Y | null | 1—40字符；未知null，不猜单位 | 人工录入 |
| start_date | LocalDate | R/Y | null | 未录入null | 人工录入 |
| end_date | LocalDate | R/Y | null | 长期或未知可null；若有不早于开始 | 人工录入 |
| schedule | Schedule | R/Y | null | 复用O的daily/weekly/times/weekdays；未录入null | 人工录入 |
| meal_requirement | Text | R/Y | null | 原要求，不自动生成 | 人工录入 |
| medical_notes | Text | R/Y | null | 实际医嘱原文，不以AI生成冒充 | 人工录入 |
| strict_timing | boolean | R/Y | null | 未知null，不当false放行偏移 | 人工录入 |
| min_interval_minutes | integer | R/Y | null | 正整数分钟，仅原资料已提供时写 | 人工录入 |
| source_file_ids | ID[] | R/N | [] | 同患者授权文件；纯手工可空 | 人工引用 |

### Draft（维护方：A2，确认事实来自O；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| draft_id | ID | R/N | 无 | 按公共类型定义 | A2，确认事实来自O |
| patient_id | ID | R/N | 无 | 按公共类型定义 | A2，确认事实来自O |
| source | string | R/N | 无 | manual/manual_transcription；均为人工核对 | A2，确认事实来自O |
| source_file_ids | ID[] | R/N | [] | 同患者授权文件 | A2，确认事实来自O |
| entries | DraftEntry[] | R/N | 无 | ≥1条；正式确认前内容可不完整 | A2，确认事实来自O |
| content_revision | Version | R/N | 无 | 仅内容修改递增；O的draft_revision引用此字段 | A2，确认事实来自O |
| status | string | R/N | 无 | editing/pending_confirmation/confirmed/returned | A2，确认事实来自O |
| submission_id | ID | R/Y | null | 提交后独立审计ID | A2，确认事实来自O |
| submitted_revision | Version | R/Y | null | 提交的content_revision，不能随查询浮动 | A2，确认事实来自O |
| formal_plan | PlanRef | R/Y | null | 只由O正式确认结果写；未确认null | A2，确认事实来自O |
| return_reason | Text | R/Y | null | returned时必须说明 | A2，确认事实来自O |
| meta | Meta | R/N | 无 | 资源revision包括状态变化，不能冒充content_revision | A2，确认事实来自O |

### DraftCreateInput（维护方：网页→A2；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| source_file_ids | ID[] | O/N | [] | 同患者文件 | 调用方 |
| entries | DraftEntry[] | R/N | 无 | ≥1，允许尚缺字段 | 用户 |

### DraftPutInput（维护方：网页→A2；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | 匹配Draft.meta.revision | 用户引用 |
| source_file_ids | ID[] | R/N | 无 | 全量快照，[]不是缺失 | 用户 |
| entries | DraftEntry[] | R/N | 无 | 完整草稿行快照 | 用户 |

### DraftSubmitInput（维护方：网页→A2；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | 当前资源修订 | 用户引用 |
| content_revision | Version | R/N | 无 | 本次提交精确内容修订 | 用户引用 |

### EvidencePayload（维护方：A2/A3/A4；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| reported_status | string | R/Y | null | taken/not_taken/postponed/unknown；报告与设备观察二选一 | A2/A3/A4 |
| observation | string | R/Y | null | box_opened/inferred_intake；设备观察，不等于本人报告 | A2/A3/A4 |
| medication_id | ID | R/Y | null | 无可靠条目引用可null | A2/A3/A4 |
| dose_slot_id | ID | R/Y | null | 需验证归属、版本，不能自报匹配成功 | A2/A3/A4 |
| plan_ref | PlanRef | R/Y | null | 有引用时必须与时段及患者一致 | A2/A3/A4 |
| raw_text | Text | R/Y | null | 保留可核对报告，非可执行指令 | A2/A3/A4 |

### MeasurementPayload（维护方：A2/A3/A4；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| metric_code | ShortText | R/N | 无 | 注册指标代码 | A2/A3/A4 |
| value | number | R/Y | null | 有限数值或null；0和null不同 | A2/A3/A4 |
| unit | string | R/Y | null | 原单位1—40字符；缺失采集可null | A2/A3/A4 |
| method_code | ShortText | R/Y | null | 实际测量方法；未知保留null | A2/A3/A4 |
| missing_reason | Reason | R/Y | null | value=null时必须非空；值存在时不得伪称未采集 | A2/A3/A4 |

### NormalizedMeasurement（维护方：A4；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| metric_code | ShortText | R/N | 无 | 按公共类型定义 | A4 |
| value | number | R/Y | null | 有限原/换算值；缺失不补零 | A4 |
| unit | string | R/Y | null | 已确认标准单位；未知单位不猜 | A4 |
| method_code | ShortText | R/Y | null | 不同方法不可无条件比较 | A4 |
| missing_reason | Reason | R/Y | null | 缺失或不可标准化原因 | A4 |

### Quality（维护方：A4；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| event_id | ID | R/N | 无 | 按公共类型定义 | A4 |
| event_revision | Version | R/N | 无 | 质量对应精确有效修订 | A4 |
| status | string | R/N | 无 | pending_validation/valid/needs_review/processing_failed | A4 |
| issues | Issue[] | R/N | [] | 质量问题非临床诊断 | A4 |
| normalized_measurement | NormalizedMeasurement | R/Y | null | 服药事件或尚未处理时null | A4 |
| processing_version | string | R/Y | null | 未处理null，处理后可定位 | A4 |
| processed_at | DateTime | R/Y | null | 未处理null | A4 |

### SourceEvent（维护方：A2/A3接收，A4维护有效视图；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| event_id | ID | R/N | 无 | 原始事实唯一ID | A2/A3接收，A4维护有效视图 |
| patient_id | ID | R/N | 无 | 可信身份/设备绑定决定 | A2/A3接收，A4维护有效视图 |
| event_kind | string | R/N | 无 | medication/measurement | A2/A3接收，A4维护有效视图 |
| source | string | R/N | 无 | manual/box/wearable；由可信适配决定 | A2/A3接收，A4维护有效视图 |
| source_event_id | ID | R/N | 无 | 来源内稳定编号 | A2/A3接收，A4维护有效视图 |
| evidence_type | string | R/Y | null | medication时self_report/family_report/box_opening/device_inference；measurement时null | A2/A3接收，A4维护有效视图 |
| occurred_at | DateTime | R/N | 无 | 事件实际发生，迟到不挪到接收当天 | A2/A3接收，A4维护有效视图 |
| received_at | DateTime | R/N | 无 | 服务器首次接收，重试不改变 | A2/A3接收，A4维护有效视图 |
| reporter_account_id | ID | R/Y | null | 手动来源取实际会话；设备来源null | A2/A3接收，A4维护有效视图 |
| device_id | ID | R/Y | null | 设备来源必有，手动null | A2/A3接收，A4维护有效视图 |
| state | string | R/N | 无 | effective/withdrawn | A2/A3接收，A4维护有效视图 |
| payload | EventPayload | R/N | 无 | 按event_kind为EvidencePayload或MeasurementPayload；此处是当前有效修订视图 | A2/A3接收，A4维护有效视图 |
| quality | Quality | R/N | 无 | 按公共类型定义 | A2/A3接收，A4维护有效视图 |
| link_status | string | R/N | 无 | unmatched/matched/review_required/not_applicable；独立于质量 | A2/A3接收，A4维护有效视图 |
| meta | Meta | R/N | 无 | revision对应有效事件修订；原始修订仍存历史 | A2/A3接收，A4维护有效视图 |

### MedicationEventInput（维护方：网页→A2；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| source_event_id | ID | R/N | 无 | 当前报告账号内稳定编号 | 用户 |
| occurred_at | DateTime | R/N | 无 | 不能无时区或猜吞服时间 | 用户 |
| reported_status | string | R/N | 无 | taken/not_taken/postponed/unknown | 用户 |
| medication_id | ID | O/Y | null | 同患者药品 | 调用方 |
| dose_slot_id | ID | O/Y | null | 同患者正式时段，仍须核验 | 调用方 |
| plan_ref | PlanRef | O/Y | null | 显式版本引用 | 调用方 |
| raw_text | Text | O/Y | null | 可选原话 | 调用方 |

### MeasurementInput（维护方：网页→A2；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| source_event_id | ID | R/N | 无 | 来源稳定编号 | 用户 |
| occurred_at | DateTime | R/N | 无 | 实际采样时刻 | 用户 |
| payload | MeasurementPayload | R/N | 无 | 字段逐项见上，不由网页提交质量 | 用户 |

### EventRevision（维护方：A4；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| event_id | ID | R/N | 无 | 按公共类型定义 | A4 |
| revision | Version | R/N | 无 | 按公共类型定义 | A4 |
| change_kind | string | R/N | 无 | original/correction/withdrawal | A4 |
| occurred_at | DateTime | R/N | 无 | 此修订的发生时间解释 | A4 |
| payload | EventPayload | R/N | 无 | 完整原始/更正内容 | A4 |
| reason | Reason | R/Y | null | original可null，更正/撤销必填 | A4 |
| replaces_revision | Version | R/Y | null | original=null；其他引用旧有效修订 | A4 |
| actor_account_id | ID | R/Y | null | 实际操作者或可信服务身份对应审计 | A4 |
| created_at | DateTime | R/N | 无 | 按公共类型定义 | A4 |
| is_simulated | boolean | R/N | 无 | 后端环境决定 | A4 |

### CorrectionInput（维护方：网页/可信服务→A4；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | 匹配当前有效事件修订 | 用户引用 |
| reason | Reason | R/N | 无 | 必须明确 | 用户 |
| occurred_at | DateTime | R/N | 无 | 完整替换时间解释 | 用户 |
| payload | EventPayload | R/N | 无 | 与原event_kind同类型；不能改患者/来源身份/来源号 | 用户 |

### WithdrawalInput（维护方：网页/可信服务→A4；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | 当前有效事件修订 | 用户引用 |
| reason | Reason | R/N | 无 | 撤销不是删除历史 | 用户 |

### ReprocessInput（维护方：受控服务→A4；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | 精确待处理修订 | 可信调用方 |

### DeviceBinding（维护方：建议A3维护，O供患者授权；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| binding_id | ID | R/N | 无 | 按公共类型定义 | 建议A3维护，O供患者授权 |
| device_id | ID | R/N | 无 | 可信已注册设备 | 建议A3维护，O供患者授权 |
| patient_id | ID | R/N | 无 | 实际本人确认绑定 | 建议A3维护，O供患者授权 |
| source | string | R/N | 无 | box/wearable/mock_adapter | 建议A3维护，O供患者授权 |
| status | string | R/N | 无 | active/revoked | 建议A3维护，O供患者授权 |
| bound_at | DateTime | R/N | 无 | 按公共类型定义 | 建议A3维护，O供患者授权 |
| revoked_at | DateTime | R/Y | null | 按公共类型定义 | 建议A3维护，O供患者授权 |
| meta | Meta | R/N | 无 | 按公共类型定义 | 建议A3维护，O供患者授权 |

### DeviceBindingInput（维护方：本人/受控管理→A3；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| device_id | ID | R/N | 无 | 必须已经可信注册，不能body自造设备 | 调用方 |
| confirmed | boolean | R/N | 无 | 必须true且服务端核实本人动作 | 本人 |

### DeviceEventInput（维护方：可信设备→A3；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| device_id | ID | R/N | 无 | 必须匹配认证主体 | 设备 |
| source_event_id | ID | R/N | 无 | 设备内稳定编号 | 设备 |
| occurred_at | DateTime | R/N | 无 | 采样/观察真实发生时间 | 设备 |
| event_kind | string | R/N | 无 | medication/measurement | 设备 |
| payload | EventPayload | R/N | 无 | 设备仅可设备观察或指标，不能填self_report | 设备 |

### DemoDeviceInput（维护方：演示管理→A3；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| patient_id | ID | R/N | 无 | 仅虚构案例 | 演示者 |
| device_id | ID | R/N | 无 | 已绑定模拟设备 | 演示者 |
| scenario | string | R/N | 无 | normal_box/duplicate/late_upload/measurement_missing/unknown_unit/unbound | 演示者 |
| scenario_run_id | ID | R/N | 无 | 同次场景重放稳定，用于派生来源事件ID | 演示者 |
| occurred_at | DateTime | R/N | 无 | 可控演示时刻 | 演示者 |

### Match（维护方：A6；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| match_id | ID | R/N | 无 | 按公共类型定义 | A6 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | A6 |
| event_id | ID | R/N | 无 | 按公共类型定义 | A6 |
| event_revision | Version | R/N | 无 | 当前有效证据修订 | A6 |
| dose_slot_id | ID | R/Y | null | 唯一合法关联或null | A6 |
| candidate_slot_ids | ID[] | R/N | [] | 只同患者/版本合法候选 | A6 |
| link_status | string | R/N | 无 | unmatched/matched/review_required/not_applicable | A6 |
| reason | Reason | R/Y | null | 未匹配/待复核必须说明 | A6 |
| rule_version | string | R/N | 无 | 精确匹配规则 | A6 |
| generated_at | DateTime | R/N | 无 | 按公共类型定义 | A6 |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | A6 |

### MatchReviewInput（维护方：受控复核→A6；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| event_id | ID | R/N | 无 | 同患者有效服药事件 | 复核者 |
| expected_revision | Version | R/N | 无 | 有效事件修订 | 复核者引用 |
| dose_slot_id | ID | R/Y | null | null明确解除当前关联 | 复核者 |
| reason | Reason | R/N | 无 | 人工复核依据，不能修改本人报告来源 | 复核者 |

### StatisticsIssue（维护方：A6；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| dose_slot_id | ID | R/Y | null | 窗口级原因可null | A6 |
| code | ShortText | R/N | 无 | 如no_record/conflicting_reports/quality_pending/no_plan_doses | A6 |
| message | Text | R/N | 无 | 按公共类型定义 | A6 |
| event_ids | ID[] | R/N | [] | 实际证据引用，不能造ID | A6 |

### Statistics（维护方：A6；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| statistics_id | ID | R/N | 无 | 一次可定位计算结果 | A6 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | A6 |
| window_start | DateTime | R/N | 无 | [start,end) | A6 |
| window_end | DateTime | R/N | 无 | >start | A6 |
| as_of | DateTime | R/N | 无 | 冻结本次已到时判断 | A6 |
| timezone | Timezone | R/N | 无 | 患者日历含义 | A6 |
| data_environment | string | R/N | 无 | demo/real，禁止未声明混合 | A6 |
| plan_refs | PlanRef[] | R/N | [] | 实际纳入的正式版本 | A6 |
| planned_dose_count | integer | R/N | 无 | ≥0，唯一有效已到时原子时段 | A6 |
| patient_confirmed_count | integer | R/N | 无 | ≥0，仅本人明确已服 | A6 |
| reported_not_taken_count | integer | R/N | 无 | ≥0，本人明确未服 | A6 |
| postponed_count | integer | R/N | 无 | ≥0，本人暂延尚无结果 | A6 |
| unconfirmed_evidence_count | integer | R/N | 无 | ≥0，仅其他来源证据 | A6 |
| unknown_count | integer | R/N | 无 | ≥0，缺失或冲突待复核 | A6 |
| patient_confirmation_ratio | number | R/Y | null | 0—1；分母0时null，非CAS/吞服验证率 | A6 |
| data_status | string | R/N | 无 | ready/stale/not_computable | A6 |
| issues | StatisticsIssue[] | R/N | [] | 零分母/未知/冲突/待更新原因 | A6 |
| rule_version | string | R/N | 无 | 计数口径版本 | A6 |
| updated_at | DateTime | R/N | 无 | 按公共类型定义 | A6 |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | A6 |

### MedicationTrend（维护方：A6；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| patient_id | ID | R/N | 无 | 按公共类型定义 | A6 |
| period | string | R/N | 无 | day，本期建议只日桶 | A6 |
| items | Statistics[] | R/N | 无 | 按患者当地日期排序 | A6 |
| aggregate | Statistics | R/N | 无 | 窗口总分子分母相加后求比，不平均日百分比 | A6 |

### MeasurementPoint（维护方：A4/A6；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| event_id | ID | R/N | 无 | 按公共类型定义 | A4/A6 |
| event_revision | Version | R/N | 无 | 按公共类型定义 | A4/A6 |
| occurred_at | DateTime | R/N | 无 | 按公共类型定义 | A4/A6 |
| value | number | R/Y | null | 实际值，缺失null | A4/A6 |
| missing_reason | Reason | R/Y | null | 缺失必有 | A4/A6 |
| quality_status | string | R/N | 无 | valid/needs_review/pending_validation/processing_failed | A4/A6 |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | A4/A6 |

### MeasurementTrend（维护方：A4/A6；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| patient_id | ID | R/N | 无 | 按公共类型定义 | A4/A6 |
| metric_code | ShortText | R/N | 无 | 按公共类型定义 | A4/A6 |
| unit | string | R/N | 无 | 本查询明确的可比单位 | A4/A6 |
| method_code | ShortText | R/Y | null | 查询明确的方法；未知不强合其他方法 | A4/A6 |
| window_start | DateTime | R/N | 无 | 按公共类型定义 | A4/A6 |
| window_end | DateTime | R/N | 无 | 按公共类型定义 | A4/A6 |
| points | MeasurementPoint[] | R/N | 无 | 按实际采样时间排序；未知单位不进入正常数值线 | A4/A6 |
| issues | Issue[] | R/N | [] | 不同单位/方法、质量和缺失原因 | A4/A6 |

### MeasurementOverview（维护方：A5；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| metric_code | ShortText | R/N | 无 | 按公共类型定义 | A5 |
| latest_event_id | ID | R/Y | null | 无可用样本null | A5 |
| latest_value | number | R/Y | null | 缺失不补0 | A5 |
| unit | string | R/Y | null | 按公共类型定义 | A5 |
| sampled_at | DateTime | R/Y | null | 实际采样时刻 | A5 |
| method_code | ShortText | R/Y | null | 按公共类型定义 | A5 |
| availability | Availability | R/N | 无 | 按来源独立说明 | A5 |
| missing_items | Reason[] | R/N | [] | 样本/覆盖不足，不诊断 | A5 |

### FeedbackRef（维护方：B/C原事实，A5只引用；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| record_kind | string | R/N | 无 | intervention/service/points/redemption/self_report | B/C原事实，A5只引用 |
| record_id | ID | R/N | 无 | 原模块真实记录 | B/C原事实，A5只引用 |
| source_version | string | R/Y | null | 源未提供版本时null并说明局限 | B/C原事实，A5只引用 |
| recorded_at | DateTime | R/N | 无 | 按公共类型定义 | B/C原事实，A5只引用 |
| service_status | string | R/Y | null | 仅service可取submitted/in_progress/completed/cancelled/failed，其他null | B/C原事实，A5只引用 |
| support_needs | Text | R/Y | null | C已采集描述；无反馈null，不当0分 | B/C原事实，A5只引用 |
| support_acceptance | Text | R/Y | null | C已采集描述 | B/C原事实，A5只引用 |
| intervention_effectiveness | Text | R/Y | null | 实际结果/主观反馈说明，非因果疗效 | B/C原事实，A5只引用 |
| is_simulated | boolean | R/N | 无 | 来自原事实 | B/C原事实，A5只引用 |

### FeedbackSource（维护方：A5读取B/C；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| source_module | string | R/N | 无 | B/C | A5读取B/C |
| availability | Availability | R/N | 无 | 按公共类型定义 | A5读取B/C |
| records | FeedbackRef[] | R/N | [] | 仅真正无记录/未接入等可为空，必须配availability | A5读取B/C |
| reason | Reason | R/Y | null | 非available时说明，不泄露受限内容 | A5读取B/C |

### FeedbackOverview（维护方：A5；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| patient_id | ID | R/N | 无 | 按公共类型定义 | A5 |
| window_start | DateTime | R/N | 无 | 按公共类型定义 | A5 |
| window_end | DateTime | R/N | 无 | 按公共类型定义 | A5 |
| sources | FeedbackSource[] | R/N | 无 | B/C逐项，不伪造完成/效果 | A5 |
| updated_at | DateTime | R/N | 无 | 按公共类型定义 | A5 |

### MissingItem（维护方：A5；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| source | ShortText | R/N | 无 | statistics/measurement/B/C等 | A5 |
| code | ShortText | R/N | 无 | 按公共类型定义 | A5 |
| message | Text | R/N | 无 | 缺失、失败、受限分开 | A5 |

### Summary（维护方：A5；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| summary_id | ID | R/N | 无 | 按公共类型定义 | A5 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | A5 |
| window_start | DateTime | R/N | 无 | 按公共类型定义 | A5 |
| window_end | DateTime | R/N | 无 | 按公共类型定义 | A5 |
| generated_at | DateTime | R/N | 无 | 按公共类型定义 | A5 |
| valid_until | DateTime | R/N | 无 | 建议generated_at+15分钟，工程参数待确认 | A5 |
| updated_at | DateTime | R/N | 无 | 按公共类型定义 | A5 |
| data_status | string | R/N | 无 | fresh/stale/insufficient（基线语义） | A5 |
| plan_refs | PlanRef[] | R/N | [] | 来自A6实际纳入版本 | A5 |
| record_overview | Statistics | R/Y | null | 直接复用A6，暂不可用null并列原因，不能自算 | A5 |
| measurement_overview | MeasurementOverview[] | R/N | [] | 每项有真实来源和不足 | A5 |
| feedback_overview | FeedbackOverview | R/N | 无 | 按公共类型定义 | A5 |
| missing_items | MissingItem[] | R/N | [] | 逐来源说明 | A5 |
| schema_version | string | R/N | 无 | 可定位摘要结构 | A5 |
| is_simulated | boolean | R/N | 无 | 按公共类型定义 | A5 |

### RefreshInput（维护方：网页/可信模块→A5；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| window_start | DateTime | R/N | 无 | 固定范围 | 调用方 |
| window_end | DateTime | R/N | 无 | 建议≤31天 | 调用方 |
| as_of | DateTime | O/N | 服务器当前时间 | 请求内固定 | 调用方 |
| data_environment | string | R/N | 无 | demo/real，需与环境权限相符 | 调用方 |

### WindowTaskPayload（维护方：A7注册载荷；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| window_start | DateTime | R/N | 无 | 按公共类型定义 | A7注册载荷 |
| window_end | DateTime | R/N | 无 | 按公共类型定义 | A7注册载荷 |
| data_environment | string | R/N | 无 | demo/real | A7注册载荷 |

### ReminderTaskPayload（维护方：O5→A7；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| dose_slot_id | ID | R/N | 无 | 按公共类型定义 | O5→A7 |
| reminder_revision | Version | R/N | 无 | O配置精确修订 | O5→A7 |
| content_ref | ID | R/N | 无 | 受控中性文案/提醒记录引用，不是执行代码 | O5→A7 |

### CheckinTaskPayload（维护方：B规则→A7；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| cycle_id | ID | R/N | 无 | 周期归B定义、起点引用O enrollment_at | B规则→A7 |
| node_code | ShortText | R/N | 无 | B定义，不在A写死第1/4周日数 | B规则→A7 |
| rule_version | string | R/N | 无 | B检查规则 | B规则→A7 |

### InterventionTaskPayload（维护方：B5→A7；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| intervention_id | ID | R/N | 无 | 按公共类型定义 | B5→A7 |
| content_ref | ID | R/N | 无 | B已校验的内容引用，不直接执行模型输出 | B5→A7 |
| channel | string | R/N | 无 | 本期mock；真实渠道未接入 | B5→A7 |

### TaskCreateInput（维护方：可信业务模块→A7；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| patient_id | ID | R/N | 无 | 权限及来源模块校验 | 可信服务 |
| kind | TaskKind | R/N | 无 | 五种注册能力之一 | 可信服务 |
| owner_module | string | R/N | 无 | O/A/B；不得由患者自由自报 | 可信适配 |
| owner_operation_key | string | R/N | 无 | 1—200字符，业务稳定去重键 | 业务维护方 |
| scheduled_at | DateTime | R/N | 无 | 计划执行时刻 | 业务维护方 |
| valid_until | DateTime | R/N | 无 | >scheduled_at，不自动猜过期 | 业务维护方 |
| payload | TaskPayload | R/N | 无 | 按kind选择载荷 | 业务维护方 |
| intervention_id | ID | O/Y | null | B干预引用，非task_id | 调用方 |
| rule_version | string | R/N | 无 | 来源业务规则 | 业务维护方 |

### Task（维护方：A7；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| task_id | ID | R/N | 无 | 按公共类型定义 | A7 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | A7 |
| kind | TaskKind | R/N | 无 | 按公共类型定义 | A7 |
| owner_module | string | R/N | 无 | O/A/B | A7 |
| owner_operation_key | string | R/N | 无 | 同来源业务唯一键 | A7 |
| scheduled_at | DateTime | R/N | 无 | 按公共类型定义 | A7 |
| valid_until | DateTime | R/N | 无 | 按公共类型定义 | A7 |
| payload | TaskPayload | R/N | 无 | 按公共类型定义 | A7 |
| intervention_id | ID | R/Y | null | 按公共类型定义 | A7 |
| rule_version | string | R/N | 无 | 按公共类型定义 | A7 |
| status | string | R/N | 无 | pending/running/retry_wait/succeeded/failed/cancelled/expired | A7 |
| cancellation_requested | boolean | R/N | 无 | 初始false；在途取消不伪称已撤回副作用 | A7 |
| attempt_count | integer | R/N | 无 | ≥0，实际尝试次数 | A7 |
| max_attempts | integer | R/N | 无 | 建议3，含首次；模型预算仍由B统一限制 | A7 |
| next_attempt_at | DateTime | R/Y | null | retry_wait时非空；建议间隔60秒 | A7 |
| failure_reason | Reason | R/Y | null | 实际失败/未知说明 | A7 |
| meta | Meta | R/N | 无 | 按公共类型定义 | A7 |

### TaskCancelInput（维护方：业务维护方/授权管理→A7；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | 任务当前修订 | 调用方引用 |
| reason | Reason | R/N | 无 | 取消原因 | 调用方 |

### TaskRunInput（维护方：受控执行→A7；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| expected_revision | Version | R/N | 无 | 任务当前修订 | 可信调用方 |

### Execution（维护方：A7；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| execution_id | ID | R/N | 无 | 按公共类型定义 | A7 |
| task_id | ID | R/N | 无 | 按公共类型定义 | A7 |
| patient_id | ID | R/N | 无 | 按公共类型定义 | A7 |
| intervention_id | ID | R/Y | null | 按公共类型定义 | A7 |
| attempt | integer | R/N | 无 | ≥1，此任务内唯一尝试 | A7 |
| execution_status | string | R/N | 无 | pending/running/completed/failed/cancelled/expired/outcome_unknown | A7 |
| delivery_status | string | R/N | 无 | not_applicable/pending/submitted/delivered/failed/cancelled/expired/unknown | A7 |
| channel | string | R/Y | null | mock/in_app；计算任务null；in_app也不等于已展示 | A7 |
| is_simulated | boolean | R/N | 无 | 实际适配决定 | A7 |
| result_ref | ID | R/Y | null | 统计/摘要等真实结果引用 | A7 |
| error_code | ShortText | R/Y | null | 按公共类型定义 | A7 |
| error_message | Text | R/Y | null | 不含敏感堆栈/密钥 | A7 |
| retryable | boolean | R/N | 无 | 确定未发生副作用才可按预算重试 | A7 |
| started_at | DateTime | R/N | 无 | 按公共类型定义 | A7 |
| finished_at | DateTime | R/Y | null | 按公共类型定义 | A7 |
| submitted_at | DateTime | R/Y | null | 渠道接受提交时间 | A7 |
| delivered_at | DateTime | R/Y | null | 仅可信明确送达回执；mock不得冒充真实送达 | A7 |

### DeliveryReceiptInput（维护方：可信渠道→A7；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| provider_event_id | ID | R/N | 无 | 渠道稳定事件号，独立request_id | 渠道 |
| execution_id | ID | R/N | 无 | 精确执行引用 | 渠道 |
| occurred_at | DateTime | R/N | 无 | 渠道事件发生时间 | 渠道 |
| status | string | R/N | 无 | submitted/delivered/failed；需实际能力支持 | 渠道 |
| failure_code | ShortText | O/Y | null | failed时非空 | 调用方 |
| failure_message | Text | O/Y | null | 脱敏原因 | 调用方 |

### DeliveryReceipt（维护方：A7；字段版本A-draft01）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| receipt_id | ID | R/N | 无 | 按公共类型定义 | A7 |
| provider_event_id | ID | R/N | 无 | 按公共类型定义 | A7 |
| execution_id | ID | R/N | 无 | 按公共类型定义 | A7 |
| occurred_at | DateTime | R/N | 无 | 按公共类型定义 | A7 |
| received_at | DateTime | R/N | 无 | 首次接收不随重试变 | A7 |
| status | string | R/N | 无 | submitted/delivered/failed | A7 |
| applied | boolean | R/N | 无 | 重复/晚到非法转换可false，保留审计 | A7 |
| ignore_reason | Reason | R/Y | null | 未应用时说明 | A7 |
| is_simulated | boolean | R/N | 无 | 由可信适配决定 | A7 |
| execution | Execution | R/N | 无 | 应用后可见执行结果，不生成展示/用户响应 | A7 |

## 3 单一事实与状态的重要细化（本批待确认）

1. FileContent保持Envelope四字段，通过base64承载单文件演示下载，不返回服务器路径或公开链接。File保存状态不代表识别/草稿/正式计划成功；内部受控storage_ref仅A1保存。
2. Draft.content_revision专指内容修订，提交/回传改变meta.revision而不改变已提交内容号；O28的draft_revision=content_revision，正式计划保存该号。O回传只在同库受控服务中写formal_plan，不接收网页“已确认”字段。
3. SourceEvent.payload是当前有效修订视图；EventRevision的original保存初始原文，correction/withdrawal追加，不覆盖。source/source_event_id/reporter/device/patient固定不改；更正occurred_at影响旧新窗口，received_at永不随重放改变。
4. self_report仅由本人实际会话生成。家人无论报告taken/not_taken/postponed都仍是family_report；开盒与推断分别保存。设备不可提交self_report。不同来源证据可并存，同一时段不多计一次。
5. 质量valid表示技术校验通过，缺失采集记录可有效表达“未采集”但不变成数值0；未知单位/不兼容方法needs_review。处理异常processing_failed不当成患者填错或临床异常。
6. Statistics五类计数必须非负整数且总和等于planned_dose_count；分母0时全部0、ratio=null并有原因。计划/时段依赖不可用返回503或契约未就绪409，不伪造0分母。未知/冲突保留issues，不用减少分母掩盖不足。
7. Summary.record_overview直接引用A6该结果和更新时间；组成来源可部分缺失，保留可用部分。来源不可用/未接入/受限分别说明，不能伪装正常空列表。摘要读取不得以summary:read绕过底层文件/记录/B/C权限。
8. 新事件、迟到、更正、撤销或计划变化在同库事务中登记change_outbox/失效需求，A6/A5重算或标stale。重复处理不产生新的有效事实。旧新两个范围都受影响时都登记；本轮不实现队列。
9. Task、Execution、DeliveryReceipt、B的intervention_id、C的service_id分别维护。计算任务可completed且delivery_status=not_applicable；投递completed只表示执行动作已完成，submitted不等于delivered，更不等于网页展示/患者响应。mock回执不得标真实送达。
10. 建议总尝试上限3、重试间隔60秒，仅确认未产生副作用的暂时性失败可重试；outcome_unknown先查询核实，取消/过期/撤销不得被晚到回执恢复。B模型预算仍由B统一计数，A任务重试不能绕过。
11. 示例指标注册建议sleep_duration(h)、step_count(count)、heart_rate(beats/min)，仅说明代码/单位结构，未定义任何医学危险阈值；扩展单位转换须团队确认，不默认从未知单位猜换算。
12. A1内部建议字段：schema_versions(version:string, applied_at:DateTime, checksum:SHA256, outcome:applied/failed)；idempotency_receipts(scope_hash:SHA256,key_hash:SHA256,request_fingerprint:SHA256,state:in_progress/committed/rejected/unknown,resource_refs:ID[],created_at/valid_until:DateTime)；change_outbox(change_id:ID,patient_id:ID,source_event_id:ID?,old_window/new_window:窗口?,status:pending/processed/failed,created_at/processed_at:DateTime?)。这些是存储规划，不是患者API字段；需A批确认后在数据字典/迁移阶段展开约束，旧迁移不覆盖。令牌/密钥不进表或日志。

## 4 确认边界

本文件没有改变已确认总口径；新增代码、单位表、字段/状态和工程数值均等待A批确认。完整路径、权限、事务、成功失败及待实施验收在A02；A00的AQ01—AQ14和公共/O的U01—U08未决项继续有效。后续版本通过新增草案/追加确认登记，不覆盖本轮字段快照。

