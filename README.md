# 药物依从性平台

大创项目，面向慢性病患者及家属的用药依从性支持平台。O 模块负责账号、家庭授权和问卷画像，A 模块负责用药计划、服药记录、病历识别与统计提醒，B 模块提供 AI 沟通与干预，C 模块提供服务授权查看与匿名同辈互助。本地演示使用虚构账号，支持本地模拟与外部模型配置。问卷支持 CAS 自报计分、按题解读卡片与可选的本地 CPU 模型预测。

## 快速开始

要启用本地 CAS 模型预测或外部模型识别/对话，按[本地网站配置](docs/本地网站配置.md)安装依赖与配置环境变量。下列步骤可启动基础演示。

装好 devenv 和 direnv 后：

```sh
direnv allow
pnpm install && pnpm build
cd backend
uv run python -m medplatform init-demo
uv run python -m medplatform serve
```

不用 devenv 时，需要 uv、Node.js 和 pnpm：在根目录先运行一次 `./start.sh init-demo`，之后运行 `./start.sh` 即可构建前端并启动服务（Windows 用 `start.cmd`）。

启动后打开 http://127.0.0.1:8000/ 。全部命令见 [运维文档](docs/运维.md)。

## 开发

```sh
cd backend
uv run python -B -X utf8 -m unittest discover -s tests
uv run ruff check && uv run ruff format
cd ..
pnpm test && pnpm typecheck
pnpm lint && pnpm format
```

后端（Python、FastAPI）在 `backend/`，前端源码在 `frontend/`（Solid、Vite、Tailwind CSS）。pnpm 命令在根目录运行。`pnpm dev` 启动带热更新的开发服务器，`/api` 代理到同时运行的 `serve`（127.0.0.1:8000）。

pre-commit 钩子要用 pnpm，请在 direnv 已加载的终端里提交。

## 文档

- [架构](docs/架构.md)
- [运维](docs/运维.md)
- [本地网站配置](docs/本地网站配置.md)
- [CAS 接入与验收](docs/CAS接入与验收.md)
- [数据字典](docs/数据字典.md)
- [演示脚本](docs/演示脚本.md)
- [验收用例](docs/验收用例.md)
- [历史接口目录](docs/contracts/全平台接口目录_v0.1.md)与[答辩调整增量](docs/contracts/全流程_v0.3_答辩调整增量.md)
- [历史需求基线](docs/baseline/v1.1/00_全平台分阶段编码汇总Prompt.md)
