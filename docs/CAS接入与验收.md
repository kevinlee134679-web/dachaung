# CAS 接入与验收

本机研究演示采用单版本八主题问卷 `initial-cas-review-v1`，定义文件位于 `backend/medplatform/profile/cas_questionnaire.json`。

| 项目 | 口径与实现位置 |
| --- | --- |
| 问卷定义与校验 | `backend/medplatform/profile/cas_questionnaire.py`。`definition()` 返回去掉 `result_notes` 的单版本定义；`validate_answers()` 校验字段归属、单选/量表/多选合法性、`visible_when` 条件可见性、`exclusive` 互斥（如 `req_none`）及 `main_barrier` 必须属于已选 `barriers`。「无法判断」作为 `code="unknown"` 选项保存在各题作答值中，无独立作答状态字段。 |
| `cas_observed` 自报计分 | `observed_result()`。仅当患者本人作答、提交时确认 `same_episode=true` 且 Q1 `knowledge`、Q2 `adherence_freq`、Q3 `difficulty` 均已填写且不为 `unknown` 时，按 `Q1 + 频率分 + (6 - Q3)` 计算整数 3–15；否则状态为 `insufficient`，返回 `missing_items` 与 `reasons`。 |
| `cas` 模型预测 | `backend/medplatform/profile/cas_model.py` 的 `CasModel`。未配置 `CAS_RETRAINED_BUNDLE` 时 `cas_questionnaire.unavailable_cas()` 返回 `status="unavailable"`、`value=null`、`model_version=null`。配置后，需本人填写完整 Q5–Q8 且 Q8 `stable_experience != "否"` 才返回 `status="estimated"`、`value` 与 `model_version`；缺项、家属代答或 `stable_experience == "否"` 返回 `status="insufficient"` 及原因。 |
| `cards` 解读卡片与 `factors` | `cards()` 按 Q1、Q2、Q3、Q4、Q6、Q7 顺序生成卡片，跳过无有效作答或仅选 `unknown` 的主题；每张卡片含 `question_id`、`title`、`answers`、`level`（`good`/`neutral`/`attention`）与 `note`（Q4 若选了 `main_barrier`，则将该障碍说明置于 `note` 首行）。`factors()` 从 Q4 提取要点供 B 模块对话上下文使用。 |
| 接口行为（O15–O22、O32） | `backend/medplatform/identity/service.py` 与 `api.py`。`O15` `GET /api/v1/questionnaires/initial` 不接受版本参数；`O16` 新建替代答卷以空白初始化；`O17` 按主题整段替换保存；`O22` 使用方法版本 `cas-questionnaire-v2`，同一答卷在方法版本与当前模型版本不变时复用已有画像；`O32` `GET /api/v1/patients/{p}/questionnaire-responses/latest-submitted` 仅限本人读取最近已提交答卷及对应画像（未生成时为 `null`）；`O20` 读取当前画像（不带 `source` 参数），`O21` 读取历史画像。 |

## 模型包与依赖

模型发布包位于 `backend/data/models/cas-dl2-retrain-20261124/`，包含权重 `ensemble.pt`、预处理参数 `preprocessing.json` 与四组虚构对照样例 `reference_cases.json`。`CasModel.load` 直接读取 `preprocessing.json` 与 `ensemble.pt` 加载五成员 `MultiHeadAttentionMLP` 集成模型，特征映射由 `MODEL_INPUTS` 负责；`numpy` 与 CPU 版 `torch` 由 `backend/pyproject.toml` 的 `cas` 依赖组锁定。

安装、环境变量与本地启动步骤见[本地网站配置](本地网站配置.md)。管理员可通过 `GET /api/v1/config/status` 查看 `cas` 能力是否就绪。

## 前端流程与界面展示

前端实现位于 `frontend/src/features/questionnaire/`（`adherence-page.tsx`、`questionnaire-page.tsx`、`question-wizard.tsx`、`profile-page.tsx`、`questionnaire.ts`、`profile.ts`），入口位于「我的 → 依从性类型」，首次引导也在 `frontend/src/features/onboarding/questionnaire-step.tsx` 复用该页面。

- **开始评估与隐私确认**：无草稿时点击「开始评估」，先弹出隐私说明确认框，用户确认后才创建答卷。
- **卡片式向导**：按当前可见字段一屏一题展示；单选与量表题保存后自动进入下一题，多选题与选填字段提供「下一题」按钮，隐藏字段在保存前由 `clearHidden` 清理。在第一个选填主题（Q5）前插入说明屏，提供「继续填写」与「跳过选填部分」。
- **提交与结果展示**：本人提交后自动调用 `O22` 生成结果并切到结果视图；家属协助作答仅提交问卷，不生成画像。结果页按主题展示 `cards` 的标题、等级标签、作答摘要与建议文案，不展示 CAS 数值或分型标签。

## 验收与检查

- **后端测试**：`backend/tests/identity/test_cas_questionnaire.py`（覆盖计分、`observed_result` 缺项/代答/非同次经历分支、卡片等级与主因文案排序、答案校验、`unknown` 支持、提交与画像复用、家属代答限制、`latest-submitted`、空白替代答卷，以及 `CasModelTests` 对照 `reference_cases.json` 的预测与不足条件校验）与 `backend/tests/identity/test_identity.py`。安装 `cas` 依赖组后 `CasModelTests` 实际执行预测校验；未安装 `torch` 时该测试类跳过。
- **前端测试**：`frontend/test/features/questionnaire/questionnaire.test.tsx`（覆盖草稿恢复隔离、隐私确认取消/确认、单选自动保存、Q4 条件显隐与隐藏清理、跳过选填提交及结果卡片渲染）。

运行检查命令（后端在 `backend/`，前端在仓库根目录）：

```sh
uv run --locked python -B -X utf8 -m unittest discover -s tests
uv run --locked ruff check && uv run --locked ruff format --check
pnpm test && pnpm typecheck && pnpm lint && pnpm format:check && pnpm knip
```
