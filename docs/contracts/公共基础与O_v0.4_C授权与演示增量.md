# 公共基础与O v0.4：C确认后的授权与演示增量

2026-11-16，Asia/Shanghai。依据用户“确认C”、C_v0.1_确认清单.md及不可变C原稿。只登记已经提出的CX-01/CQ02/CQ15，不覆盖v0.1—v0.3或旧授权。

## 1 已确认权限枚举

Scope追加support:read、services:prepare、services:read、services:apply、service-feedback:write、peer:read、peer:participate、points:read、rewards:redeem。逐卡仍须本人/归属/资源/环境/角色检查；有Scope字符串不等于允许代申请、代兑换、代发帖/评价。

旧Grant.scopes不自动补项，家庭绑定不等于授予全部C权限。家人仅在明确有效授权内准备草稿及查看；服务正式确认/申请、兑换、小组参与及患者反馈仍本人。服务方身份、组审核角色和demo:manage由可信适配/受控账号确定，不可通过家庭Grant转授。

## 2 O权威共享引用

C01字段表SharingScopeRef的完整12字段及其类型、R/O/null、来源纳入O维护的共享事实；C的ServiceConfirmation引用它，不能维护可独立改动的第二套授权。类别采用C已列support_question/medication_plan/medication_records/profile_summary，按资源的required/optional集合及患者明确选择取最小范围，不默认共享整段对话/病历原文件。

C34的同一次明确确认动作调用O权威服务，同库保存O范围、C服务确认及回执；默认24小时。复用必须患者、资源/版本、接收主体、服务用途和类别相同，且确认与O范围均有效。家庭接收方另验O关系/适用Grant。C36调用O撤销相关范围并保存审计；任务/重放/回调重验，不能把缓存active视为仍有授权。

C34—C36是C对外路由，O为内部权威服务，不增加第二个对外“授权已确认”接口。本增量不新增来源中未定义的会话时长、回执签名、数据留存或监护协议。

## 3 O维护的演示例外路由

确认C40：POST /api/v1/demo/patients/{p}/profile-fixtures；完整接口卡及成功/失败样例引用C02，字段ProfileFixtureInput/ProfileFixtureResult引用C01。输入profile_fixture_id:ID R/N、expected_profile_id:ID R/N、confirmed:boolean R/N且true，均无默认；输出patient_id/profile_fixture_id/profile_id均ID R/N及is_simulated:boolean R/N且true。

只允许demo:manage受控身份、虚构患者与O固定已登记问卷来源；O发布/选择模拟画像，保留旧记录，CAS仍null。C仅提供入口并重新读取O结果，不接受网页任意类型/CAS。非demo、未知fixture、跨患者和旧expected_profile_id拒绝。真实分类映射与验证继续未决。

未来O Meta.contract_version可采用public-o-v0.4；原33卡和各既有字段保持有效，C40明确增加一条由O维护的例外路由。无运行版本、迁移或应用实现，不授权S01。
