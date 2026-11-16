# B v0.4：到期投影与全流程衔接增量

2026-11-16，Asia/Shanghai。依据用户确认F06 draft02及F00—F03完整方案，见全流程_v0.1_确认清单.md。B-v0.1—v0.3和deferred-v0.1继续有效；原来源、原结果与旧示例不改写。契约B-v0.4，新增字段B-0.4，不代表应用/调度/方法已实现或授权S01。

## 1 B19模式有效投影（FQ14）

确认既有GET /api/v1/sessions/{s}/ui-mode的UIModeView追加effective_ui_mode:string R/N（normal/simplified，无默认）与evaluated_at:DateTime R/N（服务器判断时刻，无调用方默认）。完整类型/权限/参数/返回/成功失败例见F03第2节；原current/changes/next_cursor保留，UIState和ModeChange原字段不变，B20仍返回原UIState，不改包裹类型。

仅当current=simplified、会话active且evaluated_at<valid_until时effective为simplified，其余normal。GET只投影，原current仍保留实际持久化模式/修订/时间，不写到期恢复历史/启动调度/调用模型。客户端按有效投影显示，不能锁住恢复；实际恢复由受控维护/B处理器完成。

## 2 离线到期与检查节点（FQ10—FQ12）

受控维护按目标ID/预期revision比较交换处理过期模式/邀请/建议，不论停机多久只补实际应有失效/恢复记录，不重发过期邀请/覆盖新选择；ModeChange.changed_at记实际维护时间，原valid_until保留逻辑到期依据。GET不代写；写响应入口即使存储仍pending也重验now并拒绝过期。旧pending+过期时间向页面说明“已到期，历史待维护”，不伪称持久化已完成。

节点仍enrollment_at+7/+28天起24小时触发窗口、同节点唯一；缺起点不编造，过窗记录错过，不重置周期或批量补邀请。接受邀请不代写用户发言；极简本人明确动作/2小时/立即恢复、24小时再建议等既定规则保持。

## 3 内部干预修订和公共通知

确认F03 BInterventionRevision：intervention_id:ID R/N、revision:Version R/N默认1、updated_at:DateTime R/N默认实际now，完整约束继承原表。干预执行/展示/响应的实际变化同事务递增并写通知，重复不递增。它是内部并发版本，不给原Intervention凭空加meta/revision。

按A-v0.4的注册通知读源事实/目标消费回执同事务；方法、证据、授权/有效期变化使旧决策失效，旧通知不能覆盖新状态。B InputSnapshot完整字段、方法/配置/知识引用及消息/生成/call预算保留，F03内部A计算清单不替代它。

消息先保存唯一用户发言/生成快照/预算，锁外模型，每次实际尝试先预留预算；single_pass2、STAR8/候选2/60秒等原限不变。A重试/重启不重置，未知先核查，失败可保存用户消息、网页按原号恢复，真实失败不转mock。策略最多15分钟且不超证据，fresh不足时刷新一次仍失败只一般沟通/询问，不捏造风险/执行。

## 4 C衔接/保留能力/版本

B只代理C唯一服务，精确草稿修订/确认/O范围、同库映射、预分配服务/任务初始修订、状态/晚回执按C-v0.2；不将执行/投递/展示/患者响应混合。C关联案例仍禁止B重置，不添加级联清理；新演示使用新库/案例，不删旧事实。

CAS/强度延期接入按deferred-v0.1，B15独立8字段映射视图按B-v0.3有效，none不代未配置；本增量不改变该视图。真实评分、临床阈值、供应商未知核查协议、合格医学审核/安全路径等仍后续专项，不造已启用版本或专业结论。

未来G02/版本登记声明B-v0.4；带Meta的适用B对象可标该契约，UIModeView/StrategyView没有Meta则不新增未列字段。新增必填输出须消费者同步升级，旧结果/历史不回写；没有存量运行应用，不声称已迁移。所有业务/模型/网页/调度测试未运行，不授权S01。

条件字段澄清：第1节“current=simplified”按F03明确指current.ui_mode=simplified，current仍是完整UIState对象；不将对象与字符串比较或改变原字段类型。
