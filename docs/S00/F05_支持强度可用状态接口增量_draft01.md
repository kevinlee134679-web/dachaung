# S00：B15支持强度可用状态接口增量（draft01）

2026-11-16，Asia/Shanghai。依据用户已确认deferred-v0.1/DP03，为DU01补齐具体接口方案。**本文件新增对外字段、状态投影、时效及兼容细节均为建议、待确认、未冻结、未实现**。不把延期适配确认当作本卡确认，不编码、不调用模型或付费API。

## 1 范围和具体待确认项

保留原B15 GET /api/v1/sessions/{s}/strategy及原StrategyView的8字段，建议增加intensity_mapping:IntensityMappingView。原Intervention.support_intensity仍必填不可null且仅none/low/moderate/high；不向原枚举加unknown、不写null、不用none代未配置。无新增URL或方法，现有153张卡不增计数。

| 编号 | 本批具体建议 | 影响 |
| --- | --- | --- |
| IM01 | StrategyView新增必填不可null的intensity_mapping，采用下述8字段视图 | 独立表达能力状态，不改变原Intervention；前后端须共同按新B契约升级 |
| IM02 | 方法明确未配置/关闭/资料不足/已有失败时，正常读取到状态返回HTTP 200；无法读取必要配置/存储返回503 | 200表示真实读到当前状态，不能冒称完成映射；503不伪装not_configured或空结果 |
| IM03 | GET只投影配置与已保存结果，不触发映射/模型/建任务；evaluated须原结果仍有效且同方法/输入版本 | 失效投影insufficient并说明，不回写原结果；展示和执行分别重验 |
| IM04 | 当前结果时效最多15分钟且不超源证据有效期，新增valid_until明确该边界；数据/方法变化使旧结果失效 | 15分钟复用已确认B策略上限；本视图具体表达仍本轮待确认 |
| IM05 | 未配置不关闭聊天/主动模式/主动服务；只阻止依赖该映射的自动动作，旧方法/历史结果不覆盖 | 不抹掉患者需求，实际动作仍遵守原身份/授权/确认/预算 |

确认本卡后再新增B契约版本，当前仅以intensity-view-draft01标识样例；B-v0.1/v0.2及deferred-v0.1继续有效。F00—F03其余参数/新提醒API/B19模式字段未因本卡提出而冻结。

## 2 字段完整定义

R/N必出现不可null，R/Y必出现可null；输出无可省略字段，均由服务器生成。公共ID/Version/DateTime/Reason/List/Meta/Envelope沿用原公共定义，EvidenceRef/Intervention/Suggestion/Invitation/UIState完整递归字段继承原B01及其已确认增量，不以JSON示例替代字段表。

### StrategyView（原8字段加1字段）

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/范围/语义 | 生成方/版本 |
| --- | --- | --- | --- | --- | --- |
| session_id | ID | R/N | 无 | 原当前会话 | B5/原B定义 |
| patient_id | ID | R/N | 无 | 原实际患者 | B5/原B定义 |
| status | string | R/N | 无 | 原active/none/expired；表示当前策略视图，不代表患者是否需要帮助 | B5/原B定义 |
| current_intervention | Intervention | R/Y | null | 原当前有效决策；未就绪或无可用决策可null；内部Intervention原字段不变 | B5/原B定义 |
| suggestions | Suggestion[] | R/N | [] | 原当前有效建议，历史保留 | B5/原B定义 |
| invitations | Invitation[] | R/N | [] | 原本会话邀请；背景邀请仍B39 | B5/原B定义 |
| ui_state | UIState | R/N | 无 | 原10字段，同一模式事实，不悄悄加入F03未确认字段 | B5/原B定义 |
| generated_at | DateTime | R/N | 服务器投影时刻 | 原只读投影，不代表映射已运行 | B5/原B定义 |
| intensity_mapping | IntensityMappingView | R/N | 无 | 本次可访问、有效的能力视图 | B5/intensity-view-draft01 |

### IntensityMappingView（完整8字段）

前7字段沿用已确认内部IntensityMappingResult的值域和来源，再明确对外只读投影语义；最后valid_until为本轮新增建议，不静默给内部原对象加字段。

| 字段 | 类型 | 必填/可空 | 默认 | 枚举/格式/范围/语义 | 生成方/版本 |
| --- | --- | --- | --- | --- | --- |
| availability | string | R/N | 无方法时not_configured | not_configured/disabled/insufficient/evaluated/failed；实际读取配置/结果确定，不因数据库失败猜默认 | B5/intensity-view-draft01 |
| support_intensity | string | R/Y | null | none/low/moderate/high；evaluated必须非null，其余必须null | B5/intensity-view-draft01 |
| method_version | string | R/Y | null | 1—128字符；evaluated必须为实际启用方法版本；没有实际方法不造版本 | B5/intensity-view-draft01 |
| reason | Reason | R/Y | null | 非evaluated必须非null；说明未配置/关闭/不足/过期/失败，不含思维链或受限正文 | B5/intensity-view-draft01 |
| evidence_refs | EvidenceRef[] | R/N | [] | 原source_type/record_id/version/label完整定义；只包含当前有权读取的引用/标签 | B5/intensity-view-draft01 |
| evaluated_at | DateTime | R/N | 无已保存检查时为本次状态检查时刻 | 有结果沿用其真实检查/计算时刻，不随GET伪造新计算；未配置仅表示检查能力状态 | B5/intensity-view-draft01 |
| is_simulated | boolean | R/N | 实际适配/环境 | 显式模拟结果不冒充真实验证，不用单个模型标记替代身份/渠道来源 | B5/intensity-view-draft01 |
| valid_until | DateTime | R/Y | null | evaluated必非null且>evaluated_at；≤原计算时刻+15分钟且不超任何已定义源有效期；其他状态可保留过期边界或null | B5/intensity-view-draft01 |

已配置但未生成可用结果为insufficient并说明，不因GET主动计算。evaluated只允许服务器now<valid_until、方法仍启用且证据/输入版本未失效；边界now=valid_until即失效。旧结果保留，GET投影insufficient、强度null，reason说明过期或输入变化；evaluated_at仍保留原真实时刻，不能伪称重新评估。

读取结果的底层权限不足时，不返回其受限evidence_refs/标签或强度；可提供insufficient与“部分依据受限，当前不能提供映射结果”的最小说明，不自动扩张家庭权限。current_intervention及其他字段继续分别按原卡核权，不能借新增字段绕过授权。

未配置不代表患者没有需求。依赖映射的自动候选不可执行，示例current_intervention=null/status=none仅指没有当前可用自动策略；若存在独立于该映射的已确认合法功能，仍按其原业务规则工作。映射为low等也不直接执行，仍通过B业务及O/A/C约束。

## 3 B15完整增量接口卡

| 项目 | 定义 |
| --- | --- |
| 用途/维护/页面 | 在现有策略旁展示支持强度方法可用性/原因；B5；聊天辅助区/支持入口 |
| 方法/路径 | GET /api/v1/sessions/{s}/strategy（既有B15，不新增路由） |
| 身份/患者范围 | 本人或当前有效interventions:read；会话实际患者/环境一致，底层证据权限另验；可执行控件仍仅本人 |
| 路径 | session_id:ID R/N，无默认；{s}是会话ID，不是patient_id |
| 查询/请求体 | 均无；未知查询422；不接收LLM/规则版本/强度覆盖参数 |
| 请求头 | Cookie.session按公共必需；GET无CSRF、Idempotency-Key和Content-Type要求，HTTP请求追踪沿用公共规则 |
| 完整成功返回 | HTTP 200 Envelope<StrategyView>；第2节完整9字段，递归对象引用既有完整表；未配置/不足也正常200并明确能力状态 |
| 失败 | 原401 AUTH_REQUIRED、403授权不足、404 RESOURCE_NOT_FOUND、422非法查询/结构、503 STRATEGY_UNAVAILABLE；失败data=null、error含稳定code/message |
| 只读/重复/在途 | GET无业务写入，无模型调用/映射调用/预算预留/调度；重复读可有新request_id/generated_at，已保存结果evaluated_at不刷新。原POST生成/干预入口的幂等/在途409仍有效，不由本GET重试执行 |
| 状态/合法性 | 内部可用状态与Intervention强度分开，遵守第2节条件；存储/配置不可用不伪造not_configured；模型失败不降mock；过期只投影，不写恢复历史 |
| 事务/快照 | 只读同一一致性快照取得会话/当前配置/策略/映射引用，按O当前授权过滤；配置变化的竞争导致无法确定一致结果则明确503或重新读取一次，不拼接两套方法数据 |
| 来源/版本 | 引用deferred-v0.1内部结果及实际启用方法/证据；策略版本由原rule_version/版本登记定位，StrategyView本身没有meta，不偷偷加Meta；确认后在G02/版本登记说明新B契约版本 |
| 原执行边界 | 入口/任务执行前重新核验当时方法、证据、有效期和授权；GET返回evaluated不构成用户同意，不直接触发第三方/模式/积分/用药改变 |
| 待实施验收 | 未配置与none区分、500/503不伪空、时间边界、方法切换/证据更正/授权撤销、跨患者、刷新无调用副作用、旧客户端升级和独立用户功能可用 |

## 4 完整结构例子（全部虚构、未运行）

### 成功：方法未配置（HTTP 200）

```json
{
  "request_id": "req-intensity-view-001",
  "status": "success",
  "data": {
    "session_id": "session-demo-001",
    "patient_id": "p-demo-001",
    "status": "none",
    "current_intervention": null,
    "suggestions": [],
    "invitations": [],
    "ui_state": {
      "session_id": "session-demo-001",
      "patient_id": "p-demo-001",
      "scope": "session",
      "ui_mode": "normal",
      "revision": 1,
      "changed_at": "2026-11-16T10:00:00Z",
      "valid_until": null,
      "minimum_until": null,
      "last_offer_at": null,
      "is_simulated": true
    },
    "generated_at": "2026-11-16T10:00:00Z",
    "intensity_mapping": {
      "availability": "not_configured",
      "support_intensity": null,
      "method_version": null,
      "reason": "支持强度方法尚未适配；仍可聊天、主动切换模式或浏览和申请服务",
      "evidence_refs": [],
      "evaluated_at": "2026-11-16T10:00:00Z",
      "is_simulated": true,
      "valid_until": null
    }
  },
  "error": null
}
```

### 成功：模拟方法已评估为none（HTTP 200）

这里只说明未来已登记模拟fixture的返回形状；fixture/方法ID是示例，不表示现已启用规则或已确认任何临床阈值。

```json
{
  "request_id": "req-intensity-view-002",
  "status": "success",
  "data": {
    "session_id": "session-demo-001",
    "patient_id": "p-demo-001",
    "status": "none",
    "current_intervention": null,
    "suggestions": [],
    "invitations": [],
    "ui_state": {
      "session_id": "session-demo-001",
      "patient_id": "p-demo-001",
      "scope": "session",
      "ui_mode": "normal",
      "revision": 1,
      "changed_at": "2026-11-16T10:00:00Z",
      "valid_until": null,
      "minimum_until": null,
      "last_offer_at": null,
      "is_simulated": true
    },
    "generated_at": "2026-11-16T10:02:00Z",
    "intensity_mapping": {
      "availability": "evaluated",
      "support_intensity": "none",
      "method_version": "demo-intensity-fixture-example-v1",
      "reason": "模拟样例：已评估后本轮无需额外自动干预",
      "evidence_refs": [],
      "evaluated_at": "2026-11-16T10:00:00Z",
      "is_simulated": true,
      "valid_until": "2026-11-16T10:15:00Z"
    }
  },
  "error": null
}
```

### 失败：必要存储不可用（HTTP 503）

```json
{
  "request_id": "req-intensity-view-003",
  "status": "error",
  "data": null,
  "error": {
    "code": "STRATEGY_UNAVAILABLE",
    "message": "暂时无法读取策略及方法状态，请稍后重试"
  }
}
```

## 5 兼容、持久化与验收计划

新增输出字段需新B契约版本并同步消费者；当前无部署应用/业务库，不虚构已执行迁移。未来若有旧结果没有映射记录，不补造已评估强度：按真实配置/输入给not_configured或insufficient并说明；原Intervention/历史结果只读保留。持久化是否保存独立映射结果、如何关联输入快照，沿用已确认独立结果/方法版本原则，具体表约束在获准实施前补齐，不自动追溯执行旧干预。

| 编号 | 计划场景 | 预期（全部未运行） |
| --- | --- | --- |
| IT01 | 无映射方法且CAS未适配 | CAS独立null；B15返回not_configured/强度null，聊天/主动入口按原规则可用 |
| IT02 | 方法evaluated输出none，与not_configured比较 | 同为无自动动作时，字段可明确区分，不用none伪装缺方法 |
| IT03 | 已配置但无输入/无结果、关闭、保存失败结果 | 分别insufficient/disabled/failed，非evaluated强度null且原因非null，不隐式重算 |
| IT04 | now恰等valid_until、输入更正或方法版本切换 | 原记录保留；旧结果不可继续作为可执行映射，投影不足或新真实状态 |
| IT05 | 存储/配置依赖不可读 | 503四字段错误，不伪not_configured/空策略/0分 |
| IT06 | 家人无底层证据权限、撤销、跨患者 | 不泄露引用/正文/强度，不扩大授权，越权按原卡拒绝 |
| IT07 | 多次刷新/并发读取/关闭再开启方法 | 无模型/任务/模式/积分副作用，历史计算时间不刷新，不复活旧执行 |
| IT08 | 新旧客户端、B15无Meta、B19未确认字段 | 明确新版本升级；原对象字段不偷改、不混入另一个未确认增量 |

本卡补齐对外设计供确认，不实现方法/阈值，不标业务验收通过。确认本卡后再登记B有效增量；其余FQ及明确S01阶段入口仍独立遵守。
