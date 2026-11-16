# 公共基础与O v0.3：B确认后的权限增量

2026-11-16，Asia/Shanghai。用户确认B批，依据B_v0.1_确认清单.md；在v0.1/v0.2上追加，不覆盖旧文件/旧授权。

BX-01新增dialogue:read、dialogue:write、assessment:read、assessment:write、interventions:read、mode:write、knowledge:read、knowledge:manage、knowledge:review、exports:read、demo:manage。Scope代码作为统一枚举可引用，但有效操作仍需本人/对象归属/资格/环境检查，不靠枚举字符串自报放行。

旧Grant.scopes不自动增加。家属用药摘要权限不包含整段对话；完整读取须患者专门授权dialogue:read。本期不启用家人代患者发言、切模式或接受邀请；真实监护和代聊仍待专项。知识审核还须后端可核验人员资格，模型不能自审；管理配置/演示权限由受控账号白名单决定，不作为普通家庭授权可转授能力。

未来O Meta.contract_version可标public-o-v0.3；原v0.1/v0.2字段及接口保持兼容，新增权限不改原用途。B38仅选已登记配置，B39仅按患者读邀请，均不增加改处方/余额权限。

本登记不解决U/AU/BU其余未决，不代表有真实认证、专业审核、付费调用或应用实现，不授权S01。
