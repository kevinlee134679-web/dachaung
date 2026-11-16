# 公共基础与O v0.5：全流程确认增量

2026-11-16，Asia/Shanghai。依据用户确认F06 draft02及其明确包含的F00—F03完整方案，统一确认见全流程_v0.1_确认清单.md。本文只登记已提出并获确认的衔接，不覆盖旧来源/历史，不代表应用实现或授权S01。

契约标识public-o-v0.5，新增字段版本P-0.5/O-0.5；public-o-v0.1—v0.4与其余既有确认继续有效。原F-draft01示例保留，不回填历史版本。

## 1 身份、权限与公共写入

- 本地demo会话绝对8小时、不滑动续期；Cookie HttpOnly/SameSite=Lax/Path=/，HTTPS时Secure；同源写操作检查Origin与会话CSRF。退出/过期不凭旧幂等键复活。生产认证/监护协议不启用。
- 本期O22生成画像、O28发布正式计划仅本人；家人可按有效授权协助问卷/准备草稿/报告/读取，不自动获得plan:confirm或主动画像生成能力。A27只受控演示复核，不假称临床资质。
- C35完整服务确认DTO仅本人；C39家人需feedback:read与services:read交集及底层权利。旧Grant不扩权，C共享仍O权威，读写/执行/回调/重放分别重验。
- 幂等作用域、规范化指纹、7天普通完整回执、之后最小墓碑、409在途/冲突/过期及敏感回执保护完整继承F01第1节和F03 IdempotencyReceipt的14字段定义。敏感Cookie/CSRF/绑定码不存明文普通回执；本地OS账户保护载荷只在原会话/码仍有效且未撤销/消费时受控重放，解密失败不另造事实。绑定码原5分钟保持。

## 2 正式计划和稳定时段

O定义业务、A持久化；单药条目一次应服一个原子slot。自然键为patient_id/data_environment/plan_id/plan_version/plan_entry_id/scheduled_at_utc，首次唯一插入分配UUIDv4、重放复用。普通发布只接受effective_from≥now、daily/weekly、计划时区Asia/Shanghai；条目start_date/end_date按当地日含首尾，版本区间左闭右开，新生效点归新版。

O发布、A精确草稿content_revision正式引用和相关通知同库原子提交；旧未来slot从生效点标superseded，历史事件不改挂。发布生成从生效当地日到第31个后续日零点的右开窗口并裁剪生效点/条目日期；受控显式维护按≤31天窗口补齐，GET不生成/修复，不把未物化当0分母。回溯/按需/复杂疗程、暂停/取消医嘱、跨时区排程/DST本期不启用；展示时区变化不平移旧计划。

## 3 提醒数值与新增接口

默认提醒关闭、零重复及隐私等既有默认不变。启用重复时30—120分钟、最多2次重复，每slot初次/重复/稍后合计最多3次。锚点偏移[-60,60]分钟，结果距计划时刻≤60分钟；strict_timing未明确false时只允许原时刻。所有数值是通知工程边界，不是医学服药时间窗；不满足明确医嘱/下一时段条件时拒绝，不改scheduled_at或静默裁剪。

确认F-API01 POST /api/v1/patients/{p}/reminder-snoozes，业务O5、执行/Task存储A7。原F03第1节完整接口卡/字段/成功失败例纳入：ReminderSnoozeInput的source_task_id:ID、expected_task_revision:Version、snooze_minutes:integer均R/N无默认，稍后5—120分钟；输出完整A Task，不写服药证据或把通知稍后当延迟服药。

只允许本人或有效reminder:write家人；原O in_app任务须结果明确、同患者/slot/环境/计划且仍适用。source_task_id+原修订至多一个子任务，次数核验/关联/新任务/回执同事务；超过每slot总3次、严格时间未知或其他前置不满足409。稍后时刻为明确动作now+分钟且早于原dose scheduled_at+4小时及下一正式时段；valid_until取新通知+30分钟与上述边界较早者。配置关闭/患者明确处理该slot/计划替代或撤销时停止待发，不据此推断已服。

普通提醒仅在原通知后30分钟内且未到下一时段补发；更长停机不批量补发。执行前重验O配置、授权、slot和有效期，家人通知不能绕过原单独同意。真实推送/关闭网页可靠送达仍未接入。

## 4 字段、版本与实施边界

ReminderSnoozeInput、ReminderSnoozeLink完整类型/可空/默认/范围/来源逐项继承F03；共享幂等/通知对象按F03与A-v0.4维护，不新增任意payload或执行权限。新路由返回A Task时，其Meta按A资源的适用契约标识，不强塞O字段。

CAS/画像与支持强度保留延期接入继续deferred-v0.1；无分类规则描述性/insufficient、CAS null，研究方法不被本次替代。原33卡、O维护的C40和本次新F-API01共同见全平台接口目录_v0.1.md。无应用/迁移/业务测试/付费调用，不自动进入S01。
