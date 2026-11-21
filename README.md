# 药物依从性平台

大创项目：面向慢性病患者及家属的用药依从性支持平台。O 模块负责账号、家庭授权和问卷画像，A 模块负责用药计划、服药记录和统计提醒，B 模块提供 AI 沟通与干预，C 模块提供社会支持服务、同辈互助和积分兑换。目前只能本地演示：数据是虚构的，用演示账号登录，模型是 mock。

## 快速开始

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
- [数据字典](docs/数据字典.md)
- [演示脚本](docs/演示脚本.md)
- [验收用例](docs/验收用例.md)
- [已确认契约](docs/contracts/)，接口目录见 [全平台接口目录](docs/contracts/全平台接口目录_v0.1.md)
- [需求基线](docs/baseline/v1.1/00_全平台分阶段编码汇总Prompt.md)
