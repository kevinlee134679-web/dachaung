# S00 C批：40张接口卡（draft01）

2026-11-16，Asia/Shanghai。**全部新增方案待确认、未冻结、未实现**。原目录33卡与C34—C40七项新增操作分别标明；字段C-draft01，完整递归定义见C01，问题和前置排除见C00/各确认清单。所有成功例子都是独立虚构状态快照，不是已申请/已授权/已发奖/已交付事实。

## 1 所有卡片共同契约

Envelope<T>完整字段按公共四字段定义，T/子对象/Meta/List/外部FeedbackSource均使用C01及前置字段表，示例不代替定义。请求只对应Input，未列字段422；客户端不能自报余额、状态、审核者、真实药师、共享有效性或模拟标记。

- 前缀/api/v1；网页JSON写入Cookie+X-CSRF-Token+Idempotency-Key+application/json，GET仅会话。可信服务/交付回调与内部核奖用实际服务身份，真实协议缺失拒绝，不拿患者Cookie或body角色冒充。
- HTTP401未登录、403权限/资格、跨患者资源404、422格式/未知字段、409内容/版本/在途/状态/余额/确认冲突、503依赖未就绪；失败data=null+error，不回首页HTML/假空列表/假成功。
- 同键同内容同业务资源；同键异内容409；在途409+Retry-After:1；业务已提交稳定重放；完全回滚才能原键安全重试；结果未知先核查。重放前重验授权，不能旧回执泄露撤销健康内容。
- 来源事件号、request_id、幂等键与业务ID分别维护。服务唯一性患者+草稿+内容修订，奖励业务键不含规则版本，退款唯一refund:redemption_id；不同幂等键不能绕过业务唯一约束。
- 数据库同库事务覆盖事实/修订/业务去重/回执/待执行登记，网络/投递在写锁外做；C不发第二套画像、计划、知识或授权。owner_module=C及注册任务需CQ14确认后登记A增量，不另建调度。
- Service五状态与草稿/确认/成员/兑换/交付状态各自独立。提交/投递/完成/患者反馈分开，真实在途取消先请求标记，不假称第三方已停止；终态晚回执审计，不回退。
- 该批所有积分数值、资格、24小时确认、5日分配/退分等均是待确认建议。必要医疗/药学服务不受点数门槛；LLM不能改余额或伪造来源；不因漏服/不适/暂停扣已有积分。
- 声称专业答复须可信来源/资格，mock_example清晰标识；病例、资料、模型输出不执行为指令。peer帖子本人主动发布纯文本，不自动夹带病历/对话；实际匿名保护与社群运营不能被虚构成已验证。
- 所有验收均未运行；本轮只文档静态验证，未真实发消息、通知、服务申请、积分操作或付费API调用。

## 2 接口卡

### C01 需求与首页支持推荐

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/support-recommendations` |
| 用途/维护/页面 | 需求与首页支持推荐 / C1/C3/C5 / 首页/社会支持 |
| 身份/患者范围 | 本人或support:read，O/A/B原来源范围同时校验 |
| 路径/查询/头/体 | path patient_id；query need O/N=现有上下文；body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<SupportRecommendation>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 SUPPORT_CONTEXT_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读O画像/A统计/B需求与本人意愿，最多主1次2；无需求不生卡，不足明确insufficient；不重算分类/CAS，不因一次未知联系家属。 |
| 待实施验收 | 原始分类保持不变；无库存数据不伪称药物即将用尽。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "patient_id": "p-demo-001",
    "profile_id": null,
    "primary_profile_type": null,
    "additional_profile_types": [],
    "need_status": "needed",
    "main_need": "professional",
    "primary_action": {
      "resource_id": "resource-pharmacist-demo",
      "provider_type": "pharmacist",
      "action_type": "pharmacist_consultation",
      "reason": "患者主动希望了解已有用药安排，不重新判定依从性。",
      "title": "查看咨询申请入口",
      "page_entry": "support/social",
      "requires_confirmation": true
    },
    "secondary_actions": [],
    "source_refs": [
      {
        "module": "C",
        "record_kind": "service_draft",
        "record_id": "service-draft-demo-001",
        "version": "1",
        "recorded_at": "2026-11-16T06:00:00Z"
      }
    ],
    "missing_items": [
      {
        "code": "profile_not_available",
        "message": "当前结构示例没有可用O画像；依据患者主动需求展示入口。",
        "field": "profile_id"
      }
    ],
    "generated_at": "2026-11-16T06:00:00Z",
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
    "code": "SUPPORT_CONTEXT_UNAVAILABLE",
    "message": "支持上下文暂不可用"
  }
}
```

### C02 当前资源目录

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/support-resources` |
| 用途/维护/页面 | 当前资源目录 / C3 / 支持服务/社会支持 |
| 身份/患者范围 | 本人或support:read；仅实际可见资源，真实未接入明确标 |
| 路径/查询/头/体 | path/body无；query channel O/N=support、cursor/limit；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<List<SupportResource>>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 SUPPORT_RESOURCE_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | support_free与reward_only分开；必要药学服务不查积分；availability按实际/模拟源，不伪造真实人员容量。 |
| 待实施验收 | 积分0仍可看必要专业支持；家庭权限不能自动扩成药师访问全库。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "resource_id": "resource-pharmacist-demo",
        "resource_version": "resource-demo-v1",
        "service_kind": "pharmacist_consultation",
        "name": "药学咨询申请（模拟）",
        "description": "仅演示申请和状态，不提供真实药师答复。",
        "provider": {
          "provider_id": "provider-pharmacist-demo",
          "provider_type": "pharmacist",
          "display_name": "演示药师资源（模拟，未接入真实人员）",
          "qualification_status": "not_verified",
          "is_simulated": true
        },
        "availability": "available",
        "access_mode": "support_free",
        "is_essential": true,
        "required_shared_categories": [
          "support_question"
        ],
        "optional_shared_categories": [
          "medication_plan"
        ],
        "peer_group_id": null,
        "is_simulated": true
      }
    ],
    "next_cursor": null
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
    "code": "SUPPORT_RESOURCE_UNAVAILABLE",
    "message": "资源目录暂不可用"
  }
}
```

### C03 资源主体/版本与共享要求

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/support-resources/{id}` |
| 用途/维护/页面 | 资源主体/版本与共享要求 / C3 / 服务详情/授权前说明 |
| 身份/患者范围 | 本人或support:read，按资源环境/范围 |
| 路径/查询/头/体 | path resource_id；query/body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<SupportResource>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读明确主体、用途和必要/可选共享类别；管理元数据不暴露凭据/真实隐私。 |
| 待实施验收 | 用户能核对接收方；未知资质不显示已验证药师。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "resource_id": "resource-pharmacist-demo",
    "resource_version": "resource-demo-v1",
    "service_kind": "pharmacist_consultation",
    "name": "药学咨询申请（模拟）",
    "description": "仅演示申请和状态，不提供真实药师答复。",
    "provider": {
      "provider_id": "provider-pharmacist-demo",
      "provider_type": "pharmacist",
      "display_name": "演示药师资源（模拟，未接入真实人员）",
      "qualification_status": "not_verified",
      "is_simulated": true
    },
    "availability": "available",
    "access_mode": "support_free",
    "is_essential": true,
    "required_shared_categories": [
      "support_question"
    ],
    "optional_shared_categories": [
      "medication_plan"
    ],
    "peer_group_id": null,
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
    "message": "资源不可访问或不存在"
  }
}
```

### C04 准备服务草稿

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/service-drafts` |
| 用途/维护/页面 | 准备服务草稿 / C3/C7 / 社会支持/准备问题 |
| 身份/患者范围 | 本人或明确services:prepare家人，仅准备无共享通知 |
| 路径/查询/头/体 | path patient_id；query无；JSON=ServiceDraftInput；网页写入头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 201；Envelope<ServiceDraft>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 422 INVALID_SERVICE_DRAFT；另继承公共错误 |
| 幂等/状态/事务/来源 | 保存preparing+draft_revision=1，验证同患者资源/建议，不创建Service，不通知第三方；未确认业务ID与正式service_id分开。 |
| 待实施验收 | 家人能准备不等于获准申请；未授权草稿不送给服务方。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "service_draft_id": "service-draft-demo-001",
    "patient_id": "p-demo-001",
    "draft_revision": 1,
    "resource_id": "resource-pharmacist-demo",
    "resource_version": "resource-demo-v1",
    "request_text": "我想了解如何读懂自己的用药安排（虚构咨询）。",
    "peer_group_id": null,
    "source_suggestion_id": null,
    "status": "preparing",
    "confirmation_ref_id": null,
    "sharing_scope_ref_id": null,
    "service_id": null,
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 1,
      "contract_version": "C-draft01",
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
    "code": "INVALID_SERVICE_DRAFT",
    "message": "资源、版本或来源建议不合法"
  }
}
```

### C05 草稿与确认准备状态

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/service-drafts/{id}` |
| 用途/维护/页面 | 草稿与确认准备状态 / C7 / 服务准备/刷新恢复 |
| 身份/患者范围 | 本人或services:prepare；不能越过源内容读取权限 |
| 路径/查询/头/体 | path service_draft_id；query/body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<ServiceDraft>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读当前内容修订/关联引用；查询O授权状态不能假称已正式提交；旧草稿仍与当前患者区分。 |
| 待实施验收 | 草稿不混进已申请列表；刷新不多建申请。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "service_draft_id": "service-draft-demo-001",
    "patient_id": "p-demo-001",
    "draft_revision": 1,
    "resource_id": "resource-pharmacist-demo",
    "resource_version": "resource-demo-v1",
    "request_text": "我想了解如何读懂自己的用药安排（虚构咨询）。",
    "peer_group_id": null,
    "source_suggestion_id": null,
    "status": "preparing",
    "confirmation_ref_id": null,
    "sharing_scope_ref_id": null,
    "service_id": null,
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 1,
      "contract_version": "C-draft01",
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
    "message": "草稿不可访问或不存在"
  }
}
```

### C06 修改准备内容

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `PUT /api/v1/service-drafts/{id}` |
| 用途/维护/页面 | 修改准备内容 / C7 / 服务准备/编辑 |
| 身份/患者范围 | 本人或services:prepare；submitted草稿不可原地改成新申请 |
| 路径/查询/头/体 | path service_draft_id；query无；JSON=ServiceDraftPutInput；网页写入头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<ServiceDraft>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 SERVICE_DRAFT_REVISION_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 完整新内容修订，旧内容保留；主体/用途/资源版本/共享类别改变令旧确认不适用；单改问题文字也须用户核对本次提交，但相同有效范围不重问同意。 |
| 待实施验收 | 旧标签页不能覆盖新内容；不能改患者/自填已授权标志。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "service_draft_id": "service-draft-demo-001",
    "patient_id": "p-demo-001",
    "draft_revision": 2,
    "resource_id": "resource-pharmacist-demo",
    "resource_version": "resource-demo-v1",
    "request_text": "我想了解如何读懂自己的用药安排（虚构咨询）。",
    "peer_group_id": null,
    "source_suggestion_id": null,
    "status": "preparing",
    "confirmation_ref_id": null,
    "sharing_scope_ref_id": null,
    "service_id": null,
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 2,
      "contract_version": "C-draft01",
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
    "code": "SERVICE_DRAFT_REVISION_CONFLICT",
    "message": "草稿已变化或已提交"
  }
}
```

### C07 唯一正式服务创建

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/services` |
| 用途/维护/页面 | 唯一正式服务创建 / C3/C7 / 社会支持/提交；B23同一后台服务 |
| 身份/患者范围 | 仅本人或经核验B代理，C/O确认有效；家人准备不等于可正式代申请 |
| 路径/查询/头/体 | path patient_id；query无；JSON=ServiceCreateInput；网页或可信B身份+幂等头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 201；Envelope<Service>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 SERVICE_CONFIRMATION_REQUIRED；另继承公共错误 |
| 幂等/状态/事务/来源 | 同库核验精确草稿修订、资源、确认和O授权→唯一submitted→链接草稿、去重及待派发；唯一键patient/draft/revision，不同幂等键也不多建；reward_only需可信兑换上下文。 |
| 待实施验收 | 未授权/未确认不申请不通知；正常C直申与B重试得到同一service_id。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "service_id": "service-demo-001",
    "patient_id": "p-demo-001",
    "service_draft_id": "service-draft-demo-001",
    "draft_revision": 1,
    "resource_id": "resource-pharmacist-demo",
    "resource_version": "resource-demo-v1",
    "service_name": "药学咨询申请（模拟）",
    "service_kind": "pharmacist_consultation",
    "provider": {
      "provider_id": "provider-pharmacist-demo",
      "provider_type": "pharmacist",
      "display_name": "演示药师资源（模拟，未接入真实人员）",
      "qualification_status": "not_verified",
      "is_simulated": true
    },
    "request_text": "我想了解如何读懂自己的用药安排（虚构咨询）。",
    "status": "submitted",
    "submitted_at": "2026-11-16T06:00:00Z",
    "started_at": null,
    "completed_at": null,
    "cancelled_at": null,
    "failed_at": null,
    "failure_reason": null,
    "cancellation_requested": false,
    "cancellation_reason": null,
    "confirmation_ref_id": "service-confirmation-demo-001",
    "sharing_scope_ref_id": "sharing-scope-demo-001",
    "source_suggestion_id": null,
    "source_referral_id": null,
    "redemption_id": null,
    "dispatch_task_id": "dispatch-task-demo-001",
    "result_summary": null,
    "provider_response": null,
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 1,
      "contract_version": "C-draft01",
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
    "code": "SERVICE_CONFIRMATION_REQUIRED",
    "message": "确认/共享/草稿版本无效，未创建申请"
  }
}
```

### C08 正式服务记录及筛选

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/services` |
| 用途/维护/页面 | 正式服务记录及筛选 / C7 / 我的/服务记录 |
| 身份/患者范围 | 本人或services:read，健康/答复内容按实际授权最小化 |
| 路径/查询/头/体 | path patient_id；query status O/N=不筛选、cursor/limit；body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<List<Service>>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 SERVICE_STORE_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 按submitted_at/service_id排序；只五状态正式服务，草稿/积分兑换不混入；真实依赖失败不假空列表。 |
| 待实施验收 | 首页最近状态与此事实一致；完成/取消/失败分别保留。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "service_id": "service-demo-001",
        "patient_id": "p-demo-001",
        "service_draft_id": "service-draft-demo-001",
        "draft_revision": 1,
        "resource_id": "resource-pharmacist-demo",
        "resource_version": "resource-demo-v1",
        "service_name": "药学咨询申请（模拟）",
        "service_kind": "pharmacist_consultation",
        "provider": {
          "provider_id": "provider-pharmacist-demo",
          "provider_type": "pharmacist",
          "display_name": "演示药师资源（模拟，未接入真实人员）",
          "qualification_status": "not_verified",
          "is_simulated": true
        },
        "request_text": "我想了解如何读懂自己的用药安排（虚构咨询）。",
        "status": "submitted",
        "submitted_at": "2026-11-16T06:00:00Z",
        "started_at": null,
        "completed_at": null,
        "cancelled_at": null,
        "failed_at": null,
        "failure_reason": null,
        "cancellation_requested": false,
        "cancellation_reason": null,
        "confirmation_ref_id": "service-confirmation-demo-001",
        "sharing_scope_ref_id": "sharing-scope-demo-001",
        "source_suggestion_id": null,
        "source_referral_id": null,
        "redemption_id": null,
        "dispatch_task_id": "dispatch-task-demo-001",
        "result_summary": null,
        "provider_response": null,
        "meta": {
          "created_at": "2026-11-16T06:00:00Z",
          "updated_at": "2026-11-16T06:00:00Z",
          "revision": 1,
          "contract_version": "C-draft01",
          "is_simulated": true
        }
      }
    ],
    "next_cursor": null
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
    "code": "SERVICE_STORE_UNAVAILABLE",
    "message": "服务记录暂不可读取"
  }
}
```

### C09 服务详情及执行/答复来源

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/services/{id}` |
| 用途/维护/页面 | 服务详情及执行/答复来源 / C7 / 服务详情 |
| 身份/患者范围 | 本人或services:read；服务主体仅经可信服务适配读取获准范围 |
| 路径/查询/头/体 | path service_id；query/body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<Service>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读C权威状态/取消请求/结果和答复来源；mock_example不能显示真实药师意见；不据AI建议改status。 |
| 待实施验收 | 未接真实药师标模拟；没有评价不显示干预有效。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "service_id": "service-demo-001",
    "patient_id": "p-demo-001",
    "service_draft_id": "service-draft-demo-001",
    "draft_revision": 1,
    "resource_id": "resource-pharmacist-demo",
    "resource_version": "resource-demo-v1",
    "service_name": "药学咨询申请（模拟）",
    "service_kind": "pharmacist_consultation",
    "provider": {
      "provider_id": "provider-pharmacist-demo",
      "provider_type": "pharmacist",
      "display_name": "演示药师资源（模拟，未接入真实人员）",
      "qualification_status": "not_verified",
      "is_simulated": true
    },
    "request_text": "我想了解如何读懂自己的用药安排（虚构咨询）。",
    "status": "submitted",
    "submitted_at": "2026-11-16T06:00:00Z",
    "started_at": null,
    "completed_at": null,
    "cancelled_at": null,
    "failed_at": null,
    "failure_reason": null,
    "cancellation_requested": false,
    "cancellation_reason": null,
    "confirmation_ref_id": "service-confirmation-demo-001",
    "sharing_scope_ref_id": "sharing-scope-demo-001",
    "source_suggestion_id": null,
    "source_referral_id": null,
    "redemption_id": null,
    "dispatch_task_id": "dispatch-task-demo-001",
    "result_summary": null,
    "provider_response": null,
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 1,
      "contract_version": "C-draft01",
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
    "message": "服务不可访问或不存在"
  }
}
```

### C10 取消或登记取消请求

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/services/{id}/cancel` |
| 用途/维护/页面 | 取消或登记取消请求 / C7 / 我的/服务详情 |
| 身份/患者范围 | 仅本人，当前submitted/in_progress且修订匹配 |
| 路径/查询/头/体 | path service_id；query无；JSON=ServiceCancelInput；网页写入头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<Service>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 SERVICE_TERMINAL；另继承公共错误 |
| 幂等/状态/事务/来源 | demo可合法cancelled；真实在途先cancellation_requested，可靠结果确认后再改终态，不伪称服务方已停。取消事务审计/共享重检/待派发失效，终态不恢复。 |
| 待实施验收 | 完成后不能取消回退；并发回执按版本判定；重复取消不多操作。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "service_id": "service-demo-001",
    "patient_id": "p-demo-001",
    "service_draft_id": "service-draft-demo-001",
    "draft_revision": 1,
    "resource_id": "resource-pharmacist-demo",
    "resource_version": "resource-demo-v1",
    "service_name": "药学咨询申请（模拟）",
    "service_kind": "pharmacist_consultation",
    "provider": {
      "provider_id": "provider-pharmacist-demo",
      "provider_type": "pharmacist",
      "display_name": "演示药师资源（模拟，未接入真实人员）",
      "qualification_status": "not_verified",
      "is_simulated": true
    },
    "request_text": "我想了解如何读懂自己的用药安排（虚构咨询）。",
    "status": "cancelled",
    "submitted_at": "2026-11-16T06:00:00Z",
    "started_at": null,
    "completed_at": null,
    "cancelled_at": "2026-11-16T06:00:00Z",
    "failed_at": null,
    "failure_reason": null,
    "cancellation_requested": true,
    "cancellation_reason": "虚构患者主动取消",
    "confirmation_ref_id": "service-confirmation-demo-001",
    "sharing_scope_ref_id": "sharing-scope-demo-001",
    "source_suggestion_id": null,
    "source_referral_id": null,
    "redemption_id": null,
    "dispatch_task_id": "dispatch-task-demo-001",
    "result_summary": null,
    "provider_response": null,
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 2,
      "contract_version": "C-draft01",
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
    "code": "SERVICE_TERMINAL",
    "message": "服务已终止或修订变化，不能回退"
  }
}
```

### C11 可信服务执行回执

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/integrations/service-receipts` |
| 用途/维护/页面 | 可信服务执行回执 / C7 / 服务方适配→C |
| 身份/患者范围 | 独立主体身份/资格，绑定service/resource/provider/授权 |
| 路径/查询/头/体 | path/query无；JSON=ServiceReceiptInput；服务认证/签名适配+Idempotency-Key；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<OperationAck>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 SERVICE_RECEIPT_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 来源去重+状态/结果/审计同事务，submitted→in_progress→completed，前两者可cancelled/failed；非法回退/晚到不应用。已链接兑换的C服务状态驱动同一交付事实，不生成第二份服务完成。 |
| 待实施验收 | completed须结果，failed须原因；无资质不当真实药师；最小Ack不回传余额。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "operation_id": "service-receipt-demo-001",
    "resource_id": "service-demo-001",
    "applied": true,
    "ignore_reason": null,
    "received_at": "2026-11-16T06:00:00Z",
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
    "code": "SERVICE_RECEIPT_CONFLICT",
    "message": "来源事件号、版本或服务关联冲突"
  }
}
```

### C12 模拟合法状态变化

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/demo/services/{id}/transitions` |
| 用途/维护/页面 | 模拟合法状态变化 / C7 / 独立演示控制台 |
| 身份/患者范围 | 仅demo:manage、模拟资源/患者/服务；非真实服务方接口 |
| 路径/查询/头/体 | path service_id；query无；JSON=DemoTransitionInput；管理Cookie/CSRF/Idempotency-Key；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<Service>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 ILLEGAL_SERVICE_TRANSITION；另继承公共错误 |
| 幂等/状态/事务/来源 | 调用同一C状态机并记录模拟来源，不任意改状态；模拟完成也需结果说明，评价另外保存。 |
| 待实施验收 | submitted不能直接跳completed；完成/取消/失败不回处理中。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "service_id": "service-demo-001",
    "patient_id": "p-demo-001",
    "service_draft_id": "service-draft-demo-001",
    "draft_revision": 1,
    "resource_id": "resource-pharmacist-demo",
    "resource_version": "resource-demo-v1",
    "service_name": "药学咨询申请（模拟）",
    "service_kind": "pharmacist_consultation",
    "provider": {
      "provider_id": "provider-pharmacist-demo",
      "provider_type": "pharmacist",
      "display_name": "演示药师资源（模拟，未接入真实人员）",
      "qualification_status": "not_verified",
      "is_simulated": true
    },
    "request_text": "我想了解如何读懂自己的用药安排（虚构咨询）。",
    "status": "in_progress",
    "submitted_at": "2026-11-16T06:00:00Z",
    "started_at": "2026-11-16T06:00:00Z",
    "completed_at": null,
    "cancelled_at": null,
    "failed_at": null,
    "failure_reason": null,
    "cancellation_requested": false,
    "cancellation_reason": null,
    "confirmation_ref_id": "service-confirmation-demo-001",
    "sharing_scope_ref_id": "sharing-scope-demo-001",
    "source_suggestion_id": null,
    "source_referral_id": null,
    "redemption_id": null,
    "dispatch_task_id": "dispatch-task-demo-001",
    "result_summary": null,
    "provider_response": null,
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 2,
      "contract_version": "C-draft01",
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
    "code": "ILLEGAL_SERVICE_TRANSITION",
    "message": "不允许该状态转换或终态回退"
  }
}
```

### C13 患者三维反馈或不参与

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/services/{id}/feedback` |
| 用途/维护/页面 | 患者三维反馈或不参与 / C6 / 服务完成/自愿反馈 |
| 身份/患者范围 | 仅本人service-feedback:write；completed后收集，取消/失败可自愿留说明 |
| 路径/查询/头/体 | path service_id；query无；JSON=ServiceFeedbackInput；网页写入头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 201；Envelope<ServiceFeedback>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 FEEDBACK_REVISION_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 首次0，新反馈/更正追加版本与前驱，不改旧意见；provided至少一维有内容，declined/unable保留原因；不修改服务完成或画像/模型。 |
| 待实施验收 | 不反馈不当无效/不配合；反馈与真实履约分开。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "feedback_id": "service-feedback-demo-001",
    "patient_id": "p-demo-001",
    "service_id": "service-demo-001",
    "feedback_revision": 1,
    "supersedes_feedback_id": null,
    "participation": "provided",
    "support_needs": "仍有一些安排上的疑问（虚构反馈）",
    "support_acceptance": "愿意继续了解可选帮助（虚构反馈）",
    "intervention_effectiveness": "本例仅展示模拟反馈，不代表真实干预效果。",
    "willing_to_continue": true,
    "missing_reason": null,
    "recorded_at": "2026-11-16T06:00:00Z",
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 1,
      "contract_version": "C-draft01",
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
    "code": "FEEDBACK_REVISION_CONFLICT",
    "message": "反馈修订或服务状态不适合本次提交"
  }
}
```

### C14 反馈历史与更正来源

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/services/{id}/feedback` |
| 用途/维护/页面 | 反馈历史与更正来源 / C6 / 我的/服务评价历史 |
| 身份/患者范围 | 本人或services:read且具相应反馈访问范围 |
| 路径/查询/头/体 | path service_id；query cursor/limit；body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<List<ServiceFeedback>>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | feedback_revision顺序，保留原意见/来源；资料不足不造评分；共享范围不包含的维度不对第三方返回。 |
| 待实施验收 | 更正不覆盖原反馈；不能用service_id猜他人主观意见。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "feedback_id": "service-feedback-demo-001",
        "patient_id": "p-demo-001",
        "service_id": "service-demo-001",
        "feedback_revision": 1,
        "supersedes_feedback_id": null,
        "participation": "provided",
        "support_needs": "仍有一些安排上的疑问（虚构反馈）",
        "support_acceptance": "愿意继续了解可选帮助（虚构反馈）",
        "intervention_effectiveness": "本例仅展示模拟反馈，不代表真实干预效果。",
        "willing_to_continue": true,
        "missing_reason": null,
        "recorded_at": "2026-11-16T06:00:00Z",
        "meta": {
          "created_at": "2026-11-16T06:00:00Z",
          "updated_at": "2026-11-16T06:00:00Z",
          "revision": 1,
          "contract_version": "C-draft01",
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
    "message": "反馈不可访问或不存在"
  }
}
```

### C15 A/B最小支持反馈

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/support-feedback` |
| 用途/维护/页面 | A/B最小支持反馈 / C6/A5 / A摘要/B下一轮支持 |
| 身份/患者范围 | 可信A/B服务或本人feedback:read，底层C授权同时校验 |
| 路径/查询/头/体 | path patient_id；query window_start/end:DateTime R/N（[start,end)，≤31天）、cursor/limit；body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<FeedbackSource>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 SUPPORT_FEEDBACK_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 复用A FeedbackSource/Ref，服务状态与三维描述独立；没有反馈null+原因，不写0分/改善；未接入、故障、受限分别说明。 |
| 待实施验收 | 仅submitted不显示完成/有效；C不改O画像或训练模型。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "source_module": "C",
    "availability": "available",
    "records": [
      {
        "record_kind": "service",
        "record_id": "service-demo-001",
        "source_version": "3",
        "recorded_at": "2026-11-16T06:00:00Z",
        "service_status": "completed",
        "support_needs": "仍有一些安排上的疑问（虚构反馈）",
        "support_acceptance": "愿意继续了解可选帮助（虚构反馈）",
        "intervention_effectiveness": "本例仅展示模拟反馈，不代表真实干预效果。",
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
    "code": "SUPPORT_FEEDBACK_UNAVAILABLE",
    "message": "C反馈来源暂不可用"
  }
}
```

### C16 匿名同辈目录

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/peer-groups` |
| 用途/维护/页面 | 匿名同辈目录 / C4 / 社会支持/同辈小组 |
| 身份/患者范围 | 本人或peer:read，服务范围允许；不列其他患者身份 |
| 路径/查询/头/体 | path/body无；query group_id O/N、cursor/limit；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<List<PeerGroup>>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 PEER_GROUPS_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 只组级标签/主题和模拟可用性，匹配参考O既有标签/自愿需求，不重新分类；不暴露成员疾病/药品。 |
| 待实施验收 | 没有真实运营仅演示；不按积分强制参与。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "group_id": "group-demo-001",
        "resource_id": "resource-peer-demo",
        "title": "同伴交流微小组（虚构）",
        "description": "模拟主题交流，不替代专业咨询。",
        "matching_tags": [
          "演示病种甲",
          "演示用药阶段甲",
          "规律作息"
        ],
        "moderator_label": "演示志愿者（模拟）",
        "availability": "available",
        "is_simulated": true
      }
    ],
    "next_cursor": null
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
    "code": "PEER_GROUPS_UNAVAILABLE",
    "message": "小组目录暂不可用"
  }
}
```

### C17 小组介绍

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/peer-groups/{id}` |
| 用途/维护/页面 | 小组介绍 / C4 / 小组详情/自愿加入 |
| 身份/患者范围 | 本人或peer:read，按资源/环境访问 |
| 路径/查询/头/体 | path group_id；query/body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<PeerGroup>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读主题/规则/志愿者引导标签，不承诺绝对匿名或专业医疗服务。 |
| 待实施验收 | 患者可暂不参与；不因拒绝自动贴心理标签。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "group_id": "group-demo-001",
    "resource_id": "resource-peer-demo",
    "title": "同伴交流微小组（虚构）",
    "description": "模拟主题交流，不替代专业咨询。",
    "matching_tags": [
      "演示病种甲",
      "演示用药阶段甲",
      "规律作息"
    ],
    "moderator_label": "演示志愿者（模拟）",
    "availability": "available",
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
    "message": "小组不可访问或不存在"
  }
}
```

### C18 复用C申请建立入组准备

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/peer-groups/{id}/memberships` |
| 用途/维护/页面 | 复用C申请建立入组准备 / C4/C7 / 小组/申请加入 |
| 身份/患者范围 | 仅本人peer:participate并有C确认/O范围，目标peer_support资源一致 |
| 路径/查询/头/体 | path group_id；query无；JSON=MembershipCreateInput；网页写入头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 201；Envelope<Membership>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 PEER_JOIN_CONFIRMATION_REQUIRED；另继承公共错误 |
| 幂等/状态/事务/来源 | 同库复用C07唯一服务+本人pending成员资格，实际受理才active；同患者/组已有pending或active不重复入组申请；昵称随机，非真实姓名派生。 |
| 待实施验收 | 确认前不实际入组/发帖；B或直申不建第二条服务。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "membership_id": "membership-demo-001",
    "patient_id": "p-demo-001",
    "group_id": "group-demo-001",
    "service_id": "service-peer-demo-001",
    "alias": "晨光伙伴7",
    "status": "pending",
    "joined_at": "2026-11-16T06:00:00Z",
    "activated_at": null,
    "left_at": null,
    "leave_reason": null,
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 1,
      "contract_version": "C-draft01",
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
    "code": "PEER_JOIN_CONFIRMATION_REQUIRED",
    "message": "入组确认、共享或服务草稿无效"
  }
}
```

### C19 自主退出小组

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/memberships/{id}/leave` |
| 用途/维护/页面 | 自主退出小组 / C4 / 小组/退出 |
| 身份/患者范围 | 仅本人，pending/active自己的成员资格 |
| 路径/查询/头/体 | path membership_id；query无；JSON=MembershipLeaveInput；网页写入头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<Membership>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 MEMBERSHIP_REVISION_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | pending/active→left，立刻停止后续读/发帖权限；正式服务终态不回退，未完成关联按取消请求流程处理；不删历史/他人帖子。 |
| 待实施验收 | 退出不扣已有积分；重试不多退出事件；真实身份不泄露。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "membership_id": "membership-demo-001",
    "patient_id": "p-demo-001",
    "group_id": "group-demo-001",
    "service_id": "service-peer-demo-001",
    "alias": "晨光伙伴7",
    "status": "left",
    "joined_at": "2026-11-16T06:00:00Z",
    "activated_at": null,
    "left_at": "2026-11-16T06:00:00Z",
    "leave_reason": null,
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 2,
      "contract_version": "C-draft01",
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
    "code": "MEMBERSHIP_REVISION_CONFLICT",
    "message": "成员资格已变化"
  }
}
```

### C20 匿名文字交流与审核队列

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/peer-groups/{id}/posts` |
| 用途/维护/页面 | 匿名文字交流与审核队列 / C4 / 小组交流/受控审核 |
| 身份/患者范围 | 活跃成员仅visible；本人可见自己pending；审核者限定本组 |
| 路径/查询/头/体 | path group_id；query cursor/limit、include_pending O/N=false（仅审核身份）；body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<List<PeerPost>>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 403 PEER_MEMBERSHIP_REQUIRED；另继承公共错误 |
| 幂等/状态/事务/来源 | 只匿名PeerPost视图，不含patient/account/membership ID；按created_at/post_id排序；安全文本，退出后不凭旧游标继续访问。 |
| 待实施验收 | 未审核帖子不向其他成员公开；组外/退出者不能遍历。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "post_id": "post-demo-001",
        "group_id": "group-demo-001",
        "author_alias": "晨光伙伴7",
        "content": "我想分享一个整理日程的小习惯（虚构交流）。",
        "moderation_status": "visible",
        "created_at": "2026-11-16T06:00:00Z",
        "moderated_at": "2026-11-16T06:00:00Z",
        "revision": 1,
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
    "code": "PEER_MEMBERSHIP_REQUIRED",
    "message": "需要有效成员资格或审核范围"
  }
}
```

### C21 提交短文字待审核

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/peer-groups/{id}/posts` |
| 用途/维护/页面 | 提交短文字待审核 / C4 / 小组交流/发布 |
| 身份/患者范围 | 仅本人active成员peer:participate，明确发布本段文本 |
| 路径/查询/头/体 | path group_id；query无；JSON=PeerPostInput；网页写入头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 201；Envelope<PeerPost>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 422 INVALID_PEER_POST；另继承公共错误 |
| 幂等/状态/事务/来源 | 本人主动提交短纯文本，先pending，不能自填审核状态/真实他人身份/附件或外链；审核后才可见/计参与，不自动带入病历/对话。 |
| 待实施验收 | 重复client_post_id只一帖；自动模型/家人不能冒充本人参与。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "post_id": "post-demo-001",
    "group_id": "group-demo-001",
    "author_alias": "晨光伙伴7",
    "content": "我想分享一个整理日程的小习惯（虚构交流）。",
    "moderation_status": "pending",
    "created_at": "2026-11-16T06:00:00Z",
    "moderated_at": null,
    "revision": 1,
    "is_simulated": true
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
    "code": "INVALID_PEER_POST",
    "message": "文字、身份隐私或发布条件不合法"
  }
}
```

### C22 当前可用积分

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/points` |
| 用途/维护/页面 | 当前可用积分 / C4 / 积分权益/首页 |
| 身份/患者范围 | 本人或points:read，账户属该患者 |
| 路径/查询/头/体 | path patient_id；query/body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<PointsAccount>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 POINTS_ACCOUNT_NOT_READY；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读持久账户及版本，不GET建账/造余额；余额由不可变流水和原子事务维护，LLM不能改。 |
| 待实施验收 | 余额0仍可申请必要专业支持；页面刷新与后端一致。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "points_account_id": "points-account-demo-001",
    "patient_id": "p-demo-001",
    "balance": 30,
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 1,
      "contract_version": "C-draft01",
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
    "code": "POINTS_ACCOUNT_NOT_READY",
    "message": "账户尚未显式初始化或存储不可用"
  }
}
```

### C23 正向奖励规则版本

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/points/rules` |
| 用途/维护/页面 | 正向奖励规则版本 / C4 / 积分权益/规则说明 |
| 身份/患者范围 | 已登录可读启用演示规则，真实未启用须如实说明 |
| 路径/查询/头/体 | path/body无；query rules_version O/N=当前启用；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<PointsRules>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 POINTS_RULES_NOT_ENABLED；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读版本、数值/周期和实际资格；不把原Prompt建议自动当既定，本批需确认后未来启用；不按LLM印象给分。 |
| 待实施验收 | 说明记录参与非真实吞服奖励；漏服/不适/暂停不扣已有积分。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "rules_version": "points-demo-draft01",
    "timezone_source": "patient",
    "week_start_day": 1,
    "rules": [
      {
        "rule_code": "daily_record",
        "points": 2,
        "period": "day",
        "max_awards_per_period": 1,
        "eligibility_description": "当日本人或获准家人的一条有效手动记录，不要求必须已服；自动设备不单独奖励。"
      },
      {
        "rule_code": "five_day_block",
        "points": 5,
        "period": "five_day_block",
        "max_awards_per_period": 1,
        "eligibility_description": "不重叠连续5个合格日，每日期最多分配一次。"
      },
      {
        "rule_code": "weekly_review",
        "points": 3,
        "period": "week",
        "max_awards_per_period": 1,
        "eligibility_description": "本人明确完成当前本地ISO周的管理回顾。"
      },
      {
        "rule_code": "peer_participation",
        "points": 2,
        "period": "week",
        "max_awards_per_period": 1,
        "eligibility_description": "本人本周实际可见文字交流参与，非仅收到推荐或自动回复。"
      }
    ],
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
    "code": "POINTS_RULES_NOT_ENABLED",
    "message": "规则版本未确认启用或不存在"
  }
}
```

### C24 不可变积分流水

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/points-ledger` |
| 用途/维护/页面 | 不可变积分流水 / C4 / 积分权益/获取消费历史 |
| 身份/患者范围 | 本人或points:read |
| 路径/查询/头/体 | path patient_id；query window_start/end:DateTime R/N（[start,end)，≤31天）、cursor/limit；body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<List<LedgerEntry>>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 POINTS_LEDGER_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 按created_at/ledger_id顺序，来源/规则/业务键/兑换和退分引用可追溯；不覆盖旧流水或伪装真实发奖。 |
| 待实施验收 | 十五条隔日+2示例余额30；扣减/退款不是服药惩罚。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "ledger_id": "ledger-award-demo-01",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 2,
        "business_key": "p-demo-001:daily_record:2026-10-16",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-1",
            "version": "1",
            "recorded_at": "2026-10-16T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-10-16T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-02",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 4,
        "business_key": "p-demo-001:daily_record:2026-10-18",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-2",
            "version": "1",
            "recorded_at": "2026-10-18T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-10-18T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-03",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 6,
        "business_key": "p-demo-001:daily_record:2026-10-20",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-3",
            "version": "1",
            "recorded_at": "2026-10-20T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-10-20T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-04",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 8,
        "business_key": "p-demo-001:daily_record:2026-10-22",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-4",
            "version": "1",
            "recorded_at": "2026-10-22T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-10-22T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-05",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 10,
        "business_key": "p-demo-001:daily_record:2026-10-24",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-5",
            "version": "1",
            "recorded_at": "2026-10-24T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-10-24T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-06",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 12,
        "business_key": "p-demo-001:daily_record:2026-10-26",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-6",
            "version": "1",
            "recorded_at": "2026-10-26T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-10-26T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-07",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 14,
        "business_key": "p-demo-001:daily_record:2026-10-28",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-7",
            "version": "1",
            "recorded_at": "2026-10-28T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-10-28T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-08",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 16,
        "business_key": "p-demo-001:daily_record:2026-10-30",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-8",
            "version": "1",
            "recorded_at": "2026-10-30T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-10-30T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-09",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 18,
        "business_key": "p-demo-001:daily_record:2026-11-01",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-9",
            "version": "1",
            "recorded_at": "2026-11-01T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-11-01T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-10",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 20,
        "business_key": "p-demo-001:daily_record:2026-11-03",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-10",
            "version": "1",
            "recorded_at": "2026-11-03T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-11-03T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-11",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 22,
        "business_key": "p-demo-001:daily_record:2026-11-05",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-11",
            "version": "1",
            "recorded_at": "2026-11-05T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-11-05T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-12",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 24,
        "business_key": "p-demo-001:daily_record:2026-11-07",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-12",
            "version": "1",
            "recorded_at": "2026-11-07T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-11-07T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-13",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 26,
        "business_key": "p-demo-001:daily_record:2026-11-09",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-13",
            "version": "1",
            "recorded_at": "2026-11-09T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-11-09T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-14",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 28,
        "business_key": "p-demo-001:daily_record:2026-11-11",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-14",
            "version": "1",
            "recorded_at": "2026-11-11T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-11-11T04:00:00Z",
        "is_simulated": true
      },
      {
        "ledger_id": "ledger-award-demo-15",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 30,
        "business_key": "p-demo-001:daily_record:2026-11-13",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-15",
            "version": "1",
            "recorded_at": "2026-11-13T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-11-13T04:00:00Z",
        "is_simulated": true
      }
    ],
    "next_cursor": null
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
    "code": "POINTS_LEDGER_UNAVAILABLE",
    "message": "积分流水暂不可用"
  }
}
```

### C25 程序按有效来源核奖

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/internal/points/reconcile` |
| 用途/维护/页面 | 程序按有效来源核奖 / C4，A供证据 / 可信业务事件/受控演示 |
| 身份/患者范围 | 独立C程序身份或明确demo管理范围，患者/LLM不能直接调金额 |
| 路径/查询/头/体 | path/query无；JSON=PointsReconcileInput；可信身份或管理Cookie/CSRF+Idempotency-Key；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<PointsReconcileResult>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 POINTS_RECONCILE_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 从A当前有效手动记录/C周回顾/可见本人参与读取资格；同业务期不因规则版本重发；五日分配每日期唯一；账户/奖励/来源/分配/幂等同事务。后更正不自动追回已有奖励。 |
| 待实施验收 | 重复/并发只一奖；未服/延迟/未知参与不算已服；自动设备不发参与奖。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "patient_id": "p-demo-001",
    "window_start": "2026-11-15T00:00:00+08:00",
    "window_end": "2026-11-16T00:00:00+08:00",
    "account": {
      "points_account_id": "points-account-demo-001",
      "patient_id": "p-demo-001",
      "balance": 32,
      "meta": {
        "created_at": "2026-11-16T06:00:00Z",
        "updated_at": "2026-11-16T06:00:00Z",
        "revision": 2,
        "contract_version": "C-draft01",
        "is_simulated": true
      }
    },
    "new_entries": [
      {
        "ledger_id": "ledger-award-demo-16",
        "points_account_id": "points-account-demo-001",
        "patient_id": "p-demo-001",
        "entry_kind": "award",
        "delta": 2,
        "balance_after": 32,
        "business_key": "p-demo-001:daily_record:2026-11-15",
        "rule_code": "daily_record",
        "rules_version": "points-demo-draft01",
        "source_refs": [
          {
            "module": "A",
            "record_kind": "event",
            "record_id": "manual-event-demo-16",
            "version": "1",
            "recorded_at": "2026-11-15T04:00:00Z"
          }
        ],
        "redemption_id": null,
        "reverses_ledger_id": null,
        "created_at": "2026-11-16T06:00:00Z",
        "is_simulated": true
      }
    ],
    "new_allocations": [],
    "skipped_keys": [],
    "source_issues": [],
    "rules_version": "points-demo-draft01"
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
    "code": "POINTS_RECONCILE_CONFLICT",
    "message": "规则、来源或账户版本不适合本次核算"
  }
}
```

### C26 自愿额外权益目录

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/rewards` |
| 用途/维护/页面 | 自愿额外权益目录 / C4 / 积分权益 |
| 身份/患者范围 | 本人或points:read，权益入口不因支持需求隐藏 |
| 路径/查询/头/体 | path/body无；query cursor/limit；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<List<Reward>>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 REWARD_CATALOG_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 只列自愿额外权益和实际/模拟交付边界；必要医疗不放兑换门槛，资源unknown不假装库存充足。 |
| 待实施验收 | 建议成本30/40/50/60/80需C确认；社会支持与权益独立可见。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "reward_id": "reward-reminder-demo",
        "reward_version": "reward-demo-v1",
        "name": "专属提醒定制（模拟）",
        "description": "额外提醒外观与文字定制，不改变医嘱。",
        "points_cost": 30,
        "kind": "digital_content",
        "availability": "available",
        "resource_id": null,
        "is_essential": false,
        "is_simulated": true
      },
      {
        "reward_id": "reward-card-demo",
        "reward_version": "reward-demo-v1",
        "name": "个人用药管理卡（模拟）",
        "description": "按已确认资料整理管理记录。",
        "points_cost": 40,
        "kind": "digital_content",
        "availability": "available",
        "resource_id": null,
        "is_essential": false,
        "is_simulated": true
      },
      {
        "reward_id": "reward-routine-demo",
        "reward_version": "reward-demo-v1",
        "name": "个性化作息清单（模拟）",
        "description": "用户作息管理清单，不调整服药时间。",
        "points_cost": 50,
        "kind": "digital_content",
        "availability": "available",
        "resource_id": null,
        "is_essential": false,
        "is_simulated": true
      },
      {
        "reward_id": "reward-companionship-demo",
        "reward_version": "reward-demo-v1",
        "name": "额外陪伴预约（模拟）",
        "description": "自愿额外权益，不替代按需要获得的基本支持。",
        "points_cost": 60,
        "kind": "service_appointment",
        "availability": "available",
        "resource_id": "resource-extra-companion-demo",
        "is_essential": false,
        "is_simulated": true
      },
      {
        "reward_id": "reward-toolkit-demo",
        "reward_version": "reward-demo-v1",
        "name": "健康管理工具包（模拟）",
        "description": "打卡表和整理清单等数字内容。",
        "points_cost": 80,
        "kind": "digital_content",
        "availability": "available",
        "resource_id": null,
        "is_essential": false,
        "is_simulated": true
      }
    ],
    "next_cursor": null
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
    "code": "REWARD_CATALOG_UNAVAILABLE",
    "message": "权益目录暂不可用"
  }
}
```

### C27 权益成本/版本/交付说明

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/rewards/{id}` |
| 用途/维护/页面 | 权益成本/版本/交付说明 / C4 / 权益详情 |
| 身份/患者范围 | 本人或points:read，按环境/可见性 |
| 路径/查询/头/体 | path reward_id；query/body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<Reward>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 核对明确版本与价格，人员服务需C准备/共享确认；数字管理内容不调整医嘱。 |
| 待实施验收 | 价格变化需重核对，不能用旧页面悄悄按新成本扣分。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "reward_id": "reward-reminder-demo",
    "reward_version": "reward-demo-v1",
    "name": "专属提醒定制（模拟）",
    "description": "额外提醒外观与文字定制，不改变医嘱。",
    "points_cost": 30,
    "kind": "digital_content",
    "availability": "available",
    "resource_id": null,
    "is_essential": false,
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
    "message": "权益不可访问或不存在"
  }
}
```

### C28 自愿兑换原子扣分与准备交付

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/redemptions` |
| 用途/维护/页面 | 自愿兑换原子扣分与准备交付 / C4/C7 / 积分权益/确认兑换 |
| 身份/患者范围 | 仅本人rewards:redeem，余额/版本/资源及必要确认有效 |
| 路径/查询/头/体 | path patient_id；query无；JSON=RedemptionInput；网页写入头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 201；Envelope<Redemption>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 INSUFFICIENT_POINTS；另继承公共错误 |
| 幂等/状态/事务/来源 | 事务校验→单次扣减流水+兑换+交付/必要C服务+待执行；失败无半扣/负余额。数字无第三方共享不多索确认，人员预约复用相同有效服务/共享同意。 |
| 待实施验收 | 重复键不多扣；两个并发兑换不能负余额；失败回滚不丢已有积分。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "redemption_id": "redemption-demo-001",
    "patient_id": "p-demo-001",
    "reward_id": "reward-reminder-demo",
    "reward_version": "reward-demo-v1",
    "reward_name": "专属提醒定制（模拟）",
    "points_spent": 30,
    "status": "submitted",
    "points_status": "debited",
    "debit_ledger_id": "ledger-debit-demo-001",
    "refund_ledger_id": null,
    "balance_after_debit": 0,
    "fulfillment_id": "fulfillment-demo-001",
    "service_id": null,
    "redeemed_at": "2026-11-16T06:00:00Z",
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 1,
      "contract_version": "C-draft01",
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
    "code": "INSUFFICIENT_POINTS",
    "message": "积分不足、版本变化或资源未就绪"
  }
}
```

### C29 独立兑换记录

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/redemptions` |
| 用途/维护/页面 | 独立兑换记录 / C4 / 积分权益/兑换历史 |
| 身份/患者范围 | 本人或points:read，记录属患者 |
| 路径/查询/头/体 | path patient_id；query cursor/limit；body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<List<Redemption>>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 REDEMPTION_STORE_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 按redeemed_at/redemption_id排序；points_status与交付status分开，人员service_id仅关联不混入该列表作为另一申请。 |
| 待实施验收 | 历史cost快照不随目录更新；查询重启可恢复是未来验收，当前未实现。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "redemption_id": "redemption-demo-001",
        "patient_id": "p-demo-001",
        "reward_id": "reward-reminder-demo",
        "reward_version": "reward-demo-v1",
        "reward_name": "专属提醒定制（模拟）",
        "points_spent": 30,
        "status": "submitted",
        "points_status": "debited",
        "debit_ledger_id": "ledger-debit-demo-001",
        "refund_ledger_id": null,
        "balance_after_debit": 0,
        "fulfillment_id": "fulfillment-demo-001",
        "service_id": null,
        "redeemed_at": "2026-11-16T06:00:00Z",
        "meta": {
          "created_at": "2026-11-16T06:00:00Z",
          "updated_at": "2026-11-16T06:00:00Z",
          "revision": 1,
          "contract_version": "C-draft01",
          "is_simulated": true
        }
      }
    ],
    "next_cursor": null
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
    "code": "REDEMPTION_STORE_UNAVAILABLE",
    "message": "兑换记录暂不可用"
  }
}
```

### C30 兑换与点数/服务关联

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/redemptions/{id}` |
| 用途/维护/页面 | 兑换与点数/服务关联 / C4 / 兑换详情 |
| 身份/患者范围 | 本人或points:read，服务正文另需C服务权限 |
| 路径/查询/头/体 | path redemption_id；query/body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<Redemption>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读原扣减/退分和交付引用；balance_after_debit为当时快照，不冒充永远当前余额。 |
| 待实施验收 | 服务完成与评价分开；结果未知不显示已交付/已退分。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "redemption_id": "redemption-demo-001",
    "patient_id": "p-demo-001",
    "reward_id": "reward-reminder-demo",
    "reward_version": "reward-demo-v1",
    "reward_name": "专属提醒定制（模拟）",
    "points_spent": 30,
    "status": "submitted",
    "points_status": "debited",
    "debit_ledger_id": "ledger-debit-demo-001",
    "refund_ledger_id": null,
    "balance_after_debit": 0,
    "fulfillment_id": "fulfillment-demo-001",
    "service_id": null,
    "redeemed_at": "2026-11-16T06:00:00Z",
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 1,
      "contract_version": "C-draft01",
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
    "message": "兑换不可访问或不存在"
  }
}
```

### C31 可信交付/失败回执

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/integrations/fulfillment-receipts` |
| 用途/维护/页面 | 可信交付/失败回执 / C4 / 交付适配→C |
| 身份/患者范围 | 独立交付身份，精确绑定fulfillment/兑换，服务型须C原服务事实 |
| 路径/查询/头/体 | path/query无；JSON=FulfillmentReceiptInput；可信认证+Idempotency-Key；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<OperationAck>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 FULFILLMENT_RECEIPT_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 来源去重/交付状态/必要一次退分与账本同事务；明确未交付failed/cancelled才全退一次；unknown先核查。服务型完成必须C原service已完成，不独造完成。最小Ack不泄露余额。 |
| 待实施验收 | 重复失败只退一次；已完成不退回失败；退款后晚成功不自动复活/二次发货。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "operation_id": "fulfillment-receipt-demo-001",
    "resource_id": "fulfillment-demo-001",
    "applied": true,
    "ignore_reason": null,
    "received_at": "2026-11-16T06:00:00Z",
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
    "code": "FULFILLMENT_RECEIPT_CONFLICT",
    "message": "回执内容、来源或交付状态冲突"
  }
}
```

### C32 交付与数字内容读取

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/redemptions/{id}/fulfillment` |
| 用途/维护/页面 | 交付与数字内容读取 / C4 / 兑换详情/保存管理内容 |
| 身份/患者范围 | 本人或points:read；数字内容仅该患者，人员正文另验服务授权 |
| 路径/查询/头/体 | path redemption_id；query/body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<Fulfillment>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 FULFILLMENT_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | pending不造artifact；完成数字有真实text/plain产物和来源，人员型读取C service状态映射。安全文本，不执行任意HTML/URL/模型指令。 |
| 待实施验收 | 模拟明示；未接服务不冒充药师/配送完成；无改药补服建议。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "fulfillment_id": "fulfillment-demo-001",
    "redemption_id": "redemption-demo-001",
    "patient_id": "p-demo-001",
    "kind": "digital_content",
    "status": "pending",
    "service_id": null,
    "artifact": null,
    "failure_reason": null,
    "task_id": "fulfillment-task-demo-001",
    "updated_at": "2026-11-16T06:00:00Z",
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
    "code": "FULFILLMENT_UNAVAILABLE",
    "message": "交付记录暂不可用"
  }
}
```

### C33 独立权益体验评价

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/redemptions/{id}/feedback` |
| 用途/维护/页面 | 独立权益体验评价 / C4/C6 / 兑换完成/评价 |
| 身份/患者范围 | 仅本人且属于本人兑换；不强制参与 |
| 路径/查询/头/体 | path redemption_id；query无；JSON=RedemptionFeedbackInput；网页写入头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 201；Envelope<RedemptionFeedback>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 REDEMPTION_FEEDBACK_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 保存体验/拒绝参与与原服务反馈引用；相同有效服务已反馈可引用，免重复问同一内容；不当真实疗效或训练授权。 |
| 待实施验收 | 不同患者/其他服务反馈不能挂接；评价不自动增减积分。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "feedback_id": "redemption-feedback-demo-001",
    "patient_id": "p-demo-001",
    "redemption_id": "redemption-demo-001",
    "participation": "provided",
    "experience": "这份模拟管理内容便于查看。",
    "service_feedback_id": null,
    "recorded_at": "2026-11-16T06:00:00Z",
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
    "code": "REDEMPTION_FEEDBACK_CONFLICT",
    "message": "评价来源或关联服务不一致"
  }
}
```

### C34 确认服务并取得O共享引用

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/service-confirmations` |
| 用途/维护/页面 | 确认服务并取得O共享引用 / C3/O / 服务准备/一次确认 |
| 身份/患者范围 | 仅本人明确操作；O患者/家庭/用途授权核验，家人不能自行扩大范围 |
| 路径/查询/头/体 | path patient_id；query无；JSON=ServiceConfirmationInput；网页写入头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 201；Envelope<ServiceConfirmation>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 SHARING_CONFIRMATION_REQUIRED；另继承公共错误 |
| 幂等/状态/事务/来源 | 固定草稿内容，向O服务取得精确共享引用，同库保存C确认/指纹/回执；同服务同范围有效确认复用（可200），主体/范围变更再确认；建议24小时。这里不创建实际Service/通知。 |
| 待实施验收 | 客户端confirmed=true不能绕过O；选择范围可见；同意已有效不重复弹问。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "confirmation_ref_id": "service-confirmation-demo-001",
    "patient_id": "p-demo-001",
    "resource_id": "resource-pharmacist-demo",
    "resource_version": "resource-demo-v1",
    "provider_id": "provider-pharmacist-demo",
    "service_kind": "pharmacist_consultation",
    "descriptor_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "origin_draft_id": "service-draft-demo-001",
    "origin_draft_revision": 1,
    "sharing_scope": {
      "sharing_scope_ref_id": "sharing-scope-demo-001",
      "scope_version": 1,
      "patient_id": "p-demo-001",
      "recipient_id": "provider-pharmacist-demo",
      "recipient_type": "pharmacist",
      "purpose_code": "pharmacist_consultation",
      "data_categories": [
        "support_question"
      ],
      "related_grant_ids": [],
      "status": "active",
      "confirmed_at": "2026-11-16T06:00:00Z",
      "valid_until": "2026-11-17T06:00:00Z",
      "is_simulated": true
    },
    "status": "active",
    "confirmed_at": "2026-11-16T06:00:00Z",
    "valid_until": "2026-11-17T06:00:00Z",
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 1,
      "contract_version": "C-draft01",
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
    "code": "SHARING_CONFIRMATION_REQUIRED",
    "message": "草稿、范围或O权威授权无法确认"
  }
}
```

### C35 核验可复用确认与范围

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/service-confirmations/{id}` |
| 用途/维护/页面 | 核验可复用确认与范围 / C3/O / 服务准备/授权历史 |
| 身份/患者范围 | 本人；家人/服务方仅获准最小状态，不公开健康内容 |
| 路径/查询/头/体 | path confirmation_ref_id；query/body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<ServiceConfirmation>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 503 SHARING_AUTHORITY_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 读C确认与O权威有效性交集，不把缓存active当仍授权；过期/撤销分别说明，不自动续期。 |
| 待实施验收 | 旧确认只能相同服务/主体/范围复用；跨患者ID拒绝。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "confirmation_ref_id": "service-confirmation-demo-001",
    "patient_id": "p-demo-001",
    "resource_id": "resource-pharmacist-demo",
    "resource_version": "resource-demo-v1",
    "provider_id": "provider-pharmacist-demo",
    "service_kind": "pharmacist_consultation",
    "descriptor_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "origin_draft_id": "service-draft-demo-001",
    "origin_draft_revision": 1,
    "sharing_scope": {
      "sharing_scope_ref_id": "sharing-scope-demo-001",
      "scope_version": 1,
      "patient_id": "p-demo-001",
      "recipient_id": "provider-pharmacist-demo",
      "recipient_type": "pharmacist",
      "purpose_code": "pharmacist_consultation",
      "data_categories": [
        "support_question"
      ],
      "related_grant_ids": [],
      "status": "active",
      "confirmed_at": "2026-11-16T06:00:00Z",
      "valid_until": "2026-11-17T06:00:00Z",
      "is_simulated": true
    },
    "status": "active",
    "confirmed_at": "2026-11-16T06:00:00Z",
    "valid_until": "2026-11-17T06:00:00Z",
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 1,
      "contract_version": "C-draft01",
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
    "code": "SHARING_AUTHORITY_UNAVAILABLE",
    "message": "O共享授权状态暂不可核验"
  }
}
```

### C36 撤销确认与相关共享

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/service-confirmations/{id}/revoke` |
| 用途/维护/页面 | 撤销确认与相关共享 / C3/O / 我的/服务授权 |
| 身份/患者范围 | 仅本人；不能撤销他人独立确认或扩大共享 |
| 路径/查询/头/体 | path confirmation_ref_id；query无；JSON=公共RevokeInput（expected_revision/reason）；网页写入头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<ServiceConfirmation>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 CONFIRMATION_REVISION_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 调用O权威撤销并保存C审计、待派发失效；不改历史授权事实，不伪称所有在途第三方已停；相同共享引用的有效性重验，不自动恢复终态。 |
| 待实施验收 | 撤销后重放/任务不能再共享；回执可审计，不复活操作。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "confirmation_ref_id": "service-confirmation-demo-001",
    "patient_id": "p-demo-001",
    "resource_id": "resource-pharmacist-demo",
    "resource_version": "resource-demo-v1",
    "provider_id": "provider-pharmacist-demo",
    "service_kind": "pharmacist_consultation",
    "descriptor_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "origin_draft_id": "service-draft-demo-001",
    "origin_draft_revision": 1,
    "sharing_scope": {
      "sharing_scope_ref_id": "sharing-scope-demo-001",
      "scope_version": 2,
      "patient_id": "p-demo-001",
      "recipient_id": "provider-pharmacist-demo",
      "recipient_type": "pharmacist",
      "purpose_code": "pharmacist_consultation",
      "data_categories": [
        "support_question"
      ],
      "related_grant_ids": [],
      "status": "revoked",
      "confirmed_at": "2026-11-16T06:00:00Z",
      "valid_until": "2026-11-17T06:00:00Z",
      "is_simulated": true
    },
    "status": "revoked",
    "confirmed_at": "2026-11-16T06:00:00Z",
    "valid_until": "2026-11-17T06:00:00Z",
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 2,
      "contract_version": "C-draft01",
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
    "code": "CONFIRMATION_REVISION_CONFLICT",
    "message": "确认或授权版本已变化"
  }
}
```

### C37 受控文字审核

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/peer-posts/{id}/moderation` |
| 用途/维护/页面 | 受控文字审核 / C4 / 志愿者/演示管理审核 |
| 身份/患者范围 | 限定该组受控审核身份；不是普通家庭或患者权限 |
| 路径/查询/头/体 | path post_id；query无；JSON=PostModerationInput；受控身份/CSRF/Idempotency-Key；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<PeerPost>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 403 PEER_MODERATOR_REQUIRED；另继承公共错误 |
| 幂等/状态/事务/来源 | 核对修订，pending→visible/hidden，保留审核日志；审核者不能改成医疗处方，不把审核当专业医疗背书；实际人员未提供只模拟。 |
| 待实施验收 | 普通成员不能自批；重复回调不重复发参与积分。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "post_id": "post-demo-001",
    "group_id": "group-demo-001",
    "author_alias": "晨光伙伴7",
    "content": "我想分享一个整理日程的小习惯（虚构交流）。",
    "moderation_status": "visible",
    "created_at": "2026-11-16T06:00:00Z",
    "moderated_at": "2026-11-16T06:00:00Z",
    "revision": 2,
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
    "code": "PEER_MODERATOR_REQUIRED",
    "message": "缺少该组审核权限"
  }
}
```

### C38 明确完成本周管理回顾

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/management-reviews` |
| 用途/维护/页面 | 明确完成本周管理回顾 / C4/C6 / 我的/每周管理回顾 |
| 身份/患者范围 | 仅本人明确完成，非家人/模型代造 |
| 路径/查询/头/体 | path patient_id；query无；JSON=ManagementReviewInput；网页写入头；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 201；Envelope<ManagementReview>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 409 MANAGEMENT_REVIEW_PERIOD_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 当前本地ISO周、明确完成一次，保留低负担描述，无心理量表分数；C核奖程序后续按业务键一次+3，提交不由LLM任意改余额。 |
| 待实施验收 | 重复提交只一周资格；未来/任意旧周不能冒充当前完成。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "review_id": "management-review-demo-001",
    "patient_id": "p-demo-001",
    "week_start": "2026-11-16",
    "reflection": "本周想把提醒和日程整理得更清楚（虚构回顾）。",
    "completed_at": "2026-11-16T06:00:00Z",
    "rules_version": "points-demo-draft01",
    "meta": {
      "created_at": "2026-11-16T06:00:00Z",
      "updated_at": "2026-11-16T06:00:00Z",
      "revision": 1,
      "contract_version": "C-draft01",
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
    "code": "MANAGEMENT_REVIEW_PERIOD_CONFLICT",
    "message": "回顾周次或提交编号不符合当前周期"
  }
}
```

### C39 管理回顾历史

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/management-reviews` |
| 用途/维护/页面 | 管理回顾历史 / C4/C6 / 我的/回顾记录 |
| 身份/患者范围 | 本人或明确相应反馈查看授权，不因家庭绑定全开放 |
| 路径/查询/头/体 | path patient_id；query window_start/end:DateTime R/N（[start,end)，≤31天）、cursor/limit；body无；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<List<ManagementReview>>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 按completed_at/review_id排序，按实际周次/来源展示；不自动给分、改画像或训练。 |
| 待实施验收 | 没有回顾不造已完成；历史规则版本可追溯。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "review_id": "management-review-demo-001",
        "patient_id": "p-demo-001",
        "week_start": "2026-11-16",
        "reflection": "本周想把提醒和日程整理得更清楚（虚构回顾）。",
        "completed_at": "2026-11-16T06:00:00Z",
        "rules_version": "points-demo-draft01",
        "meta": {
          "created_at": "2026-11-16T06:00:00Z",
          "updated_at": "2026-11-16T06:00:00Z",
          "revision": 1,
          "contract_version": "C-draft01",
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
    "message": "回顾不可访问或不存在"
  }
}
```

### C40 由O切换预登记模拟画像

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/demo/patients/{p}/profile-fixtures` |
| 用途/维护/页面 | 由O切换预登记模拟画像 / O演示适配，C仅页面入口 / 独立演示控制台/三类社会支持场景 |
| 身份/患者范围 | 仅demo:manage受控身份，虚构患者及O固定fixture |
| 路径/查询/头/体 | path patient_id；query无；JSON=ProfileFixtureInput；管理Cookie/CSRF/Idempotency-Key；类型、R/O/可空、默认、枚举/格式/单位、生成方/版本见C01逐字段定义 |
| 完整成功返回 | HTTP 200；Envelope<ProfileFixtureResult>，按完整递归字段表，无任意扩展字段 |
| 失败 | 本卡特例HTTP 403 PROFILE_FIXTURE_DISABLED；另继承公共错误 |
| 幂等/状态/事务/来源 | 调用O authority发布/选择有虚构问卷来源的模拟结果，旧O画像保留；不由C计算/写任意分类，不生成CAS，不改研究资料。C后续重新读取O事实刷新推荐。 |
| 待实施验收 | 普通患者不能改画像标签；未知fixture/跨患者拒绝；模拟标记不可关。 另核对跨患者/授权撤销、并发同键异内容、在途/回滚、过期/晚回执及历史不覆盖。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "patient_id": "p-demo-001",
    "profile_fixture_id": "profile-fixture-operations-demo",
    "profile_id": "profile-o-demo-operations",
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
    "code": "PROFILE_FIXTURE_DISABLED",
    "message": "非演示、任意标签或未登记fixture不允许切换"
  }
}
```

## 3 状态/事务与非法行为矩阵（C新增细节待确认）

| 对象 | 建议合法行为 | 非法/特殊处理 |
| --- | --- | --- |
| 服务草稿 | preparing→新内容修订；正式提交后submitted；明确放弃abandoned | 草稿不通知；submitted不能原地改成另一申请；新申请新草稿 |
| 服务确认/O共享 | 明确用户动作取得同意与O范围；相同有效服务/主体/用途/类别可复用；可revoked/expired | confirmed=true非权限；过期不自动续；范围变/主体变重新确认，旧Grant不扩权 |
| Service | submitted→in_progress→completed；submitted/in_progress→cancelled/failed | submitted不直接completed；后三终态不回退；真实在途取消只先请求，不伪停外部服务 |
| 服务反馈 | 自愿provided/declined/unable；更正新feedback_revision引用前驱 | 不反馈不变服务失败；不生成心理总分/疗效；原意见不覆盖 |
| Membership | pending→active→left；pending也可left；入组服务完成不自动退组 | left后读/发帖拒绝；其他组员无本人真实ID；服务生命周期单独维护 |
| PeerPost | 明确本人提交pending→审核visible/hidden；更正审核留历史 | 普通成员自设审核拒绝；不把待审/自动消息当参与；不公开真实身份或未授权健康资料 |
| 积分奖励 | C程序校验真实来源，同周期业务键至多一奖，5日分配不重叠 | 不按服药“顺从”给分，不因改答/不适/暂停自动扣旧分，不因规则升级重复发奖 |
| 兑换/交付 | 原子扣分+独立兑换/交付，人员需唯一C服务；submitted→fulfilling→completed或failed | 不负余额/半扣；必要医疗无积分门槛；模拟产物/人员不冒真实完成 |
| 退分/未知 | 明确未交付失败/取消，全额一次；unknown先核查 | 重复失败不再退；已完成/已退分后的晚成功不自动复活；部分履约/争议另待定 |
| 回调 | 独立可信身份/来源号/资源映射，合法状态才applied | 最小Ack不回传余额/健康详情；取消/撤销晚回执审计，不恢复共享 |
| O演示fixture | 注册虚构问卷/画像结果切换，CAS null、旧结果保留 | 非demo、任意标签、跨患者或改研究资料拒绝 |

## 4 固定验收计划（未运行）

1. 未授权/未确认草稿不创建实际Service或通知；确认一次后精确草稿修订至多一条；B直申/重试不重复。有效相同范围同意复用，范围/主体变化重确认。
2. 五状态合法/非法/终态回退、在途取消/过期/授权撤销和乱序回执；模拟标记贯穿，不把服务受理/完成当患者已评价或真实疗效。
3. 小组自愿加入/退出、本人匿名视图、帖子pending审核、组外拒绝、无真实运营时只模拟；不自动共享病历/对话或给“读了一条推荐”参与奖。
4. 日+2/5日+5/周+3/参与+2仅建议；重复核奖/迟到/更正/规则升级不多发，5日日期不可重用，不因漏服/不适/暂停扣已有分。
5. 余额30兑换成本30后0；不足/旧版本/两个并发事务至少一方冲突，不出现负数/半条记录；原流水不可变。
6. 明确失败未交付一次+30退分恢复30；重复失败仍30；unknown不盲退/重发；已交付争议按未决流程不擅自改账。
7. 数字管理内容不修改医嘱，人员交付映射唯一C Service；兑换和服务记录/反馈分别有入口，反馈引用可避免重复问同一内容。
8. A/B可读同一C权威状态/三维反馈；O画像不自动变化；没有库存/专业资料/真实机构时不造来源、审核、风险阈值或已联系记录。

字段/JSON/算术/引用静态检查不等于上述业务测试。确认C后进入全流程联合契约及未决收敛，继续S00，不执行S01。

