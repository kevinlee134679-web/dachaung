# S00 全流程：接口目录与权限来源（draft01）

2026-11-16，Asia/Shanghai。153张既有卡的方法/路径和原权限逐卡从不可变来源提取，引用其当前确认清单；**本表的跨流程补充/FQ建议尚待确认**。不是运行路由表，全部应用接口尚未实现。153卡=G2+O31+A41+B39+C40，C40业务维护O。

每卡完整参数、字段、返回、成功/失败例子、错误、幂等及状态仍读来源原卡+有效增量，不能仅以本索引实施。原卡历史“待确认”由各确认清单限定；原卡中尚未定义的角色/算法不因索引出现而解决。

## 1 共用权限交集

- 本人也须已验证账号、对象归属、当前环境和操作资格；家人须有效关系+明确Grant+本卡Scope，旧Grant不自动补新项。
- 摘要/反馈/任务最小状态不等于底层正文访问权；service identity/审核/管理能力不能经普通家庭Grant转授。
- 读取、写入、执行、回调、幂等重放分别重验；失效授权不从旧快照泄露。跨患者统一404、当前患者授权不足403、未登录401、schema错误422、冲突409、必要依赖503，沿用原卡。
- 真实入口缺身份/签名/适配拒绝；内部模块同库调用使用受控服务上下文，不对浏览器开放任意owner_module/角色/函数。
- FQ03另建议：O22/O28本期只本人；A27受控演示复核，不将其当临床资质；C35完整确认DTO只本人，服务方最小Ack仍按既有回调卡；C39家人须feedback:read与services:read交集。这些收敛项需本批确认，不能提前覆盖原卡。

## 2 全目录

路径已含/api/v1；{p}/{s}/{id}均按原卡定义，不能互换患者与资源ID。

| 卡 | 方法/路径 | 用途/模块 | 原卡身份/患者范围 | 当前有效增量或本批待确认影响 |
| --- | --- | --- | --- | --- |
| G01 | `GET /api/v1/health` | 运行和必要依赖就绪检查 / A0 | 无需患者身份；仅最小进程/依赖状态 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| G02 | `GET /api/v1/config/status` | 查看脱敏配置和实际能力 / A0 | 已登录的后端白名单演示管理账号，不是任意家人 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O01 | `POST /api/v1/auth/demo-session` | 进入一个预置虚构身份 / O | 只在AUTH_MODE=demo且本地受控入口；不接收外部用户自报身份 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O02 | `GET /api/v1/auth/me` | 读取账号和当前患者上下文 / O | 仅当前会话；可管理集合每次按授权计算 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O03 | `POST /api/v1/auth/logout` | 主动注销当前会话 / O | 当前会话的本人账号；不得注销其他账号 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O04 | `GET /api/v1/patients` | 列出本人及授权照护对象 / O | 仅当前账号可管理对象；显示家人关系不授予额外健康范围 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O05 | `PUT /api/v1/auth/current-patient` | 记住上次管理对象 / O | 当前账号可管理目标患者，查验实时授权 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O06 | `GET /api/v1/patients/{p}` | 查看基础资料 / O | 本人或patient:read；{p}为ID，实体验证患者范围 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O07 | `PATCH /api/v1/patients/{p}` | 更新基础资料与显示时区 / O | 本人或patient:edit；不能修改enrollment_at/归属 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O08 | `POST /api/v1/patients/{p}/family-binding-codes` | 患者主动发起家庭关联 / O | 仅患者本人，监护例外未定义不放行 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O09 | `POST /api/v1/family-bindings/redeem` | 家人兑换患者发起的绑定码 / O | 当前登录家人账号；患者从可信码取得 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O10 | `GET /api/v1/patients/{p}/family-bindings` | 查看家庭关系状态 / O | 本人可看全部；家人仅自己的关系和最小状态 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O11 | `POST /api/v1/family-bindings/{id}/revoke` | 解除本人授权的关系或家人退出自己的关系 / O | 患者本人或该关系的family_account；不能解除他人关系 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O12 | `PUT /api/v1/family-bindings/{id}/grant` | 精确设置某家人的授权范围 / O | 仅该患者本人；关系必须active；监护替代未定义 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O13 | `GET /api/v1/patients/{p}/grants` | 查看当前授权与必要历史 / O | 本人查看全部；家人仅自己的Grant | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O14 | `POST /api/v1/grants/{id}/revoke` | 撤销单条健康共享授权 / O | 仅患者本人；是否允许家人放弃权限可通过解除自身绑定完成 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O15 | `GET /api/v1/questionnaires/initial` | 取得八主题定义与选项 / O | 已登录且准备管理本人或有questionnaire:assist/read的患者 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O16 | `POST /api/v1/patients/{p}/questionnaire-responses` | 新建/复制问卷进度 / O | 本人或questionnaire:assist；作答身份由会话确定 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O17 | `PUT /api/v1/questionnaire-responses/{id}/answers` | 保存完整八题进度快照 / O | 本人草稿作答者或获questionnaire:assist的该草稿家人；跨作答者接管用新副本 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O18 | `GET /api/v1/questionnaire-responses/{id}` | 恢复进度及查看历史回答 / O | 本人或questionnaire:read；单有assist是否可读取该家人草稿建议允许本人作答范围 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O19 | `POST /api/v1/questionnaire-responses/{id}/submit` | 提交明确修订 / O | 本人或已授权questionnaire:assist的当前作答者 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O20 | `GET /api/v1/patients/{p}/profiles/current` | 读取当前有效画像与不足 / O | 本人或profile:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O21 | `GET /api/v1/profiles/{id}` | 读取历史画像版本 / O | 本人或profile:read，按画像归属核验 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O22 | `POST /api/v1/patients/{p}/profiles` | 对指定已提交响应创建评估结果 / O | 本人或具有questionnaire:assist且获准完成本次评估的家人；后者待Q04 | 既有家人主动评估仍待U02；FQ03建议本期仅本人 |
| O23 | `GET /api/v1/patients/{p}/medications` | 读取患者药品清单 / O | 本人或medication:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O24 | `POST /api/v1/patients/{p}/medications` | 新增药品资料 / O | 本人或medication:edit | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O25 | `PATCH /api/v1/medications/{id}` | 纠正药品名称/备注 / O | 本人或medication:edit，查资源患者归属 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O26 | `GET /api/v1/patients/{p}/plans` | 查看正式计划及版本历史 / O | 本人或plan:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O27 | `GET /api/v1/plans/{id}/versions/{version}` | 读取指定正式计划完整版本 / O | 本人或plan:read；计划、患者、版本一致 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O28 | `POST /api/v1/patients/{p}/plan-confirmations` | 核对并发布A草稿指定修订 / O | 本人；plan:confirm家人可否确认待Q08，未确认前不放行 | plan:confirm家人仍未启用；FQ03建议本期仅本人 |
| O29 | `GET /api/v1/patients/{p}/dose-slots` | 读取正式计划日程 / O | 本人或plan:read；不隐含records:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O30 | `GET /api/v1/patients/{p}/reminder-preferences` | 读取实际保存的提醒配置 / O | 本人或reminder:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| O31 | `PUT /api/v1/patients/{p}/reminder-preferences` | 明确保存提醒和隐私偏好 / O | 本人或reminder:write；notify_family还需患者有效共享同意 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A01 | `POST /api/v1/patients/{p}/files` | 上传并保存文件 / A | 本人或files:write | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A02 | `GET /api/v1/patients/{p}/files` | 文件列表 / A | 本人或files:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A03 | `GET /api/v1/files/{id}` | 文件元信息 / A | 本人或files:read；按file_id核验患者 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A04 | `GET /api/v1/files/{id}/content` | 授权读取原文件 / A | 本人或files:read；每次读取重验 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A05 | `POST /api/v1/patients/{p}/drafts` | 新建人工结构化草稿 / A | 本人或drafts:write；药品/来源文件各自需访问权 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A06 | `GET /api/v1/drafts/{id}` | 草稿详情与确认进度 / A | 本人或drafts:read；来源文件另查files:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A07 | `PUT /api/v1/drafts/{id}` | 保存新草稿内容修订 / A | 本人或drafts:write；只editing/returned可写 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A08 | `POST /api/v1/drafts/{id}/submit` | 提交确定内容等待O确认 / A | 本人或drafts:submit；不等于O plan:confirm | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A09 | `GET /api/v1/patients/{p}/drafts` | 草稿及提交列表 / A | 本人或drafts:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A10 | `POST /api/v1/patients/{p}/medication-events` | 接收实际身份的服药报告 / A | 本人或records:report；家人只能family_report | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A11 | `GET /api/v1/patients/{p}/medication-events` | 服药证据列表 / A | 本人或records:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A12 | `GET /api/v1/medication-events/{id}` | 服药证据精确详情 / A | 本人或records:read；event_kind必须medication | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A13 | `POST /api/v1/patients/{p}/measurements` | 接收手动指标与缺失说明 / A | 本人或measurements:write | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A14 | `GET /api/v1/patients/{p}/measurements` | 指标事件列表 / A | 本人或measurements:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A15 | `GET /api/v1/measurements/{id}` | 指标原来源与质量 / A | 本人或measurements:read；event_kind必须measurement | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A16 | `POST /api/v1/events/{id}/corrections` | 追加经过授权的更正 / A | 本人可更正本人手动记录；家人需records:correct且仅自己的报告；设备证据仅受控复核身份 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A17 | `POST /api/v1/events/{id}/withdrawals` | 撤销当前有效证据 / A | 同A16更正权限，按实际来源限制 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A18 | `GET /api/v1/events/{id}/revisions` | 原始及更正修订历史 / A | 需对应records:read或measurements:read，受限来源不能绕过 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A19 | `GET /api/v1/events/{id}/quality` | 质量状态查询 / A | 需对应事件读取权限 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A20 | `POST /api/v1/events/{id}/reprocess` | 显式重跑已注册清洗规则 / A | 受控数据维护身份，非任意患者触发内部命令 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A21 | `GET /api/v1/patients/{p}/device-bindings` | 查询设备绑定 / A | 本人或devices:manage | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A22 | `POST /api/v1/patients/{p}/device-bindings` | 关联已可信注册设备 / A | 仅患者本人或明确配置的可信维护身份；家人是否可绑定仍不默认允许 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A23 | `POST /api/v1/device-bindings/{id}/revoke` | 撤销设备关联 / A | 本人或获准devices:manage；需重验绑定归属 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A24 | `POST /api/v1/integrations/device-events` | 可信设备统一接收 / A | 独立设备认证/签名适配，主体必须匹配device_id及当前授权绑定 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A25 | `POST /api/v1/demo/device-events` | 固定编号模拟器入口 / A | 仅demo管理白名单、虚构患者与模拟设备 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A26 | `GET /api/v1/patients/{p}/dose-matches` | 查看匹配及未匹配原因 / A | 本人或statistics:read并具records:read；证据来源按授权裁剪 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A27 | `POST /api/v1/dose-matches/review` | 受控人工复核关联 / A | 受控复核身份，需records:correct且可访问患者及计划 | 复核角色分配仍待AU05；FQ03建议仅受控演示复核身份 |
| A28 | `GET /api/v1/patients/{p}/medication-statistics` | 五类统一统计 / A | 本人或statistics:read；健康内容最小授权 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A29 | `GET /api/v1/patients/{p}/medication-trends` | 按日统计和正确加总 / A | 本人或statistics:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A30 | `GET /api/v1/patients/{p}/measurement-trends` | 可比指标趋势 / A | 本人或measurements:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A31 | `GET /api/v1/patients/{p}/summary` | 读取共享状态摘要 / A | 本人或summary:read，组成部分还需底层相应权限 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A32 | `POST /api/v1/patients/{p}/summary-refresh` | 显式刷新同一汇总能力 / A | 本人或summary:read且可刷新当前患者；跨模块服务身份单独核验 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A33 | `POST /api/v1/tasks` | 创建已注册公共任务 / A | 可信业务维护方，owner_module由适配核验，患者与授权逐次检查 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A34 | `GET /api/v1/tasks/{id}` | 公共任务详情 / A | 可信来源模块；本人或tasks:read仅可最小状态，不越权看B内容引用后的正文 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A35 | `GET /api/v1/patients/{p}/tasks` | 患者范围任务列表 / A | 本人或tasks:read，按来源记录权限检查 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A36 | `POST /api/v1/tasks/{id}/run` | 受控执行一次 / A | 任务来源模块/本地管理执行身份，不能由任意家人调用 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A37 | `POST /api/v1/tasks/{id}/cancel` | 取消或登记在途取消请求 / A | 可信来源模块或获准管理身份；不是通用患者改状态 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A38 | `GET /api/v1/executions/{id}` | 执行与投递分层结果 / A | 可信来源模块；本人或tasks:read按患者和来源范围 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A39 | `GET /api/v1/tasks/{id}/executions` | 执行历史与尝试次数 / A | 同A38，按原任务患者授权 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A40 | `POST /api/v1/integrations/delivery-receipts` | 可信渠道回执接收 / A | 独立渠道身份/签名，匹配execution及患者/来源授权；不能靠body自报合法 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| A41 | `GET /api/v1/patients/{p}/feedback-overview` | 汇总B/C来源反馈引用 / A | 本人或feedback:read；还需B/C原来源授权，未确认权限不绕过 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B01 | `POST /api/v1/config/check-model` | 显式模型探测 / B | 仅后端管理白名单；本轮禁止执行真实探测 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B02 | `GET /api/v1/cases` | 虚构案例列表 / B | 仅demo:manage白名单；真实环境禁演示入口 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B03 | `GET /api/v1/cases/{id}` | 案例模板与开场草稿 / B | 同B02，案例及患者范围核验 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B04 | `POST /api/v1/cases/{id}/reset` | 案例范围明确确认重置 / B | 仅demo:manage，模板/案例版本一致，仅虚构范围 | C关联时仍阻止重置；本批未增加级联清理 |
| B05 | `POST /api/v1/sessions` | 创建会话或进入已接受邀请 / B | 本人dialogue:write；家人代发言本批不启用 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B06 | `GET /api/v1/sessions` | 分页会话历史 / B | 本人或dialogue:read专门授权；不因家庭绑定开放整段聊天 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B07 | `GET /api/v1/sessions/{s}` | 会话当前状态 / B | 本人或dialogue:read；核验session患者 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B08 | `POST /api/v1/sessions/{s}/close` | 关闭会话 / B | 仅本人明确操作；家人不能擅自结束患者会话 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B09 | `POST /api/v1/sessions/{s}/messages` | 保存原消息后非流式生成一轮 / B | 本人dialogue:write且active；身份不从文本/role字段取得 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B10 | `GET /api/v1/sessions/{s}/messages` | 历史及失败提交恢复 / B | 本人或dialogue:read，专门授权不超范围 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B11 | `POST /api/v1/messages/{id}/generation-retries` | 引用原消息的安全重试 / B | 本人dialogue:write，原user消息属active当前会话 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B12 | `GET /api/v1/sessions/{s}/assessments` | 分来源评估/线索历史 / B | 本人或assessment:read，不能因dialogue摘要授权取得全部心理信息 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B13 | `POST /api/v1/sessions/{s}/self-reports` | 描述性患者自评 / B | 仅本人assessment:write，active会话 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B14 | `GET /api/v1/assessments/{id}` | 精确评估与版本 / B | 本人或assessment:read，按原患者/会话权限 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B15 | `GET /api/v1/sessions/{s}/strategy` | 当前有效策略与建议 / B | 本人或interventions:read；可执行控件仅本人可操作 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B16 | `GET /api/v1/interventions/{id}` | 决策与执行分层详情 / B | 本人或interventions:read，底层证据按原授权访问 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B17 | `POST /api/v1/suggestions/{id}/response` | 明确接受/拒绝/取消建议 / B | 仅本人，pending且未过期，同患者会话 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B18 | `POST /api/v1/interventions/{id}/display-receipts` | 独立网页展示回执 / B | 本人会话及可展示该干预，不能管理台假称患者已读 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B19 | `GET /api/v1/sessions/{s}/ui-mode` | 读取模式和可选变更历史 / B | 本人或interventions:read；切换权限另验 | FQ14建议追加2个只读投影字段，当前未冻结 |
| B20 | `PUT /api/v1/sessions/{s}/ui-mode` | 主动切换与恢复 / B | 仅本人mode:write与明确操作，active会话 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B21 | `GET /api/v1/sessions/{s}/invitations` | 该会话的邀请历史 / B | 本人或interventions:read，限定该会话归属 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B22 | `POST /api/v1/invitations/{id}/response` | 响应邀请并准备会话入口 / B | 仅本人，pending且有效，同患者 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B23 | `POST /api/v1/referrals` | 复用C唯一正式申请创建 / B | 本人且C已有相应服务确认/共享范围授权；不是仅接受建议就申请 | 已确认B-v0.2：必填service_draft_revision，代理C07唯一服务 |
| B24 | `GET /api/v1/referrals/{id}` | 转介代理与实际服务映射 / B | 本人或获准interventions:read且具C服务相应读取权限 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B25 | `POST /api/v1/integrations/state-events` | A状态事件与检查触发 / B | 独立模块身份，核验患者与summary_ref实际来源/授权 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B26 | `POST /api/v1/integrations/execution-receipts` | A执行与投递回传 / B | 独立A模块身份，task/execution/intervention/patient关联全相等 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B27 | `POST /api/v1/integrations/referral-receipts` | C服务状态回传 / B | 独立C身份，referral映射service_id/patient一致 | 已确认B-v0.2：source_version为C Service.meta.revision十进制字符串 |
| B28 | `POST /api/v1/demo/triggers` | 受控场景/故障模拟 / B | 仅demo:manage，虚构案例及实际mock模型；不能伪造真实故障成功 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B29 | `GET /api/v1/patients/{p}/intervention-feedback` | A汇总所需最小反馈 / B | 可信A服务或本人feedback:read且具B原来源权限 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B30 | `GET /api/v1/interventions/export` | 研究反馈窗口JSON导出 / B | 本人或exports:read专门授权，底层B数据权限同时满足 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B31 | `GET /api/v1/knowledge` | 共用知识列表与管理预览 / B | 患者knowledge:read仅可适用有效已审核；include_unreviewed仅knowledge:manage | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B32 | `GET /api/v1/knowledge/{id}/versions/{version}` | 精确资料版本与旧引用 / B | 当前医学用途需reviewed适用有效；旧会话曾引用版本或管理身份可看历史状态 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B33 | `POST /api/v1/knowledge/search` | 适用知识检索与集合 / B | 本人knowledge:read或可信模块用途授权；患者最小化范围 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B34 | `POST /api/v1/knowledge` | 新增资料草稿 / B | knowledge:manage受控管理身份，非患者/模型自建专业资料 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B35 | `POST /api/v1/knowledge/{id}/versions` | 新增不可变内容版本 / B | knowledge:manage且当前内容版本匹配 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B36 | `POST /api/v1/knowledge/{id}/review` | 真实有资格审核动作 / B | knowledge:review及后端可核验审核资格；模型不能自审 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B37 | `POST /api/v1/knowledge/{id}/withdraw` | 撤回资料版本 / B | knowledge:manage受控身份，精确版本/修订 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B38 | `PUT /api/v1/config/model-profile` | 选择后端白名单模型/流水线配置 / B | 仅后端管理白名单；患者/消息不能更改系统配置 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| B39 | `GET /api/v1/patients/{p}/invitations` | 首页读取未绑定会话的邀请 / B | 本人或interventions:read；接受/拒绝仅本人 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C01 | `GET /api/v1/patients/{p}/support-recommendations` | 需求与首页支持推荐 / C | 本人或support:read，O/A/B原来源范围同时校验 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C02 | `GET /api/v1/support-resources` | 当前资源目录 / C | 本人或support:read；仅实际可见资源，真实未接入明确标 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C03 | `GET /api/v1/support-resources/{id}` | 资源主体/版本与共享要求 / C | 本人或support:read，按资源环境/范围 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C04 | `POST /api/v1/patients/{p}/service-drafts` | 准备服务草稿 / C | 本人或明确services:prepare家人，仅准备无共享通知 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C05 | `GET /api/v1/service-drafts/{id}` | 草稿与确认准备状态 / C | 本人或services:prepare；不能越过源内容读取权限 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C06 | `PUT /api/v1/service-drafts/{id}` | 修改准备内容 / C | 本人或services:prepare；submitted草稿不可原地改成新申请 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C07 | `POST /api/v1/patients/{p}/services` | 唯一正式服务创建 / C | 仅本人或经核验B代理，C/O确认有效；家人准备不等于可正式代申请 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C08 | `GET /api/v1/patients/{p}/services` | 正式服务记录及筛选 / C | 本人或services:read，健康/答复内容按实际授权最小化 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C09 | `GET /api/v1/services/{id}` | 服务详情及执行/答复来源 / C | 本人或services:read；服务主体仅经可信服务适配读取获准范围 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C10 | `POST /api/v1/services/{id}/cancel` | 取消或登记取消请求 / C | 仅本人，当前submitted/in_progress且修订匹配 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C11 | `POST /api/v1/integrations/service-receipts` | 可信服务执行回执 / C | 独立主体身份/资格，绑定service/resource/provider/授权 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C12 | `POST /api/v1/demo/services/{id}/transitions` | 模拟合法状态变化 / C | 仅demo:manage、模拟资源/患者/服务；非真实服务方接口 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C13 | `POST /api/v1/services/{id}/feedback` | 患者三维反馈或不参与 / C | 仅本人service-feedback:write；completed后收集，取消/失败可自愿留说明 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C14 | `GET /api/v1/services/{id}/feedback` | 反馈历史与更正来源 / C | 本人或services:read且具相应反馈访问范围 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C15 | `GET /api/v1/patients/{p}/support-feedback` | A/B最小支持反馈 / C | 可信A/B服务或本人feedback:read，底层C授权同时校验 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C16 | `GET /api/v1/peer-groups` | 匿名同辈目录 / C | 本人或peer:read，服务范围允许；不列其他患者身份 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C17 | `GET /api/v1/peer-groups/{id}` | 小组介绍 / C | 本人或peer:read，按资源/环境访问 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C18 | `POST /api/v1/peer-groups/{id}/memberships` | 复用C申请建立入组准备 / C | 仅本人peer:participate并有C确认/O范围，目标peer_support资源一致 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C19 | `POST /api/v1/memberships/{id}/leave` | 自主退出小组 / C | 仅本人，pending/active自己的成员资格 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C20 | `GET /api/v1/peer-groups/{id}/posts` | 匿名文字交流与审核队列 / C | 活跃成员仅visible；本人可见自己pending；审核者限定本组 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C21 | `POST /api/v1/peer-groups/{id}/posts` | 提交短文字待审核 / C | 仅本人active成员peer:participate，明确发布本段文本 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C22 | `GET /api/v1/patients/{p}/points` | 当前可用积分 / C | 本人或points:read，账户属该患者 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C23 | `GET /api/v1/points/rules` | 正向奖励规则版本 / C | 已登录可读启用演示规则，真实未启用须如实说明 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C24 | `GET /api/v1/patients/{p}/points-ledger` | 不可变积分流水 / C | 本人或points:read | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C25 | `POST /api/v1/internal/points/reconcile` | 程序按有效来源核奖 / C | 独立C程序身份或明确demo管理范围，患者/LLM不能直接调金额 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C26 | `GET /api/v1/rewards` | 自愿额外权益目录 / C | 本人或points:read，权益入口不因支持需求隐藏 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C27 | `GET /api/v1/rewards/{id}` | 权益成本/版本/交付说明 / C | 本人或points:read，按环境/可见性 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C28 | `POST /api/v1/patients/{p}/redemptions` | 自愿兑换原子扣分与准备交付 / C | 仅本人rewards:redeem，余额/版本/资源及必要确认有效 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C29 | `GET /api/v1/patients/{p}/redemptions` | 独立兑换记录 / C | 本人或points:read，记录属患者 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C30 | `GET /api/v1/redemptions/{id}` | 兑换与点数/服务关联 / C | 本人或points:read，服务正文另需C服务权限 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C31 | `POST /api/v1/integrations/fulfillment-receipts` | 可信交付/失败回执 / C | 独立交付身份，精确绑定fulfillment/兑换，服务型须C原服务事实 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C32 | `GET /api/v1/redemptions/{id}/fulfillment` | 交付与数字内容读取 / C | 本人或points:read；数字内容仅该患者，人员正文另验服务授权 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C33 | `POST /api/v1/redemptions/{id}/feedback` | 独立权益体验评价 / C | 仅本人且属于本人兑换；不强制参与 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C34 | `POST /api/v1/patients/{p}/service-confirmations` | 确认服务并取得O共享引用 / C | 仅本人明确操作；O患者/家庭/用途授权核验，家人不能自行扩大范围 | 已确认O-v0.4：同库O权威范围+C确认，默认24小时 |
| C35 | `GET /api/v1/service-confirmations/{id}` | 核验可复用确认与范围 / C | 本人；家人/服务方仅获准最小状态，不公开健康内容 | 原卡最小状态/完整对象边界；FQ03建议该完整DTO仅本人 |
| C36 | `POST /api/v1/service-confirmations/{id}/revoke` | 撤销确认与相关共享 / C | 仅本人；不能撤销他人独立确认或扩大共享 | 已确认O-v0.4：O权威撤销，不能只改C缓存 |
| C37 | `POST /api/v1/peer-posts/{id}/moderation` | 受控文字审核 / C | 限定该组受控审核身份；不是普通家庭或患者权限 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C38 | `POST /api/v1/patients/{p}/management-reviews` | 明确完成本周管理回顾 / C | 仅本人明确完成，非家人/模型代造 | 继承原卡及其确认清单；源项授权/患者/环境逐次重验 |
| C39 | `GET /api/v1/patients/{p}/management-reviews` | 管理回顾历史 / C | 本人或明确相应反馈查看授权，不因家庭绑定全开放 | 原卡相应反馈授权仍需精确化；FQ03建议feedback:read且services:read |
| C40 | `POST /api/v1/demo/patients/{p}/profile-fixtures` | 由O切换预登记模拟画像 / O | 仅demo:manage受控身份，虚构患者及O固定fixture | 已确认O-v0.4：唯一业务维护O，demo:manage且虚构fixture |

## 3 字段、原卡和状态来源

| 组 | 字段完整定义 | 原接口卡 | 当前确认/增量 |
| --- | --- | --- | --- |
| G/O | 01_公共基础与O字段_draft01.md | 02_公共基础与O接口卡_draft01.md | 公共/O v0.1—v0.4 |
| A | A01_字段_draft01.md | A02_接口卡_draft01.md | A v0.1—v0.3 |
| B | B01_字段_draft01.md | B02_接口卡_draft01.md | B v0.1/v0.2 |
| C | C01_字段_draft01.md | C02_接口卡_draft01.md | C v0.1；C40引用O-v0.4 |

对象状态不共用一个status：O正式版本/问卷/授权，A质量/匹配/五类/任务/执行/投递，B生成/建议/邀请/模式/代理，C服务五状态/成员/帖子/积分/兑换/交付/评价各自继承对应表。跨模块转换按F01，不将A succeeded、C completed、渠道delivered、页面displayed或患者accepted当成同一结果。

## 4 本批新增建议与兼容

F-API01 POST /api/v1/patients/{p}/reminder-snoozes是第154条候选路由，业务维护O、执行A，完整卡及字段/例子见F03。未确认前仍只有153张已确认卡。

B19 UIModeView建议追加effective_ui_mode/evaluated_at两个必填输出字段，需消费者按新版本升级；B20自身仍返回原UIState，不自动增加未列字段。原source卡/旧JSON不回写。

FQ07的as_of同时限制接收与修订可见性、FQ03权限收敛、FQ08通知上限及上述新增字段/路由均是本轮新取舍，须确认后新增公共/O/A/B等对应增量。没有存量部署，未执行迁移；将来如有存量按实际精确引用迁移，不猜历史或清表。

全流程F00—F03未经确认仅本地保留，不随C确认批归档推送。

