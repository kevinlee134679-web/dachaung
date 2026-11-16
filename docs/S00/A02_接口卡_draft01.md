# S00 A批：41张接口卡（draft01）

2026-11-16，Asia/Shanghai；全部新增方案**待确认、未冻结、未实现**。字段版本A-draft01。完整字段表见A01_字段_draft01.md；范围、维护与AQ01—AQ14见A00。公共/O确认范围及排除项由docs/contracts/公共基础与O_v0.1_确认清单.md约束。

## 1 所有卡片继承的定义

每卡列出的T完整返回Envelope<T>，递归字段在A01和已确认公共/O表定义；List<T>固定items/next_cursor。示例不能替代字段表。路径和body不含可覆盖服务端身份/来源/模拟/质量/权限的字段。未列path/query/body视为无，未列JSON字段422。成功例子均为虚构结构，不是已执行证据；所有验收均未运行。

- 路径统一/api/v1；查询类型/R/O/可空/默认与范围逐项见A01第1节。专用medication/measurement路由固定类型，不接受客户端改event_kind。
- 网页JSON写入默认Cookie、X-CSRF-Token、Idempotency-Key、Content-Type:application/json；上传multipart例外；GET只Cookie。设备/服务/渠道独立身份适配，签名协议缺失的真实入口拒绝，演示身份不替代。AX-01新Scopes仍待A批确认，不已授权实施。
- 未登录401、授权不足403、跨患者资源404、格式/未知字段422、版本/内容/在途冲突409、大小413、类型415、依赖/存储失败503；API失败不回首页HTML或假空数据。具体错误码均本批建议。
- 幂等继承公共/O：同键同内容同业务资源，同键异内容409；处理在途409 OPERATION_IN_PROGRESS与Retry-After:1；完全回滚可原键重试；已提交稳定重放；副作用未知先查原执行。回执至少7天为本批建议，不改写旧事实。重新鉴权在重放之前，不能用旧回执读取已撤销健康数据。
- 来源唯一键建议=(patient_id,data_environment,source,可信设备或实际报告账号,source_event_id)；同来源号异内容409，不以文字相似/时间接近吞并不同来源；模型/设备/家属不能冒充本人。
- 同库事务覆盖业务、修订/有效指针、业务去重/幂等和失效登记；外部动作不在长写事务中做。文件采用本次临时文件受控完成/补偿，不误删其他文件。任何依赖未接入明确说明，不造真实联通。
- 来源、字段版本和模拟标记完整返回；O正式计划精确引用，A不发第二份计划。统计/摘要各来源更新时间固定。首版手动执行一次/刷新可复用，周期调度的具体B节点留后续确认。

## 2 接口卡

### A01 上传并保存文件

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/files` |
| 用途/维护/页面 | 上传并保存文件 / A2 / 用药管理/资料上传 |
| 身份/患者范围 | 本人或files:write |
| 路径/查询/头/体 | path patient_id；query无；multipart=FileUploadInput；Cookie/CSRF/Idempotency-Key；Content-Type=multipart/form-data；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<File>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 413 FILE_TOO_LARGE；另继承公共错误 |
| 幂等/状态/事务/来源 | 校验类型/大小/权限→临时写→元信息与幂等提交→受控文件完成；失败补偿仅本次临时文件；重复source_event_id同内容返回原File，异内容409。保存不是识别或正式计划。 |
| 待实施验收 | 重复上传不重复有效事实；跨患者拒绝；保存中断不伪称成功。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "file_id": "file-demo-001",
    "patient_id": "p-demo-001",
    "source_event_id": "upload-demo-001",
    "original_name": "虚构结构示例.png",
    "media_type": "image/png",
    "size_bytes": 68,
    "sha256": "017adf2aaa2cc40c7404e7131ad0f1766b993ee5924b0913ee667d6b58a641ba",
    "status": "saved",
    "source": "manual_upload",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
      "is_simulated": true
    }
  },
  "error": null
}
```

失败结构示例（HTTP 413）：

```json
{
  "request_id": "req-example-002",
  "status": "error",
  "data": null,
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "文件超过本批建议的10MiB"
  }
}
```

### A02 文件列表

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/files` |
| 用途/维护/页面 | 文件列表 / A2 / 资料管理 |
| 身份/患者范围 | 本人或files:read |
| 路径/查询/头/体 | path patient_id；query cursor/limit；无body；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<File>>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 503 FILE_STORE_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读，created_at/file_id排序；不返回物理路径；真正无数据才items=[]。 |
| 待实施验收 | 家人仅有medication:read不能读取病历文件列表。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "file_id": "file-demo-001",
        "patient_id": "p-demo-001",
        "source_event_id": "upload-demo-001",
        "original_name": "虚构结构示例.png",
        "media_type": "image/png",
        "size_bytes": 68,
        "sha256": "017adf2aaa2cc40c7404e7131ad0f1766b993ee5924b0913ee667d6b58a641ba",
        "status": "saved",
        "source": "manual_upload",
        "meta": {
          "created_at": "2026-11-16T04:00:00Z",
          "updated_at": "2026-11-16T04:00:00Z",
          "revision": 1,
          "contract_version": "A-draft01",
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
    "code": "FILE_STORE_UNAVAILABLE",
    "message": "文件元信息存储暂不可用"
  }
}
```

### A03 文件元信息

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/files/{id}` |
| 用途/维护/页面 | 文件元信息 / A2 / 资料详情 |
| 身份/患者范围 | 本人或files:read；按file_id核验患者 |
| 路径/查询/头/体 | path file_id；query/body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<File>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读精确文件；保存失败状态不被显示为可读取完成。 |
| 待实施验收 | 伪造其他患者file_id拒绝且不泄露存在性。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "file_id": "file-demo-001",
    "patient_id": "p-demo-001",
    "source_event_id": "upload-demo-001",
    "original_name": "虚构结构示例.png",
    "media_type": "image/png",
    "size_bytes": 68,
    "sha256": "017adf2aaa2cc40c7404e7131ad0f1766b993ee5924b0913ee667d6b58a641ba",
    "status": "saved",
    "source": "manual_upload",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
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
    "message": "文件不可访问或不存在"
  }
}
```

### A04 授权读取原文件

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/files/{id}/content` |
| 用途/维护/页面 | 授权读取原文件 / A2 / 资料详情/查看原件 |
| 身份/患者范围 | 本人或files:read；每次读取重验 |
| 路径/查询/头/体 | path file_id；query/body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<FileContent>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 503 FILE_CONTENT_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 使用Envelope JSON+base64保持四字段；不返回服务器路径或公开URL；解码字节SHA256与File一致；不得把下载失败回退成网页。 |
| 待实施验收 | 撤销授权后原入口失效；原始文件完整性可核对。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "file_id": "file-demo-001",
    "media_type": "image/png",
    "content_encoding": "base64",
    "content_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXxkAAAAASUVORK5CYII=",
    "sha256": "017adf2aaa2cc40c7404e7131ad0f1766b993ee5924b0913ee667d6b58a641ba"
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
    "code": "FILE_CONTENT_UNAVAILABLE",
    "message": "原文件内容暂不可读取"
  }
}
```

### A05 新建人工结构化草稿

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/drafts` |
| 用途/维护/页面 | 新建人工结构化草稿 / A2 / 用药管理/人工录入 |
| 身份/患者范围 | 本人或drafts:write；药品/来源文件各自需访问权 |
| 路径/查询/头/体 | path patient_id；query无；JSON=DraftCreateInput；公共网页写入头；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<Draft>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 422 INVALID_DRAFT；另继承公共错误 |
| 幂等/状态/事务/来源 | 新建editing和content_revision=1；临时行ID不是正式计划条目；同患者文件/药品校验，未填字段保留null；不创建正式计划/任务。 |
| 待实施验收 | 纯手工无文件可保存；未确认内容不计入统计。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "draft_id": "draft-demo-001",
    "patient_id": "p-demo-001",
    "source": "manual",
    "source_file_ids": [],
    "entries": [
      {
        "draft_entry_id": "draft-row-demo-001",
        "medication_id": "med-demo-001",
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
        "medical_notes": "仅作字段示例，不构成用药建议",
        "strict_timing": null,
        "min_interval_minutes": null,
        "source_file_ids": []
      }
    ],
    "content_revision": 1,
    "status": "editing",
    "submission_id": null,
    "submitted_revision": null,
    "formal_plan": null,
    "return_reason": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
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
    "code": "INVALID_DRAFT",
    "message": "草稿引用或字段不合法"
  }
}
```

### A06 草稿详情与确认进度

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/drafts/{id}` |
| 用途/维护/页面 | 草稿详情与确认进度 / A2 / 人工核对/保存进度 |
| 身份/患者范围 | 本人或drafts:read；来源文件另查files:read |
| 路径/查询/头/体 | path draft_id；query/body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Draft>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读当前资源修订及内容修订；confirmed时引用O真实PlanRef，不把pending当已发布。 |
| 待实施验收 | 内容号与资源meta.revision显示清楚，不查最新内容冒充提交内容。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "draft_id": "draft-demo-001",
    "patient_id": "p-demo-001",
    "source": "manual",
    "source_file_ids": [],
    "entries": [
      {
        "draft_entry_id": "draft-row-demo-001",
        "medication_id": "med-demo-001",
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
        "medical_notes": "仅作字段示例，不构成用药建议",
        "strict_timing": null,
        "min_interval_minutes": null,
        "source_file_ids": []
      }
    ],
    "content_revision": 1,
    "status": "editing",
    "submission_id": null,
    "submitted_revision": null,
    "formal_plan": null,
    "return_reason": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
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

### A07 保存新草稿内容修订

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `PUT /api/v1/drafts/{id}` |
| 用途/维护/页面 | 保存新草稿内容修订 / A2 / 人工核对/修改 |
| 身份/患者范围 | 本人或drafts:write；只editing/returned可写 |
| 路径/查询/头/体 | path draft_id；query无；JSON=DraftPutInput；公共网页写入头；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Draft>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 DRAFT_LOCKED；另继承公共错误 |
| 幂等/状态/事务/来源 | expected_revision匹配资源修订，完整内容新增content_revision；returned编辑后回editing；pending/confirmed拒绝，保留已提交历史。 |
| 待实施验收 | 旧页覆盖409；未确认医嘱不自动补全；修改不能改患者归属。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "draft_id": "draft-demo-001",
    "patient_id": "p-demo-001",
    "source": "manual",
    "source_file_ids": [],
    "entries": [
      {
        "draft_entry_id": "draft-row-demo-001",
        "medication_id": "med-demo-001",
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
        "medical_notes": "仅作字段示例，不构成用药建议",
        "strict_timing": null,
        "min_interval_minutes": null,
        "source_file_ids": []
      }
    ],
    "content_revision": 2,
    "status": "editing",
    "submission_id": null,
    "submitted_revision": null,
    "formal_plan": null,
    "return_reason": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "A-draft01",
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
    "code": "DRAFT_LOCKED",
    "message": "草稿待确认或已正式确认，不能原地覆盖"
  }
}
```

### A08 提交确定内容等待O确认

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/drafts/{id}/submit` |
| 用途/维护/页面 | 提交确定内容等待O确认 / A2 / 核对资料/提交 |
| 身份/患者范围 | 本人或drafts:submit；不等于O plan:confirm |
| 路径/查询/头/体 | path draft_id；query无；JSON=DraftSubmitInput；公共网页写入头；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Draft>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 DRAFT_CONTENT_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | editing/returned→pending_confirmation；保存submission_id与content_revision快照；提交不发布计划、不通知医院；O28后续同库确认才写formal_plan。O明确退回结果通过可信内部服务登记returned及原因。 |
| 待实施验收 | 同修订重复提交只一条有效提交；超时保持待确认/未知，不假装审核完成。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "draft_id": "draft-demo-001",
    "patient_id": "p-demo-001",
    "source": "manual",
    "source_file_ids": [],
    "entries": [
      {
        "draft_entry_id": "draft-row-demo-001",
        "medication_id": "med-demo-001",
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
        "medical_notes": "仅作字段示例，不构成用药建议",
        "strict_timing": null,
        "min_interval_minutes": null,
        "source_file_ids": []
      }
    ],
    "content_revision": 1,
    "status": "pending_confirmation",
    "submission_id": "submission-demo-001",
    "submitted_revision": 1,
    "formal_plan": null,
    "return_reason": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "A-draft01",
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
    "code": "DRAFT_CONTENT_CONFLICT",
    "message": "草稿内容修订已变化"
  }
}
```

### A09 草稿及提交列表

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/drafts` |
| 用途/维护/页面 | 草稿及提交列表 / A2 / 用药管理/待核对 |
| 身份/患者范围 | 本人或drafts:read |
| 路径/查询/头/体 | path patient_id；query cursor/limit、status O/N=不筛选；无body；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<Draft>>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 503 DRAFT_STORE_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读，updated_at/draft_id排序；待确认与正式计划分开。 |
| 待实施验收 | 依赖失败不变空清单；切换患者不串草稿。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "draft_id": "draft-demo-001",
        "patient_id": "p-demo-001",
        "source": "manual",
        "source_file_ids": [],
        "entries": [
          {
            "draft_entry_id": "draft-row-demo-001",
            "medication_id": "med-demo-001",
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
            "medical_notes": "仅作字段示例，不构成用药建议",
            "strict_timing": null,
            "min_interval_minutes": null,
            "source_file_ids": []
          }
        ],
        "content_revision": 1,
        "status": "editing",
        "submission_id": null,
        "submitted_revision": null,
        "formal_plan": null,
        "return_reason": null,
        "meta": {
          "created_at": "2026-11-16T04:00:00Z",
          "updated_at": "2026-11-16T04:00:00Z",
          "revision": 1,
          "contract_version": "A-draft01",
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
    "code": "DRAFT_STORE_UNAVAILABLE",
    "message": "草稿列表暂不可用"
  }
}
```

### A10 接收实际身份的服药报告

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/medication-events` |
| 用途/维护/页面 | 接收实际身份的服药报告 / A2/A4 / 首页/核心用药确认 |
| 身份/患者范围 | 本人或records:report；家人只能family_report |
| 路径/查询/头/体 | path patient_id；query无；JSON=MedicationEventInput；公共网页写入头；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<SourceEvent>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 SOURCE_EVENT_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 身份生成evidence_type/reporter，环境决定模拟标记；原始事件、初始修订、去重和质量/统计失效需求同事务；quality可先pending_validation，不等于已计数。显式时段仍要检查归属。 |
| 待实施验收 | 同表单重试一事实；家人报告taken不进入本人已服；开盒另来源可并存。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "event_id": "event-demo-001",
    "patient_id": "p-demo-001",
    "event_kind": "medication",
    "source": "manual",
    "source_event_id": "report-demo-001",
    "evidence_type": "self_report",
    "occurred_at": "2026-11-16T03:58:00Z",
    "received_at": "2026-11-16T04:00:00Z",
    "reporter_account_id": "acct-demo-001",
    "device_id": null,
    "state": "effective",
    "payload": {
      "reported_status": "taken",
      "observation": null,
      "medication_id": "med-demo-001",
      "dose_slot_id": "slot-demo-001",
      "plan_ref": {
        "plan_id": "plan-demo-001",
        "plan_version": 1
      },
      "raw_text": "虚构本人报告示例"
    },
    "quality": {
      "event_id": "event-demo-001",
      "event_revision": 1,
      "status": "valid",
      "issues": [],
      "normalized_measurement": null,
      "processing_version": "quality-draft01",
      "processed_at": "2026-11-16T04:00:00Z"
    },
    "link_status": "matched",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
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
    "code": "SOURCE_EVENT_CONFLICT",
    "message": "同一来源事件号对应不同内容"
  }
}
```

### A11 服药证据列表

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/medication-events` |
| 用途/维护/页面 | 服药证据列表 / A2/A4 / 用药记录/报告 |
| 身份/患者范围 | 本人或records:read |
| 路径/查询/头/体 | path patient_id；query window_start/end:DateTime R/N（≤31天），data_environment:demo/real R/N，as_of:DateTime O/N=服务器当前时间、cursor/limit、state O/N=effective；无body；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<SourceEvent>>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读当前有效视图；按occurred_at/event_id排序；state=all需同等权限；发生时间与首次接收分开。 |
| 待实施验收 | 迟到事件仍在原发生窗口；撤销证据不继续计数。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "event_id": "event-demo-001",
        "patient_id": "p-demo-001",
        "event_kind": "medication",
        "source": "manual",
        "source_event_id": "report-demo-001",
        "evidence_type": "self_report",
        "occurred_at": "2026-11-16T03:58:00Z",
        "received_at": "2026-11-16T04:00:00Z",
        "reporter_account_id": "acct-demo-001",
        "device_id": null,
        "state": "effective",
        "payload": {
          "reported_status": "taken",
          "observation": null,
          "medication_id": "med-demo-001",
          "dose_slot_id": "slot-demo-001",
          "plan_ref": {
            "plan_id": "plan-demo-001",
            "plan_version": 1
          },
          "raw_text": "虚构本人报告示例"
        },
        "quality": {
          "event_id": "event-demo-001",
          "event_revision": 1,
          "status": "valid",
          "issues": [],
          "normalized_measurement": null,
          "processing_version": "quality-draft01",
          "processed_at": "2026-11-16T04:00:00Z"
        },
        "link_status": "matched",
        "meta": {
          "created_at": "2026-11-16T04:00:00Z",
          "updated_at": "2026-11-16T04:00:00Z",
          "revision": 1,
          "contract_version": "A-draft01",
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
    "message": "记录不可访问"
  }
}
```

### A12 服药证据精确详情

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/medication-events/{id}` |
| 用途/维护/页面 | 服药证据精确详情 / A2/A4 / 记录详情/待复核 |
| 身份/患者范围 | 本人或records:read；event_kind必须medication |
| 路径/查询/头/体 | path event_id；query/body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<SourceEvent>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 返回当前修订与来源/质量/关联状态；历史走A18；不能把measurement ID放该路由。 |
| 待实施验收 | 本人报告和开盒保留原来源，缺记录不当未服。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "event_id": "event-demo-001",
    "patient_id": "p-demo-001",
    "event_kind": "medication",
    "source": "manual",
    "source_event_id": "report-demo-001",
    "evidence_type": "self_report",
    "occurred_at": "2026-11-16T03:58:00Z",
    "received_at": "2026-11-16T04:00:00Z",
    "reporter_account_id": "acct-demo-001",
    "device_id": null,
    "state": "effective",
    "payload": {
      "reported_status": "taken",
      "observation": null,
      "medication_id": "med-demo-001",
      "dose_slot_id": "slot-demo-001",
      "plan_ref": {
        "plan_id": "plan-demo-001",
        "plan_version": 1
      },
      "raw_text": "虚构本人报告示例"
    },
    "quality": {
      "event_id": "event-demo-001",
      "event_revision": 1,
      "status": "valid",
      "issues": [],
      "normalized_measurement": null,
      "processing_version": "quality-draft01",
      "processed_at": "2026-11-16T04:00:00Z"
    },
    "link_status": "matched",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
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
    "message": "服药证据不可访问或不存在"
  }
}
```

### A13 接收手动指标与缺失说明

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/measurements` |
| 用途/维护/页面 | 接收手动指标与缺失说明 / A2/A4 / 用药管理/指标录入 |
| 身份/患者范围 | 本人或measurements:write |
| 路径/查询/头/体 | path patient_id；query无；JSON=MeasurementInput；公共网页写入头；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<SourceEvent>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 422 INVALID_MEASUREMENT；另继承公共错误 |
| 幂等/状态/事务/来源 | 来源去重与初始修订同事务；value=null必须missing_reason；未知单位不猜，保存原值并needs_review；心理量表/心理分数不在此接口临时生成。 |
| 待实施验收 | 0与null不同；无时区拒绝；未知单位不伪变正常单位。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "event_id": "measurement-demo-001",
    "patient_id": "p-demo-001",
    "event_kind": "measurement",
    "source": "manual",
    "source_event_id": "measure-source-demo-001",
    "evidence_type": null,
    "occurred_at": "2026-11-16T03:58:00Z",
    "received_at": "2026-11-16T04:00:00Z",
    "reporter_account_id": "acct-demo-001",
    "device_id": null,
    "state": "effective",
    "payload": {
      "metric_code": "step_count",
      "value": 4500,
      "unit": "count",
      "method_code": "manual_entry",
      "missing_reason": null
    },
    "quality": {
      "event_id": "measurement-demo-001",
      "event_revision": 1,
      "status": "valid",
      "issues": [],
      "normalized_measurement": {
        "metric_code": "step_count",
        "value": 4500,
        "unit": "count",
        "method_code": "manual_entry",
        "missing_reason": null
      },
      "processing_version": "quality-draft01",
      "processed_at": "2026-11-16T04:00:00Z"
    },
    "link_status": "not_applicable",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
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
    "code": "INVALID_MEASUREMENT",
    "message": "指标值、单位、时间或缺失原因不合法"
  }
}
```

### A14 指标事件列表

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/measurements` |
| 用途/维护/页面 | 指标事件列表 / A2/A4 / 指标记录 |
| 身份/患者范围 | 本人或measurements:read |
| 路径/查询/头/体 | path patient_id；query window_start/end:DateTime R/N（≤31天），data_environment:demo/real R/N，as_of:DateTime O/N=服务器当前时间、cursor/limit、metric_code O/N、state O/N=effective；无body；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<SourceEvent>>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 503 MEASUREMENT_STORE_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 按实际occurred_at/event_id排序，保留原值/单位和质量；列表不按网页采样时间猜测补齐。 |
| 待实施验收 | 缺失采集记录可查，趋势不填0；未接设备不伪称同步。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "event_id": "measurement-demo-001",
        "patient_id": "p-demo-001",
        "event_kind": "measurement",
        "source": "manual",
        "source_event_id": "measure-source-demo-001",
        "evidence_type": null,
        "occurred_at": "2026-11-16T03:58:00Z",
        "received_at": "2026-11-16T04:00:00Z",
        "reporter_account_id": "acct-demo-001",
        "device_id": null,
        "state": "effective",
        "payload": {
          "metric_code": "step_count",
          "value": 4500,
          "unit": "count",
          "method_code": "manual_entry",
          "missing_reason": null
        },
        "quality": {
          "event_id": "measurement-demo-001",
          "event_revision": 1,
          "status": "valid",
          "issues": [],
          "normalized_measurement": {
            "metric_code": "step_count",
            "value": 4500,
            "unit": "count",
            "method_code": "manual_entry",
            "missing_reason": null
          },
          "processing_version": "quality-draft01",
          "processed_at": "2026-11-16T04:00:00Z"
        },
        "link_status": "not_applicable",
        "meta": {
          "created_at": "2026-11-16T04:00:00Z",
          "updated_at": "2026-11-16T04:00:00Z",
          "revision": 1,
          "contract_version": "A-draft01",
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
    "code": "MEASUREMENT_STORE_UNAVAILABLE",
    "message": "指标存储暂不可用"
  }
}
```

### A15 指标原来源与质量

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/measurements/{id}` |
| 用途/维护/页面 | 指标原来源与质量 / A2/A4 / 指标详情 |
| 身份/患者范围 | 本人或measurements:read；event_kind必须measurement |
| 路径/查询/头/体 | path event_id；query/body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<SourceEvent>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读有效修订；标准化结果在quality，原修订A18可追溯。 |
| 待实施验收 | 跨患者和错误种类ID拒绝；不隐藏单位问题。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "event_id": "measurement-demo-001",
    "patient_id": "p-demo-001",
    "event_kind": "measurement",
    "source": "manual",
    "source_event_id": "measure-source-demo-001",
    "evidence_type": null,
    "occurred_at": "2026-11-16T03:58:00Z",
    "received_at": "2026-11-16T04:00:00Z",
    "reporter_account_id": "acct-demo-001",
    "device_id": null,
    "state": "effective",
    "payload": {
      "metric_code": "step_count",
      "value": 4500,
      "unit": "count",
      "method_code": "manual_entry",
      "missing_reason": null
    },
    "quality": {
      "event_id": "measurement-demo-001",
      "event_revision": 1,
      "status": "valid",
      "issues": [],
      "normalized_measurement": {
        "metric_code": "step_count",
        "value": 4500,
        "unit": "count",
        "method_code": "manual_entry",
        "missing_reason": null
      },
      "processing_version": "quality-draft01",
      "processed_at": "2026-11-16T04:00:00Z"
    },
    "link_status": "not_applicable",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
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
    "message": "指标不可访问或不存在"
  }
}
```

### A16 追加经过授权的更正

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/events/{id}/corrections` |
| 用途/维护/页面 | 追加经过授权的更正 / A4 / 记录详情/更正 |
| 身份/患者范围 | 本人可更正本人手动记录；家人需records:correct且仅自己的报告；设备证据仅受控复核身份 |
| 路径/查询/头/体 | path event_id；query无；JSON=CorrectionInput；公共写入头；还需原事件类型的读写权限；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<SourceEvent>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 REVISION_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 不可变旧修订→新correction；同库保存更正原因/操作者、有效指针和旧新窗口失效；原patient/source/source_event_id/received_at不变。撤销后的恢复规则未确认，不隐式复活。 |
| 待实施验收 | 旧修订仍可查；更正时间同时影响旧新统计；同键不重复新增修订。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "event_id": "event-demo-001",
    "patient_id": "p-demo-001",
    "event_kind": "medication",
    "source": "manual",
    "source_event_id": "report-demo-001",
    "evidence_type": "self_report",
    "occurred_at": "2026-11-16T03:58:00Z",
    "received_at": "2026-11-16T04:00:00Z",
    "reporter_account_id": "acct-demo-001",
    "device_id": null,
    "state": "effective",
    "payload": {
      "reported_status": "taken",
      "observation": null,
      "medication_id": "med-demo-001",
      "dose_slot_id": "slot-demo-001",
      "plan_ref": {
        "plan_id": "plan-demo-001",
        "plan_version": 1
      },
      "raw_text": "虚构更正报告示例"
    },
    "quality": {
      "event_id": "event-demo-001",
      "event_revision": 2,
      "status": "pending_validation",
      "issues": [],
      "normalized_measurement": null,
      "processing_version": null,
      "processed_at": null
    },
    "link_status": "matched",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "A-draft01",
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
    "message": "原事件有效修订已变化"
  }
}
```

### A17 撤销当前有效证据

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/events/{id}/withdrawals` |
| 用途/维护/页面 | 撤销当前有效证据 / A4 / 记录详情/撤销 |
| 身份/患者范围 | 同A16更正权限，按实际来源限制 |
| 路径/查询/头/体 | path event_id；query无；JSON=WithdrawalInput；公共写入头；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<SourceEvent>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 EVENT_ALREADY_WITHDRAWN；另继承公共错误 |
| 幂等/状态/事务/来源 | effective→withdrawn，新建withdrawal修订并登记重算，不删除旧依据；同键重放原撤销，新的重复操作不另增有效事实。 |
| 待实施验收 | 撤销不清空历史；统计和摘要不继续引用失效证据。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "event_id": "event-demo-001",
    "patient_id": "p-demo-001",
    "event_kind": "medication",
    "source": "manual",
    "source_event_id": "report-demo-001",
    "evidence_type": "self_report",
    "occurred_at": "2026-11-16T03:58:00Z",
    "received_at": "2026-11-16T04:00:00Z",
    "reporter_account_id": "acct-demo-001",
    "device_id": null,
    "state": "withdrawn",
    "payload": {
      "reported_status": "taken",
      "observation": null,
      "medication_id": "med-demo-001",
      "dose_slot_id": "slot-demo-001",
      "plan_ref": {
        "plan_id": "plan-demo-001",
        "plan_version": 1
      },
      "raw_text": "虚构本人报告示例"
    },
    "quality": {
      "event_id": "event-demo-001",
      "event_revision": 2,
      "status": "valid",
      "issues": [],
      "normalized_measurement": null,
      "processing_version": "quality-draft01",
      "processed_at": "2026-11-16T04:00:00Z"
    },
    "link_status": "matched",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "A-draft01",
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
    "code": "EVENT_ALREADY_WITHDRAWN",
    "message": "事件已撤销或修订已变化"
  }
}
```

### A18 原始及更正修订历史

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/events/{id}/revisions` |
| 用途/维护/页面 | 原始及更正修订历史 / A4 / 记录来源/更正历史 |
| 身份/患者范围 | 需对应records:read或measurements:read，受限来源不能绕过 |
| 路径/查询/头/体 | path event_id；query cursor/limit；body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<EventRevision>>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 按revision递增；original和correction/withdrawal分别保留，不把处理规则重跑当新患者报告。 |
| 待实施验收 | 更正/撤销后原字节依据仍能追溯；不跨患者。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "event_id": "event-demo-001",
        "revision": 1,
        "change_kind": "original",
        "occurred_at": "2026-11-16T03:58:00Z",
        "payload": {
          "reported_status": "taken",
          "observation": null,
          "medication_id": "med-demo-001",
          "dose_slot_id": "slot-demo-001",
          "plan_ref": {
            "plan_id": "plan-demo-001",
            "plan_version": 1
          },
          "raw_text": "虚构本人报告示例"
        },
        "reason": null,
        "replaces_revision": null,
        "actor_account_id": "acct-demo-001",
        "created_at": "2026-11-16T04:00:00Z",
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
    "message": "修订历史不可访问"
  }
}
```

### A19 质量状态查询

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/events/{id}/quality` |
| 用途/维护/页面 | 质量状态查询 / A4 / 记录详情/质量说明 |
| 身份/患者范围 | 需对应事件读取权限 |
| 路径/查询/头/体 | path event_id；query/body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Quality>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 503 QUALITY_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 读取精确有效修订质量，状态与link_status分开；处理失败附原因，不说明患者临床异常。 |
| 待实施验收 | valid不显示为服药已证实；未知单位needs_review。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "event_id": "event-demo-001",
    "event_revision": 1,
    "status": "valid",
    "issues": [],
    "normalized_measurement": null,
    "processing_version": "quality-draft01",
    "processed_at": "2026-11-16T04:00:00Z"
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
    "code": "QUALITY_UNAVAILABLE",
    "message": "质量处理状态暂不可查询"
  }
}
```

### A20 显式重跑已注册清洗规则

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/events/{id}/reprocess` |
| 用途/维护/页面 | 显式重跑已注册清洗规则 / A4 / 独立演示控制台/可信模块 |
| 身份/患者范围 | 受控数据维护身份，非任意患者触发内部命令 |
| 路径/查询/头/体 | path event_id；query无；JSON=ReprocessInput；可信服务认证或本地管理Cookie/CSRF；Idempotency-Key；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Quality>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 PROCESSING_VERSION_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 锁定输入修订与规则快照；不持长写锁做外部调用；重复处理不重复事实，失败processing_failed；变化登记A6/A5更新。 |
| 待实施验收 | 相同输入规则重放不增修订；不允许请求指定任意代码。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "event_id": "event-demo-001",
    "event_revision": 1,
    "status": "valid",
    "issues": [],
    "normalized_measurement": null,
    "processing_version": "quality-draft01",
    "processed_at": "2026-11-16T04:00:00Z"
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
    "code": "PROCESSING_VERSION_CONFLICT",
    "message": "事件修订已变化，请核对后重处理"
  }
}
```

### A21 查询设备绑定

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/device-bindings` |
| 用途/维护/页面 | 查询设备绑定 / A3/O / 我的/设备接入状态 |
| 身份/患者范围 | 本人或devices:manage |
| 路径/查询/头/体 | path patient_id；query cursor/limit；body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<DeviceBinding>>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读绑定元信息，不返回设备凭据；按bound_at/binding_id排序。 |
| 待实施验收 | 显示模拟/真实来源，未接入不伪称在线。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "binding_id": "device-binding-demo-001",
        "device_id": "device-demo-001",
        "patient_id": "p-demo-001",
        "source": "box",
        "status": "active",
        "bound_at": "2026-11-16T04:00:00Z",
        "revoked_at": null,
        "meta": {
          "created_at": "2026-11-16T04:00:00Z",
          "updated_at": "2026-11-16T04:00:00Z",
          "revision": 1,
          "contract_version": "A-draft01",
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
    "message": "设备关联不可访问"
  }
}
```

### A22 关联已可信注册设备

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/device-bindings` |
| 用途/维护/页面 | 关联已可信注册设备 / 建议A3，O核验本人授权 / 我的/设备绑定 |
| 身份/患者范围 | 仅患者本人或明确配置的可信维护身份；家人是否可绑定仍不默认允许 |
| 路径/查询/头/体 | path patient_id；query无；JSON=DeviceBindingInput；公共写入头；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<DeviceBinding>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 DEVICE_BINDING_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 可信设备身份预先注册；同库校验患者确认和设备有效绑定；客户端body.device_id不创造可信设备。真实认证协议未接入时拒绝真实绑定。 |
| 待实施验收 | 未注册设备不能写患者数据；并发绑定不串患者。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "binding_id": "device-binding-demo-001",
    "device_id": "device-demo-001",
    "patient_id": "p-demo-001",
    "source": "box",
    "status": "active",
    "bound_at": "2026-11-16T04:00:00Z",
    "revoked_at": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
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
    "code": "DEVICE_BINDING_CONFLICT",
    "message": "设备未可信注册或已有冲突绑定"
  }
}
```

### A23 撤销设备关联

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/device-bindings/{id}/revoke` |
| 用途/维护/页面 | 撤销设备关联 / A3/O / 设备管理 |
| 身份/患者范围 | 本人或获准devices:manage；需重验绑定归属 |
| 路径/查询/头/体 | path binding_id；query无；JSON=公共O的RevokeInput；公共写入头；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<DeviceBinding>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 REVISION_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | active→revoked并留审计，后续接收/任务重查；历史事件保留，不因解绑改历史来源。 |
| 待实施验收 | 解绑后新上传拒绝，晚到回调不恢复绑定。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "binding_id": "device-binding-demo-001",
    "device_id": "device-demo-001",
    "patient_id": "p-demo-001",
    "source": "box",
    "status": "revoked",
    "bound_at": "2026-11-16T04:00:00Z",
    "revoked_at": "2026-11-16T04:00:00Z",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "A-draft01",
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
    "message": "设备绑定已变化"
  }
}
```

### A24 可信设备统一接收

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/integrations/device-events` |
| 用途/维护/页面 | 可信设备统一接收 / A3/A4 / 设备适配，不是患者表单 |
| 身份/患者范围 | 独立设备认证/签名适配，主体必须匹配device_id及当前授权绑定 |
| 路径/查询/头/体 | path/query无；JSON=DeviceEventInput；Idempotency-Key；Content-Type JSON；可信设备认证头由接入协议确认，不用Cookie冒充；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<SourceEvent>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 403 DEVICE_NOT_AUTHORIZED；另继承公共错误 |
| 幂等/状态/事务/来源 | 患者从可信有效绑定推导；设备协议→同一事件接收→质量，不建第二套原始事实；同来源事件号冲突409；真实依赖缺失503，不退模拟。 |
| 待实施验收 | 药盒仍box_opening；重传一事实；迟到保存实际occurred_at。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "event_id": "box-event-demo-001",
    "patient_id": "p-demo-001",
    "event_kind": "medication",
    "source": "box",
    "source_event_id": "box-source-demo-001",
    "evidence_type": "box_opening",
    "occurred_at": "2026-11-16T03:58:00Z",
    "received_at": "2026-11-16T04:00:00Z",
    "reporter_account_id": null,
    "device_id": "device-demo-001",
    "state": "effective",
    "payload": {
      "reported_status": null,
      "observation": "box_opened",
      "medication_id": "med-demo-001",
      "dose_slot_id": "slot-demo-001",
      "plan_ref": {
        "plan_id": "plan-demo-001",
        "plan_version": 1
      },
      "raw_text": null
    },
    "quality": {
      "event_id": "box-event-demo-001",
      "event_revision": 1,
      "status": "valid",
      "issues": [],
      "normalized_measurement": null,
      "processing_version": "quality-draft01",
      "processed_at": "2026-11-16T04:00:00Z"
    },
    "link_status": "matched",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
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
    "code": "DEVICE_NOT_AUTHORIZED",
    "message": "设备身份、患者绑定或授权无效"
  }
}
```

### A25 固定编号模拟器入口

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/demo/device-events` |
| 用途/维护/页面 | 固定编号模拟器入口 / A3 / 独立演示控制台 |
| 身份/患者范围 | 仅demo管理白名单、虚构患者与模拟设备 |
| 路径/查询/头/体 | path/query无；JSON=DemoDeviceInput；管理Cookie/CSRF/Idempotency-Key；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<SourceEvent>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 403 DEMO_DISABLED；另继承公共错误 |
| 幂等/状态/事务/来源 | 固定scenario_run_id派生同一来源号，重放复用A24共同接收/清洗能力；根据场景可明确失败；不得把is_simulated设false。 |
| 待实施验收 | duplicate不改计数；late_upload不挪日；unbound拒绝；unknown_unit需复核。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "event_id": "box-event-demo-001",
    "patient_id": "p-demo-001",
    "event_kind": "medication",
    "source": "box",
    "source_event_id": "box-source-demo-001",
    "evidence_type": "box_opening",
    "occurred_at": "2026-11-16T03:58:00Z",
    "received_at": "2026-11-16T04:00:00Z",
    "reporter_account_id": null,
    "device_id": "device-demo-001",
    "state": "effective",
    "payload": {
      "reported_status": null,
      "observation": "box_opened",
      "medication_id": "med-demo-001",
      "dose_slot_id": "slot-demo-001",
      "plan_ref": {
        "plan_id": "plan-demo-001",
        "plan_version": 1
      },
      "raw_text": null
    },
    "quality": {
      "event_id": "box-event-demo-001",
      "event_revision": 1,
      "status": "valid",
      "issues": [],
      "normalized_measurement": null,
      "processing_version": "quality-draft01",
      "processed_at": "2026-11-16T04:00:00Z"
    },
    "link_status": "matched",
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
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
    "code": "DEMO_DISABLED",
    "message": "当前环境不允许伪造设备事件"
  }
}
```

### A26 查看匹配及未匹配原因

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/dose-matches` |
| 用途/维护/页面 | 查看匹配及未匹配原因 / A6 / 用药报告/待复核 |
| 身份/患者范围 | 本人或statistics:read并具records:read；证据来源按授权裁剪 |
| 路径/查询/头/体 | path patient_id；query window_start/end:DateTime R/N（≤31天），data_environment:demo/real R/N，as_of:DateTime O/N=服务器当前时间、cursor/limit、plan_id O/N；body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<Match>>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 SLOT_CONTRACT_NOT_READY；另继承公共错误 |
| 幂等/状态/事务/来源 | 按generated_at/match_id排序，显示真实候选及依据；无规则不自动最近匹配；一个原子证据不覆盖所有药。 |
| 待实施验收 | 多个候选保留review_required；跨患者候选不返回。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "match_id": "match-demo-001",
        "patient_id": "p-demo-001",
        "event_id": "event-demo-001",
        "event_revision": 1,
        "dose_slot_id": "slot-demo-001",
        "candidate_slot_ids": [
          "slot-demo-001"
        ],
        "link_status": "matched",
        "reason": null,
        "rule_version": "match-draft01",
        "generated_at": "2026-11-16T04:00:00Z",
        "is_simulated": true
      }
    ],
    "next_cursor": null
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
    "message": "计划时段或匹配契约未就绪"
  }
}
```

### A27 受控人工复核关联

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/dose-matches/review` |
| 用途/维护/页面 | 受控人工复核关联 / A6 / 独立数据复核入口 |
| 身份/患者范围 | 受控复核身份，需records:correct且可访问患者及计划 |
| 路径/查询/头/体 | path/query无；JSON=MatchReviewInput；可信认证或管理Cookie/CSRF；Idempotency-Key；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Match>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 MATCH_REVIEW_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 核对有效修订、时段归属与版本；追加复核原因和关联修订，旧关联不抹；登记旧新统计窗口更新；不改变原evidence_type。 |
| 待实施验收 | 人工指定跨患者时段拒绝；空关联显式解除而非删除历史。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "match_id": "match-demo-001",
    "patient_id": "p-demo-001",
    "event_id": "event-demo-001",
    "event_revision": 1,
    "dose_slot_id": "slot-demo-001",
    "candidate_slot_ids": [
      "slot-demo-001"
    ],
    "link_status": "matched",
    "reason": null,
    "rule_version": "match-draft01",
    "generated_at": "2026-11-16T04:00:00Z",
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
    "code": "MATCH_REVIEW_CONFLICT",
    "message": "证据修订或候选条件已变化"
  }
}
```

### A28 五类统一统计

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/medication-statistics` |
| 用途/维护/页面 | 五类统一统计 / A6 / 首页/用药报告/B/C读取 |
| 身份/患者范围 | 本人或statistics:read；健康内容最小授权 |
| 路径/查询/头/体 | path patient_id；query window_start/end:DateTime R/N（≤31天），data_environment:demo/real R/N，as_of:DateTime O/N=服务器当前时间；body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Statistics>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 503 PLAN_DEPENDENCY_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读已明确规则下的实际结果；分母来自有效已到时原子时段；计划不可用不返回0，契约未齐409；无计划真零才ratio=null。五类互斥且和等于分母。 |
| 待实施验收 | 10/14与11/14；未服/延迟不入分子；冲突归未知；确认比例不等于客观吞服率。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "statistics_id": "statistics-demo-001",
    "patient_id": "p-demo-001",
    "window_start": "2026-11-09T00:00:00+08:00",
    "window_end": "2026-11-16T00:00:00+08:00",
    "as_of": "2026-11-16T04:00:00Z",
    "timezone": "Asia/Shanghai",
    "data_environment": "demo",
    "plan_refs": [
      {
        "plan_id": "plan-demo-001",
        "plan_version": 1
      }
    ],
    "planned_dose_count": 14,
    "patient_confirmed_count": 10,
    "reported_not_taken_count": 0,
    "postponed_count": 0,
    "unconfirmed_evidence_count": 2,
    "unknown_count": 2,
    "patient_confirmation_ratio": 0.7142857142857143,
    "data_status": "ready",
    "issues": [
      {
        "dose_slot_id": "slot-unknown-demo-001",
        "code": "no_record",
        "message": "暂无有效本人报告或其他证据",
        "event_ids": []
      },
      {
        "dose_slot_id": "slot-unknown-demo-002",
        "code": "no_record",
        "message": "暂无有效本人报告或其他证据",
        "event_ids": []
      }
    ],
    "rule_version": "count-draft01",
    "updated_at": "2026-11-16T04:00:00Z",
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
    "code": "PLAN_DEPENDENCY_UNAVAILABLE",
    "message": "计划或有效时段依赖不可用"
  }
}
```

### A29 按日统计和正确加总

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/medication-trends` |
| 用途/维护/页面 | 按日统计和正确加总 / A6 / 用药报告/趋势 |
| 身份/患者范围 | 本人或statistics:read |
| 路径/查询/头/体 | path patient_id；query window_start/end:DateTime R/N（≤31天），data_environment:demo/real R/N，as_of:DateTime O/N=服务器当前时间；body无；period固定day不接受其他值；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<MedicationTrend>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 503 STATISTICS_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 按患者时区分日、先加总分子分母再求总比例；固定as_of，缺失和版本边界保留，不画伪造改善线。 |
| 待实施验收 | 1/1和0/3加总为1/4；跨日迟到更正更新受影响桶。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "patient_id": "p-demo-001",
    "period": "day",
    "items": [
      {
        "statistics_id": "statistics-day-demo-001",
        "patient_id": "p-demo-001",
        "window_start": "2026-11-15T00:00:00+08:00",
        "window_end": "2026-11-16T00:00:00+08:00",
        "as_of": "2026-11-16T04:00:00Z",
        "timezone": "Asia/Shanghai",
        "data_environment": "demo",
        "plan_refs": [
          {
            "plan_id": "plan-demo-001",
            "plan_version": 1
          }
        ],
        "planned_dose_count": 2,
        "patient_confirmed_count": 2,
        "reported_not_taken_count": 0,
        "postponed_count": 0,
        "unconfirmed_evidence_count": 0,
        "unknown_count": 0,
        "patient_confirmation_ratio": 1,
        "data_status": "ready",
        "issues": [],
        "rule_version": "count-draft01",
        "updated_at": "2026-11-16T04:00:00Z",
        "is_simulated": true
      }
    ],
    "aggregate": {
      "statistics_id": "statistics-trend-demo-001",
      "patient_id": "p-demo-001",
      "window_start": "2026-11-15T00:00:00+08:00",
      "window_end": "2026-11-16T00:00:00+08:00",
      "as_of": "2026-11-16T04:00:00Z",
      "timezone": "Asia/Shanghai",
      "data_environment": "demo",
      "plan_refs": [
        {
          "plan_id": "plan-demo-001",
          "plan_version": 1
        }
      ],
      "planned_dose_count": 2,
      "patient_confirmed_count": 2,
      "reported_not_taken_count": 0,
      "postponed_count": 0,
      "unconfirmed_evidence_count": 0,
      "unknown_count": 0,
      "patient_confirmation_ratio": 1,
      "data_status": "ready",
      "issues": [],
      "rule_version": "count-draft01",
      "updated_at": "2026-11-16T04:00:00Z",
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
    "code": "STATISTICS_UNAVAILABLE",
    "message": "统计结果暂不可用"
  }
}
```

### A30 可比指标趋势

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/measurement-trends` |
| 用途/维护/页面 | 可比指标趋势 / A4/A6 / 指标趋势 |
| 身份/患者范围 | 本人或measurements:read |
| 路径/查询/头/体 | path patient_id；query window_start/end:DateTime R/N（≤31天），data_environment:demo/real R/N，as_of:DateTime O/N=服务器当前时间、metric_code R/N、unit R/N、method_code O/Y=null；body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<MeasurementTrend>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 422 INCOMPARABLE_MEASUREMENT_QUERY；另继承公共错误 |
| 幂等/状态/事务/来源 | 只同单位/方法组，按真实occurred_at排序；缺失点null附原因，未知单位归issues不猜转换；不生成心理诊断/医学阈值。 |
| 待实施验收 | 0保留0；缺失不连成伪正常趋势；跨方法不强合。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "patient_id": "p-demo-001",
    "metric_code": "step_count",
    "unit": "count",
    "method_code": "manual_entry",
    "window_start": "2026-11-16T00:00:00+08:00",
    "window_end": "2026-11-17T00:00:00+08:00",
    "points": [
      {
        "event_id": "measurement-demo-001",
        "event_revision": 1,
        "occurred_at": "2026-11-16T03:58:00Z",
        "value": 4500,
        "missing_reason": null,
        "quality_status": "valid",
        "is_simulated": true
      }
    ],
    "issues": []
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
    "code": "INCOMPARABLE_MEASUREMENT_QUERY",
    "message": "指标、单位或方法不能按该方式比较"
  }
}
```

### A31 读取共享状态摘要

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/summary` |
| 用途/维护/页面 | 读取共享状态摘要 / A5 / 首页/B支持上下文/C匹配 |
| 身份/患者范围 | 本人或summary:read，组成部分还需底层相应权限 |
| 路径/查询/头/体 | path patient_id；query window_start/end:DateTime R/N（≤31天），data_environment:demo/real R/N，as_of:DateTime O/N=服务器当前时间；body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Summary>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 503 SUMMARY_STORE_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | record_overview引用A6，不另算比例；各来源分开availability与missing_items；缺B/C保留A统计；源失败/未接入/受限分别说明；读取不隐式训练/改画像。 |
| 待实施验收 | 缺生理不抹用药统计；过期stale；不得凭summary权限读取受限B/C内容。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "summary_id": "summary-demo-001",
    "patient_id": "p-demo-001",
    "window_start": "2026-11-09T00:00:00+08:00",
    "window_end": "2026-11-16T00:00:00+08:00",
    "generated_at": "2026-11-16T04:00:00Z",
    "valid_until": "2026-11-16T04:15:00Z",
    "updated_at": "2026-11-16T04:00:00Z",
    "data_status": "insufficient",
    "plan_refs": [
      {
        "plan_id": "plan-demo-001",
        "plan_version": 1
      }
    ],
    "record_overview": {
      "statistics_id": "statistics-demo-001",
      "patient_id": "p-demo-001",
      "window_start": "2026-11-09T00:00:00+08:00",
      "window_end": "2026-11-16T00:00:00+08:00",
      "as_of": "2026-11-16T04:00:00Z",
      "timezone": "Asia/Shanghai",
      "data_environment": "demo",
      "plan_refs": [
        {
          "plan_id": "plan-demo-001",
          "plan_version": 1
        }
      ],
      "planned_dose_count": 14,
      "patient_confirmed_count": 10,
      "reported_not_taken_count": 0,
      "postponed_count": 0,
      "unconfirmed_evidence_count": 2,
      "unknown_count": 2,
      "patient_confirmation_ratio": 0.7142857142857143,
      "data_status": "ready",
      "issues": [
        {
          "dose_slot_id": "slot-unknown-demo-001",
          "code": "no_record",
          "message": "暂无有效本人报告或其他证据",
          "event_ids": []
        },
        {
          "dose_slot_id": "slot-unknown-demo-002",
          "code": "no_record",
          "message": "暂无有效本人报告或其他证据",
          "event_ids": []
        }
      ],
      "rule_version": "count-draft01",
      "updated_at": "2026-11-16T04:00:00Z",
      "is_simulated": true
    },
    "measurement_overview": [],
    "feedback_overview": {
      "patient_id": "p-demo-001",
      "window_start": "2026-11-09T00:00:00+08:00",
      "window_end": "2026-11-16T00:00:00+08:00",
      "sources": [
        {
          "source_module": "B",
          "availability": "not_integrated",
          "records": [],
          "reason": "B业务尚未接入"
        },
        {
          "source_module": "C",
          "availability": "not_integrated",
          "records": [],
          "reason": "C业务尚未接入"
        }
      ],
      "updated_at": "2026-11-16T04:00:00Z"
    },
    "missing_items": [
      {
        "source": "measurement",
        "code": "not_collected",
        "message": "该统计窗口尚无可用指标"
      },
      {
        "source": "B",
        "code": "not_integrated",
        "message": "B尚未接入"
      },
      {
        "source": "C",
        "code": "not_integrated",
        "message": "C尚未接入"
      }
    ],
    "schema_version": "summary-draft01",
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
    "code": "SUMMARY_STORE_UNAVAILABLE",
    "message": "摘要结果暂不可读取"
  }
}
```

### A32 显式刷新同一汇总能力

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/patients/{p}/summary-refresh` |
| 用途/维护/页面 | 显式刷新同一汇总能力 / A5/A6 / 报告刷新/可信任务 |
| 身份/患者范围 | 本人或summary:read且可刷新当前患者；跨模块服务身份单独核验 |
| 路径/查询/头/体 | path patient_id；query无；JSON=RefreshInput；公共写入头；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Summary>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 503 SUMMARY_REFRESH_FAILED；另继承公共错误 |
| 幂等/状态/事务/来源 | 固定窗口/数据环境/版本→调用A6与有效指标/反馈→保存摘要与回执；不另造比例；失败旧结果stale并留原因，不假称fresh。 |
| 待实施验收 | 补录后11/14对应同一窗口；同键复用结果；依赖失败与真无反馈区分。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "summary_id": "summary-demo-001",
    "patient_id": "p-demo-001",
    "window_start": "2026-11-09T00:00:00+08:00",
    "window_end": "2026-11-16T00:00:00+08:00",
    "generated_at": "2026-11-16T04:00:00Z",
    "valid_until": "2026-11-16T04:15:00Z",
    "updated_at": "2026-11-16T04:00:00Z",
    "data_status": "insufficient",
    "plan_refs": [
      {
        "plan_id": "plan-demo-001",
        "plan_version": 1
      }
    ],
    "record_overview": {
      "statistics_id": "statistics-demo-001",
      "patient_id": "p-demo-001",
      "window_start": "2026-11-09T00:00:00+08:00",
      "window_end": "2026-11-16T00:00:00+08:00",
      "as_of": "2026-11-16T04:00:00Z",
      "timezone": "Asia/Shanghai",
      "data_environment": "demo",
      "plan_refs": [
        {
          "plan_id": "plan-demo-001",
          "plan_version": 1
        }
      ],
      "planned_dose_count": 14,
      "patient_confirmed_count": 10,
      "reported_not_taken_count": 0,
      "postponed_count": 0,
      "unconfirmed_evidence_count": 2,
      "unknown_count": 2,
      "patient_confirmation_ratio": 0.7142857142857143,
      "data_status": "ready",
      "issues": [
        {
          "dose_slot_id": "slot-unknown-demo-001",
          "code": "no_record",
          "message": "暂无有效本人报告或其他证据",
          "event_ids": []
        },
        {
          "dose_slot_id": "slot-unknown-demo-002",
          "code": "no_record",
          "message": "暂无有效本人报告或其他证据",
          "event_ids": []
        }
      ],
      "rule_version": "count-draft01",
      "updated_at": "2026-11-16T04:00:00Z",
      "is_simulated": true
    },
    "measurement_overview": [],
    "feedback_overview": {
      "patient_id": "p-demo-001",
      "window_start": "2026-11-09T00:00:00+08:00",
      "window_end": "2026-11-16T00:00:00+08:00",
      "sources": [
        {
          "source_module": "B",
          "availability": "not_integrated",
          "records": [],
          "reason": "B业务尚未接入"
        },
        {
          "source_module": "C",
          "availability": "not_integrated",
          "records": [],
          "reason": "C业务尚未接入"
        }
      ],
      "updated_at": "2026-11-16T04:00:00Z"
    },
    "missing_items": [
      {
        "source": "measurement",
        "code": "not_collected",
        "message": "该统计窗口尚无可用指标"
      },
      {
        "source": "B",
        "code": "not_integrated",
        "message": "B尚未接入"
      },
      {
        "source": "C",
        "code": "not_integrated",
        "message": "C尚未接入"
      }
    ],
    "schema_version": "summary-draft01",
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
    "code": "SUMMARY_REFRESH_FAILED",
    "message": "摘要刷新失败，旧结果已标待更新"
  }
}
```

### A33 创建已注册公共任务

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/tasks` |
| 用途/维护/页面 | 创建已注册公共任务 / A7 / O/B/A可信服务，不开放任意患者任务创建 |
| 身份/患者范围 | 可信业务维护方，owner_module由适配核验，患者与授权逐次检查 |
| 路径/查询/头/体 | path/query无；JSON=TaskCreateInput；独立服务身份+Idempotency-Key；禁止患者自报owner_module；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 201；Envelope<Task>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 422 TASK_TYPE_NOT_REGISTERED；另继承公共错误 |
| 幂等/状态/事务/来源 | 任务、业务去重键、初始状态与幂等同事务；只有注册能力；业务键含来源周期节点/时段/干预，规则升级不默认骚扰重发；新建不自动执行。 |
| 待实施验收 | 请求带任意Python/URL拒绝；相同业务键最多一个有效任务。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 201）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "task_id": "task-demo-001",
    "patient_id": "p-demo-001",
    "kind": "deliver_intervention",
    "owner_module": "B",
    "owner_operation_key": "demo-intervention-001:rule-draft01",
    "scheduled_at": "2026-11-16T04:00:00Z",
    "valid_until": "2026-11-16T05:00:00Z",
    "payload": {
      "intervention_id": "intervention-demo-001",
      "content_ref": "content-demo-001",
      "channel": "mock"
    },
    "intervention_id": "intervention-demo-001",
    "rule_version": "support-draft01",
    "status": "pending",
    "cancellation_requested": false,
    "attempt_count": 0,
    "max_attempts": 3,
    "next_attempt_at": null,
    "failure_reason": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
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
    "code": "TASK_TYPE_NOT_REGISTERED",
    "message": "任务类型或载荷未注册"
  }
}
```

### A34 公共任务详情

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/tasks/{id}` |
| 用途/维护/页面 | 公共任务详情 / A7 / 演示控制台/授权任务状态 |
| 身份/患者范围 | 可信来源模块；本人或tasks:read仅可最小状态，不越权看B内容引用后的正文 |
| 路径/查询/头/体 | path task_id；query/body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Task>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读持久化事实；状态不作实际送达/患者响应证明。 |
| 待实施验收 | 授权撤销后不能读待共享内容；无送达回执不显示已读。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "task_id": "task-demo-001",
    "patient_id": "p-demo-001",
    "kind": "deliver_intervention",
    "owner_module": "B",
    "owner_operation_key": "demo-intervention-001:rule-draft01",
    "scheduled_at": "2026-11-16T04:00:00Z",
    "valid_until": "2026-11-16T05:00:00Z",
    "payload": {
      "intervention_id": "intervention-demo-001",
      "content_ref": "content-demo-001",
      "channel": "mock"
    },
    "intervention_id": "intervention-demo-001",
    "rule_version": "support-draft01",
    "status": "pending",
    "cancellation_requested": false,
    "attempt_count": 0,
    "max_attempts": 3,
    "next_attempt_at": null,
    "failure_reason": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 1,
      "contract_version": "A-draft01",
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
    "message": "任务不可访问或不存在"
  }
}
```

### A35 患者范围任务列表

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/tasks` |
| 用途/维护/页面 | 患者范围任务列表 / A7 / 提醒状态/演示控制台 |
| 身份/患者范围 | 本人或tasks:read，按来源记录权限检查 |
| 路径/查询/头/体 | path patient_id；query cursor/limit、status O/N=不筛选；body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<Task>>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 503 TASK_STORE_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 按scheduled_at/task_id排序；不因查询启动调度或重复创建节点。 |
| 待实施验收 | 刷新/重启读取同一任务，不重复检查/投递。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "task_id": "task-demo-001",
        "patient_id": "p-demo-001",
        "kind": "deliver_intervention",
        "owner_module": "B",
        "owner_operation_key": "demo-intervention-001:rule-draft01",
        "scheduled_at": "2026-11-16T04:00:00Z",
        "valid_until": "2026-11-16T05:00:00Z",
        "payload": {
          "intervention_id": "intervention-demo-001",
          "content_ref": "content-demo-001",
          "channel": "mock"
        },
        "intervention_id": "intervention-demo-001",
        "rule_version": "support-draft01",
        "status": "pending",
        "cancellation_requested": false,
        "attempt_count": 0,
        "max_attempts": 3,
        "next_attempt_at": null,
        "failure_reason": null,
        "meta": {
          "created_at": "2026-11-16T04:00:00Z",
          "updated_at": "2026-11-16T04:00:00Z",
          "revision": 1,
          "contract_version": "A-draft01",
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
    "code": "TASK_STORE_UNAVAILABLE",
    "message": "任务状态暂不可查询"
  }
}
```

### A36 受控执行一次

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/tasks/{id}/run` |
| 用途/维护/页面 | 受控执行一次 / A7 / 演示控制台/显式CLI或可信调度 |
| 身份/患者范围 | 任务来源模块/本地管理执行身份，不能由任意家人调用 |
| 路径/查询/头/体 | path task_id；query无；JSON=TaskRunInput；独立服务认证或管理Cookie/CSRF；Idempotency-Key；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Execution>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 TASK_NOT_RUNNABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 重新验证授权/有效期/取消，原子领取执行attempt，释放写锁执行注册能力，再保存结果；同键同执行，任务在途不并发重复；outcome_unknown先核查不盲重发。 |
| 待实施验收 | 同任务并发最多一个有效attempt；取消/撤销后拒绝；mock提交不代表患者收到。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "execution_id": "execution-demo-001",
    "task_id": "task-demo-001",
    "patient_id": "p-demo-001",
    "intervention_id": "intervention-demo-001",
    "attempt": 1,
    "execution_status": "completed",
    "delivery_status": "submitted",
    "channel": "mock",
    "is_simulated": true,
    "result_ref": null,
    "error_code": null,
    "error_message": null,
    "retryable": false,
    "started_at": "2026-11-16T04:00:00Z",
    "finished_at": "2026-11-16T04:00:01Z",
    "submitted_at": "2026-11-16T04:00:01Z",
    "delivered_at": null
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
    "code": "TASK_NOT_RUNNABLE",
    "message": "任务在途、终止、过期或结果尚未核清"
  }
}
```

### A37 取消或登记在途取消请求

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/tasks/{id}/cancel` |
| 用途/维护/页面 | 取消或登记在途取消请求 / A7 / 业务来源控制/提醒取消 |
| 身份/患者范围 | 可信来源模块或获准管理身份；不是通用患者改状态 |
| 路径/查询/头/体 | path task_id；query无；JSON=TaskCancelInput；受控认证/CSRF及Idempotency-Key；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Task>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 TASK_TERMINAL_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | pending/retry_wait可原子cancelled；running先置cancellation_requested并由执行器安全点确认，不承诺已撤回；已完成/失败/过期不回退，晚回执仅审计。 |
| 待实施验收 | 在途取消不伪称副作用消失；重复取消不产生新执行。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "task_id": "task-demo-001",
    "patient_id": "p-demo-001",
    "kind": "deliver_intervention",
    "owner_module": "B",
    "owner_operation_key": "demo-intervention-001:rule-draft01",
    "scheduled_at": "2026-11-16T04:00:00Z",
    "valid_until": "2026-11-16T05:00:00Z",
    "payload": {
      "intervention_id": "intervention-demo-001",
      "content_ref": "content-demo-001",
      "channel": "mock"
    },
    "intervention_id": "intervention-demo-001",
    "rule_version": "support-draft01",
    "status": "cancelled",
    "cancellation_requested": true,
    "attempt_count": 0,
    "max_attempts": 3,
    "next_attempt_at": null,
    "failure_reason": null,
    "meta": {
      "created_at": "2026-11-16T04:00:00Z",
      "updated_at": "2026-11-16T04:00:00Z",
      "revision": 2,
      "contract_version": "A-draft01",
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
    "code": "TASK_TERMINAL_CONFLICT",
    "message": "任务已终止，不能回退或伪撤回已发生动作"
  }
}
```

### A38 执行与投递分层结果

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/executions/{id}` |
| 用途/维护/页面 | 执行与投递分层结果 / A7 / 任务详情/B回传查看 |
| 身份/患者范围 | 可信来源模块；本人或tasks:read按患者和来源范围 |
| 路径/查询/头/体 | path execution_id；query/body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<Execution>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 只读真实执行状态、渠道和模拟标记；unknown保留未知，不把finished_at当delivered_at。 |
| 待实施验收 | 计算完成delivery=not_applicable；mock submitted不能显示真实已送达。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "execution_id": "execution-demo-001",
    "task_id": "task-demo-001",
    "patient_id": "p-demo-001",
    "intervention_id": "intervention-demo-001",
    "attempt": 1,
    "execution_status": "completed",
    "delivery_status": "submitted",
    "channel": "mock",
    "is_simulated": true,
    "result_ref": null,
    "error_code": null,
    "error_message": null,
    "retryable": false,
    "started_at": "2026-11-16T04:00:00Z",
    "finished_at": "2026-11-16T04:00:01Z",
    "submitted_at": "2026-11-16T04:00:01Z",
    "delivered_at": null
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
    "message": "执行不可访问或不存在"
  }
}
```

### A39 执行历史与尝试次数

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/tasks/{id}/executions` |
| 用途/维护/页面 | 执行历史与尝试次数 / A7 / 任务历史/排错 |
| 身份/患者范围 | 同A38，按原任务患者授权 |
| 路径/查询/头/体 | path task_id；query cursor/limit；body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<List<Execution>>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 404 RESOURCE_NOT_FOUND；另继承公共错误 |
| 幂等/状态/事务/来源 | 按attempt/execution_id排序；所有尝试计入任务预算，B模型调用仍计入B总预算，不复制执行当新干预。 |
| 待实施验收 | 失败/重试次数可追溯；任务与干预ID不混用。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "items": [
      {
        "execution_id": "execution-demo-001",
        "task_id": "task-demo-001",
        "patient_id": "p-demo-001",
        "intervention_id": "intervention-demo-001",
        "attempt": 1,
        "execution_status": "completed",
        "delivery_status": "submitted",
        "channel": "mock",
        "is_simulated": true,
        "result_ref": null,
        "error_code": null,
        "error_message": null,
        "retryable": false,
        "started_at": "2026-11-16T04:00:00Z",
        "finished_at": "2026-11-16T04:00:01Z",
        "submitted_at": "2026-11-16T04:00:01Z",
        "delivered_at": null
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
    "message": "执行历史不可访问"
  }
}
```

### A40 可信渠道回执接收

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `POST /api/v1/integrations/delivery-receipts` |
| 用途/维护/页面 | 可信渠道回执接收 / A7 / 渠道适配→A7→B执行回传 |
| 身份/患者范围 | 独立渠道身份/签名，匹配execution及患者/来源授权；不能靠body自报合法 |
| 路径/查询/头/体 | path/query无；JSON=DeliveryReceiptInput；Idempotency-Key及可信渠道认证头（真实协议待确认）；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<DeliveryReceipt>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 409 RECEIPT_CONTENT_CONFLICT；另继承公共错误 |
| 幂等/状态/事务/来源 | 回执来源去重、审计与合法执行状态更新同事务；晚到/重复不重复计数；非法回退applied=false附原因；取消/授权撤销后不恢复共享。mock环境由适配标true，不能自报真实。 |
| 待实施验收 | submitted≠delivered；乱序不得回退终态；无展示/用户响应不能推断已读。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "receipt_id": "receipt-demo-001",
    "provider_event_id": "provider-event-demo-001",
    "execution_id": "execution-demo-001",
    "occurred_at": "2026-11-16T04:00:01Z",
    "received_at": "2026-11-16T04:00:02Z",
    "status": "submitted",
    "applied": true,
    "ignore_reason": null,
    "is_simulated": true,
    "execution": {
      "execution_id": "execution-demo-001",
      "task_id": "task-demo-001",
      "patient_id": "p-demo-001",
      "intervention_id": "intervention-demo-001",
      "attempt": 1,
      "execution_status": "completed",
      "delivery_status": "submitted",
      "channel": "mock",
      "is_simulated": true,
      "result_ref": null,
      "error_code": null,
      "error_message": null,
      "retryable": false,
      "started_at": "2026-11-16T04:00:00Z",
      "finished_at": "2026-11-16T04:00:01Z",
      "submitted_at": "2026-11-16T04:00:01Z",
      "delivered_at": null
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
    "code": "RECEIPT_CONTENT_CONFLICT",
    "message": "同一渠道事件号内容冲突"
  }
}
```

### A41 汇总B/C来源反馈引用

| 项目 | 定义 |
| --- | --- |
| 方法/路径 | `GET /api/v1/patients/{p}/feedback-overview` |
| 用途/维护/页面 | 汇总B/C来源反馈引用 / A5 / 报告/下一轮策略输入 |
| 身份/患者范围 | 本人或feedback:read；还需B/C原来源授权，未确认权限不绕过 |
| 路径/查询/头/体 | path patient_id；query window_start/end:DateTime R/N（≤31天），data_environment:demo/real R/N，as_of:DateTime O/N=服务器当前时间；body无；所有字段类型、必填/可空、默认、枚举/格式/单位、生成方/版本见A01对应定义 |
| 完整成功返回 | HTTP 200；Envelope<FeedbackOverview>；递归对象与Meta逐字段使用A01/公共O完整表，无任意扩展字段 |
| 失败 | 特例HTTP 503 FEEDBACK_AGGREGATION_UNAVAILABLE；另继承公共错误 |
| 幂等/状态/事务/来源 | 各来源分别标available/not_collected/not_integrated/unavailable/restricted；空records需真实原因；C服务状态与三维反馈分开，不把申请当效果；只读引用不改O画像/模型。 |
| 待实施验收 | B/C未接入显示not_integrated；只提交服务不能显示服务完成/有效。 另检查跨患者、并发/同键重复异内容、在途/回滚、撤销后重放。 |

成功结构示例（HTTP 200）：

```json
{
  "request_id": "req-example-001",
  "status": "success",
  "data": {
    "patient_id": "p-demo-001",
    "window_start": "2026-11-09T00:00:00+08:00",
    "window_end": "2026-11-16T00:00:00+08:00",
    "sources": [
      {
        "source_module": "B",
        "availability": "not_integrated",
        "records": [],
        "reason": "B业务尚未接入"
      },
      {
        "source_module": "C",
        "availability": "not_integrated",
        "records": [],
        "reason": "C业务尚未接入"
      }
    ],
    "updated_at": "2026-11-16T04:00:00Z"
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
    "code": "FEEDBACK_AGGREGATION_UNAVAILABLE",
    "message": "反馈汇总本身暂不可用"
  }
}
```

## 3 状态机、非法转换和事务边界（均为本批待确认细化）

| 对象 | 建议合法转换 | 非法/特殊情况与事务边界 |
| --- | --- | --- |
| 文件 | 保存成功saved；失败save_failed | 保存成功不代表识别/正式计划。临时文件完成、元信息/回执一致；存储中断返回失败，不清理其他用户文件 |
| 草稿 | editing→pending_confirmation→confirmed/returned；returned编辑成新内容号→editing | 待确认/已确认不原地改内容；只有O可信结果能confirmed/formal_plan；网页status字段422 |
| 事件 | original有效→追加correction；有效→追加withdrawal | 原patient/source/source_event_id/received_at不可改；撤销后恢复未定义不自发复活；新修订/有效指针/失效登记同事务 |
| 质量 | pending_validation→valid/needs_review/processing_failed；明确重处理可重新处理 | 质量不是是否服药/是否匹配；未知单位不猜，处理失败不是患者临床异常；对应事件修订必须一致 |
| 匹配 | unmatched/review_required→合法唯一matched；明确复核可解除/改关联并留历史 | 一原子证据不默认多药全服；跨患者、已替代版本、仅最近时间的强配拒绝 |
| 统计 | ready→stale→新结果ready；真零分母not_computable并说明 | 计划依赖失败不是零计划；五类和=分母，未服/延迟不入分子；旧新窗口更新，按版本引用 |
| 摘要 | fresh→stale；缺必要来源insufficient；显式刷新生成新结果 | 部分有效数据保留；来源失败/缺失/未接入/受限分开；A5不重算A6比例 |
| 任务 | pending→running；可安全重试running→retry_wait→running；完成/最终失败；未执行可cancelled/expired | running取消先cancellation_requested，待安全点确认；unknown副作用不自动再执行；终态不被晚回执回退 |
| 执行 | pending→running→completed/failed/cancelled/expired/outcome_unknown | 一attempt一个execution_id；未知需核查，不能把超时直接当未发生；不因重新启动重复执行 |
| 投递 | pending→submitted→delivered或failed；取消/过期保留 | submitted非delivered，delivered非展示/响应；无回执保持未知；mock来源明确不称真实收到 |
| 渠道回执 | 首次合法应用，重复/乱序保留审计，可applied=false | provider_event_id独立于请求追踪；同号异内容409；撤销/取消后的晚回执不恢复业务 |

## 4 本批待实施的固定验收矩阵

| 案例 | 预期；本轮执行状态 |
| --- | --- |
| 7天14有效时段：10本人已服、2仅开盒、2未知 | 五类=10/0/0/2/2，比例10/14；仅计划，未运行 |
| 重放原事件/并发重复提交 | 事实、时段和有效任务/申请均不增；仅计划，未运行 |
| 一个未知补充本人已服 | 11/0/0/2/1，分母14；摘要引用同一结果；未运行 |
| 9本人已服+1未服+1延迟+2其他+1未知 | 五类和14，比例9/14；未服/延迟不进分子；未运行 |
| 上述延迟明确本人已服 | 10/1/0/2/1，分母不变、比例10/14；未运行 |
| 一时段开盒和本人确认并存 | 证据原文都在，本人已服只计1；未运行 |
| 两日1/1、0/3 | 总1/4，不平均为1/2；未运行 |
| 质量缺失/未知单位/不兼容方法 | 保留null/原单位与原因，不补零或强合；未运行 |
| 迟到/更正跨窗口/撤销 | 原时间保留，旧新窗口登记更新，历史修订不消失；未运行 |
| 跨患者/家庭撤销/未绑定设备 | 拒绝，重放旧回执也不能泄露健康信息；未运行 |
| 计划依赖故障/暂存失败/刷新失败 | 明确错误，不伪零计划/空列表/最新摘要；未运行 |
| 在途取消/过期/未知外部结果/乱序回执 | 不盲重试、不恢复终态、不伪称患者收到；未运行 |
| 重启后任务/回执查询 | 未来实现需持久化一致，不能启动自动重发；未运行 |

本轮只对字段/卡片完整性、JSON可解析及静态算术约束做文档检查；这些不等于数据库/接口/网页验收。确认A批后再继续B，S00未整体完成前不编码。

