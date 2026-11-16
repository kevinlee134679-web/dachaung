# S00 第一轮：公共基础与 O 接口卡（draft01）

2026-11-16，Asia/Shanghai。依据总 Prompt v1.1 与本轮用户指令。**所有卡片均为建议、待确认、未实现**；完整字段定义见同目录《01_公共基础与O字段_draft01.md》，不能把本文件示例当实际运行结果。只追加修订或新建版本，不覆盖本轮历史。

## 1 全卡共同契约

下列规则除“已确认”标明外均为待确认建议，字段版本P-draft01/O-draft01。路径统一建议前缀 `/api/v1`。每卡的输出T完整继承Envelope<T>与字段表中T的递归定义；“无”意味着没有该类输入。path/query/header/body各自独立，不允许查询参数或请求体覆盖服务端身份、来源、质量结果、版本和模拟标记。

- **已确认**：四字段响应；ID/追踪/幂等分开；同键同内容同业务结果、同键异内容冲突；每次访问及执行重验身份/患者/授权；重复请求不能重复创建/执行/计数；缺失/错误不伪装成功。
- 公共请求头及每种字段的R/O、可空、默认、范围、生成方和版本，逐项见字段表第1—2节。除各卡例外，GET带Cookie，不需要CSRF/幂等键；所有JSON写操作带Cookie、CSRF、Content-Type与Idempotency-Key。退出和初次演示登录的特殊规则见对应卡，生产认证不在此自造协议。
- 请求未知字段422；非法/无时区时间422；跨患者资源统一404候选以免泄露存在性；已知当前患者但授权不足403；未登录401。存储/依赖失败503，不返回空数组、零比例或“已完成”。
- 资源修改按expected_revision/expected_plan_version乐观并发。旧版本409；事务回滚不会留下半条业务、部分授权、已消费码或半发布计划。
- 幂等建议作用域=(已验证账号,患者,操作类型,Idempotency-Key)，请求规范化内容固定。只读与重放均先重新鉴权；不能因旧回执泄露被撤销授权的数据。相同操作同键正在处理时返回409 OPERATION_IN_PROGRESS并建议Retry-After: 1；操作超时结果未知先查询原结果，不盲目另建操作。
- 若未发生任何业务提交且可确认已回滚，可用原键重试；若业务已提交，稳定返回已提交资源；若已记录确定业务拒绝，同键重放拒绝，修改内容需新键。外部副作用结果未知不自动重做。键保留期、指纹算法、回执过期语义和受控返回Cookie/绑定码需公共/A确认，本轮不擅自写成有效规则。
- 纯读取不写业务状态、不训练、不调用付费模型。对需后续模块的接口，可列目录和契约；未实现就标未实现，不制作假成功实现。
- 列表类型List<T>固定items/next_cursor，均无隐藏任意字段；列表排序以每卡为准。path.id为卡内指定资源ID；列表空集仅适用于确实无数据。所有时间窗口建议[start,end)，O29最大31天待确认。
- 来源：账号/患者/授权由O校验；模型、设备、确认、服务各有独立来源和模拟标记。O不另接服药确认事实、A不另发正式计划、知识读B2、正式服务由C创建。
- 下列每卡JSON都是虚构的**结构示例**，未执行测试；O15为缩小示例体积每题只示一个选项，完整候选见字段表；计划剂量是“虚构单位”，不是医疗指令。成功码之外的422/401/403/404/409/503共通失败仍适用。

## 2 接口卡

### G01 运行和必要依赖就绪检查

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/health` |
| 维护方 / 入口 | A0 / 启动检查/管理 |
| 身份与患者范围 | 无需患者身份；仅最小进程/依赖状态 |
| 路径/查询/头/体 | 路径/查询/请求体均无；无Cookie/CSRF/幂等键；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<Health>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 503 DEPENDENCY_NOT_READY；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 无写入、无外网/付费模型探测；检查必须有超时。 |
| 待实施验收（未执行） | 断开必要依赖返回503；不因进程活着就宣称业务可用。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "process_status": "running",
    "readiness": "ready",
    "dependencies": [
      {
        "name": "database",
        "status": "available",
        "reason": null
      }
    ],
    "app_version": "example-only",
    "checked_at": "2026-11-16T04:00:00Z"
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
    "code": "DEPENDENCY_NOT_READY",
    "message": "必要依赖未就绪"
  }
}
```

### G02 查看脱敏配置和实际能力

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/config/status` |
| 维护方 / 入口 | A0/B1 / 独立演示控制台 |
| 身份与患者范围 | 已登录的后端白名单演示管理账号，不是任意家人 |
| 路径/查询/头/体 | 路径/查询/请求体无；Cookie必需，GET无CSRF/幂等键；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<ConfigStatus>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 403 ADMIN_REQUIRED；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读本地配置与既有探测结果，不发模型请求；不输出密钥/完整地址/数据库路径。 |
| 待实施验收（未执行） | 普通患者被拒；未探测显示unverified，不能声称real已联通。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "auth_mode": "demo",
    "llm_mode": "mock",
    "requested_pipeline": "single_pass",
    "model_configured": false,
    "model_connectivity": "unverified",
    "capabilities": [
      {
        "code": "in_app_notification",
        "available": true,
        "reason": null
      }
    ],
    "version_refs": []
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
    "code": "ADMIN_REQUIRED",
    "message": "当前账号不能查看管理配置"
  }
}
```

### O01 进入一个预置虚构身份

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/auth/demo-session` |
| 维护方 / 入口 | O1/A身份适配 / 首次身份选择/演示控制台 |
| 身份与患者范围 | 只在AUTH_MODE=demo且本地受控入口；不接收外部用户自报身份 |
| 路径/查询/头/体 | 路径/查询无；JSON=DemoLoginInput；Idempotency-Key必需；登录前无会话CSRF，校验同源Origin；未列查询字段不接受 |
| 完整返回定义 | HTTP 201，Envelope<IdentityContext>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 403 DEMO_DISABLED；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 创建会话与幂等回执原子一致；返回Set-Cookie和CSRF，不把会话标识当患者ID；同键重放同一有效会话结果，过期后不得凭旧键复活登录。 |
| 待实施验收（未执行） | external时拒绝；未知演示账号拒绝；同键不产生多个有效会话。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "account": {
      "account_id": "acct-demo-001",
      "display_name": "演示本人账号",
      "auth_mode": "demo",
      "is_simulated": true
    },
    "current_patient_id": "p-demo-001",
    "patients": [
      {
        "patient": {
          "patient_id": "p-demo-001",
          "display_name": "虚构患者甲",
          "timezone": "Asia/Shanghai",
          "enrollment_at": null,
          "meta": {
            "created_at": "2026-11-16T04:00:00Z",
            "updated_at": "2026-11-16T04:00:00Z",
            "revision": 1,
            "contract_version": "O-draft01",
            "is_simulated": true
          }
        },
        "relationship": "self",
        "effective_scopes": [
          "patient:read",
          "plan:read"
        ]
      }
    ],
    "csrf_token": "example-only-not-a-real-token",
    "expires_at": "2026-11-16T12:00:00Z"
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
    "message": "当前身份模式不允许演示登录"
  }
}
```

### O02 读取账号和当前患者上下文

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/auth/me` |
| 维护方 / 入口 | O1 / 全局身份栏/我的 |
| 身份与患者范围 | 仅当前会话；可管理集合每次按授权计算 |
| 路径/查询/头/体 | 路径/查询/请求体无；Cookie必需；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<IdentityContext>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 401 AUTH_REQUIRED；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读；撤销授权后不重放旧上下文缓存。 |
| 待实施验收（未执行） | 家人授权撤销后目标从有效集合移除；不泄露其他患者。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "account": {
      "account_id": "acct-demo-001",
      "display_name": "演示本人账号",
      "auth_mode": "demo",
      "is_simulated": true
    },
    "current_patient_id": "p-demo-001",
    "patients": [
      {
        "patient": {
          "patient_id": "p-demo-001",
          "display_name": "虚构患者甲",
          "timezone": "Asia/Shanghai",
          "enrollment_at": null,
          "meta": {
            "created_at": "2026-11-16T04:00:00Z",
            "updated_at": "2026-11-16T04:00:00Z",
            "revision": 1,
            "contract_version": "O-draft01",
            "is_simulated": true
          }
        },
        "relationship": "self",
        "effective_scopes": [
          "patient:read",
          "plan:read"
        ]
      }
    ],
    "csrf_token": "example-only-not-a-real-token",
    "expires_at": "2026-11-16T12:00:00Z"
  },
  "error": null
}
```

失败结构示例（HTTP 401）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "AUTH_REQUIRED",
    "message": "会话无效或已过期"
  }
}
```

### O03 主动注销当前会话

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/auth/logout` |
| 维护方 / 入口 | O1 / 我的/退出 |
| 身份与患者范围 | 当前会话的本人账号；不得注销其他账号 |
| 路径/查询/头/体 | 路径/查询无；请求体={}；Cookie/CSRF/Idempotency-Key；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<OperationResult>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 401 AUTH_REQUIRED；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 事务使会话失效并保存最小退出回执；同一已注销凭据只能受控读取自己的无健康数据退出回执，不能恢复会话或读取业务数据；过期无回执返回401。 |
| 待实施验收（未执行） | 退出后me返回401；重试不新建会话；退出回执不含健康信息。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "operation_id": "op-demo-001",
    "outcome": "logged_out",
    "affected_ids": [],
    "completed_at": "2026-11-16T04:00:00Z"
  },
  "error": null
}
```

失败结构示例（HTTP 401）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "AUTH_REQUIRED",
    "message": "无法验证当前退出凭据"
  }
}
```

### O04 列出本人及授权照护对象

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients` |
| 维护方 / 入口 | O1 / 身份切换/家庭入口 |
| 身份与患者范围 | 仅当前账号可管理对象；显示家人关系不授予额外健康范围 |
| 路径/查询/头/体 | 查询cursor、limit用公共表；路径/请求体无；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<List<PatientAccess>>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 401 AUTH_REQUIRED；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读，按patient_id稳定排序，游标绑定当前账号。 |
| 待实施验收（未执行） | 一账号可同时self/family；撤销后不能靠旧游标继续读取。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "patient": {
          "patient_id": "p-demo-001",
          "display_name": "虚构患者甲",
          "timezone": "Asia/Shanghai",
          "enrollment_at": null,
          "meta": {
            "created_at": "2026-11-16T04:00:00Z",
            "updated_at": "2026-11-16T04:00:00Z",
            "revision": 1,
            "contract_version": "O-draft01",
            "is_simulated": true
          }
        },
        "relationship": "self",
        "effective_scopes": [
          "patient:read",
          "plan:read"
        ]
      }
    ],
    "next_cursor": null
  },
  "error": null
}
```

失败结构示例（HTTP 401）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "AUTH_REQUIRED",
    "message": "请重新选择有效身份"
  }
}
```

### O05 记住上次管理对象

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `PUT /api/v1/auth/current-patient` |
| 维护方 / 入口 | O1 / 全局对象切换 |
| 身份与患者范围 | 当前账号可管理目标患者，查验实时授权 |
| 路径/查询/头/体 | 路径/查询无；JSON=CurrentPatientInput；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<IdentityContext>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 403 PATIENT_ACCESS_DENIED；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 仅更新账号的选择偏好，不修改资源归属；保存前重查可管理集合，同键重放前也重鉴权。 |
| 待实施验收（未执行） | 甲切乙后旧表单携带甲路径也不能被系统改写成乙；前端清空旧卡片。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "account": {
      "account_id": "acct-demo-001",
      "display_name": "演示本人账号",
      "auth_mode": "demo",
      "is_simulated": true
    },
    "current_patient_id": "p-demo-001",
    "patients": [
      {
        "patient": {
          "patient_id": "p-demo-001",
          "display_name": "虚构患者甲",
          "timezone": "Asia/Shanghai",
          "enrollment_at": null,
          "meta": {
            "created_at": "2026-11-16T04:00:00Z",
            "updated_at": "2026-11-16T04:00:00Z",
            "revision": 1,
            "contract_version": "O-draft01",
            "is_simulated": true
          }
        },
        "relationship": "self",
        "effective_scopes": [
          "patient:read",
          "plan:read"
        ]
      }
    ],
    "csrf_token": "example-only-not-a-real-token",
    "expires_at": "2026-11-16T12:00:00Z"
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
    "code": "PATIENT_ACCESS_DENIED",
    "message": "不能管理该患者"
  }
}
```

### O06 查看基础资料

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}` |
| 维护方 / 入口 | O1 / 我的/个人资料 |
| 身份与患者范围 | 本人或patient:read；{p}为ID，实体验证患者范围 |
| 路径/查询/头/体 | 路径patient_id；查询/请求体无；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<Patient>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读最小资料；拒绝时不透露跨患者存在性。 |
| 待实施验收（未执行） | 家人有计划查看权限但无基础查看权限时不能扩大读取。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "patient_id": "p-demo-001",
    "display_name": "虚构患者甲",
    "timezone": "Asia/Shanghai",
    "enrollment_at": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "O-draft01",
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
    "message": "资料不可访问或不存在"
  }
}
```

### O07 更新基础资料与显示时区

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `PATCH /api/v1/patients/{p}` |
| 维护方 / 入口 | O1 / 我的/编辑资料 |
| 身份与患者范围 | 本人或patient:edit；不能修改enrollment_at/归属 |
| 路径/查询/头/体 | 路径patient_id；查询无；JSON=PatientPatch；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<Patient>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 409 REVISION_CONFLICT；另继承公共错误定义 |
| 幂等/状态/事务/来源 | expected_revision检查、字段修订和幂等结果同一事务；时区变更不平移原始事件/旧计划快照。 |
| 待实施验收（未执行） | 旧修订拒绝；PATCH省略notes类字段不等于清空；未知字段422。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "patient_id": "p-demo-001",
    "display_name": "虚构患者甲（昵称更正）",
    "timezone": "Asia/Shanghai",
    "enrollment_at": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "O-draft01",
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
    "code": "REVISION_CONFLICT",
    "message": "资料已被其他操作更新"
  }
}
```

### O08 患者主动发起家庭关联

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/family-binding-codes` |
| 维护方 / 入口 | O1 / 家庭管理/邀请家人 |
| 身份与患者范围 | 仅患者本人，监护例外未定义不放行 |
| 路径/查询/头/体 | 路径patient_id；查询无；JSON={}；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 201，Envelope<BindingCode>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 403 PATIENT_CONFIRMATION_REQUIRED；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 生成限时一次性码及回执原子提交；响应受控，日志不记录明文；新码不产生默认健康授权。 |
| 待实施验收（未执行） | 家人不能代本人发码扩大权限；同键不会制造多码。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "code_id": "code-demo-001",
    "binding_code": "EXAMPLE-ONLY-CODE",
    "patient_id": "p-demo-001",
    "expires_at": "2026-11-16T04:05:00Z",
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
    "code": "PATIENT_CONFIRMATION_REQUIRED",
    "message": "仅患者本人可发起绑定"
  }
}
```

### O09 家人兑换患者发起的绑定码

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/family-bindings/redeem` |
| 维护方 / 入口 | O1 / 家庭管理/帮助家人 |
| 身份与患者范围 | 当前登录家人账号；患者从可信码取得 |
| 路径/查询/头/体 | 路径/查询无；JSON=RedeemInput；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 201，Envelope<FamilyBinding>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 409 BINDING_CODE_UNAVAILABLE；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 核验码、消费码、创建关系和幂等结果同事务；禁止自己绑定自己；同键返回原关系，其他账号重复兑换冲突；建立关系不附带Grant。 |
| 待实施验收（未执行） | 并发兑换最多一个有效结果；码过期不创建关系；响应不附健康详情。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "binding_id": "binding-demo-001",
    "patient_id": "p-demo-001",
    "family_account_id": "acct-demo-002",
    "status": "active",
    "established_at": "2026-11-16T04:00:00Z",
    "revoked_at": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "O-draft01",
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
    "code": "BINDING_CODE_UNAVAILABLE",
    "message": "绑定码已用、失效或不可用"
  }
}
```

### O10 查看家庭关系状态

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/family-bindings` |
| 维护方 / 入口 | O1 / 家庭成员/授权入口 |
| 身份与患者范围 | 本人可看全部；家人仅自己的关系和最小状态 |
| 路径/查询/头/体 | 路径patient_id；查询cursor、limit；请求体无；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<List<FamilyBinding>>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读；按established_at、binding_id排序；不返回其他家人的授权细节给无权者。 |
| 待实施验收（未执行） | 多对多关系正确；家人不因一条关系获得全部家庭名单。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "binding_id": "binding-demo-001",
        "patient_id": "p-demo-001",
        "family_account_id": "acct-demo-002",
        "status": "active",
        "established_at": "2026-11-16T04:00:00Z",
        "revoked_at": null,
        "meta": {
          "created_at": "2026-11-16T04:00:00Z",
          "updated_at": "2026-11-16T04:00:00Z",
          "revision": 1,
          "contract_version": "O-draft01",
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
    "message": "关系不可访问或不存在"
  }
}
```

### O11 解除本人授权的关系或家人退出自己的关系

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/family-bindings/{id}/revoke` |
| 维护方 / 入口 | O1 / 家庭管理/解除绑定 |
| 身份与患者范围 | 患者本人或该关系的family_account；不能解除他人关系 |
| 路径/查询/头/体 | 路径binding_id；查询无；JSON=RevokeInput；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<FamilyBinding>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 409 REVISION_CONFLICT；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 关系active→revoked并使相关Grant不可用，同库事务留审计；相同状态重放不再产生撤销；对待执行共享登记失效，执行时重检；不存在revoked→active恢复。 |
| 待实施验收（未执行） | 解除后旧缓存/任务无法访问健康数据；重新绑定须新关系，不回退历史。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "binding_id": "binding-demo-001",
    "patient_id": "p-demo-001",
    "family_account_id": "acct-demo-002",
    "status": "revoked",
    "established_at": "2026-11-16T04:00:00Z",
    "revoked_at": "2026-11-16T04:00:00Z",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "O-draft01",
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
    "code": "REVISION_CONFLICT",
    "message": "关系已更新，请重新核对"
  }
}
```

### O12 精确设置某家人的授权范围

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `PUT /api/v1/family-bindings/{id}/grant` |
| 维护方 / 入口 | O1 / 家庭管理/权限编辑 |
| 身份与患者范围 | 仅该患者本人；关系必须active；监护替代未定义 |
| 路径/查询/头/体 | 路径binding_id；查询无；JSON=GrantPutInput；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<Grant>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 409 GRANT_VERSION_CONFLICT；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 首次expected_revision=0；授权版本、确认记录和幂等结果同事务；全量替换scopes，扩权必须明确确认；撤销或过期后的重新授权创建新授权事实/历史，不抹旧事实。 |
| 待实施验收（未执行） | 家人不能给自己授权；scopes=[]不默认为全部；同键不同范围409。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "grant_id": "grant-demo-001",
    "binding_id": "binding-demo-001",
    "patient_id": "p-demo-001",
    "grantee_account_id": "acct-demo-002",
    "scopes": [
      "plan:read"
    ],
    "grant_version": 1,
    "status": "active",
    "valid_until": null,
    "confirmed_at": "2026-11-16T04:00:00Z",
    "revoked_at": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "O-draft01",
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
    "code": "GRANT_VERSION_CONFLICT",
    "message": "授权范围或关系已变化"
  }
}
```

### O13 查看当前授权与必要历史

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/grants` |
| 维护方 / 入口 | O1 / 我的/授权管理 |
| 身份与患者范围 | 本人查看全部；家人仅自己的Grant |
| 路径/查询/头/体 | 路径patient_id；查询cursor、limit；请求体无；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<List<Grant>>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 按confirmed_at、grant_id排序；计算过期状态不改写历史确认时间；不公开其他家人权限。 |
| 待实施验收（未执行） | 历史授权仍可追溯；已过期不视为有效权限。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "grant_id": "grant-demo-001",
        "binding_id": "binding-demo-001",
        "patient_id": "p-demo-001",
        "grantee_account_id": "acct-demo-002",
        "scopes": [
          "plan:read"
        ],
        "grant_version": 1,
        "status": "active",
        "valid_until": null,
        "confirmed_at": "2026-11-16T04:00:00Z",
        "revoked_at": null,
        "meta": {
          "created_at": "2026-11-16T04:00:00Z",
          "updated_at": "2026-11-16T04:00:00Z",
          "revision": 1,
          "contract_version": "O-draft01",
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
    "message": "授权不可访问或不存在"
  }
}
```

### O14 撤销单条健康共享授权

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/grants/{id}/revoke` |
| 维护方 / 入口 | O1 / 我的/授权管理 |
| 身份与患者范围 | 仅患者本人；是否允许家人放弃权限可通过解除自身绑定完成 |
| 路径/查询/头/体 | 路径grant_id；查询无；JSON=RevokeInput；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<Grant>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 409 REVISION_CONFLICT；另继承公共错误定义 |
| 幂等/状态/事务/来源 | active→revoked，版本递增，保留原因与历史；关系可以仍存在；旧缓存及幂等重放前查权限，待执行共享停止；不恢复已撤销事实。 |
| 待实施验收（未执行） | 撤销后家人查询被拒；授权关系和家庭关系可区分。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "grant_id": "grant-demo-001",
    "binding_id": "binding-demo-001",
    "patient_id": "p-demo-001",
    "grantee_account_id": "acct-demo-002",
    "scopes": [
      "plan:read"
    ],
    "grant_version": 2,
    "status": "revoked",
    "valid_until": null,
    "confirmed_at": "2026-11-16T04:00:00Z",
    "revoked_at": "2026-11-16T04:00:00Z",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "O-draft01",
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
    "code": "REVISION_CONFLICT",
    "message": "授权已变化"
  }
}
```

### O15 取得八主题定义与选项

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/questionnaires/initial` |
| 维护方 / 入口 | O2 / 首次问卷/复评 |
| 身份与患者范围 | 已登录且准备管理本人或有questionnaire:assist/read的患者 |
| 路径/查询/头/体 | 查询version:string，O/N，省略取当前已发布问卷；请求体/路径无；仅返回定义不带患者答案；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<QuestionnaireDefinition>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 404 QUESTIONNAIRE_VERSION_NOT_FOUND；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读，无模型调用；示例每主题仅展示一个选项，完整候选以字段表为准。 |
| 待实施验收（未执行） | 严格八主题；选项版本变化不使旧回答按新含义解释。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "questionnaire_id": "initial",
    "version": "initial-draft01",
    "purpose": "收集自报行为、障碍及偏好；八主题不等价于原量表，不保证可预测CAS。",
    "themes": [
      {
        "question_id": "Q1",
        "prompt": "最近一个月，你的实际用药情况更接近哪一种？",
        "interaction": "scenario",
        "options": [
          {
            "code": "follows_plan",
            "label": "按医嘱"
          }
        ],
        "allows_unknown": true,
        "allows_not_applicable": true
      },
      {
        "question_id": "Q2",
        "prompt": "哪些事情最容易让你难以坚持用药？",
        "interaction": "multi_rank",
        "options": [
          {
            "code": "forget",
            "label": "容易忘记"
          }
        ],
        "allows_unknown": true,
        "allows_not_applicable": true
      },
      {
        "question_id": "Q3",
        "prompt": "身体好转或无明显症状时，你怎样看待继续服药？",
        "interaction": "scenario",
        "options": [
          {
            "code": "follow_advice",
            "label": "仍按医嘱"
          }
        ],
        "allows_unknown": true,
        "allows_not_applicable": true
      },
      {
        "question_id": "Q4",
        "prompt": "对于目前用药，你最担心哪些事情？",
        "interaction": "multi_concern",
        "options": [
          {
            "code": "none",
            "label": "没有上述担心"
          }
        ],
        "allows_unknown": true,
        "allows_not_applicable": true
      },
      {
        "question_id": "Q5",
        "prompt": "什么情况下最容易错过原定服药时间？",
        "interaction": "multi_frequency",
        "options": [
          {
            "code": "none",
            "label": "无这些影响"
          }
        ],
        "allows_unknown": true,
        "allows_not_applicable": true
      },
      {
        "question_id": "Q6",
        "prompt": "忙碌、疲惫或日程变化时，你有多大把握按医嘱完成？",
        "interaction": "confidence",
        "options": [
          {
            "code": "3",
            "label": "一般"
          }
        ],
        "allows_unknown": true,
        "allows_not_applicable": true
      },
      {
        "question_id": "Q7",
        "prompt": "理解和执行当前用药安排时，你最需要弄清楚什么？",
        "interaction": "multi_rank",
        "options": [
          {
            "code": "none",
            "label": "目前基本清楚"
          }
        ],
        "allows_unknown": true,
        "allows_not_applicable": true
      },
      {
        "question_id": "Q8",
        "prompt": "平台提供帮助时，你最希望获得哪些支持？",
        "interaction": "multi_rank",
        "options": [
          {
            "code": "timed_reminder",
            "label": "到时间提醒"
          }
        ],
        "allows_unknown": true,
        "allows_not_applicable": true
      }
    ]
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
    "code": "QUESTIONNAIRE_VERSION_NOT_FOUND",
    "message": "问卷版本未发布或不存在"
  }
}
```

### O16 新建/复制问卷进度

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/questionnaire-responses` |
| 维护方 / 入口 | O2 / 首次问卷/复评/更正 |
| 身份与患者范围 | 本人或questionnaire:assist；作答身份由会话确定 |
| 路径/查询/头/体 | 路径patient_id；查询无；JSON=ResponseCreateInput；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 201，Envelope<QuestionnaireResponse>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 404 SOURCE_RESPONSE_NOT_FOUND；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 创建draft及初始八题状态；supersedes引用同患者旧回答并复制内容，旧响应不修改；当前respondent由服务端写入。 |
| 待实施验收（未执行） | 家人不能把respondent_mode设成self；复评保留旧结果。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "response_id": "response-demo-001",
    "patient_id": "p-demo-001",
    "questionnaire_version": "initial-draft01",
    "respondent_account_id": "acct-demo-001",
    "respondent_mode": "self",
    "status": "draft",
    "answers": {
      "Q1": {
        "state": "answered",
        "value": {
          "primary": "follows_plan",
          "additional": []
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q2": {
        "state": "answered",
        "value": {
          "selected": [
            "forget"
          ],
          "top_ranked": [
            "forget"
          ],
          "other_text": null
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q3": {
        "state": "answered",
        "value": {
          "choice": "follow_advice"
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q4": {
        "state": "answered",
        "value": {
          "selected": [
            "none"
          ],
          "top_concerns": [],
          "intensity": null
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q5": {
        "state": "answered",
        "value": {
          "selected": [
            "none"
          ],
          "frequency": null
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q6": {
        "state": "answered",
        "value": {
          "confidence_level": 3
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q7": {
        "state": "answered",
        "value": {
          "selected": [
            "none"
          ]
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q8": {
        "state": "answered",
        "value": {
          "selected": [
            "timed_reminder"
          ],
          "ranked": [
            "timed_reminder"
          ]
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      }
    },
    "supersedes_response_id": null,
    "submitted_at": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "O-draft01",
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
    "code": "SOURCE_RESPONSE_NOT_FOUND",
    "message": "要更正的回答不可访问或不存在"
  }
}
```

### O17 保存完整八题进度快照

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `PUT /api/v1/questionnaire-responses/{id}/answers` |
| 维护方 / 入口 | O2 / 问卷返回/保存进度 |
| 身份与患者范围 | 本人草稿作答者或获questionnaire:assist的该草稿家人；跨作答者接管用新副本 |
| 路径/查询/头/体 | 路径response_id；查询无；JSON=AnswersPutInput；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<QuestionnaireResponse>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 422 INVALID_ANSWER；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 仅draft可写，expected_revision、答案修订及回执同事务；submitted写入409；none互斥、排序子集、unknown保持null；不按答案自动生成CAS。 |
| 待实施验收（未执行） | none和顾虑并选拒绝；家人不知道主观感受可unknown；无权修改/旧修订拒绝。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "response_id": "response-demo-001",
    "patient_id": "p-demo-001",
    "questionnaire_version": "initial-draft01",
    "respondent_account_id": "acct-demo-001",
    "respondent_mode": "self",
    "status": "draft",
    "answers": {
      "Q1": {
        "state": "answered",
        "value": {
          "primary": "follows_plan",
          "additional": []
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q2": {
        "state": "answered",
        "value": {
          "selected": [
            "forget"
          ],
          "top_ranked": [
            "forget"
          ],
          "other_text": null
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q3": {
        "state": "answered",
        "value": {
          "choice": "follow_advice"
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q4": {
        "state": "answered",
        "value": {
          "selected": [
            "none"
          ],
          "top_concerns": [],
          "intensity": null
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q5": {
        "state": "answered",
        "value": {
          "selected": [
            "none"
          ],
          "frequency": null
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q6": {
        "state": "answered",
        "value": {
          "confidence_level": 3
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q7": {
        "state": "answered",
        "value": {
          "selected": [
            "none"
          ]
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q8": {
        "state": "answered",
        "value": {
          "selected": [
            "timed_reminder"
          ],
          "ranked": [
            "timed_reminder"
          ]
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      }
    },
    "supersedes_response_id": null,
    "submitted_at": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "O-draft01",
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
    "code": "INVALID_ANSWER",
    "message": "答案形状、互斥或排序不合法"
  }
}
```

### O18 恢复进度及查看历史回答

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/questionnaire-responses/{id}` |
| 维护方 / 入口 | O2 / 问卷/我的/历史 |
| 身份与患者范围 | 本人或questionnaire:read；单有assist是否可读取该家人草稿建议允许本人作答范围 |
| 路径/查询/头/体 | 路径response_id；查询/请求体无；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<QuestionnaireResponse>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读精确响应，不用最新版本覆盖原始答案；授权撤销后拒绝。 |
| 待实施验收（未执行） | 刷新恢复进度；已提交历史保持原选项与版本。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "response_id": "response-demo-001",
    "patient_id": "p-demo-001",
    "questionnaire_version": "initial-draft01",
    "respondent_account_id": "acct-demo-001",
    "respondent_mode": "self",
    "status": "draft",
    "answers": {
      "Q1": {
        "state": "answered",
        "value": {
          "primary": "follows_plan",
          "additional": []
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q2": {
        "state": "answered",
        "value": {
          "selected": [
            "forget"
          ],
          "top_ranked": [
            "forget"
          ],
          "other_text": null
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q3": {
        "state": "answered",
        "value": {
          "choice": "follow_advice"
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q4": {
        "state": "answered",
        "value": {
          "selected": [
            "none"
          ],
          "top_concerns": [],
          "intensity": null
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q5": {
        "state": "answered",
        "value": {
          "selected": [
            "none"
          ],
          "frequency": null
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q6": {
        "state": "answered",
        "value": {
          "confidence_level": 3
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q7": {
        "state": "answered",
        "value": {
          "selected": [
            "none"
          ]
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q8": {
        "state": "answered",
        "value": {
          "selected": [
            "timed_reminder"
          ],
          "ranked": [
            "timed_reminder"
          ]
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      }
    },
    "supersedes_response_id": null,
    "submitted_at": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "O-draft01",
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
    "message": "回答不可访问或不存在"
  }
}
```

### O19 提交明确修订

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/questionnaire-responses/{id}/submit` |
| 维护方 / 入口 | O2 / 问卷完成 |
| 身份与患者范围 | 本人或已授权questionnaire:assist的当前作答者 |
| 路径/查询/头/体 | 路径response_id；查询无；JSON=SubmitInput；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<QuestionnaireResponse>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 409 RESPONSE_REVISION_CONFLICT；另继承公共错误定义 |
| 幂等/状态/事务/来源 | draft→submitted和回执原子提交；不得直接传已提交状态；unknown/not_applicable允许，遗留not_answered策略待Q05；不调用模型、不自动判型；同键返回原提交。 |
| 待实施验收（未执行） | 提交特定修订；提交后更正创建新响应；重复提交不产生多次评估。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "response_id": "response-demo-001",
    "patient_id": "p-demo-001",
    "questionnaire_version": "initial-draft01",
    "respondent_account_id": "acct-demo-001",
    "respondent_mode": "self",
    "status": "submitted",
    "answers": {
      "Q1": {
        "state": "answered",
        "value": {
          "primary": "follows_plan",
          "additional": []
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q2": {
        "state": "answered",
        "value": {
          "selected": [
            "forget"
          ],
          "top_ranked": [
            "forget"
          ],
          "other_text": null
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q3": {
        "state": "answered",
        "value": {
          "choice": "follow_advice"
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q4": {
        "state": "answered",
        "value": {
          "selected": [
            "none"
          ],
          "top_concerns": [],
          "intensity": null
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q5": {
        "state": "answered",
        "value": {
          "selected": [
            "none"
          ],
          "frequency": null
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q6": {
        "state": "answered",
        "value": {
          "confidence_level": 3
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q7": {
        "state": "answered",
        "value": {
          "selected": [
            "none"
          ]
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      },
      "Q8": {
        "state": "answered",
        "value": {
          "selected": [
            "timed_reminder"
          ],
          "ranked": [
            "timed_reminder"
          ]
        },
        "answered_by": "self",
        "updated_at": "2026-11-16T04:00:00Z"
      }
    },
    "supersedes_response_id": null,
    "submitted_at": "2026-11-16T04:00:00Z",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "O-draft01",
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
    "code": "RESPONSE_REVISION_CONFLICT",
    "message": "回答已变化，需重新核对"
  }
}
```

### O20 读取当前有效画像与不足

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/profiles/current` |
| 维护方 / 入口 | O3 / 首页摘要/我的/画像 |
| 身份与患者范围 | 本人或profile:read |
| 路径/查询/头/体 | 路径patient_id；查询/请求体无；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<Profile>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 404 PROFILE_NOT_AVAILABLE；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读最近有效结果，不隐式运行评估/LLM/训练；insufficient结果与根本没有结果区别。 |
| 待实施验收（未执行） | CAS未适配返回null及原因；C反馈不会偷偷覆盖画像。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "profile_id": "profile-demo-001",
    "patient_id": "p-demo-001",
    "response_id": "response-demo-001",
    "status": "insufficient",
    "primary_type": null,
    "additional_types": [],
    "reported_behavior": "follows_plan",
    "cas": {
      "status": "unavailable",
      "value": null,
      "reason": "模型输入映射、预处理与验证尚未完成",
      "model_version": null,
      "preprocessing_version": null
    },
    "factors": [],
    "support_entry_codes": [],
    "missing_items": [
      "分类规则未确认",
      "研究模型未适配"
    ],
    "questionnaire_version": "initial-draft01",
    "assessment_method_version": null,
    "generated_at": "2026-11-16T04:00:00Z",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "O-draft01",
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
    "code": "PROFILE_NOT_AVAILABLE",
    "message": "尚无可用画像，请完成明确评估"
  }
}
```

### O21 读取历史画像版本

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/profiles/{id}` |
| 维护方 / 入口 | O3 / 我的/复评历史 |
| 身份与患者范围 | 本人或profile:read，按画像归属核验 |
| 路径/查询/头/体 | 路径profile_id；查询/请求体无；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<Profile>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 历史结果与当时questionnaire/method/model版本一起返回；不以当前规则重新解释。 |
| 待实施验收（未执行） | 新复评不覆盖旧画像；跨患者ID被拒。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "profile_id": "profile-demo-001",
    "patient_id": "p-demo-001",
    "response_id": "response-demo-001",
    "status": "insufficient",
    "primary_type": null,
    "additional_types": [],
    "reported_behavior": "follows_plan",
    "cas": {
      "status": "unavailable",
      "value": null,
      "reason": "模型输入映射、预处理与验证尚未完成",
      "model_version": null,
      "preprocessing_version": null
    },
    "factors": [],
    "support_entry_codes": [],
    "missing_items": [
      "分类规则未确认",
      "研究模型未适配"
    ],
    "questionnaire_version": "initial-draft01",
    "assessment_method_version": null,
    "generated_at": "2026-11-16T04:00:00Z",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "O-draft01",
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
    "message": "画像不可访问或不存在"
  }
}
```

### O22 对指定已提交响应创建评估结果

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/profiles` |
| 维护方 / 入口 | O3 / 问卷结果/主动复评 |
| 身份与患者范围 | 本人或具有questionnaire:assist且获准完成本次评估的家人；后者待Q04 |
| 路径/查询/头/体 | 路径patient_id；查询无；JSON=ProfileCreateInput；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 201，Envelope<Profile>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 409 RESPONSE_NOT_SUBMITTED；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 输入快照、方法状态、结果和幂等记录关联保存；同响应同有效评估版本复用，方法变更创建新结果；无已确认规则时只描述/不足，CAS null；不得现场训练或付费LLM调用。 |
| 待实施验收（未执行） | draft不评估；未知不补零；未验证模型不输出精确指数；规则缺失清楚显示。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "profile_id": "profile-demo-001",
    "patient_id": "p-demo-001",
    "response_id": "response-demo-001",
    "status": "insufficient",
    "primary_type": null,
    "additional_types": [],
    "reported_behavior": "follows_plan",
    "cas": {
      "status": "unavailable",
      "value": null,
      "reason": "模型输入映射、预处理与验证尚未完成",
      "model_version": null,
      "preprocessing_version": null
    },
    "factors": [],
    "support_entry_codes": [],
    "missing_items": [
      "分类规则未确认",
      "研究模型未适配"
    ],
    "questionnaire_version": "initial-draft01",
    "assessment_method_version": null,
    "generated_at": "2026-11-16T04:00:00Z",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "O-draft01",
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
    "code": "RESPONSE_NOT_SUBMITTED",
    "message": "回答尚未正式提交"
  }
}
```

### O23 读取患者药品清单

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/medications` |
| 维护方 / 入口 | O4 / 用药管理/药品 |
| 身份与患者范围 | 本人或medication:read |
| 路径/查询/头/体 | 路径patient_id；查询cursor、limit；请求体无；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<List<Medication>>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读，按created_at、medication_id排序；不从药名推导处方。 |
| 待实施验收（未执行） | 切换患者清除旧清单；无资料与依赖失败分别处理。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "medication_id": "med-demo-001",
        "patient_id": "p-demo-001",
        "name": "演示药品甲（虚构）",
        "notes": null,
        "meta": {
          "created_at": "2026-11-16T04:00:00Z",
          "updated_at": "2026-11-16T04:00:00Z",
          "revision": 1,
          "contract_version": "O-draft01",
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
    "message": "药品清单不可访问"
  }
}
```

### O24 新增药品资料

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/medications` |
| 维护方 / 入口 | O4 / 用药管理/添加药品 |
| 身份与患者范围 | 本人或medication:edit |
| 路径/查询/头/体 | 路径patient_id；查询无；JSON=MedicationCreateInput；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 201，Envelope<Medication>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 422 INVALID_MEDICATION；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 药品资料和修订/幂等同事务；不自动创建正式计划/提醒；不同操作是否重名合并不猜，按用户明确条目保存。 |
| 待实施验收（未执行） | 同键同内容只一条；重名不自动合并另一药物；无剂量字段可越权改医嘱。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "medication_id": "med-demo-001",
    "patient_id": "p-demo-001",
    "name": "演示药品甲（虚构）",
    "notes": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "O-draft01",
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
    "code": "INVALID_MEDICATION",
    "message": "药品名称或备注不合法"
  }
}
```

### O25 纠正药品名称/备注

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `PATCH /api/v1/medications/{id}` |
| 维护方 / 入口 | O4 / 用药管理/编辑资料 |
| 身份与患者范围 | 本人或medication:edit，查资源患者归属 |
| 路径/查询/头/体 | 路径medication_id；查询无；JSON=MedicationPatch；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<Medication>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 409 REVISION_CONFLICT；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 至少修改name或notes；修订留存，旧计划保留名称快照；剂量/频次修改必须经A草稿→O确认，不在此接口接收。 |
| 待实施验收（未执行） | notes省略保持、null明确清空；新增dose_value字段422。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "medication_id": "med-demo-001",
    "patient_id": "p-demo-001",
    "name": "演示药品甲（虚构）",
    "notes": "虚构资料备注",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "O-draft01",
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
    "code": "REVISION_CONFLICT",
    "message": "药品资料已被更新"
  }
}
```

### O26 查看正式计划及版本历史

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/plans` |
| 维护方 / 入口 | O4 / 用药管理/计划/历史 |
| 身份与患者范围 | 本人或plan:read |
| 路径/查询/头/体 | 路径patient_id；查询cursor、limit；可选plan_id:ID O/N筛选；请求体无；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<List<PlanVersion>>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 503 PLAN_STORE_UNAVAILABLE；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读全部正式版本，按confirmed_at、plan_id、plan_version排序；A草稿不混入。 |
| 待实施验收（未执行） | 未确认草稿不出现；服务失败不伪装没有计划。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "plan_id": "plan-demo-001",
        "plan_version": 1,
        "patient_id": "p-demo-001",
        "status": "confirmed",
        "effective_from": "2026-11-16T00:00:00+08:00",
        "effective_until": null,
        "timezone": "Asia/Shanghai",
        "entries": [
          {
            "plan_entry_id": "entry-demo-001",
            "medication_id": "med-demo-001",
            "medication_name_snapshot": "演示药品甲（虚构）",
            "dose_value": "1",
            "dose_unit": "虚构单位",
            "start_date": "2026-11-16",
            "end_date": null,
            "schedule": {
              "kind": "daily",
              "times": [
                "08:00"
              ],
              "weekdays": []
            },
            "meal_requirement": null,
            "medical_notes": "仅为契约结构示例，不构成用药建议",
            "strict_timing": null,
            "min_interval_minutes": null,
            "source_file_ids": []
          }
        ],
        "source_draft_id": "draft-demo-001",
        "source_draft_revision": 1,
        "confirmed_by_account_id": "acct-demo-001",
        "confirmed_at": "2026-11-16T04:00:00Z",
        "is_confirmation_simulated": true,
        "meta": {
          "created_at": "2026-11-16T04:00:00Z",
          "updated_at": "2026-11-16T04:00:00Z",
          "revision": 1,
          "contract_version": "O-draft01",
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
    "code": "PLAN_STORE_UNAVAILABLE",
    "message": "计划存储暂不可用"
  }
}
```

### O27 读取指定正式计划完整版本

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/plans/{id}/versions/{version}` |
| 维护方 / 入口 | O4 / 计划核对/历史/今日安排 |
| 身份与患者范围 | 本人或plan:read；计划、患者、版本一致 |
| 路径/查询/头/体 | 路径plan_id:ID、version:Version；查询/请求体无；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<PlanVersion>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 404 PLAN_VERSION_NOT_FOUND；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读不可变版本与确认来源；superseded仍可按权限查历史，不冒充现行。 |
| 待实施验收（未执行） | 旧版引用可追溯；不同患者同编号不能串用。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "plan_id": "plan-demo-001",
    "plan_version": 1,
    "patient_id": "p-demo-001",
    "status": "confirmed",
    "effective_from": "2026-11-16T00:00:00+08:00",
    "effective_until": null,
    "timezone": "Asia/Shanghai",
    "entries": [
      {
        "plan_entry_id": "entry-demo-001",
        "medication_id": "med-demo-001",
        "medication_name_snapshot": "演示药品甲（虚构）",
        "dose_value": "1",
        "dose_unit": "虚构单位",
        "start_date": "2026-11-16",
        "end_date": null,
        "schedule": {
          "kind": "daily",
          "times": [
            "08:00"
          ],
          "weekdays": []
        },
        "meal_requirement": null,
        "medical_notes": "仅为契约结构示例，不构成用药建议",
        "strict_timing": null,
        "min_interval_minutes": null,
        "source_file_ids": []
      }
    ],
    "source_draft_id": "draft-demo-001",
    "source_draft_revision": 1,
    "confirmed_by_account_id": "acct-demo-001",
    "confirmed_at": "2026-11-16T04:00:00Z",
    "is_confirmation_simulated": true,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "O-draft01",
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
    "code": "PLAN_VERSION_NOT_FOUND",
    "message": "计划版本不可访问或不存在"
  }
}
```

### O28 核对并发布A草稿指定修订

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/plan-confirmations` |
| 维护方 / 入口 | O4，A2提供草稿/回写引用 / 用药管理/核对与确认 |
| 身份与患者范围 | 本人；plan:confirm家人可否确认待Q08，未确认前不放行 |
| 路径/查询/头/体 | 路径patient_id；查询无；JSON=PlanConfirmInput；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 201，Envelope<PlanVersion>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 409 DRAFT_REVISION_CONFLICT；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 核验A草稿属于患者且已提交指定修订，核对医嘱字段完整/无推断；同库发布版本、保存A正式引用、登记后续更新需求同事务；失败回滚，不留半发布。多药粒度/生效/替换未确认则拒绝相应发布，不自定；同草稿修订确认不重复发版。 |
| 待实施验收（未执行） | 新旧标签页并发确认最多一个有效版本；家人改confirmed=true不能越权；超时/依赖失败明确失败或待核，不伪称医院审核。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "plan_id": "plan-demo-001",
    "plan_version": 1,
    "patient_id": "p-demo-001",
    "status": "confirmed",
    "effective_from": "2026-11-16T00:00:00+08:00",
    "effective_until": null,
    "timezone": "Asia/Shanghai",
    "entries": [
      {
        "plan_entry_id": "entry-demo-001",
        "medication_id": "med-demo-001",
        "medication_name_snapshot": "演示药品甲（虚构）",
        "dose_value": "1",
        "dose_unit": "虚构单位",
        "start_date": "2026-11-16",
        "end_date": null,
        "schedule": {
          "kind": "daily",
          "times": [
            "08:00"
          ],
          "weekdays": []
        },
        "meal_requirement": null,
        "medical_notes": "仅为契约结构示例，不构成用药建议",
        "strict_timing": null,
        "min_interval_minutes": null,
        "source_file_ids": []
      }
    ],
    "source_draft_id": "draft-demo-001",
    "source_draft_revision": 1,
    "confirmed_by_account_id": "acct-demo-001",
    "confirmed_at": "2026-11-16T04:00:00Z",
    "is_confirmation_simulated": true,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "O-draft01",
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
    "code": "DRAFT_REVISION_CONFLICT",
    "message": "草稿或计划版本已变化，请重新核对"
  }
}
```

### O29 读取正式计划日程

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/dose-slots` |
| 维护方 / 入口 | O4业务，建议O规则/A保存 / 首页今日安排/用药管理 |
| 身份与患者范围 | 本人或plan:read；不隐含records:read |
| 路径/查询/头/体 | 路径patient_id；查询window_start:DateTime R/N、window_end:DateTime R/N、cursor/limit可选；请求体无；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<SlotWindow>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 409 SLOT_CONTRACT_NOT_READY；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读已明确生成的稳定时段，GET不隐式建表/发版；未确认生成规则时明确不可用。未来安排可展示，不等于A分母已纳入；服药状态另读A。 |
| 待实施验收（未执行） | 相同计划窗口重复读取ID稳定；多药不因同一时间自动合并；不把未来未点确认叫漏服。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "dose_slot_id": "slot-demo-001",
        "patient_id": "p-demo-001",
        "plan_id": "plan-demo-001",
        "plan_version": 1,
        "plan_entry_id": "entry-demo-001",
        "medication_id": "med-demo-001",
        "scheduled_at": "2026-11-16T08:00:00+08:00",
        "status": "active",
        "source_rule_version": "slot-rule-draft01",
        "is_simulated": true
      }
    ],
    "next_cursor": null,
    "window_start": "2026-11-16T00:00:00+08:00",
    "window_end": "2026-11-17T00:00:00+08:00"
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
    "code": "SLOT_CONTRACT_NOT_READY",
    "message": "时段生成或多药计数契约尚未确认"
  }
}
```

### O30 读取实际保存的提醒配置

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/reminder-preferences` |
| 维护方 / 入口 | O5 / 提醒/隐私设置 |
| 身份与患者范围 | 本人或reminder:read |
| 路径/查询/头/体 | 路径patient_id；查询/请求体无；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<ReminderPreferences>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 404 REMINDER_PREFERENCES_NOT_INITIALIZED；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 只读，不在GET时创建配置/启用通知；首次引导采用已确认默认展示，用户通过O31保存，或显式虚构初始化时建立；不能因GET宣称提醒已执行。 |
| 待实施验收（未执行） | 未初始化明确404；通知不支持时配置与能力分别显示。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "patient_id": "p-demo-001",
    "enabled": false,
    "channels": [
      "in_app"
    ],
    "sound_enabled": false,
    "vibration_enabled": false,
    "routine_mode": "regular",
    "anchors": [],
    "privacy_enabled": false,
    "custom_text": null,
    "privacy_windows": [],
    "repeat_interval_minutes": null,
    "max_repeats": 0,
    "snooze_minutes": null,
    "notify_family": false,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "O-draft01",
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
    "code": "REMINDER_PREFERENCES_NOT_INITIALIZED",
    "message": "尚未保存提醒设置"
  }
}
```

### O31 明确保存提醒和隐私偏好

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `PUT /api/v1/patients/{p}/reminder-preferences` |
| 维护方 / 入口 | O5，执行复用A7 / 提醒/隐私/作息设置 |
| 身份与患者范围 | 本人或reminder:write；notify_family还需患者有效共享同意 |
| 路径/查询/头/体 | 路径patient_id；查询无；JSON=ReminderPutInput；公共写入头；未列查询字段不接受 |
| 完整返回定义 | HTTP 200，Envelope<ReminderPreferences>；字段逐项引用字段表对应对象（含递归子对象、Meta和版本）；无未定义扩展字段 |
| 失败定义 | 本卡特例HTTP 422 UNSUPPORTED_REMINDER_CONFIGURATION；另继承公共错误定义 |
| 幂等/状态/事务/来源 | 首次expected_revision=0，后续匹配；配置修订与幂等结果同事务，登记A任务更新需求；不改scheduled_at；无真实返家感知则只用主动设置。未知医学约束时不自动偏移医嘱；无能力的渠道不能报告投递成功。 |
| 待实施验收（未执行） | 拒绝系统通知仍可站内；privacy不能泄露药病名；家人无notify:receive时不能开启通知；已确认任务停止重复由A后续验证。 另覆盖跨患者、同键重放/异内容冲突、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "patient_id": "p-demo-001",
    "enabled": false,
    "channels": [
      "in_app"
    ],
    "sound_enabled": false,
    "vibration_enabled": false,
    "routine_mode": "regular",
    "anchors": [],
    "privacy_enabled": false,
    "custom_text": null,
    "privacy_windows": [],
    "repeat_interval_minutes": null,
    "max_repeats": 0,
    "snooze_minutes": null,
    "notify_family": false,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "O-draft01",
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
    "code": "UNSUPPORTED_REMINDER_CONFIGURATION",
    "message": "渠道、频率或医学约束不支持该设置"
  }
}
```

## 3 待确认的状态机与非法操作清单

| 对象 | 建议合法流转 | 必须拒绝/保留的情形 |
| --- | --- | --- |
| 演示会话 | 明确选择→有效→退出/过期 | external降回demo；旧键复活登录；跨账号读退出回执 |
| 绑定码 | 创建→消费；或过期 | 并发多次消费；用码获得默认全健康权限；自己绑定自己 |
| 家庭关系 | active→revoked | revoked回active、恢复旧授权；需新关系重新确认 |
| 授权 | active→revoked/expired；重新授权留新事实 | 家人自授权、无确认扩权、已撤销权限的缓存重放 |
| 问卷 | draft→submitted | 直接写status、提交浮动修订、已提交原地编辑；改答新建response引用旧回答 |
| 画像 | 明确评估→独立结果；复评生成新profile | 无规则硬判分类、伪造CAS、收到C反馈自动覆写旧画像 |
| 正式计划 | 确认明确草稿修订→confirmed；新版本生效→旧版superseded | 上传即正式、客户端confirmed直接放行、静默修改旧版处方、并发重复发版 |
| 计划时段 | 依据已确认规则生成稳定引用 | 用GET临时生成不同ID、开盒代表所有药、未统一粒度便计算分母 |
| 提醒配置 | 显式保存新修订；启停/恢复留历史 | 作息适应改变医嘱、未知约束视为自由调整、未授权向家人发消息 |

本表新增状态与精确错误码均待确认，不表示已经冻结。计划取消/暂停、复杂疗程、监护替代、通知频率上限和令牌时长仍是开放问题；本轮不为其创建额外业务接口。

## 4 本轮结果与下一批入口

公共基础2卡、O31卡，共33张详细卡；A/B/C只在总目录列能力，本文件不扩展其字段/状态。所有验收均为待实现用例，没有执行应用接口、网页或数据库测试。本轮评审需结合范围目录Q01—Q12确认；确认后追加记录和冻结具体范围，再展开A，保持S00，不进入S01。

