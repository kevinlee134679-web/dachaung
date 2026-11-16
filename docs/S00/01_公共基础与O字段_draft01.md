# S00 第一轮：公共基础与 O 字段草案（draft01）

依据总 Prompt v1.1；2026-11-16，Asia/Shanghai。**未确认、未冻结、未实现**。历史更新只追加说明或另建版本。本文件所有新增字段名、类型、枚举、长度、默认值均为**建议/待确认**；只有明确标记“已确认语义”的内容沿用原约束。

## 1 逐字段阅读约定

字段表列为“字段｜类型｜出现/可空｜默认｜枚举、格式、单位及限制｜生成/维护方”。`R/N`=必须出现且不接受null；`R/Y`=必须出现但可为null；`O/N`=可不传，传入不能为null；`O/Y`=可不传也可显式传null。**可不传不等于可传null**。输出字段全部为R，空集合返回[]；无法取得依赖时返回错误，不伪装空集合。

`无`表示没有默认，必须提供或由服务端生成；`省略=不改`仅用于PATCH。每一节/对象标明字段版本和默认维护方，适用于该对象每一行；行内另标者优先。公共字段版本 **P-draft01**，O对象版本 **O-draft01**，均未启用。例子采用虚构ID，未来实际ID建议UUIDv4；例子短ID不代表冻结了ID格式。

| 公共类型 | 类型/格式/范围（建议） | 空值/单位 | 生成方/版本 |
| --- | --- | --- | --- |
| ID | string，1—128字符、稳定唯一、不暴露可读健康信息；UUIDv4建议 | 不可空，引用可按字段允许空 | 对象维护方；P-draft01 |
| Version | integer ≥1 | 无单位，不可空 | 对象维护方；P-draft01 |
| DateTime | string，ISO8601带时区；存储UTC，按患者时区显示 | 毫秒精度建议；不能接收无时区值 | 事件时间来源/接收时间服务器；P-draft01 |
| LocalDate / LocalTime | YYYY-MM-DD / HH:mm，24小时制 | 仅作日历/重复时刻，不冒充完整时间戳 | 用户/计划来源；P-draft01 |
| Timezone | string，IANA时区标识 | 本地默认Asia/Shanghai已确认 | O；P-draft01 |
| Text / ShortText | string，1—2000 / 1—200字符 | 去除首尾空白，不执行HTML；禁止密钥 | 用户或可信后端；P-draft01 |
| Reason | string，1—500字符 | 稳定原因代码/可读说明按具体字段；不含内部堆栈 | 维护方；P-draft01 |
| Scope | string，取本文件权限表 | 非通配符 | O；O-draft01 |

**已确认语义**：request_id、Idempotency-Key、source_event_id、业务ID独立；所有数据有实际来源和模拟标记；时间含义不可混用；缺失不填零；mode与ui_mode独立。mode=real/mock是模型来源；ui_mode=normal/simplified是界面；auth_mode=demo/external是身份来源，不能互代。

## 2 公共响应、请求、分页和审计

### 2.1 Envelope（已确认四字段结构；字段细化版本P-draft01，A0生成）

| 字段 | 类型 | 出现/可空 | 默认 | 约束 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| request_id | ID | R/N | 服务器生成 | 每次HTTP尝试独立；错误也必须返回 | A0 |
| status | string | R/N | 无 | success/error；与HTTP一致 | A0 |
| data | 卡片指定对象或List | R/Y | 无 | 成功为指定对象；失败null | 业务模块 |
| error | Error | R/Y | 无 | 成功null；失败Error | A0 |
| Error.code | string | R/N | 无 | 稳定机器码，候选见接口卡 | A0/维护方 |
| Error.message | Text | R/N | 无 | 可读、脱敏，不透露其他患者存在与否 | A0/维护方 |

### 2.2 所有卡片继承的输入/输出规则（P-draft01）

| 位置/字段 | 类型 | 出现/可空 | 默认 | 格式/限制 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| path中资源ID | ID | R/N | 无 | 按对应资源查归属，不信任客户端自报患者 | 调用方引用 |
| path.version | Version | R/N | 无 | 精确版本，不自动替换为最新 | 调用方引用 |
| Cookie.session | opaque string | R/N，G01/O01例外 | 无 | 建议服务端会话、HttpOnly/SameSite；HTTPS时Secure | O/A适配；浏览器自动携带 |
| X-CSRF-Token | opaque string | R/N，对已登录写操作 | 无 | 与当前会话绑定，不能靠患者消息覆盖 | 服务端发给当前会话 |
| Idempotency-Key | string | R/N，对全部POST/PUT/PATCH业务写入 | 无 | 建议16—128字符；按账号/患者/操作作用域；不含病历 | 调用方每个用户操作生成 |
| Content-Type | string | R/N，对JSON写入 | application/json | 本轮卡均为JSON；上传A下一批 | 调用方 |
| list.cursor | opaque string | O/N | 首批 | 服务端签发并绑定患者/筛选；不可拿甲游标查乙 | 服务端→调用方 |
| list.limit | integer | O/N | 20（建议） | 1—100 | 调用方 |
| List.items | T[] | R/N | []（确实无数据时） | T由卡指定；顺序按卡规定 | 维护方 |
| List.next_cursor | string | R/Y | null | 没有下一页为null | 维护方 |
| Meta.created_at | DateTime | R/N | 创建时间 | 首次创建不随重试改变 | 服务器 |
| Meta.updated_at | DateTime | R/N | 创建时间 | 有效变更才更新 | 服务器 |
| Meta.revision | Version | R/N | 1 | 乐观并发版本，禁止旧修订覆盖新修订 | 服务器 |
| Meta.contract_version | string | R/N | 确认后发布的契约号 | 本轮仅O-draft01示意，不是生效契约 | 服务器 |
| Meta.is_simulated | boolean | R/N | 由环境确定 | 网页不能自行将演示数据标真实 | 接入适配 |
| ExpectedRevision.expected_revision | Version | R/N | 无 | 写入时与当前修订一致 | 调用方引用 |
| RevokeInput.reason | Reason | R/N | 无 | 撤销/解除理由，不删除原历史 | 调用方 |

域对象明确列出`meta:Meta`时才包含Meta；不把所有公共字段塞到每种对象。只读GET无幂等键/CSRF。外部服务可信身份/签名属于后续批，不允许直接拿演示Cookie替代。

### 2.3 Health / ConfigStatus（P-draft01，A0；无模型调用）

| 对象.字段 | 类型 | 出现/可空 | 默认 | 枚举/范围/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| Health.process_status | string | R/N | 无 | running | A0 |
| Health.readiness | string | R/N | 无 | ready/not_ready；不代表全业务已完成 | A0 |
| Health.dependencies | DependencyStatus[] | R/N | 无 | 必要依赖逐项列出 | A0 |
| Health.app_version | string | R/N | 无 | 实际构建标识 | A0 |
| Health.checked_at | DateTime | R/N | 当前时间 | 不主动探测付费模型 | A0 |
| DependencyStatus.name | string | R/N | 无 | 如database/schema/config | A0 |
| DependencyStatus.status | string | R/N | 无 | available/unavailable/unverified | A0 |
| DependencyStatus.reason | Reason | R/Y | null | 非available时给原因 | A0 |
| ConfigStatus.auth_mode | string | R/N | demo（已确认） | demo/external | A0 |
| ConfigStatus.llm_mode | string | R/N | mock（已确认） | mock/real | B1配置只读 |
| ConfigStatus.requested_pipeline | string | R/N | single_pass（已确认） | single_pass/star；实际逐轮结果由B记录 | B1 |
| ConfigStatus.model_configured | boolean | R/N | 实际检查 | 只表达配置完整，不等于连通 | B1 |
| ConfigStatus.model_connectivity | string | R/N | unverified | unverified/available/unavailable，附最近探测事实 | B1 |
| ConfigStatus.capabilities | Capability[] | R/N | 无 | 实际可用项，不虚构已接入 | A0及模块 |
| ConfigStatus.version_refs | VersionRef[] | R/N | [] | 没有启用的版本不编造 | A0 |
| Capability.code | string | R/N | 无 | in_app_notification/system_notification等候选 | 适配 |
| Capability.available | boolean | R/N | 无 | 后端能力；浏览器许可须客户端另确认 | 适配 |
| Capability.reason | Reason | R/Y | null | 不可用必须有原因 | 适配 |
| VersionRef.kind | string | R/N | 无 | contract/schema/rule/questionnaire/model_config等 | 维护方 |
| VersionRef.version | string | R/N | 无 | 可定位版本；草案需标draft | 维护方 |

不返回API密钥、完整模型地址、数据库物理路径或患者健康数据。G02访问范围建议只限本地演示管理角色。

## 3 O1 身份、患者、绑定和权限（全部字段版本O-draft01，O维护）

### 3.1 AccountBrief / Patient / IdentityContext

| 对象.字段 | 类型 | 出现/可空 | 默认 | 枚举/格式/范围 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| AccountBrief.account_id | ID | R/N | 无 | 账号ID，不是patient_id | O |
| AccountBrief.display_name | ShortText | R/N | 无 | 演示昵称，不要求实名 | O |
| AccountBrief.auth_mode | string | R/N | 环境 | demo/external | 身份适配 |
| AccountBrief.is_simulated | boolean | R/N | 环境 | 与身份来源一致 | 身份适配 |
| Patient.patient_id | ID | R/N | 无 | 患者主引用 | O |
| Patient.display_name | ShortText | R/N | 无 | 演示可用虚构名称 | O |
| Patient.timezone | Timezone | R/N | Asia/Shanghai | 展示及日历边界 | O |
| Patient.enrollment_at | DateTime | R/Y | null | 服务启用起点；计划更新不默认重置 | O；B引用 |
| Patient.meta | Meta | R/N | 服务器生成 | 来源/修订 | O |
| PatientAccess.patient | Patient | R/N | 无 | 仅最小基础资料 | O |
| PatientAccess.relationship | string | R/N | 无 | self/family | O身份关系 |
| PatientAccess.effective_scopes | Scope[] | R/N | 无 | 当前权限，不是永久授权快照 | O |
| IdentityContext.account | AccountBrief | R/N | 无 | 来自已验证会话 | O |
| IdentityContext.current_patient_id | ID | R/Y | null | 上次对象失效则清空，不悄悄切换写入目标 | O |
| IdentityContext.patients | PatientAccess[] | R/N | [] | 仅当前可管理对象；大规模分页策略后续 | O |
| IdentityContext.csrf_token | opaque string | R/N | 服务端生成 | 仅当前会话使用，不写日志/文档 | O/A |
| IdentityContext.expires_at | DateTime | R/N | 配置 | 会话有效期建议可配置，时长待定 | O |
| DemoLoginInput.demo_account_id | ID | R/N | 无 | 仅白名单虚构账号，external禁用 | 用户选择 |
| CurrentPatientInput.patient_id | ID | R/N | 无 | 在有效可管理集合中 | 用户选择 |
| PatientPatch.expected_revision | Version | R/N | 无 | 旧版本冲突 | 用户引用 |
| PatientPatch.display_name | ShortText | O/N | 省略=不改 | 至少一个业务字段被修改 | 用户 |
| PatientPatch.timezone | Timezone | O/N | 省略=不改 | 更改后只影响展示/后续安排，既有事件不平移 | 用户 |
| OperationResult.operation_id | ID | R/N | 服务器生成 | 操作审计ID，不是request_id | O |
| OperationResult.outcome | string | R/N | 无 | logged_out/revoked | O |
| OperationResult.affected_ids | ID[] | R/N | [] | 当前调用可见且受影响的资源 | O |
| OperationResult.completed_at | DateTime | R/N | 当前时间 | 实际事务完成时 | O |

患者注册、密码认证、监护人替代同意和研究背景字段不在本轮自行发明。既有问卷和处方以外的背景只在模型映射确认后增补，不增加隐藏必答题。

### 3.2 BindingCode / FamilyBinding / Grant

| 对象.字段 | 类型 | 出现/可空 | 默认 | 枚举/格式/范围 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| BindingCode.code_id | ID | R/N | 服务器生成 | 绑定码记录ID | O |
| BindingCode.binding_code | string | R/N | 安全随机 | 12—64字符建议；仅创建/同键重放时受控返回，不记录明文 | O |
| BindingCode.patient_id | ID | R/N | 路径 | 仅患者本人发起 | O |
| BindingCode.expires_at | DateTime | R/N | 建议5分钟 | 有效期待确认；一次使用 | O |
| BindingCode.is_simulated | boolean | R/N | 环境 | 不以演示码绑定真实患者 | O |
| RedeemInput.binding_code | string | R/N | 无 | 与发码格式一致 | 家人输入 |
| FamilyBinding.binding_id | ID | R/N | 服务器生成 | 单独关系ID | O |
| FamilyBinding.patient_id | ID | R/N | 码关联 | 不能请求体改挂 | O |
| FamilyBinding.family_account_id | ID | R/N | 当前会话 | 不信任客户端另传家人ID | O |
| FamilyBinding.status | string | R/N | active | active/revoked；是否需第二次本人确认待Q03 | O |
| FamilyBinding.established_at | DateTime | R/N | 当前时间 | 兑换成功时 | O |
| FamilyBinding.revoked_at | DateTime | R/Y | null | revoked时必有 | O |
| FamilyBinding.meta | Meta | R/N | 服务器生成 | 历史保留 | O |
| Grant.grant_id | ID | R/N | 服务器生成 | 正式授权ID | O |
| Grant.binding_id | ID | R/N | 路径 | 只对应一条有效关系 | O |
| Grant.patient_id | ID | R/N | 关系引用 | 与绑定一致 | O |
| Grant.grantee_account_id | ID | R/N | 关系引用 | 家人账号 | O |
| Grant.scopes | Scope[] | R/N | []（不自动授予） | 精确、不隐含向第三方共享全部数据 | 本人明确确认，O保存 |
| Grant.grant_version | Version | R/N | 1 | 每次授权内容/撤销变更递增；本轮与meta.revision同步 | O |
| Grant.status | string | R/N | active | active/revoked/expired；过期由时钟判定 | O |
| Grant.valid_until | DateTime | R/Y | null | null表示无预设截止，仍可撤销 | 本人/O |
| Grant.confirmed_at | DateTime | R/N | 当前时间 | 真实操作证据，不接受网页自报时间 | O |
| Grant.revoked_at | DateTime | R/Y | null | 撤销时填写 | O |
| Grant.meta | Meta | R/N | 服务器生成 | 生成方/版本 | O |
| GrantPutInput.expected_revision | integer ≥0 | R/N | 无 | 首次0，随后匹配当前meta.revision | 调用方 |
| GrantPutInput.scopes | Scope[] | R/N | 无 | 全量替换，不传不是“保留全部” | 本人 |
| GrantPutInput.valid_until | DateTime | R/Y | 无 | 未来截止或null | 本人 |
| GrantPutInput.confirmed | boolean | R/N | 无 | 必须true；仍须验证本人会话与操作，不是任意“已授权”标志 | 本人动作 |
| RevokeInput.expected_revision | Version | R/N | 无 | 绑定或授权当前修订 | 调用方 |
| RevokeInput.reason | Reason | R/N | 无 | 留痕原因 | 调用方 |

权限代码建议：`patient:read`基础查看、`patient:edit`基础编辑、`questionnaire:read`问卷读取、`questionnaire:assist`协助作答、`profile:read`画像摘要、`medication:read`药品资料查看、`medication:edit`资料编辑、`plan:read`计划查看、`plan:confirm`正式确认（家人能否获得待确认）、`reminder:read`/`reminder:write`提醒查看/编辑、`records:read`服药记录查看、`records:report`以家人身份报告、`notify:receive`接收相关通知。未授予即拒绝；本人权限也通过服务端身份关系判断。B对话、C服务信息共享需后续独立范围定义，不把本表扩展成“一次绑定通吃”。

建议关系生效与授权生效分开；解除绑定同一事务使其授权不可用。家人可解除自己的关系，不能修改患者授予他人的权限。服务方同意与家庭授权的复用规则留C/全流程批。

## 4 O2 八主题问卷（O-draft01，O2维护）

### 4.1 定义与题目

| 对象.字段 | 类型 | 出现/可空 | 默认 | 格式/枚举/范围 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| QuestionnaireDefinition.questionnaire_id | ID | R/N | 无 | 主题问卷标识 | O2 |
| QuestionnaireDefinition.version | string | R/N | 无 | 内容版本，未确认前不宣称已发布 | O2 |
| QuestionnaireDefinition.purpose | Text | R/N | 无 | 评估用途及自报限制 | O2 |
| QuestionnaireDefinition.themes | Theme[] | R/N | 无 | 必须8个，Q1—Q8；不藏新增主题 | O2 |
| Theme.question_id | string | R/N | 无 | Q1…Q8 | O2 |
| Theme.prompt | Text | R/N | 无 | 下述题意，生活化措辞 | O2 |
| Theme.interaction | string | R/N | 无 | scenario/multi_rank/multi_concern/multi_frequency/confidence | O2 |
| Theme.options | Option[] | R/N | 无 | 稳定选项代码；Q6为1—5 | O2 |
| Theme.allows_unknown | boolean | R/N | true（建议） | 尤其家人代答主观问题 | O2 |
| Theme.allows_not_applicable | boolean | R/N | true（建议） | 与unknown分开 | O2 |
| Option.code | string | R/N | 无 | 1—80字符，下表候选 | O2 |
| Option.label | ShortText | R/N | 无 | 可访问的可读标签 | O2 |

八主题题意已确认：Q1近一个月实际用药；Q2最困难原因及前三优先级；Q3无症状/好转时持续治疗看法；Q4顾虑及最关注1—2项；Q5错过时间的生活场景；Q6忙碌/疲惫下信心五级；Q7理解与执行所需信息；Q8希望的帮助及前三优先级。

**候选选项代码（均待确认，不作为模型量表得分）**：

| 题 | 选项与标签 |
| --- | --- |
| Q1 | follows_plan按医嘱；occasional_delay偶尔延迟；unintentional_miss遗忘漏服；self_adjusted主动推迟/停止；补充情况复用同组代码 |
| Q2 | forget遗忘；irregular_routine作息；busy忙碌；outside外出不便；complexity步骤复杂；unclear_use不清楚用法；stockout未补充；side_effects副作用；long_term_effects长期影响；no_symptoms无症状不必服想法；low_effect效果不明显；fatigue厌倦；low_energy压力/精力；privacy不愿被发现；access购药不便；cost经济负担；none无；other其他 |
| Q3 | follow_advice仍按医嘱；doubts有疑问；consider_change认为可少服/停服；has_changed曾自行调整/中断 |
| Q4 | side_effects副作用；long_term_effects长期影响；dependence依赖；efficacy药效；disease_progression疾病进展；cost经济；none没有上述担心 |
| Q5 | sleep_change起睡变化；meal_change三餐不定；shift轮班；travel差旅；social开会/上课/社交；no_medicine忘带药；none无这些影响 |
| Q6 | confidence_level整数1完全没有把握…5非常有把握；不是CAS或F因子 |
| Q7 | necessity长期必要性；purpose药物作用；dose_use剂量/服法解释；meal_sleep时间与餐睡；missed_delayed漏服/延迟疑问；followup复诊/咨询；none基本清楚 |
| Q8 | timed_reminder时间提醒；habit_anchor习惯关联；context_reminder忙碌/外出；privacy_reminder隐私；plain_knowledge易懂知识；organize_plan整理药单；emotional_support疲惫支持；family_support经同意家人帮助；none暂不需要 |

### 4.2 QuestionAnswer与AnswerValue（每题保存一份，版本O-draft01）

| 对象.字段 | 类型 | 出现/可空 | 默认 | 枚举/格式/范围 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| QuestionAnswer.state | string | R/N | not_answered（新草稿） | answered/unknown/not_applicable/not_answered | 作答者 |
| QuestionAnswer.value | 按题的Value | R/Y | null | answered时非null；其他状态必须null | 作答者 |
| QuestionAnswer.answered_by | string | R/N（输出）；输入禁止 | 当前会话 | self/family_assisted | O根据身份 |
| QuestionAnswer.updated_at | DateTime | R/N（输出）；输入禁止 | 服务器时间 | 非自报作答时间 | O |
| Q1Value.primary | enum string | R/N | 无 | Q1候选 | 作答者 |
| Q1Value.additional | enum string[] | R/N | [] | Q1候选、去重、不含primary | 作答者 |
| Q2Value.selected | enum string[] | R/N | 无 | Q2候选；none与其他互斥 | 作答者 |
| Q2Value.top_ranked | enum string[] | R/N | [] | 是selected子集、长度≤3、有序不重复；不足3可少选 | 作答者 |
| Q2Value.other_text | ShortText | R/Y | null | 选择other时非空，否则null | 作答者 |
| Q3Value.choice | enum string | R/N | 无 | Q3候选；unknown由state表达 | 作答者 |
| Q4Value.selected | enum string[] | R/N | 无 | Q4候选；none互斥 | 作答者 |
| Q4Value.top_concerns | enum string[] | R/N | [] | selected子集≤2 | 作答者 |
| Q4Value.intensity | integer | R/Y | null | 建议0—4，非必需；量程未确认不能计算总分 | 作答者 |
| Q5Value.selected | enum string[] | R/N | 无 | Q5候选；none互斥 | 作答者 |
| Q5Value.frequency | string | R/Y | null | never/occasionally/often；可不补充 | 作答者 |
| Q6Value.confidence_level | integer | R/N | 无 | 1—5 | 作答者 |
| Q7Value.selected | enum string[] | R/N | 无 | Q7候选；none互斥 | 作答者 |
| Q8Value.selected | enum string[] | R/N | 无 | Q8候选；建议最多3；none互斥 | 作答者 |
| Q8Value.ranked | enum string[] | R/N | [] | selected子集≤3；不强加排序负担 | 作答者 |

输入QuestionAnswer仅包含state/value；输出另含answered_by/updated_at。答案对象`Answers`固定8个键Q1—Q8，各为QuestionAnswer，均R/N；PUT输入为8题快照，未答题用not_answered/null，避免省略被误认为清空。本人作答和家人协助不互相冒充；家人不了解患者主观感受可unknown，不能替患者推断。

### 4.3 QuestionnaireResponse及写入对象

| 对象.字段 | 类型 | 出现/可空 | 默认 | 枚举/格式/范围 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| QuestionnaireResponse.response_id | ID | R/N | 服务器生成 | 一次作答/复评独立ID | O2 |
| QuestionnaireResponse.patient_id | ID | R/N | 路径 | 评估患者，不是代答家人 | O2 |
| QuestionnaireResponse.questionnaire_version | string | R/N | 指定定义 | 与选项一致 | O2 |
| QuestionnaireResponse.respondent_account_id | ID | R/N | 会话 | 当前作答账号 | O2 |
| QuestionnaireResponse.respondent_mode | string | R/N | 依据关系 | self/family_assisted | O2 |
| QuestionnaireResponse.status | string | R/N | draft | draft/submitted；提交后不可原地改写 | O2 |
| QuestionnaireResponse.answers | Answers | R/N | 全部not_answered/null | 八题固定键 | O2保存 |
| QuestionnaireResponse.supersedes_response_id | ID | R/Y | null | 更正/复评引用旧回答，必须同患者 | O2 |
| QuestionnaireResponse.submitted_at | DateTime | R/Y | null | submitted时非空 | O2 |
| QuestionnaireResponse.meta | Meta | R/N | 服务器生成 | 修订及模拟来源 | O2 |
| ResponseCreateInput.questionnaire_version | string | R/N | 无 | 已可用定义版本 | 调用方 |
| ResponseCreateInput.supersedes_response_id | ID | O/Y | null | 省略新填；非空新建副本保留原记录 | 调用方 |
| AnswersPutInput.expected_revision | Version | R/N | 无 | 当前修订 | 调用方 |
| AnswersPutInput.answers | Answers输入版 | R/N | 无 | 含state/value、不接收answered_by/updated_at | 作答者 |
| SubmitInput.expected_revision | Version | R/N | 无 | 提交确定修订 | 作答者 |
| SubmitInput.confirmed | boolean | R/N | 无 | true为明确提交，不代表模型输入齐全 | 作答者 |

建议提交允许unknown/not_applicable；是否允许not_answered待Q05决定，本草案建议阻止遗留not_answered但不强制填有内容答案。提交不自动调用LLM、不触发研究训练；评估由O22明确创建。

## 5 O3 画像与评估结果（O-draft01，O3维护）

分类体系**已确认**：A维持型、B1遗忘与习惯缺失、B2操作与外部条件受限、C1用药认知不足、C2用药顾虑与心理抗拒、C3情绪低落与用药疲劳、D1社会情境与生活冲突。这些是**画像标签**，与模块B1/B2不相干。计算规则、阈值、标签代码的API表示待确认；允许主类型为空和复合障碍，不强行给类型。

| 对象.字段 | 类型 | 出现/可空 | 默认 | 枚举/格式/范围 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| Profile.profile_id | ID | R/N | 服务器生成 | 独立结果版本，不覆盖旧画像 | O3 |
| Profile.patient_id | ID | R/N | 来源响应 | 患者一致 | O3 |
| Profile.response_id | ID | R/N | 指定响应 | 必须submitted | O3 |
| Profile.status | string | R/N | 依据真实能力 | descriptive/insufficient/model_estimate | O3 |
| Profile.primary_type | string | R/Y | null | A/B1/B2/C1/C2/C3/D1；规则未确认时null | O3 |
| Profile.additional_types | enum string[] | R/N | [] | 同组去重，不含主类型；不因顾虑判低依从 | O3 |
| Profile.reported_behavior | string | R/Y | null | Q1原选项代码，标明自报，不解释为客观率 | O3引用 |
| Profile.cas | CASResult | R/N | unavailable/null | CAS独立对象 | O3 |
| Profile.factors | FactorDescription[] | R/N | [] | 问卷障碍的可核对描述，非F1/F2/F3硬映射 | O3 |
| Profile.support_entry_codes | string[] | R/N | [] | reminder/organize_plan/knowledge/ai_support/social_support | O3建议；只导航不执行 |
| Profile.missing_items | Reason[] | R/N | [] | 输入/模型/规则不足分别说明 | O3 |
| Profile.questionnaire_version | string | R/N | 来源 | 精确问卷内容版本 | O3 |
| Profile.assessment_method_version | string | R/Y | null | 尚未确认的方法不可伪造生效版本 | O3 |
| Profile.generated_at | DateTime | R/N | 服务器时间 | 生成时间 | O3 |
| Profile.meta | Meta | R/N | 服务器生成 | 不以改写旧对象更新分类 | O3 |
| CASResult.status | string | R/N | unavailable | unavailable/insufficient/estimated | O3 |
| CASResult.value | number | R/Y | null | 未完成映射预处理验证必须null；量程后续核对 | 验证后的研究适配 |
| CASResult.reason | Reason | R/Y | null | 非estimated时必须说明；estimated仍需限制说明 | O3 |
| CASResult.model_version | string | R/Y | null | 无可定位模型时null | 研究适配 |
| CASResult.preprocessing_version | string | R/Y | null | 训练预处理不可现场重新fit冒充预测 | 研究适配 |
| FactorDescription.label | ShortText | R/N | 无 | 不诊断、不指责 | O3 |
| FactorDescription.source_question_ids | string[] | R/N | 无 | 本response中Q1…Q8的真实证据 | O3 |
| FactorDescription.source_value | Text | R/N | 无 | 选项/排序的可核对简述 | O3 |
| ProfileCreateInput.response_id | ID | R/N | 无 | 同患者的已提交响应 | 调用方 |

不增加伪造高低分阈值。没有分类规则也可返回描述性信息或insufficient，CAS显示未适配；此为建议降级行为，待Q06确认。C反馈不自动更新画像；复评通过新回答/新Profile产生。

## 6 O4 药品、正式计划、计划时段（O-draft01，O4维护；时段生成方待定）

### 6.1 Medication / MedicationInput

| 对象.字段 | 类型 | 出现/可空 | 默认 | 枚举/格式/范围 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| Medication.medication_id | ID | R/N | 服务器生成 | 患者药品资料，不等于一次计划用药 | O4 |
| Medication.patient_id | ID | R/N | 路径/原归属 | 不可编辑归属 | O4 |
| Medication.name | ShortText | R/N | 无 | 原药名，不自动推断规范名/处方 | 用户核对 |
| Medication.notes | Text | R/Y | null | 资料备注；不允许把改药指令当专业意见 | 用户 |
| Medication.meta | Meta | R/N | 服务器生成 | 每次纠正留历史 | O4 |
| MedicationCreateInput.name | ShortText | R/N | 无 | 仅创建药品条目 | 用户 |
| MedicationCreateInput.notes | Text | O/Y | null | 可省略/可显式null | 用户 |
| MedicationPatch.expected_revision | Version | R/N | 无 | 原修订 | 用户 |
| MedicationPatch.name | ShortText | O/N | 省略=不改 | 不能空名 | 用户 |
| MedicationPatch.notes | Text | O/Y | 省略=不改 | null明确清空备注 | 用户 |

剂量、频次、时间属于正式计划版本，不能通过药品名称编辑偷偷改变。拼写修正的历史名称仍可由旧计划快照追溯。

### 6.2 PlanVersion / PlanEntry / Schedule / PlanConfirmation

| 对象.字段 | 类型 | 出现/可空 | 默认 | 枚举/格式/单位/范围 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| PlanVersion.plan_id | ID | R/N | 新建或延续同一计划 | 正式计划主ID | O4 |
| PlanVersion.plan_version | Version | R/N | 单调递增 | 与meta.revision不同，是业务版本 | O4 |
| PlanVersion.patient_id | ID | R/N | 已验草稿归属 | 患者一致 | O4 |
| PlanVersion.status | string | R/N | confirmed | confirmed/superseded；取消/暂停入口另待确认，不擅自启用 | O4 |
| PlanVersion.effective_from | DateTime | R/N | 必须显式确定 | 生效边界；回溯规则待Q09 | 用户明确核对，O保存 |
| PlanVersion.effective_until | DateTime | R/Y | null | 右边界；旧版结束不改写原事件 | O4 |
| PlanVersion.timezone | Timezone | R/N | 患者当前时区快照 | 冻结计划日历含义 | O4 |
| PlanVersion.entries | PlanEntry[] | R/N | 无 | 至少1条；均来自已确认草稿 | O4 |
| PlanVersion.source_draft_id | ID | R/N | A提供 | 同一草稿指定修订 | A引用/O保存 |
| PlanVersion.source_draft_revision | Version | R/N | A提供 | 不确认“当时最新”这种浮动对象 | A引用/O保存 |
| PlanVersion.confirmed_by_account_id | ID | R/N | 已验证会话 | 本人或获准确认家人，权限待Q08 | O4 |
| PlanVersion.confirmed_at | DateTime | R/N | 服务器时间 | 不能由网页传已确认时间 | O4 |
| PlanVersion.is_confirmation_simulated | boolean | R/N | 按实际确认路径 | 演示流程明确标记 | O4 |
| PlanVersion.meta | Meta | R/N | 服务器生成 | 历史版本保留 | O4 |
| PlanEntry.plan_entry_id | ID | R/N | O生成 | 当前版本内稳定条目 | O4 |
| PlanEntry.medication_id | ID | R/N | 已核对 | 必须同患者 | O4 |
| PlanEntry.medication_name_snapshot | ShortText | R/N | 核对时药名 | 保留版本依据 | O4 |
| PlanEntry.dose_value | string decimal | R/N | 无 | 正十进制定点字符串建议，不能自动补剂量 | 已核对处方/人工资料 |
| PlanEntry.dose_unit | string | R/N | 无 | 1—40字符，原单位；单位表待A批确认 | 已核对资料 |
| PlanEntry.start_date | LocalDate | R/N | 无 | 已知用药开始日期 | 已核对资料 |
| PlanEntry.end_date | LocalDate | R/Y | null | 不早于start_date；长期未知可null | 已核对资料 |
| PlanEntry.schedule | Schedule | R/N | 无 | 频次与具体时刻 | 已核对资料 |
| PlanEntry.meal_requirement | string | R/Y | null | 原餐前/餐后等说明，未知null，不猜 | 已核对资料 |
| PlanEntry.medical_notes | Text | R/Y | null | 特殊医嘱原文 | 已核对资料 |
| PlanEntry.strict_timing | boolean | R/Y | null | 未知保持null，不能当false随意偏移 | 已核对资料 |
| PlanEntry.min_interval_minutes | integer >0 | R/Y | null | 分钟，仅实际医嘱已提供时写 | 已核对资料 |
| PlanEntry.source_file_ids | ID[] | R/N | [] | 可纯手工，无文件≠识别失败 | A引用 |
| Schedule.kind | string | R/N | 无 | daily/weekly（建议本期），按需/复杂疗程待定 | O4核对 |
| Schedule.times | LocalTime[] | R/N | 无 | 至少1、去重、按当地时刻排序 | O4核对 |
| Schedule.weekdays | integer[] | R/N | [] | weekly时1—7、至少1；daily时[] | O4核对 |
| PlanConfirmInput.draft_id | ID | R/N | 无 | A提交记录引用，不接受整份另一套计划字段 | 用户选择 |
| PlanConfirmInput.draft_revision | Version | R/N | 无 | 正在核对的精确修订 | 用户引用 |
| PlanConfirmInput.existing_plan_id | ID | R/Y | 无 | 新计划null，变更明确引用旧计划 | 用户引用 |
| PlanConfirmInput.expected_plan_version | Version | R/Y | 无 | 新计划null，旧计划必须当前版本 | 用户引用 |
| PlanConfirmInput.effective_from | DateTime | R/N | 无 | 不允许服务端猜医嘱生效时间 | 用户确认 |
| PlanConfirmInput.confirmed | boolean | R/N | 无 | 必须true，仍需身份/修订/内容核验 | 用户动作 |

A草稿的结构化计划内容须使用同一PlanEntry/Schedule语义（草稿未分配正式条目ID时使用独立临时引用，待A批对齐），本轮不扩展A的草稿字段。**发布事务建议**：核验精确草稿修订/授权→发布不可变PlanVersion→登记A正式引用→登记时段/摘要失效更新需求，同库原子提交。跨进程边界若出现则另行确认，不擅自宣称有可靠外部回传。

### 6.3 DoseSlot / SlotWindow（字段暂定，计数粒度尚未确认）

| 对象.字段 | 类型 | 出现/可空 | 默认 | 约束/语义 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| DoseSlot.dose_slot_id | ID | R/N | 生成器稳定分配 | 重放不换ID | 建议O规则/A存储 |
| DoseSlot.patient_id | ID | R/N | 计划归属 | 不跨患者 | 生成器 |
| DoseSlot.plan_id | ID | R/N | 来源计划 | 正式计划引用 | 生成器 |
| DoseSlot.plan_version | Version | R/N | 来源版本 | 不把旧证据静默改挂新版本 | 生成器 |
| DoseSlot.plan_entry_id | ID | R/N | 来源条目 | 本草案按单药一次应服提出，待Q09 | 生成器 |
| DoseSlot.medication_id | ID | R/N | 条目引用 | 不推断整盒所有药都已服 | 生成器 |
| DoseSlot.scheduled_at | DateTime | R/N | 医嘱安排 | 计划时间，不是提醒/吞服时间 | 生成器 |
| DoseSlot.status | string | R/N | active | active/superseded/cancelled（代码建议，取消触发未启用） | O计划规则 |
| DoseSlot.source_rule_version | string | R/N | 可定位生成规则 | 未确认时不实际生成 | O |
| DoseSlot.is_simulated | boolean | R/N | 来源计划/环境 | 不混真实模拟 | 接入环境 |
| SlotWindow.items | DoseSlot[] | R/N | [] | 按scheduled_at、ID稳定排序 | O/A |
| SlotWindow.next_cursor | string | R/Y | null | 与窗口、患者绑定 | O/A |
| SlotWindow.window_start | DateTime | R/N | 查询 | 建议[start,end) | 调用方/O校验 |
| SlotWindow.window_end | DateTime | R/N | 查询 | >start；建议最多31天，待确认 | 调用方/O校验 |

O不提供“已服”按钮的另一份事实。按钮调用A medication-events；O29返回安排，A返回当前五类状态与原因。未来、取消、替代和跨日规则必须在O/A确认后才确定分母。

## 7 O5 提醒与隐私配置（O-draft01，O5维护）

本节为**配置**，A7负责执行。本轮不实现调度或浏览器通知；页面关闭后提醒未承诺。首次系统通知许可必须实际用户动作，拒绝许可仍可站内使用。

| 对象.字段 | 类型 | 出现/可空 | 默认（均建议） | 枚举/格式/单位/范围 | 生成方 |
| --- | --- | --- | --- | --- | --- |
| ReminderPreferences.patient_id | ID | R/N | 路径 | 当前患者 | O5 |
| ReminderPreferences.enabled | boolean | R/N | false | 是否启用；默认值待Q11确认 | 用户/O |
| ReminderPreferences.channels | string[] | R/N | [in_app] | in_app/system_notification；后者需能力与浏览器许可 | 用户/O |
| ReminderPreferences.sound_enabled | boolean | R/N | false | 仅能力允许时；不保证后台音效 | 用户/O |
| ReminderPreferences.vibration_enabled | boolean | R/N | false | 不支持时拒绝/提示，不伪称执行 | 用户/O |
| ReminderPreferences.routine_mode | string | R/N | regular | regular/night_shift/rotating_shift/travel/custom | 用户 |
| ReminderPreferences.anchors | Anchor[] | R/N | [] | 生活事件仅影响提醒，不改变计划医嘱 | 用户 |
| ReminderPreferences.privacy_enabled | boolean | R/N | false | 用户主动开启，不推断所在场景 | 用户 |
| ReminderPreferences.custom_text | ShortText | R/Y | null | privacy开启时通知不得含药/病名，需校验或采用中性文案 | 用户/O |
| ReminderPreferences.privacy_windows | LocalWindow[] | R/N | [] | 指定时段；跨午夜建议拆两段 | 用户 |
| ReminderPreferences.repeat_interval_minutes | integer ≥1 | R/Y | null | null不重复；不可猜医学间隔，最小技术频率待定 | 用户 |
| ReminderPreferences.max_repeats | integer ≥0 | R/N | 0 | 频控上限待Q11；null间隔时必须0 | 用户/规则限制 |
| ReminderPreferences.snooze_minutes | integer >0 | R/Y | null | 稍后提醒，不是建议补服；实际任务另由A处理 | 用户 |
| ReminderPreferences.notify_family | boolean | R/N | false | 需有效notify:receive及患者确认；不能因绑定默认开启 | 用户/O |
| ReminderPreferences.meta | Meta | R/N | 服务器生成 | 配置留修订 | O5 |
| Anchor.event | string | R/N | 无 | wake/breakfast/bedtime/custom | 用户 |
| Anchor.label | ShortText | R/Y | null | event=custom时必填 | 用户 |
| Anchor.local_time | LocalTime | R/N | 无 | 用户主动设置，不伪装实时感知 | 用户 |
| Anchor.offset_minutes | integer | R/N | 0 | 分钟，正后负前；允许范围待Q11；不改变scheduled_at | 用户 |
| LocalWindow.start | LocalTime | R/N | 无 | 本地时刻 | 用户 |
| LocalWindow.end | LocalTime | R/N | 无 | >start，同日；跨午夜分段 | 用户 |
| ReminderPutInput.expected_revision | integer ≥0 | R/N | 无 | 首次0，之后当前修订 | 调用方 |
| ReminderPutInput.settings | ReminderSettings | R/N | 无 | 包含上述enabled至notify_family全部字段，均R；不含patient_id/meta | 用户 |

enabled=false仍保存用户选择，查询不会偷偷启用；已确认任务停止无意义重复提醒的执行规则在A批细化。配置修改、极简UI模式、模型mode分别维护。家人被授予编辑提醒也不能扩大第三方共享范围。

## 8 本轮未冻结的关键状态与版本

本轮提出：家庭关系active→revoked；授权active→revoked/expired；问卷draft→submitted；更正通过新response；画像用新Profile；计划confirmed→superseded；时段状态与A五类统计分开；提醒以修订配置保存。以上新增代码/转换待本轮确认，不能冒充总Prompt已冻结状态。

已确认但本轮不细化：C服务submitted/in_progress/completed/cancelled/failed，终态不回退；B建议/邀请枚举、UI模式及A摘要fresh/stale/insufficient按原Prompt，下一批补字段与卡。接口/表结构/问卷/评估/提醒规则版本分别管理，当前均无冻结契约和已应用schema。
