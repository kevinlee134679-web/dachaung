# 公共基础与O v0.2：A批确认后的衔接增量

2026-11-16，Asia/Shanghai。依据：用户确认A批；详细确认范围见A_v0.1_确认清单.md。本文是对公共/O v0.1的追加兼容登记，不覆盖原文件或先前确认历史。

## 1 AX-01权限枚举增量（已确认）

新增files:read/files:write、drafts:read/drafts:write/drafts:submit、measurements:read/measurements:write、records:correct、devices:manage、statistics:read、summary:read、feedback:read、tasks:read。

语义以A原字段/接口卡逐项权限为准；原records:read/report、medication:read/edit等继续有效。旧Grant.scopes内容不自动增补；扩大范围必须患者明确授权并产生新授权版本。medication:read不含病历原文件；summary:read/feedback:read不绕过组成来源的B/C权限；可信设备、模块和渠道不因某个患者Scope获得服务身份。

## 2 O→A字段语义对齐（已确认）

- O28 PlanConfirmInput.draft_revision以及正式计划source_draft_revision都引用A Draft.content_revision；A Meta.revision还包含提交/返回等资源状态变化，两者不可混用。
- O定义计划时段业务，A保存稳定时段；一药品条目一次应服为原子粒度，同一时间多药可页面分组，但统计不合并为一件事。
- 正常计划新版本以显式生效点替换未来安排，不自动重写既往已发生时段。分母仅纳入查询范围内正式、已到时、未取消/替代的有效时段；已到时判断使用固定as_of，窗口[start,end)，最多31天。
- O日程读取不另存服药状态，网页仍向A提交证据/读取五类结果。A的PlanRef只是O的plan_id/plan_version精确引用，不产生第二套可改计划。

## 3 版本与未决项

后续O实际Meta.contract_version可标public-o-v0.2（字段P-0.2/O-0.2）；v0.1字段/33卡保持兼容，以上增量优先用于A衔接。原稿与旧示例不回写。

原v0.1 U07权限增量由本次AX-01确认解决；U04的原子粒度/普通未来生效/cutoff部分解决。稳定键、生成周期、跨时区/夏令时、回溯/暂停等仍按A的AU01/AU02待定。其余U项没有因本次A确认自动消失。A的7天幂等下限不等于确定了所有登录/回执存储细节。

这不是运行版本或数据库迁移记录；无应用代码、无真实接入、无付费调用，不授权S01。
