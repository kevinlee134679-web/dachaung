# S00 B批：39张接口卡（draft01）

2026-11-16，Asia/Shanghai。**全部新增方案待确认、未冻结、未实现**。B01—B37承接原目录，B38/B39为BX-02/BX-04新增建议；BX-03为A任务注册兼容增量，均不自动生效。字段版本B-draft01；完整字段与递归别名见B01，问题及前置排除见B00、公共/O与A确认清单。

## 1 全卡共同契约

所有示例为虚构结构，不是已经运行、审核、申请或联通的证明。每个Envelope<T>的完整字段为B01中T及递归子对象、公共Envelope/Meta/List、A外部别名定义；示例不能代替字段表。成功/失败四字段固定，失败data=null，错误code/message脱敏。

- 默认/api/v1；路径/查询/请求头/请求体分别定义，未列字段422。网页写入Cookie+X-CSRF-Token+Idempotency-Key+application/json；可信模块/设备/渠道用实际身份适配，真实协议缺失拒绝，不信任body自报角色/患者/来源。
- GET不写状态、不调用模型、不启动调度；POST检索也不执行医学建议或任意代码。所有查询/写入/回调/执行及幂等重放先重验患者与授权。
- HTTP401未登录，403范围/资格不足，跨患者资源404，422字段格式/未知参数，409版本/内容/状态/在途/预算冲突，502上游非法回复/生成失败，503依赖未就绪；超时可504，不能静默返回mock成功或空数据。
- 同键同内容同业务资源，同键异内容409；在途409+Retry-After:1；确定未提交可安全重试，provider结果未知先核查；模型/动作预算持久化、重放不再调用。A的至少7天回执规则不删除原消息/业务唯一事实。
- message先稳定保存，生成网络阶段无SQLite长写锁；失败可能已有用户消息，B10按client_message_id恢复；B11沿用原消息/快照/预算，不重新插话，不因A重试重置2/8限制。核心结构非法明确失败，辅助无证据可剔除并说明。
- 每轮固定实际mode/requested_pipeline/actual_pipeline及模型/提示词/知识/规则版本；不显示思维链。供应商不提供稳定版本如实null。mock逻辑调用不是付费网络，用量未知null不填0。
- A执行、渠道提交/送达、B网页展示/响应分开；C唯一创建正式申请，未授权/未确认/未接入不建第二份服务。后台资料/用户文本/模型输出都非可执行指令。
- 下面所有验收均为计划，未执行接口/网页/数据库/模型评测；真实付费连通/评测只在后续用户明确允许的动作中执行，本轮禁止。

## 2 接口卡

### B01 显式模型探测

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/config/check-model` |
| 用途/维护/页面 | 显式模型探测 / B1 / 演示控制台/连接检查 |
| 身份/患者范围 | 仅后端管理白名单；本轮禁止执行真实探测 |
| 路径/查询/头/体 | path/query无；JSON=ModelProbeInput；管理Cookie/CSRF/Idempotency-Key；不接受地址或密钥；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<ModelProbeResult>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 MODEL_NOT_CONFIGURED；另继承共同错误 |
| 幂等/状态/事务/来源 | mock无网络；real须未来明确允许外部调用，探测建议最多1次，记录实际用量/未知。健康GET不探测，配置失败不自动mock。 |
| 待实施验收 | 重复探测键不重复调用；real缺钥拒绝；本轮无付费探测。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "probe_id": "probe-mock-demo-001",
    "profile_id": "profile-mock-single",
    "mode": "mock",
    "model_label": "mock-support",
    "model_config_version": "mock-config-draft01",
    "status": "available",
    "network_attempt_count": 0,
    "elapsed_ms": 1,
    "usage": {
      "input_tokens": null,
      "output_tokens": null,
      "total_tokens": null,
      "source": "unavailable",
      "missing_reason": "mock_no_provider_usage"
    },
    "checked_at": "2026-11-16T05:30:00Z"
  },
  "error": null
}
```

失败结构示例（HTTP 503）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "MODEL_NOT_CONFIGURED",
    "message": "真实模型配置或依赖未就绪"
  }
}
```

### B02 虚构案例列表

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/cases` |
| 用途/维护/页面 | 虚构案例列表 / B6 / 独立演示控制台 |
| 身份/患者范围 | 仅demo:manage白名单；真实环境禁演示入口 |
| 路径/查询/头/体 | path/body无；query cursor/limit；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<CaseDefinition>>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 403 DEMO_DISABLED；另继承共同错误 |
| 幂等/状态/事务/来源 | 只读模板，不隐式创建患者会话或模型回复。 |
| 待实施验收 | 三个虚构主题明确标模拟；不当真实患者资料。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "case_id": "case-fatigue-demo",
        "patient_id": "p-demo-001",
        "title": "长期用药疲惫（虚构）",
        "focus": "treatment_fatigue",
        "template_version": "case-draft01",
        "opening_draft": "最近每天处理这些事情，感觉有点累。",
        "is_simulated": true
      },
      {
        "case_id": "case-mood-demo",
        "patient_id": "p-demo-001",
        "title": "情绪低落（虚构）",
        "focus": "low_mood",
        "template_version": "case-draft01",
        "opening_draft": "最近每天处理这些事情，感觉有点累。",
        "is_simulated": true
      },
      {
        "case_id": "case-concerns-demo",
        "patient_id": "p-demo-001",
        "title": "焦虑与用药顾虑（虚构）",
        "focus": "anxiety_concerns",
        "template_version": "case-draft01",
        "opening_draft": "最近每天处理这些事情，感觉有点累。",
        "is_simulated": true
      }
    ],
    "next_cursor": null
  },
  "error": null
}
```

失败结构示例（HTTP 403）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "DEMO_DISABLED",
    "message": "当前环境不允许演示案例"
  }
}
```

### B03 案例模板与开场草稿

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/cases/{id}` |
| 用途/维护/页面 | 案例模板与开场草稿 / B6 / 演示控制台/案例选择 |
| 身份/患者范围 | 同B02，案例及患者范围核验 |
| 路径/查询/头/体 | path case_id；query/body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<CaseDefinition>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 CASE_NOT_FOUND；另继承共同错误 |
| 幂等/状态/事务/来源 | opening_draft只填输入框；切换清除网页旧建议/模式控件，不能伪造已发言。 |
| 待实施验收 | 真实模式的回复未来由明确发送现场生成，不使用模板回复冒充。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "case_id": "case-fatigue-demo",
    "patient_id": "p-demo-001",
    "title": "长期用药疲惫（虚构）",
    "focus": "treatment_fatigue",
    "template_version": "case-draft01",
    "opening_draft": "最近每天处理这些事情，感觉有点累。",
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "CASE_NOT_FOUND",
    "message": "案例不可访问或不存在"
  }
}
```

### B04 案例范围明确确认重置

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/cases/{id}/reset` |
| 用途/维护/页面 | 案例范围明确确认重置 / B6 / 演示控制台/重置当前案例 |
| 身份/患者范围 | 仅demo:manage，模板/案例版本一致，仅虚构范围 |
| 路径/查询/头/体 | path case_id；query无；JSON=CaseResetInput；管理Cookie/CSRF/Idempotency-Key；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<ResetResult>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 CASE_HAS_LINKED_RESOURCES；另继承共同错误 |
| 幂等/状态/事务/来源 | 预检关联C服务/积分和在途外部动作；未定义清理则拒绝。B范围清理与A待执行取消原子协调/失败回滚，保留模板、配置、其他案例、O/A原事实和工作记录。 |
| 待实施验收 | 真实环境禁用；事务失败不清一半；重复键不误清后来新数据。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "reset_id": "reset-demo-001",
    "case_id": "case-fatigue-demo",
    "affected_session_ids": [],
    "cancelled_task_ids": [],
    "reset_at": "2026-11-16T05:30:00Z",
    "preserved_template_version": "case-draft01",
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "CASE_HAS_LINKED_RESOURCES",
    "message": "案例有关联服务等尚未确认清理范围，已阻止重置"
  }
}
```

### B05 创建会话或进入已接受邀请

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/sessions` |
| 用途/维护/页面 | 创建会话或进入已接受邀请 / B3/B6 / AI情感支持/邀请入口 |
| 身份/患者范围 | 本人dialogue:write；家人代发言本批不启用 |
| 路径/查询/头/体 | path/query无；JSON=SessionCreateInput；网页写入头；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<Session>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 INVITATION_NOT_ACCEPTED；另继承共同错误 |
| 幂等/状态/事务/来源 | user直接新建；accepted_invitation须核验本人有效接受；同邀请只能关联一个有效会话，可复用已有绑定，不额外确认/代写消息；新会话normal。 |
| 待实施验收 | 同键不多会话；案例/患者不符拒绝；不重置服务周期。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "session_id": "session-demo-001",
    "patient_id": "p-demo-001",
    "case_id": "case-fatigue-demo",
    "status": "active",
    "entry_source": "user",
    "invitation_id": null,
    "turn_count": 0,
    "ui_mode": "normal",
    "opened_at": "2026-11-16T05:30:00Z",
    "closed_at": null,
    "meta": {
      "created_at": "2026-11-16T05:30:00Z",
      "updated_at": "2026-11-16T05:30:00Z",
      "revision": 1,
      "contract_version": "B-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "INVITATION_NOT_ACCEPTED",
    "message": "邀请未接受、已过期或会话归属不符"
  }
}
```

### B06 分页会话历史

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/sessions` |
| 用途/维护/页面 | 分页会话历史 / B6 / 我的/AI支持历史 |
| 身份/患者范围 | 本人或dialogue:read专门授权；不因家庭绑定开放整段聊天 |
| 路径/查询/头/体 | path/body无；query patient_id R/N、case_id O/N、cursor/limit；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<Session>>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承共同错误 |
| 幂等/状态/事务/来源 | 按opened_at/session_id排序，患者/案例过滤绑定游标；只读。 |
| 待实施验收 | 甲不能用乙游标查历史；授权撤销后立即拒绝。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "session_id": "session-demo-001",
        "patient_id": "p-demo-001",
        "case_id": "case-fatigue-demo",
        "status": "active",
        "entry_source": "user",
        "invitation_id": null,
        "turn_count": 0,
        "ui_mode": "normal",
        "opened_at": "2026-11-16T05:30:00Z",
        "closed_at": null,
        "meta": {
          "created_at": "2026-11-16T05:30:00Z",
          "updated_at": "2026-11-16T05:30:00Z",
          "revision": 1,
          "contract_version": "B-draft01",
          "is_simulated": true
        }
      }
    ],
    "next_cursor": null
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "会话列表不可访问"
  }
}
```

### B07 会话当前状态

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/sessions/{s}` |
| 用途/维护/页面 | 会话当前状态 / B3/B6 / AI支持/刷新恢复 |
| 身份/患者范围 | 本人或dialogue:read；核验session患者 |
| 路径/查询/头/体 | path session_id；query/body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Session>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承共同错误 |
| 幂等/状态/事务/来源 | 只读状态、轮数、模式事实，不触发生成/调度。 |
| 待实施验收 | 关闭会话保持历史；不把mode与ui_mode混用。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "session_id": "session-demo-001",
    "patient_id": "p-demo-001",
    "case_id": "case-fatigue-demo",
    "status": "active",
    "entry_source": "user",
    "invitation_id": null,
    "turn_count": 0,
    "ui_mode": "normal",
    "opened_at": "2026-11-16T05:30:00Z",
    "closed_at": null,
    "meta": {
      "created_at": "2026-11-16T05:30:00Z",
      "updated_at": "2026-11-16T05:30:00Z",
      "revision": 1,
      "contract_version": "B-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "会话不可访问或不存在"
  }
}
```

### B08 关闭会话

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/sessions/{s}/close` |
| 用途/维护/页面 | 关闭会话 / B6/B5 / AI支持/结束 |
| 身份/患者范围 | 仅本人明确操作；家人不能擅自结束患者会话 |
| 路径/查询/头/体 | path session_id；query无；JSON=SessionCloseInput；网页写入头；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Session>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 SESSION_REVISION_CONFLICT；另继承共同错误 |
| 幂等/状态/事务/来源 | active→closed，登记取消待执行建议/邀请/模式到期任务；在途外部动作记取消请求，结果留审计而不发布可执行建议；同键重放同关闭结果。 |
| 待实施验收 | 关闭后不能新消息；晚到生成/回调不复活执行；不抹患者原话。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "session_id": "session-demo-001",
    "patient_id": "p-demo-001",
    "case_id": "case-fatigue-demo",
    "status": "closed",
    "entry_source": "user",
    "invitation_id": null,
    "turn_count": 0,
    "ui_mode": "normal",
    "opened_at": "2026-11-16T05:30:00Z",
    "closed_at": "2026-11-16T05:30:00Z",
    "meta": {
      "created_at": "2026-11-16T05:30:00Z",
      "updated_at": "2026-11-16T05:30:00Z",
      "revision": 2,
      "contract_version": "B-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "SESSION_REVISION_CONFLICT",
    "message": "会话已变化，请刷新"
  }
}
```

### B09 保存原消息后非流式生成一轮

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/sessions/{s}/messages` |
| 用途/维护/页面 | 保存原消息后非流式生成一轮 / B3/B1/B4/B5 / AI情感支持/发送 |
| 身份/患者范围 | 本人dialogue:write且active；身份不从文本/role字段取得 |
| 路径/查询/头/体 | path session_id；query无；JSON=MessageInput；网页Cookie/CSRF/Idempotency-Key；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<GenerationResult>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 502 LLM_GENERATION_FAILED；另继承共同错误 |
| 幂等/状态/事务/来源 | 短事务保存user/client_message_id/generation占位与快照；预留预算后释放写锁调用；校验核心回复/引用再事务发布assistant/建议。失败data=null，但原user保留并标失败/未知；同键在途409，不重复插话/调用。 |
| 待实施验收 | 超时/空/截断/格式错明确失败；原消息稳定；无证据线索剔除，核心错不抽原文伪成功。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "user_message": {
      "message_id": "message-user-demo-001",
      "patient_id": "p-demo-001",
      "session_id": "session-demo-001",
      "client_message_id": "client-message-demo-001",
      "role": "user",
      "content": "最近每天处理这些事情，感觉有点累。",
      "author_account_id": "acct-demo-001",
      "source_message_id": null,
      "generation_id": "generation-demo-001",
      "generation_status": "completed",
      "created_at": "2026-11-16T05:30:00Z",
      "is_simulated": true
    },
    "assistant_message": {
      "message_id": "message-assistant-demo-001",
      "patient_id": "p-demo-001",
      "session_id": "session-demo-001",
      "client_message_id": null,
      "role": "assistant",
      "content": "每天都要惦记这些，确实会累。你愿意说说，最近哪一部分最让你费力吗？",
      "author_account_id": null,
      "source_message_id": "message-user-demo-001",
      "generation_id": "generation-demo-001",
      "generation_status": "completed",
      "created_at": "2026-11-16T05:30:01Z",
      "is_simulated": true
    },
    "generation": {
      "generation_id": "generation-demo-001",
      "patient_id": "p-demo-001",
      "session_id": "session-demo-001",
      "user_message_id": "message-user-demo-001",
      "status": "completed",
      "mode": "mock",
      "requested_pipeline": "single_pass",
      "actual_pipeline": "single_pass",
      "fallback_reason": null,
      "input_snapshot": {
        "snapshot_id": "snapshot-demo-001",
        "patient_id": "p-demo-001",
        "session_id": "session-demo-001",
        "user_message_id": "message-user-demo-001",
        "history_message_ids": [
          "message-user-demo-001"
        ],
        "profile_id": null,
        "plan_refs": [],
        "summary_ref": null,
        "retrieval_id": null,
        "version_refs": [
          {
            "kind": "prompt",
            "version": "support-prompt-draft01"
          },
          {
            "kind": "model_config",
            "version": "mock-config-draft01"
          }
        ],
        "missing_items": [
          {
            "code": "summary_not_integrated",
            "message": "A摘要尚未接入本结构示例",
            "field": "summary_ref"
          }
        ],
        "captured_at": "2026-11-16T05:30:00Z"
      },
      "budget": {
        "max_network_attempts": 2,
        "used_network_attempts": 0,
        "max_candidates": 1,
        "max_output_tokens": 1024,
        "deadline_at": "2026-11-16T05:31:00Z"
      },
      "calls": [
        {
          "call_id": "call-mock-demo-001",
          "generation_id": "generation-demo-001",
          "stage": "single_pass",
          "attempt_number": 1,
          "network_attempt_number": null,
          "mode": "mock",
          "provider_label": "deterministic-mock",
          "model_label": "mock-support",
          "provider_model_version": null,
          "model_config_version": "mock-config-draft01",
          "status": "succeeded",
          "usage": {
            "input_tokens": null,
            "output_tokens": null,
            "total_tokens": null,
            "source": "unavailable",
            "missing_reason": "mock_no_provider_usage"
          },
          "elapsed_ms": 1,
          "error_code": null,
          "started_at": "2026-11-16T05:30:00Z",
          "finished_at": "2026-11-16T05:30:01Z"
        }
      ],
      "error_code": null,
      "started_at": "2026-11-16T05:30:00Z",
      "finished_at": "2026-11-16T05:30:01Z",
      "is_simulated": true
    },
    "business_output": {
      "assistant_reply": "每天都要惦记这些，确实会累。你愿意说说，最近哪一部分最让你费力吗？",
      "support_focus": "listening",
      "difficulty_cues": [
        {
          "category": "treatment_fatigue",
          "label": "持续管理带来的疲惫线索",
          "evidence": "感觉有点累",
          "source_message_id": "message-user-demo-001"
        }
      ],
      "communication_strategy": [
        "reflection",
        "open_question"
      ],
      "suggested_action": null,
      "knowledge_citations": [],
      "change_readiness": null
    },
    "intervention_id": "intervention-demo-001",
    "suggestion_ids": []
  },
  "error": null
}
```

失败结构示例（HTTP 502）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "LLM_GENERATION_FAILED",
    "message": "生成失败；原消息可能已保存，请按原提交编号恢复"
  }
}
```

### B10 历史及失败提交恢复

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/sessions/{s}/messages` |
| 用途/维护/页面 | 历史及失败提交恢复 / B6 / 聊天历史/重试恢复 |
| 身份/患者范围 | 本人或dialogue:read，专门授权不超范围 |
| 路径/查询/头/体 | path session_id；query cursor/limit、client_message_id O/N；body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<Message>>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承共同错误 |
| 幂等/状态/事务/来源 | created_at/message_id排序；按client_message_id可找已持久化user及generation_status；未知结果先查询，不再插相同发言。 |
| 待实施验收 | 失败HTTP后可恢复原消息ID；不会把助手当用户证据。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "message_id": "message-user-demo-001",
        "patient_id": "p-demo-001",
        "session_id": "session-demo-001",
        "client_message_id": "client-message-demo-001",
        "role": "user",
        "content": "最近每天处理这些事情，感觉有点累。",
        "author_account_id": "acct-demo-001",
        "source_message_id": null,
        "generation_id": "generation-demo-001",
        "generation_status": "completed",
        "created_at": "2026-11-16T05:30:00Z",
        "is_simulated": true
      },
      {
        "message_id": "message-assistant-demo-001",
        "patient_id": "p-demo-001",
        "session_id": "session-demo-001",
        "client_message_id": null,
        "role": "assistant",
        "content": "每天都要惦记这些，确实会累。你愿意说说，最近哪一部分最让你费力吗？",
        "author_account_id": null,
        "source_message_id": "message-user-demo-001",
        "generation_id": "generation-demo-001",
        "generation_status": "completed",
        "created_at": "2026-11-16T05:30:01Z",
        "is_simulated": true
      }
    ],
    "next_cursor": null
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "消息不可访问"
  }
}
```

### B11 引用原消息的安全重试

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/messages/{id}/generation-retries` |
| 用途/维护/页面 | 引用原消息的安全重试 / B3/B1 / 聊天错误提示/重试 |
| 身份/患者范围 | 本人dialogue:write，原user消息属active当前会话 |
| 路径/查询/头/体 | path message_id；query无；JSON=GenerationRetryInput；网页写入头；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<GenerationResult>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 GENERATION_NOT_RETRYABLE；另继承共同错误 |
| 幂等/状态/事务/来源 | 复用原user/generation与固定输入，预留剩余全轮预算；确定可重试才调用。认证/配置/不支持参数不重试；provider结果未知需核查。已完成相同操作重放旧结果，不重复付费。 |
| 待实施验收 | A任务重试不能重置2/8上限；同消息不多条原话/有效助手结果。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "user_message": {
      "message_id": "message-user-demo-001",
      "patient_id": "p-demo-001",
      "session_id": "session-demo-001",
      "client_message_id": "client-message-demo-001",
      "role": "user",
      "content": "最近每天处理这些事情，感觉有点累。",
      "author_account_id": "acct-demo-001",
      "source_message_id": null,
      "generation_id": "generation-demo-001",
      "generation_status": "completed",
      "created_at": "2026-11-16T05:30:00Z",
      "is_simulated": true
    },
    "assistant_message": {
      "message_id": "message-assistant-demo-001",
      "patient_id": "p-demo-001",
      "session_id": "session-demo-001",
      "client_message_id": null,
      "role": "assistant",
      "content": "每天都要惦记这些，确实会累。你愿意说说，最近哪一部分最让你费力吗？",
      "author_account_id": null,
      "source_message_id": "message-user-demo-001",
      "generation_id": "generation-demo-001",
      "generation_status": "completed",
      "created_at": "2026-11-16T05:30:01Z",
      "is_simulated": true
    },
    "generation": {
      "generation_id": "generation-demo-001",
      "patient_id": "p-demo-001",
      "session_id": "session-demo-001",
      "user_message_id": "message-user-demo-001",
      "status": "completed",
      "mode": "mock",
      "requested_pipeline": "single_pass",
      "actual_pipeline": "single_pass",
      "fallback_reason": null,
      "input_snapshot": {
        "snapshot_id": "snapshot-demo-001",
        "patient_id": "p-demo-001",
        "session_id": "session-demo-001",
        "user_message_id": "message-user-demo-001",
        "history_message_ids": [
          "message-user-demo-001"
        ],
        "profile_id": null,
        "plan_refs": [],
        "summary_ref": null,
        "retrieval_id": null,
        "version_refs": [
          {
            "kind": "prompt",
            "version": "support-prompt-draft01"
          },
          {
            "kind": "model_config",
            "version": "mock-config-draft01"
          }
        ],
        "missing_items": [
          {
            "code": "summary_not_integrated",
            "message": "A摘要尚未接入本结构示例",
            "field": "summary_ref"
          }
        ],
        "captured_at": "2026-11-16T05:30:00Z"
      },
      "budget": {
        "max_network_attempts": 2,
        "used_network_attempts": 0,
        "max_candidates": 1,
        "max_output_tokens": 1024,
        "deadline_at": "2026-11-16T05:31:00Z"
      },
      "calls": [
        {
          "call_id": "call-mock-demo-001",
          "generation_id": "generation-demo-001",
          "stage": "single_pass",
          "attempt_number": 1,
          "network_attempt_number": null,
          "mode": "mock",
          "provider_label": "deterministic-mock",
          "model_label": "mock-support",
          "provider_model_version": null,
          "model_config_version": "mock-config-draft01",
          "status": "succeeded",
          "usage": {
            "input_tokens": null,
            "output_tokens": null,
            "total_tokens": null,
            "source": "unavailable",
            "missing_reason": "mock_no_provider_usage"
          },
          "elapsed_ms": 1,
          "error_code": null,
          "started_at": "2026-11-16T05:30:00Z",
          "finished_at": "2026-11-16T05:30:01Z"
        }
      ],
      "error_code": null,
      "started_at": "2026-11-16T05:30:00Z",
      "finished_at": "2026-11-16T05:30:01Z",
      "is_simulated": true
    },
    "business_output": {
      "assistant_reply": "每天都要惦记这些，确实会累。你愿意说说，最近哪一部分最让你费力吗？",
      "support_focus": "listening",
      "difficulty_cues": [
        {
          "category": "treatment_fatigue",
          "label": "持续管理带来的疲惫线索",
          "evidence": "感觉有点累",
          "source_message_id": "message-user-demo-001"
        }
      ],
      "communication_strategy": [
        "reflection",
        "open_question"
      ],
      "suggested_action": null,
      "knowledge_citations": [],
      "change_readiness": null
    },
    "intervention_id": "intervention-demo-001",
    "suggestion_ids": []
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "GENERATION_NOT_RETRYABLE",
    "message": "生成在途、预算耗尽、结果未知或已被新轮替代"
  }
}
```

### B12 分来源评估/线索历史

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/sessions/{s}/assessments` |
| 用途/维护/页面 | 分来源评估/线索历史 / B4 / 可折叠分析/自评历史 |
| 身份/患者范围 | 本人或assessment:read，不能因dialogue摘要授权取得全部心理信息 |
| 路径/查询/头/体 | path session_id；query cursor/limit；body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<Assessment>>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承共同错误 |
| 幂等/状态/事务/来源 | 按observed_at/assessment_id排序；患者原话、自评、模型线索和A上下文分开；过期不当当前。 |
| 待实施验收 | 无方法score=null；跨患者/虚构引用拒绝。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "assessment_id": "assessment-demo-001",
        "patient_id": "p-demo-001",
        "session_id": "session-demo-001",
        "kind": "model_cues",
        "source_message_ids": [
          "message-user-demo-001"
        ],
        "cues": [
          {
            "category": "treatment_fatigue",
            "label": "持续管理带来的疲惫线索",
            "evidence": "感觉有点累",
            "source_message_id": "message-user-demo-001"
          }
        ],
        "self_report_items": [],
        "score": null,
        "scoring_method_version": null,
        "score_missing_reason": "scoring_method_not_confirmed",
        "observed_at": "2026-11-16T05:30:00Z",
        "valid_until": "2026-11-16T05:45:00Z",
        "version_refs": [
          {
            "kind": "cue_method",
            "version": "cues-draft01"
          }
        ],
        "meta": {
          "created_at": "2026-11-16T05:30:00Z",
          "updated_at": "2026-11-16T05:30:00Z",
          "revision": 1,
          "contract_version": "B-draft01",
          "is_simulated": true
        }
      }
    ],
    "next_cursor": null
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "评估记录不可访问"
  }
}
```

### B13 描述性患者自评

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/sessions/{s}/self-reports` |
| 用途/维护/页面 | 描述性患者自评 / B4 / 支持服务/简短反馈 |
| 身份/患者范围 | 仅本人assessment:write，active会话 |
| 路径/查询/头/体 | path session_id；query无；JSON=SelfReportInput；网页写入头；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<Assessment>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 422 INVALID_SELF_REPORT；另继承共同错误 |
| 幂等/状态/事务/来源 | 保存明确自述和来源，不临时生成量表/总分；client_report_id与幂等共同防重复，不自动额外模型调用。 |
| 待实施验收 | 顾虑/必要性/负担分开；无评分方法不造精确数值。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "assessment_id": "self-report-demo-001",
    "patient_id": "p-demo-001",
    "session_id": "session-demo-001",
    "kind": "self_report",
    "source_message_ids": [
      "message-user-demo-001"
    ],
    "cues": [],
    "self_report_items": [
      {
        "dimension": "burden",
        "description": "每天安排这些事情有些费力（虚构自述）",
        "source_message_id": null
      }
    ],
    "score": null,
    "scoring_method_version": null,
    "score_missing_reason": "scoring_method_not_confirmed",
    "observed_at": "2026-11-16T05:30:00Z",
    "valid_until": "2026-11-16T05:45:00Z",
    "version_refs": [
      {
        "kind": "cue_method",
        "version": "cues-draft01"
      }
    ],
    "meta": {
      "created_at": "2026-11-16T05:30:00Z",
      "updated_at": "2026-11-16T05:30:00Z",
      "revision": 1,
      "contract_version": "B-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 422）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "INVALID_SELF_REPORT",
    "message": "自评维度、来源或内容不合法"
  }
}
```

### B14 精确评估与版本

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/assessments/{id}` |
| 用途/维护/页面 | 精确评估与版本 / B4 / 评估详情/研究说明 |
| 身份/患者范围 | 本人或assessment:read，按原患者/会话权限 |
| 路径/查询/头/体 | path assessment_id；query/body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Assessment>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承共同错误 |
| 幂等/状态/事务/来源 | 只读当时来源/方法版本，不用新方法覆盖旧结果，不展示思维链。 |
| 待实施验收 | 方法变更不拼接成同尺度趋势；证据引用可核对。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "assessment_id": "assessment-demo-001",
    "patient_id": "p-demo-001",
    "session_id": "session-demo-001",
    "kind": "model_cues",
    "source_message_ids": [
      "message-user-demo-001"
    ],
    "cues": [
      {
        "category": "treatment_fatigue",
        "label": "持续管理带来的疲惫线索",
        "evidence": "感觉有点累",
        "source_message_id": "message-user-demo-001"
      }
    ],
    "self_report_items": [],
    "score": null,
    "scoring_method_version": null,
    "score_missing_reason": "scoring_method_not_confirmed",
    "observed_at": "2026-11-16T05:30:00Z",
    "valid_until": "2026-11-16T05:45:00Z",
    "version_refs": [
      {
        "kind": "cue_method",
        "version": "cues-draft01"
      }
    ],
    "meta": {
      "created_at": "2026-11-16T05:30:00Z",
      "updated_at": "2026-11-16T05:30:00Z",
      "revision": 1,
      "contract_version": "B-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "评估不可访问或不存在"
  }
}
```

### B15 当前有效策略与建议

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/sessions/{s}/strategy` |
| 用途/维护/页面 | 当前有效策略与建议 / B5 / 聊天辅助区/支持入口 |
| 身份/患者范围 | 本人或interventions:read；可执行控件仅本人可操作 |
| 路径/查询/头/体 | path session_id；query/body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<StrategyView>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 STRATEGY_UNAVAILABLE；另继承共同错误 |
| 幂等/状态/事务/来源 | 只读有效期/来源规则下的现有事实，不隐式模型/调度；过期状态明确、历史控件只读；A摘要不足不造心理风险。 |
| 待实施验收 | 无干预允许none；刷新不重复投递；极简保留全局入口。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "session_id": "session-demo-001",
    "patient_id": "p-demo-001",
    "status": "active",
    "current_intervention": {
      "intervention_id": "intervention-demo-001",
      "patient_id": "p-demo-001",
      "session_id": "session-demo-001",
      "trigger_type": "user",
      "trigger_ref": "message-user-demo-001",
      "should_intervene": false,
      "support_type": "listening",
      "support_intensity": "low",
      "interaction_burden": "minimal",
      "channel_suggestion": "none",
      "decision_reason": "患者表达疲惫，先回应具体感受并按意愿倾听，不增加外部执行动作。",
      "evidence_refs": [
        {
          "source_type": "message",
          "record_id": "message-user-demo-001",
          "version": null,
          "label": "患者表达最近管理负担"
        }
      ],
      "input_snapshot_id": "snapshot-demo-001",
      "rule_version": "support-rule-draft01",
      "version_refs": [
        {
          "kind": "prompt",
          "version": "support-prompt-draft01"
        },
        {
          "kind": "model_config",
          "version": "mock-config-draft01"
        }
      ],
      "decided_at": "2026-11-16T05:30:00Z",
      "valid_until": "2026-11-16T05:45:00Z",
      "execution_status": "not_required",
      "execution_ids": [],
      "displayed_at": null,
      "response_ids": [],
      "is_simulated": true
    },
    "suggestions": [],
    "invitations": [],
    "ui_state": {
      "session_id": "session-demo-001",
      "patient_id": "p-demo-001",
      "scope": "session",
      "ui_mode": "normal",
      "revision": 1,
      "changed_at": "2026-11-16T05:30:00Z",
      "valid_until": null,
      "minimum_until": null,
      "last_offer_at": null,
      "is_simulated": true
    },
    "generated_at": "2026-11-16T05:30:00Z"
  },
  "error": null
}
```

失败结构示例（HTTP 503）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "STRATEGY_UNAVAILABLE",
    "message": "策略读取暂不可用"
  }
}
```

### B16 决策与执行分层详情

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/interventions/{id}` |
| 用途/维护/页面 | 决策与执行分层详情 / B5/B6 / 干预历史/来源说明 |
| 身份/患者范围 | 本人或interventions:read，底层证据按原授权访问 |
| 路径/查询/头/体 | path intervention_id；query/body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Intervention>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承共同错误 |
| 幂等/状态/事务/来源 | 返回证据和规则理由摘要，不保存内部推理链；A执行/提交/送达、B展示/响应分别记录。 |
| 待实施验收 | submitted不当delivered；服务建议接受不当C服务完成。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "intervention_id": "intervention-demo-001",
    "patient_id": "p-demo-001",
    "session_id": "session-demo-001",
    "trigger_type": "user",
    "trigger_ref": "message-user-demo-001",
    "should_intervene": false,
    "support_type": "listening",
    "support_intensity": "low",
    "interaction_burden": "minimal",
    "channel_suggestion": "none",
    "decision_reason": "患者表达疲惫，先回应具体感受并按意愿倾听，不增加外部执行动作。",
    "evidence_refs": [
      {
        "source_type": "message",
        "record_id": "message-user-demo-001",
        "version": null,
        "label": "患者表达最近管理负担"
      }
    ],
    "input_snapshot_id": "snapshot-demo-001",
    "rule_version": "support-rule-draft01",
    "version_refs": [
      {
        "kind": "prompt",
        "version": "support-prompt-draft01"
      },
      {
        "kind": "model_config",
        "version": "mock-config-draft01"
      }
    ],
    "decided_at": "2026-11-16T05:30:00Z",
    "valid_until": "2026-11-16T05:45:00Z",
    "execution_status": "not_required",
    "execution_ids": [],
    "displayed_at": null,
    "response_ids": [],
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "干预不可访问或不存在"
  }
}
```

### B17 明确接受/拒绝/取消建议

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/suggestions/{id}/response` |
| 用途/维护/页面 | 明确接受/拒绝/取消建议 / B5 / 聊天建议卡片 |
| 身份/患者范围 | 仅本人，pending且未过期，同患者会话 |
| 路径/查询/头/体 | path suggestion_id；query无；JSON=SuggestionResponseInput；网页写入头；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<SuggestionResponse>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 SUGGESTION_RESPONSE_CONFLICT；另继承共同错误 |
| 幂等/状态/事务/来源 | 响应与状态同事务；accepted极简可同事务调用模式服务并记录ModeChange，无需重复确认；small_step仅意愿，专业支持只导航，不能直接C申请。相同响应重放，相反响应不覆盖。 |
| 待实施验收 | 拒绝后同轮不反复建议；接受不能变服药确认/改药/扩权。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "response_id": "suggestion-response-demo-001",
    "suggestion_id": "suggestion-mode-demo-001",
    "patient_id": "p-demo-001",
    "choice": "accepted",
    "responded_at": "2026-11-16T05:30:00Z",
    "mode_change_id": "mode-change-demo-001",
    "referral_id": null,
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "SUGGESTION_RESPONSE_CONFLICT",
    "message": "建议已响应、失效或出现相反选择"
  }
}
```

### B18 独立网页展示回执

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/interventions/{id}/display-receipts` |
| 用途/维护/页面 | 独立网页展示回执 / B5 / 患者页面实际渲染 |
| 身份/患者范围 | 本人会话及可展示该干预，不能管理台假称患者已读 |
| 路径/查询/头/体 | path intervention_id；query无；JSON=DisplayReceiptInput；网页写入头；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<DisplayReceipt>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 DISPLAY_RECEIPT_CONFLICT；另继承共同错误 |
| 幂等/状态/事务/来源 | 客户端稳定展示号、服务器首次接收去重；仅实际展示事实，不同意/不服药/不完成服务；授权变化后不发布敏感内容。 |
| 待实施验收 | 重复渲染不重复计数；A提交不能自动填displayed_at。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "receipt_id": "display-demo-001",
    "intervention_id": "intervention-demo-001",
    "client_receipt_id": "client-display-demo-001",
    "displayed_at": "2026-11-16T05:30:00Z",
    "received_at": "2026-11-16T05:30:01Z",
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "DISPLAY_RECEIPT_CONFLICT",
    "message": "展示事件号内容冲突或对象已失效"
  }
}
```

### B19 读取模式和可选变更历史

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/sessions/{s}/ui-mode` |
| 用途/维护/页面 | 读取模式和可选变更历史 / B5 / 聊天/模式状态 |
| 身份/患者范围 | 本人或interventions:read；切换权限另验 |
| 路径/查询/头/体 | path session_id；query include_history O/N=false、cursor/limit；body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<UIModeView>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承共同错误 |
| 幂等/状态/事务/来源 | GET不写到期状态/调度；到期恢复由注册A任务B处理器登记历史；当前投影与有效期明确，不静默锁用户。 |
| 待实施验收 | normal/simplified与LLM mock/real分开；历史来源可追溯。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "current": {
      "session_id": "session-demo-001",
      "patient_id": "p-demo-001",
      "scope": "session",
      "ui_mode": "normal",
      "revision": 1,
      "changed_at": "2026-11-16T05:30:00Z",
      "valid_until": null,
      "minimum_until": null,
      "last_offer_at": null,
      "is_simulated": true
    },
    "changes": [],
    "next_cursor": null
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "模式状态不可访问"
  }
}
```

### B20 主动切换与恢复

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `PUT /api/v1/sessions/{s}/ui-mode` |
| 用途/维护/页面 | 主动切换与恢复 / B5 / 极简按钮/恢复正常 |
| 身份/患者范围 | 仅本人mode:write与明确操作，active会话 |
| 路径/查询/头/体 | path session_id；query无；JSON=UIModePutInput；网页写入头；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<UIState>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 UI_MODE_REVISION_CONFLICT；另继承共同错误 |
| 幂等/状态/事务/来源 | 同事务写UIState+ModeChange；重复选择当前模式不增事件；切简建议2小时/最短0秒，可立即恢复；登记BX-03到期任务，不改计划/积分/全局导航。接受过的相同建议不再问同意。 |
| 待实施验收 | 首次不自动切；用户可恢复；到期旧任务不能覆盖新选择。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "session_id": "session-demo-001",
    "patient_id": "p-demo-001",
    "scope": "session",
    "ui_mode": "simplified",
    "revision": 2,
    "changed_at": "2026-11-16T05:30:00Z",
    "valid_until": "2026-11-16T07:30:00Z",
    "minimum_until": "2026-11-16T05:30:00Z",
    "last_offer_at": "2026-11-16T05:30:00Z",
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "UI_MODE_REVISION_CONFLICT",
    "message": "模式已变化，请刷新"
  }
}
```

### B21 该会话的邀请历史

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/sessions/{s}/invitations` |
| 用途/维护/页面 | 该会话的邀请历史 / B5 / 聊天邀请区/历史 |
| 身份/患者范围 | 本人或interventions:read，限定该会话归属 |
| 路径/查询/头/体 | path session_id；query status O/N=不筛选、cursor/limit；body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<Invitation>>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承共同错误 |
| 幂等/状态/事务/来源 | 只读本会话邀请；未绑定会话的背景邀请走B39，避免丢失首页入口。 |
| 待实施验收 | 接受/拒绝/过期分别展示，不代用户写消息。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "invitation_id": "invitation-demo-001",
        "patient_id": "p-demo-001",
        "session_id": "session-demo-001",
        "trigger_type": "periodic",
        "trigger_ref": "cycle-node-demo-001",
        "status": "pending",
        "title": "愿意做一次简短回顾吗？",
        "description": "可以现在聊一会，也可以暂时不参加。",
        "created_at": "2026-11-16T05:30:00Z",
        "valid_until": "2026-11-17T05:30:00Z",
        "displayed_at": null,
        "resolved_session_id": null,
        "rule_version": "checkin-draft01",
        "is_simulated": true
      }
    ],
    "next_cursor": null
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "邀请不可访问"
  }
}
```

### B22 响应邀请并准备会话入口

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/invitations/{id}/response` |
| 用途/维护/页面 | 响应邀请并准备会话入口 / B5 / 首页/聊天邀请 |
| 身份/患者范围 | 仅本人，pending且有效，同患者 |
| 路径/查询/头/体 | path invitation_id；query无；JSON=InvitationResponseInput；网页写入头；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<InvitationResponse>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 INVITATION_RESPONSE_CONFLICT；另继承共同错误 |
| 幂等/状态/事务/来源 | 响应与邀请状态同事务；可绑定现有active会话，或保存accepted后B05建立唯一会话；不自动发患者消息/模型调用；相反响应不改历史。 |
| 待实施验收 | 并发接受只一次；已接受确认复用；拒绝不算抵触。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "response_id": "invitation-response-demo-001",
    "invitation_id": "invitation-demo-001",
    "patient_id": "p-demo-001",
    "choice": "accepted",
    "session_id": null,
    "responded_at": "2026-11-16T05:30:00Z",
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "INVITATION_RESPONSE_CONFLICT",
    "message": "邀请已响应、过期或会话不合法"
  }
}
```

### B23 复用C唯一正式申请创建

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/referrals` |
| 用途/维护/页面 | 复用C唯一正式申请创建 / B5代理，C实际服务 / 专业支持建议/社会支持入口 |
| 身份/患者范围 | 本人且C已有相应服务确认/共享范围授权；不是仅接受建议就申请 |
| 路径/查询/头/体 | path/query无；JSON=ReferralCreateInput；网页写入头；BCX-01字段待C联合确认；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<Referral>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 SOCIAL_SUPPORT_NOT_INTEGRATED；另继承共同错误 |
| 幂等/状态/事务/来源 | 校验C资源/草稿/有效确认与范围，同库C创建+referral映射+去重原子协调；未就绪不自建第二份服务；未知结果先查C业务键；service_id只接受C真实返回。 |
| 待实施验收 | 相同有效确认复用；范围变更重新取得相应确认；未授权不通知第三方。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "referral_id": "referral-demo-001",
    "patient_id": "p-demo-001",
    "session_id": "session-demo-001",
    "source_suggestion_id": "suggestion-professional-demo-001",
    "proxy_status": "linked",
    "service_id": "service-demo-001",
    "service_status": "submitted",
    "confirmation_ref_id": "service-confirmation-demo-001",
    "sharing_scope_ref_id": "share-scope-demo-001",
    "failure_reason": null,
    "meta": {
      "created_at": "2026-11-16T05:30:00Z",
      "updated_at": "2026-11-16T05:30:00Z",
      "revision": 1,
      "contract_version": "B-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 503）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "SOCIAL_SUPPORT_NOT_INTEGRATED",
    "message": "C正式服务能力未接入，未创建实际申请"
  }
}
```

### B24 转介代理与实际服务映射

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/referrals/{id}` |
| 用途/维护/页面 | 转介代理与实际服务映射 / B5/C / 支持建议/服务状态 |
| 身份/患者范围 | 本人或获准interventions:read且具C服务相应读取权限 |
| 路径/查询/头/体 | path referral_id；query/body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Referral>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承共同错误 |
| 幂等/状态/事务/来源 | proxy_status和C service_status分别显示；service_id=null不能显示正式提交；C五状态为事实来源，B不自改完成。 |
| 待实施验收 | 未接入/结果未知与submitted区分；终态不回退。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "referral_id": "referral-demo-001",
    "patient_id": "p-demo-001",
    "session_id": "session-demo-001",
    "source_suggestion_id": "suggestion-professional-demo-001",
    "proxy_status": "linked",
    "service_id": "service-demo-001",
    "service_status": "submitted",
    "confirmation_ref_id": "service-confirmation-demo-001",
    "sharing_scope_ref_id": "share-scope-demo-001",
    "failure_reason": null,
    "meta": {
      "created_at": "2026-11-16T05:30:00Z",
      "updated_at": "2026-11-16T05:30:00Z",
      "revision": 1,
      "contract_version": "B-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "转介不可访问或不存在"
  }
}
```

### B25 A状态事件与检查触发

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/integrations/state-events` |
| 用途/维护/页面 | A状态事件与检查触发 / B5，A来源 / 可信状态更新→B规则 |
| 身份/患者范围 | 独立模块身份，核验患者与summary_ref实际来源/授权 |
| 路径/查询/头/体 | path/query无；JSON=StateEventInput；服务认证+Idempotency-Key；非患者Cookie自报；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<IntegrationAck>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 STATE_EVENT_CONFLICT；另继承共同错误 |
| 幂等/状态/事务/来源 | 来源号去重、固定规则/输入、决定是否邀请及审计同事务；无规则不执行新干预；迟到可重算不重复节点；不写患者发言/重新算CAS。 |
| 待实施验收 | 单次开盒/无记录不发家属警报；撤销事件取消待共享，晚事件不复活。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "integration_event_id": "state-integration-demo-001",
    "source_event_id": "source-state-integration-demo-001",
    "applied": true,
    "ignore_reason": null,
    "related_ids": [
      "invitation-demo-001"
    ],
    "received_at": "2026-11-16T05:30:00Z",
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "STATE_EVENT_CONFLICT",
    "message": "同来源事件号内容不同"
  }
}
```

### B26 A执行与投递回传

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/integrations/execution-receipts` |
| 用途/维护/页面 | A执行与投递回传 / B5/A7 / A7可信回传 |
| 身份/患者范围 | 独立A模块身份，task/execution/intervention/patient关联全相等 |
| 路径/查询/头/体 | path/query无；JSON=ExecutionReceiptInput；服务认证+Idempotency-Key；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<IntegrationAck>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 EXECUTION_RECEIPT_CONFLICT；另继承共同错误 |
| 幂等/状态/事务/来源 | 原A执行快照去重/审计，合法映射B状态：completed+submitted仅submitted；unknown保留未知，不能填展示/响应；取消/过期/撤销后不恢复。 |
| 待实施验收 | 乱序不回退；mock标记保留；模型/积分/C申请不在此触发。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "integration_event_id": "execution-integration-demo-001",
    "source_event_id": "source-execution-integration-demo-001",
    "applied": true,
    "ignore_reason": null,
    "related_ids": [
      "intervention-demo-001"
    ],
    "received_at": "2026-11-16T05:30:00Z",
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "EXECUTION_RECEIPT_CONFLICT",
    "message": "回执关联或内容冲突"
  }
}
```

### B27 C服务状态回传

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/integrations/referral-receipts` |
| 用途/维护/页面 | C服务状态回传 / B5/C / C可信回传 |
| 身份/患者范围 | 独立C身份，referral映射service_id/patient一致 |
| 路径/查询/头/体 | path/query无；JSON=ReferralReceiptInput；服务认证+Idempotency-Key；C版本格式待C批；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<IntegrationAck>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 REFERRAL_RECEIPT_CONFLICT；另继承共同错误 |
| 幂等/状态/事务/来源 | 读取C权威状态更新B引用，不另创建申请；重复/乱序/终态回退不应用且留审计；未获反馈不能宣称干预有效。 |
| 待实施验收 | 取消/撤销后的晚回执不复活；完成和评价分开。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "integration_event_id": "referral-integration-demo-001",
    "source_event_id": "source-referral-integration-demo-001",
    "applied": true,
    "ignore_reason": null,
    "related_ids": [
      "referral-demo-001"
    ],
    "received_at": "2026-11-16T05:30:00Z",
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "REFERRAL_RECEIPT_CONFLICT",
    "message": "服务映射或来源版本冲突"
  }
}
```

### B28 受控场景/故障模拟

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/demo/triggers` |
| 用途/维护/页面 | 受控场景/故障模拟 / B6 / 独立演示控制台 |
| 身份/患者范围 | 仅demo:manage，虚构案例及实际mock模型；不能伪造真实故障成功 |
| 路径/查询/头/体 | path/query无；JSON=DemoTriggerInput；管理Cookie/CSRF/Idempotency-Key；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<DemoTriggerResult>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 403 DEMO_TRIGGER_DISABLED；另继承共同错误 |
| 幂等/状态/事务/来源 | scenario_run_id固定重放；配置明确模拟场景，不自动发患者消息/训练/真实模型调用；引用只本案例，会话不符拒绝。 |
| 待实施验收 | 模拟ID不串会话；STAR中途失败/超时/知识空可独立演示。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "trigger_id": "trigger-demo-001",
    "case_id": "case-fatigue-demo",
    "scenario": "knowledge_empty",
    "related_ids": [],
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 403）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "DEMO_TRIGGER_DISABLED",
    "message": "当前环境或实际模型模式不允许该模拟"
  }
}
```

### B29 A汇总所需最小反馈

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/intervention-feedback` |
| 用途/维护/页面 | A汇总所需最小反馈 / B6 / A摘要/授权反馈 |
| 身份/患者范围 | 可信A服务或本人feedback:read且具B原来源权限 |
| 路径/查询/头/体 | path patient_id；query window_start/end R/N、cursor/limit；body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<FeedbackSource>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 B_FEEDBACK_UNAVAILABLE；另继承共同错误 |
| 幂等/状态/事务/来源 | 完整复用A FeedbackSource/Ref；原话/推测/自评分别引用，默认不导出整段聊天；没有反馈不造0分或改善。 |
| 待实施验收 | A不能因反馈口径再算B诊断；无授权返回受限/拒绝，不泄露对话。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "source_module": "B",
    "availability": "available",
    "records": [
      {
        "record_kind": "intervention",
        "record_id": "intervention-demo-001",
        "source_version": "B-draft01",
        "recorded_at": "2026-11-16T05:30:00Z",
        "service_status": null,
        "support_needs": null,
        "support_acceptance": null,
        "intervention_effectiveness": null,
        "is_simulated": true
      }
    ],
    "reason": null
  },
  "error": null
}
```

失败结构示例（HTTP 503）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "B_FEEDBACK_UNAVAILABLE",
    "message": "B反馈暂不可读取"
  }
}
```

### B30 研究反馈窗口JSON导出

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/interventions/export` |
| 用途/维护/页面 | 研究反馈窗口JSON导出 / B6 / 受控研究/导出入口 |
| 身份/患者范围 | 本人或exports:read专门授权，底层B数据权限同时满足 |
| 路径/查询/头/体 | path无；query patient_id、window_start/end R/N（≤31天）、format O/N=json、cursor/limit；body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<InterventionExport>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 403 EXPORT_NOT_AUTHORIZED；另继承共同错误 |
| 幂等/状态/事务/来源 | 只读分页JSON Envelope，默认决策元信息/引用，无整段原话/内部候选/思维链；模拟/版本/缺失保留；不自动成为训练授权。 |
| 待实施验收 | 跨患者/超窗口拒绝；不会把模型自评当患者效果。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "export_id": "export-demo-001",
    "patient_id": "p-demo-001",
    "window_start": "2026-11-16T00:00:00+08:00",
    "window_end": "2026-11-17T00:00:00+08:00",
    "items": [
      {
        "intervention_id": "intervention-demo-001",
        "patient_id": "p-demo-001",
        "session_id": "session-demo-001",
        "trigger_type": "user",
        "trigger_ref": "message-user-demo-001",
        "should_intervene": false,
        "support_type": "listening",
        "support_intensity": "low",
        "interaction_burden": "minimal",
        "channel_suggestion": "none",
        "decision_reason": "患者表达疲惫，先回应具体感受并按意愿倾听，不增加外部执行动作。",
        "evidence_refs": [
          {
            "source_type": "message",
            "record_id": "message-user-demo-001",
            "version": null,
            "label": "患者表达最近管理负担"
          }
        ],
        "input_snapshot_id": "snapshot-demo-001",
        "rule_version": "support-rule-draft01",
        "version_refs": [
          {
            "kind": "prompt",
            "version": "support-prompt-draft01"
          },
          {
            "kind": "model_config",
            "version": "mock-config-draft01"
          }
        ],
        "decided_at": "2026-11-16T05:30:00Z",
        "valid_until": "2026-11-16T05:45:00Z",
        "execution_status": "not_required",
        "execution_ids": [],
        "displayed_at": null,
        "response_ids": [],
        "is_simulated": true
      }
    ],
    "next_cursor": null,
    "generated_at": "2026-11-16T05:30:00Z",
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 403）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "EXPORT_NOT_AUTHORIZED",
    "message": "没有相应数据导出授权"
  }
}
```

### B31 共用知识列表与管理预览

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/knowledge` |
| 用途/维护/页面 | 共用知识列表与管理预览 / B2 / O药学知识/B对话/C说明/管理资料 |
| 身份/患者范围 | 患者knowledge:read仅可适用有效已审核；include_unreviewed仅knowledge:manage |
| 路径/查询/头/体 | path/body无；query cursor/limit、kind O/N、include_unreviewed O/N=false；成功示例前置为管理预览；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<KnowledgeRecord>>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 403 KNOWLEDGE_PREVIEW_FORBIDDEN；另继承共同错误 |
| 幂等/状态/事务/来源 | 患者读取过滤状态/时效/范围；草稿示例不作医学事实；O/C不另建知识库；管理列表不隐式审核。 |
| 待实施验收 | 未审核/撤回不进患者医学内容；无材料明确不足。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "knowledge_id": "knowledge-demo-001",
        "version": "content-demo-v1",
        "kind": "communication",
        "title": "通用支持性沟通原则（演示草稿）",
        "body": "先理解具体困扰，尊重是否继续讨论的选择。",
        "source_locator": "project:baseline/v1.1#B3",
        "applicability_tags": [
          "general_communication"
        ],
        "language": "zh-CN",
        "review_status": "draft",
        "effective_from": "2026-11-16T05:30:00Z",
        "effective_until": null,
        "reviewed_by": null,
        "reviewed_at": null,
        "review_note": null,
        "meta": {
          "created_at": "2026-11-16T05:30:00Z",
          "updated_at": "2026-11-16T05:30:00Z",
          "revision": 1,
          "contract_version": "B-draft01",
          "is_simulated": true
        }
      }
    ],
    "next_cursor": null
  },
  "error": null
}
```

失败结构示例（HTTP 403）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "KNOWLEDGE_PREVIEW_FORBIDDEN",
    "message": "当前身份不能读取未审核资料"
  }
}
```

### B32 精确资料版本与旧引用

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/knowledge/{id}/versions/{version}` |
| 用途/维护/页面 | 精确资料版本与旧引用 / B2 / 知识详情/历史引用 |
| 身份/患者范围 | 当前医学用途需reviewed适用有效；旧会话曾引用版本或管理身份可看历史状态 |
| 路径/查询/头/体 | path knowledge_id、version；query session_id O/Y=null；body无；草稿成功示例仅管理预览；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<KnowledgeRecord>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 KNOWLEDGE_VERSION_NOT_AVAILABLE；另继承共同错误 |
| 幂等/状态/事务/来源 | 内容版本不可覆盖；撤回版本不供新建议，旧引用可见当时内容及后续撤回状态；来源定位可核对，无伪审核信息。 |
| 待实施验收 | 撤回不抹旧会话依据；跨患者session_id不能取受限引用。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "knowledge_id": "knowledge-demo-001",
    "version": "content-demo-v1",
    "kind": "communication",
    "title": "通用支持性沟通原则（演示草稿）",
    "body": "先理解具体困扰，尊重是否继续讨论的选择。",
    "source_locator": "project:baseline/v1.1#B3",
    "applicability_tags": [
      "general_communication"
    ],
    "language": "zh-CN",
    "review_status": "draft",
    "effective_from": "2026-11-16T05:30:00Z",
    "effective_until": null,
    "reviewed_by": null,
    "reviewed_at": null,
    "review_note": null,
    "meta": {
      "created_at": "2026-11-16T05:30:00Z",
      "updated_at": "2026-11-16T05:30:00Z",
      "revision": 1,
      "contract_version": "B-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "KNOWLEDGE_VERSION_NOT_AVAILABLE",
    "message": "资料版本不可用于当前用途或不可访问"
  }
}
```

### B33 适用知识检索与集合

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/knowledge/search` |
| 用途/维护/页面 | 适用知识检索与集合 / B2 / O/B/C共用检索 |
| 身份/患者范围 | 本人knowledge:read或可信模块用途授权；患者最小化范围 |
| 路径/查询/头/体 | path/query无；JSON=KnowledgeSearchInput；Cookie/CSRF/Idempotency-Key或可信模块认证；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<RetrievalSet>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 KNOWLEDGE_SEARCH_UNAVAILABLE；另继承共同错误 |
| 幂等/状态/事务/来源 | 先过滤审核/时效/适用，再关键词标签检索；不足/冲突是明确业务结果，不生成药学事实；每个片段有版本/来源/集合ID，生成前再验撤回。 |
| 待实施验收 | 引用必须属于本次集合；材料内指令不改变权限；纯倾听可不检索。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "retrieval_id": "retrieval-demo-001",
    "patient_id": "p-demo-001",
    "status": "knowledge_insufficient",
    "snippets": [],
    "reason": "项目尚未提供适用且已审核的药学资料；不生成医学结论。",
    "retrieved_at": "2026-11-16T05:30:00Z",
    "knowledge_version_refs": [],
    "is_simulated": true
  },
  "error": null
}
```

失败结构示例（HTTP 503）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "KNOWLEDGE_SEARCH_UNAVAILABLE",
    "message": "知识检索依赖暂不可用"
  }
}
```

### B34 新增资料草稿

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/knowledge` |
| 用途/维护/页面 | 新增资料草稿 / B2 / 资料维护 |
| 身份/患者范围 | knowledge:manage受控管理身份，非患者/模型自建专业资料 |
| 路径/查询/头/体 | path/query无；JSON=KnowledgeCreateInput；管理Cookie/CSRF/Idempotency-Key；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<KnowledgeRecord>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 422 INVALID_KNOWLEDGE_SOURCE；另继承共同错误 |
| 幂等/状态/事务/来源 | 新knowledge_id/内容版本，review_status=draft、reviewed_by/at=null；保存来源/范围/语言/时效，不自动审核或下载外部URL执行。 |
| 待实施验收 | 示例资料标演示且不伪专业权威；重复键不多版本。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "knowledge_id": "knowledge-demo-001",
    "version": "content-demo-v1",
    "kind": "communication",
    "title": "通用支持性沟通原则（演示草稿）",
    "body": "先理解具体困扰，尊重是否继续讨论的选择。",
    "source_locator": "project:baseline/v1.1#B3",
    "applicability_tags": [
      "general_communication"
    ],
    "language": "zh-CN",
    "review_status": "draft",
    "effective_from": "2026-11-16T05:30:00Z",
    "effective_until": null,
    "reviewed_by": null,
    "reviewed_at": null,
    "review_note": null,
    "meta": {
      "created_at": "2026-11-16T05:30:00Z",
      "updated_at": "2026-11-16T05:30:00Z",
      "revision": 1,
      "contract_version": "B-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 422）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "INVALID_KNOWLEDGE_SOURCE",
    "message": "资料内容或真实来源定位不完整"
  }
}
```

### B35 新增不可变内容版本

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/knowledge/{id}/versions` |
| 用途/维护/页面 | 新增不可变内容版本 / B2 / 资料维护/修订 |
| 身份/患者范围 | knowledge:manage且当前内容版本匹配 |
| 路径/查询/头/体 | path knowledge_id；query无；JSON=KnowledgeVersionInput；管理写入头；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<KnowledgeRecord>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 KNOWLEDGE_VERSION_CONFLICT；另继承共同错误 |
| 幂等/状态/事务/来源 | 保留旧内容/引用；新版本draft，不能继承旧版审核成为reviewed；内容/版本/幂等原子保存。 |
| 待实施验收 | 修改资料不静默改历史对话引用；旧页不能覆盖新内容。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "knowledge_id": "knowledge-demo-001",
    "version": "content-demo-v2",
    "kind": "communication",
    "title": "通用支持性沟通原则（演示草稿）",
    "body": "先理解具体困扰，尊重是否继续讨论的选择。",
    "source_locator": "project:baseline/v1.1#B3",
    "applicability_tags": [
      "general_communication"
    ],
    "language": "zh-CN",
    "review_status": "draft",
    "effective_from": "2026-11-16T05:30:00Z",
    "effective_until": null,
    "reviewed_by": null,
    "reviewed_at": null,
    "review_note": null,
    "meta": {
      "created_at": "2026-11-16T05:30:00Z",
      "updated_at": "2026-11-16T05:30:00Z",
      "revision": 1,
      "contract_version": "B-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "KNOWLEDGE_VERSION_CONFLICT",
    "message": "资料版本已变化"
  }
}
```

### B36 真实有资格审核动作

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/knowledge/{id}/review` |
| 用途/维护/页面 | 真实有资格审核动作 / B2 / 资料审核 |
| 身份/患者范围 | knowledge:review及后端可核验审核资格；模型不能自审 |
| 路径/查询/头/体 | path knowledge_id；query无；JSON=KnowledgeReviewInput；受控审核身份/CSRF/Idempotency-Key；例子为reject后草稿；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<KnowledgeRecord>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 403 QUALIFIED_REVIEWER_REQUIRED；另继承共同错误 |
| 幂等/状态/事务/来源 | 锁定精确内容版本；approve需真实资格并写服务器审核者/时间；reject回draft附说明；不接收客户端伪造reviewed_by/at；缺审核方不编造通过。 |
| 待实施验收 | LLM自评不能审核医学资料；不支持批准未定位来源版本。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "knowledge_id": "knowledge-demo-001",
    "version": "content-demo-v1",
    "kind": "communication",
    "title": "通用支持性沟通原则（演示草稿）",
    "body": "先理解具体困扰，尊重是否继续讨论的选择。",
    "source_locator": "project:baseline/v1.1#B3",
    "applicability_tags": [
      "general_communication"
    ],
    "language": "zh-CN",
    "review_status": "draft",
    "effective_from": "2026-11-16T05:30:00Z",
    "effective_until": null,
    "reviewed_by": null,
    "reviewed_at": null,
    "review_note": "演示材料尚未完成专业审核，退回补充。",
    "meta": {
      "created_at": "2026-11-16T05:30:00Z",
      "updated_at": "2026-11-16T05:30:00Z",
      "revision": 2,
      "contract_version": "B-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 403）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "QUALIFIED_REVIEWER_REQUIRED",
    "message": "缺少可核验的合格审核身份"
  }
}
```

### B37 撤回资料版本

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/knowledge/{id}/withdraw` |
| 用途/维护/页面 | 撤回资料版本 / B2 / 资料维护/撤回 |
| 身份/患者范围 | knowledge:manage受控身份，精确版本/修订 |
| 路径/查询/头/体 | path knowledge_id；query无；JSON=KnowledgeWithdrawInput；管理写入头；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<KnowledgeRecord>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 KNOWLEDGE_REVISION_CONFLICT；另继承共同错误 |
| 幂等/状态/事务/来源 | 写撤回审计，后续检索/新生成立即排除；旧引用保留当时版本及当前撤回状态；同键复用同撤回，不删历史。 |
| 待实施验收 | 缓存不得继续返回撤回医学资料作为新事实；历史可追溯。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "knowledge_id": "knowledge-demo-001",
    "version": "content-demo-v1",
    "kind": "communication",
    "title": "通用支持性沟通原则（演示草稿）",
    "body": "先理解具体困扰，尊重是否继续讨论的选择。",
    "source_locator": "project:baseline/v1.1#B3",
    "applicability_tags": [
      "general_communication"
    ],
    "language": "zh-CN",
    "review_status": "withdrawn",
    "effective_from": "2026-11-16T05:30:00Z",
    "effective_until": null,
    "reviewed_by": null,
    "reviewed_at": null,
    "review_note": "示例撤回：不再用于新检索",
    "meta": {
      "created_at": "2026-11-16T05:30:00Z",
      "updated_at": "2026-11-16T05:30:00Z",
      "revision": 2,
      "contract_version": "B-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 409）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "KNOWLEDGE_REVISION_CONFLICT",
    "message": "资料状态已变化"
  }
}
```

### B38 选择后端白名单模型/流水线配置

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `PUT /api/v1/config/model-profile` |
| 用途/维护/页面 | 选择后端白名单模型/流水线配置 / B1，BX-02新增建议 / 独立演示控制台/配置选择 |
| 身份/患者范围 | 仅后端管理白名单；患者/消息不能更改系统配置 |
| 路径/查询/头/体 | path/query无；JSON=ModelProfileInput；管理Cookie/CSRF/Idempotency-Key；不接受密钥/URL/任意参数；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<ModelProfileSelection>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 422 MODEL_PROFILE_NOT_READY；另继承共同错误 |
| 幂等/状态/事务/来源 | 只选择已登记profile，配置版本更新与回执同事务；已有生成固定旧快照；激活real缺依赖拒绝不降mock；选择不执行探测/调用。 |
| 待实施验收 | 普通患者不能改模型；未实现STAR profile不能假称可用；不会产生付费调用。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "profile_id": "profile-mock-single",
    "previous_profile_id": null,
    "mode": "mock",
    "requested_pipeline": "single_pass",
    "model_config_version": "mock-config-draft01",
    "configuration_status": "ready",
    "selected_at": "2026-11-16T05:30:00Z"
  },
  "error": null
}
```

失败结构示例（HTTP 422）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "MODEL_PROFILE_NOT_READY",
    "message": "配置未登记、阶段能力未实现或真实依赖缺失"
  }
}
```

### B39 首页读取未绑定会话的邀请

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/invitations` |
| 用途/维护/页面 | 首页读取未绑定会话的邀请 / B5，BX-04新增建议 / 首页支持邀请/尚无会话入口 |
| 身份/患者范围 | 本人或interventions:read；接受/拒绝仅本人 |
| 路径/查询/头/体 | path patient_id；query status O/N=不筛选、cursor/limit；body无；全部字段类型、R/O、可空、默认、枚举/格式/单位、生成方与版本见B01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<Invitation>>；递归完整字段表为定义，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承共同错误 |
| 幂等/状态/事务/来源 | 只读患者邀请，含session_id=null背景邀请；不因读取开会话/发消息/调度；B21保留某会话历史。 |
| 待实施验收 | 患者尚无会话也可见邀请；不重复索同一接受确认。 另核对跨患者/撤销、同键异内容、并发在途/回滚、超预算与历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "invitation_id": "invitation-demo-001",
        "patient_id": "p-demo-001",
        "session_id": null,
        "trigger_type": "periodic",
        "trigger_ref": "cycle-node-demo-001",
        "status": "pending",
        "title": "愿意做一次简短回顾吗？",
        "description": "可以现在聊一会，也可以暂时不参加。",
        "created_at": "2026-11-16T05:30:00Z",
        "valid_until": "2026-11-17T05:30:00Z",
        "displayed_at": null,
        "resolved_session_id": null,
        "rule_version": "checkin-draft01",
        "is_simulated": true
      }
    ],
    "next_cursor": null
  },
  "error": null
}
```

失败结构示例（HTTP 404）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "邀请列表不可访问"
  }
}
```

## 3 状态、事务与非法转换（本批待确认）

| 对象 | 合法/建议行为 | 必须拒绝/分开记录 |
| --- | --- | --- |
| 会话 | active→closed；新会话normal | closed再发消息拒绝；不重开旧终态或重置O服务周期 |
| 消息/生成 | user先保存→accepted/running→completed或failed/cancelled/outcome_unknown | 失败不抹user；在途不再调用；未知结果不盲重试；新轮不覆盖旧回复；预算A/B共同维护不重置 |
| 线索/自评 | 真原话/版本/时间范围；无评分方法score=null | 助手、跨患者、范围外引用拒绝；疲惫/拒绝非抵触证据；A生理值不直接诊断 |
| 知识 | draft→pending_review→reviewed；reject回draft；可withdrawn；新内容新版本 | 未审核/撤回不作新医学事实；未配置合格审核者不能伪造审核；旧内容引用不覆盖 |
| 建议 | pending→accepted/declined/cancelled/expired | 相反响应不覆盖；过期不能执行；拒绝后同轮不重复；接受小步不等于已服 |
| 模式 | 明确用户动作normal↔simplified；接受极简建议一次动作；到期恢复留ModeChange | 不自动首次切、不同会话不暗中继承；当前模式重复选择不增事件；用户恢复不能被最短时间锁住 |
| 邀请 | pending→accepted/declined/expired/cancelled；接受后绑定/新建唯一会话 | 先接受才开始沟通；不能替患者发言；规则变更/重启不重发完成节点 |
| 转介 | B代理pending→linked/failed/result_unknown；linked对应C真实service_id | 未确认授权不创建C服务；B不另建正式申请，proxy与C状态不混用；不把受理/完成当效果 |
| 执行/回执 | 来源去重、合法投影、乱序保留审计 | A completed≠送达≠展示≠接受；取消/过期/撤销后晚回执不复活 |
| 配置 | 管理者选择已登记profile、未来轮次使用新快照 | 消息/患者不能传任意URL/密钥/供应商参数；切配置不探测；旧轮次快照不变 |
| 演示重置 | 当前案例明确确认，预检跨模块引用，事务失败回滚 | 不删模板/配置/其他案例/O/A原事实/历史记录；C清理规则未定阻止而非留孤儿资源 |

## 4 固定验收计划与边界

- 沟通：只倾诉、明确求助、拒绝、疲惫、未知背景、转换话题和紧迫危险；每轮通常最多一个主要问题，不以顺从为唯一成功。
- 模型：mock正常/超时/空/非法JSON/截断/知识空/STAR中途失败；single_pass 2与STAR8预算包含全部尝试，候选≤2、60秒总预算；真实失败不降mock。
- 数据：同client_message_id重放、超时后历史恢复、同生成重试、不同患者、虚构线索、助手引用、输入范围外引用、撤回知识和资料提示注入。
- 执行：相反建议响应、首次明确极简/立即恢复/到期、新会话normal、邀请接受后唯一会话、不伪患者消息、A回调乱序/unknown、C未接入。
- 审核/权限：未审核医学知识不作为事实、无合格审核者拒绝、旧引用保留；家庭摘要权限不扩大为整段对话；研究导出不是训练授权。
- 重置与版本：真实环境禁演示入口；当前案例范围；关联C未定义清理阻止；新配置不改旧轮快照；没有记录的真实服务不编造。

本轮只做文档静态检查，不能据此宣称上述行为已实现或有效。B确认后继续C，再全流程及必要未决项；未获阶段指令不执行S01。

