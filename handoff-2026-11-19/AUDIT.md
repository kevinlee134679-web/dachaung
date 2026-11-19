# 大创项目最终总审报告

## 本次重新检出核验

独立从 GitHub 的 `develop` 重新克隆，确认 HEAD 与固定基线一致，工作树干净。原仓库在已具备 Python、Node 和 Edge 的 Windows 上完成一键验收，状态 `passed`，9 项适用检查，实际浏览器 12 组。原版 Python 登记 276 项，262 项执行通过、14 项平台跳过、0 失败、0 错误。该结果只评价 GitHub 原版 Windows 范围。

仓库有应用、示例配置、锁定依赖清单、初始化脚本和虚构场景。原基线的 `start.sh` Git 模式是 `100644`，默认 Windows 检出为 CRLF，且 GitHub 中缺少本地总审整改及发布包专用清单。完整交付采用实测 Git 树、补丁及可离线安装的依赖归档。Git 补丁在新检出重建须得到 `49db176ce5d64e74bd42ff39be2a7d4e118e41d0`。

以下为总审报告共享版。私人文件路径、原始运行日志、运行库、回执、密钥和浏览器数据留在原验收环境。相应结果见 [结构化验收证据](audit-evidence.json)、[逐项平台核对](platform-skip-crosscheck.json)和[搭建与网页使用路径](USE.md)。

交付包在新建含空格路径里离线安装，Windows 验收通过，清单核验及真实浏览器 12 组通过。

Windows 已用本包的新建环境实际启动主站、报告和积分场景，三处均通过 HTTP、演示登录、重复初始化拒绝与正常停机。

Linux 已用本包的新建环境实际启动主站、报告和积分场景，三处均通过 HTTP、演示登录、重复初始化拒绝与正常停机。

2026-11-19，北京时间。范围为应用 0.7.3、schema 0016 的 S00–S07 本地虚构演示。

## 补审与人工交接

**本地演示自动总审通过。** 同一修复源码的 Windows 原生一键验收与 Linux 完整预演都已通过。网页已经就绪，最后一步由负责人按操作单亲自确认。Windows 的 14 项平台跳过已在 Linux 实跑并逐项对照通过。

| 平台与原始状态 | Python 结果 | 实际浏览器 | 备份升级与恢复 |
| --- | --- | --- | --- |
| Windows 11 原生 `passed` | 登记 277，263 通过，14 项平台跳过 | Edge 12 组，另有独立补充 5 组 | 80 张旧表保留；DPAPI、原会话与独立副本恢复通过 |
| Debian 13 虚拟机 `rehearsal_passed_not_windows` | 277 通过，0 失败、0 错误、0 跳过 | Chromium 12 组 | 80 张旧表保留；AES-GCM、原会话、受保护回执及独立副本恢复通过 |

远端 `develop` 复查仍为 `2173030cd6c268674a0a475550e1a1af0333c95f`。本轮本地实测源码为 `b61a4cb74afb29f7a1eea32093980fc4c49f2e6f`，包含 POSIX 入口、备份联接保护、Linux 验收器等待倍率和两处测试子进程等待整改。补审记录 R0062/V0062 另存于本地提交 `47e88a593cb826ac757a13a108bc342d5dc72389`，两份历史文件逐字节核对了原前缀。源码和补审记录留在独立 review 分支，未推送、未合并。保留各轮失败证据，原工作区及原数据保持。

### Windows 环境与一键复验

已安装官方 Python Install Manager 26.4 及 CPython 3.14.10。Node 24.22.3 和 npm 11.19.1 已登记到当前用户 PATH，独立新 CMD 能识别 `py -3.14`、`node`、`npm`。实际执行 `cmd.exe /d /s /c "WINDOWS_ACCEPTANCE.cmd <NUL"`，外层脚本、内层 `start.cmd` 与无默认 venv 时的 `py` 回退均通过。最终源码为 `b61a4cb74afb29f7a1eea32093980fc4c49f2e6f`。 [Python 安装管理器](https://www.python.org/downloads/release/pymanager-264/) · [Node 发行](https://nodejs.org/en/blog/release/v24.22.3/)

最终本地验收包取自 Git 归档，单独生成清单并实际核对 325 个追踪文件。北京时间 18:20:04 完成，退出码 0，`status=passed`、`acceptance_revision=4`、`native_windows=true`、`rehearsal=false`。10 项适用检查通过，含系统 Edge 157.0.4341.60 的 12 组实测、DPAPI、worker、80 张旧业务表保留及两次正常停机。277 项 Python 登记，263 项执行通过，14 项平台跳过，失败和错误均为 0。

早先补充包回归曾超时。宿主机记录休眠、恢复及约 52 分 34 秒校时跃迁。保留该轮失败目录，后续仅在验收运行期间通过进程级电源请求阻止空闲休眠，在新验收目录通过复验。

### Linux 环境与整改

在本机 QEMU 11.1.0 软件模拟虚拟机内运行 Debian 13 x86-64、内核 `6.12.117+deb13-cloud-amd64`，验收账号 UID 1000。CPython 3.14.10、Node 24.22.3、npm 11.19.1，按原锁安装 Linux 24 项且 `pip check` 通过。系统 Chromium 156.0.8078.79 和 Playwright 1.62.1 实际运行。Git 归档校验与实际 POSIX 执行证明 `start.sh` 可用。 [QEMU 发行来源](https://www.qemu.org/download/)

首轮在服务注册路由时达到原验收启动等待上限。独立启动探针在 25.615 秒观察到 ready，并验证正常停机及数据库字节不变。代码提交 `93e5419` 增加 Linux 预演专用等待倍率，Windows 默认、浏览器用例和 STAR 业务预算保持原样。第二轮实际执行 277 项，275 项通过、2 项因测试对子进程冷启动的等待超时出错。提交 `b61a4cb` 把这两处测试的子进程等待分别从 15 秒和 10 秒延至 60 秒，HTTP 状态、无写入、优雅关闭与单库互斥断言保持原样。两项定向重跑 61.368 秒，全部通过。

独立还原覆盖原 Linux UID、原 AES-GCM 密钥及初始化标记。实际备份的 4 个文件哈希通过，目录为 0700、文件为 0600，84 张业务表逐表相等，完整性和外键通过。在新目录用原会话访问，并用同一幂等键重新获得原受保护回执；原隔离库字节不变。最早的恢复夹具初始化超时记录仍在，新复验从已通过初始化校验的隔离夹具做只读复制。

最终预演在北京时间 18:49:01 完成，退出码 0。原始结果明确 `native_windows=false`、`rehearsal=true`、`acceptance_revision=4`。9 项适用检查全过，包含实际 Chromium 12 组、独立 worker、0014→0016 保留 80 张旧表，以及两次正常关闭与释放端口。全量 277 项用时 1578.928 秒。Node 页面 56 项与验收器 5 项在 Linux 单独复核为全过，且在 Python 回归中已通过包装测试计入。

最终 Linux 归档 SHA-256 为 `d8506be5e1efe4f313c822c96ed4ec1536ce09294b394b8fa64d442e5e57df03`。在来宾系统的新检出目录核对归档、启动脚本执行位和锁定环境后执行以下命令。等待倍率只适用于验收器的观察与子进程期限。

```sh
python3.14 -B -X utf8 scripts/accept_windows.py --rehearsal --rehearsal-timeout-multiplier 4 \
  --venv <Linux验收虚拟环境> --browser-executable /usr/bin/chromium
```

### 网页人工验收

[主站](http://127.0.0.1:8131/) 已打开到虚构身份选择页。选择「演示患者甲」和「管理自己的用药」即可开始。另有 [用药报告场景](http://127.0.0.1:8132/) 和 [积分兑换场景](http://127.0.0.1:8133/)，分别准备了 14 个已到时段、10 次本人确认和 83 分虚构积分。三个站点用各自的持久化演示库，均通过本机 HTTP 和健康检查。

## 初审结论与证据归档

**Windows 实机通过。跨平台交付有条件通过。** Windows 在本地修复分支通过 revision 4 验收，Python 277 项登记中 263 项执行通过、14 项平台跳过，失败和错误均为 0。系统 Edge 通过标准 12 组与补充 5 组。独立备份恢复保留了原 DPAPI 会话、正式服务、反馈和虚构附件。

本轮 Linux 完整预演尚未执行。Windows 修复已在本地提交，远端 `develop` 仍是交接基线，仍需组内接收两项修复。跨平台结论以本轮 Windows 原始证据及历史 Linux 记录的适用范围为限。

| 平台 | 证据与结论 |
| --- | --- |
| Windows 11 实机，本次独立克隆 | `status=passed`、`acceptance_revision=4`、`native_windows=true`、`rehearsal=false`，北京时间 15:10:26 完成。9 项适用检查全过，另有 2 次原生正常退出；GitHub 克隆缺少验收发布包专用 manifest。 |
| Linux，本轮 | WSL 与 VirtualMachinePlatform 均显示禁用，宿主未提供可用 Linux 发行版或 Docker。本轮仅在 Windows 核查 Git 模式、归档字节与 Git for Windows Shell 入口。 |
| Linux，历史证据 | R0058 记录 `rehearsal_passed_not_windows`、`native_windows=false`，276 项 Python 全过、12 组实际 Chromium、80 张旧表保留。该轮针对历史验收源码，未覆盖本轮修复。 |
| Windows，历史证据 | R0060 及历史汇总转录负责人截图，记录 276 项、14 跳过、12 组浏览器、10 项检查，含发布包源码哈希。本次另有独立运行的原始结果和日志。 |

历史依据见交付源码归档内的工作记录、验收汇总和交付清单。

## 1. 源码与静态审核

- 从 GitHub `develop` 全量克隆，共 325 个追踪文件。首次及验收后 `git ls-remote` 均返回 `2173030cd6c268674a0a475550e1a1af0333c95f`；初始工作树干净、非浅克隆，`git fsck --full` 通过。远端相对固定基线无后续提交差异。该基线即 PR #1 的合并提交。 [远端 develop](https://github.com/kevinlee134679-web/dachaung/tree/develop) · [PR #1](https://github.com/kevinlee134679-web/dachaung/pull/1)
- 先读 R0060/V0060、`acceptance-summary-final.json`、交付清单及后续验收、运行、流程与延期适配文档。历史 JSON 的“远端待交付”描述早于已核实的 GitHub 合并。交接中的 `df123ca3e0ca1b5f9982ef2f9baed9b22be3cd19` 和 `f970a9cae683f98d1f60e9cdc33967ba10162fc9` 均为历史验收或本地交付标识，在此次远端分支对象中不可达。
- 合并分支最后的配置样例提交 `66c91b1` 只修改 `.env.example`，新增了 STAR、历史窗口、runner 和支持规则的样例配置。验收目录无 `.env`，本轮按 demo/mock 运行。Git 跟踪清单未包含本轮数据库、`.env`、私有日志或受保护目录。
- `start.sh` 修复前为 Git 模式 `100644`，本机 `core.autocrlf=true` 下检出为 CRLF。修复后 Git 模式 `100755`，`.gitattributes` 约束 LF，启动脚本 blob 哈希未变。Git 归档确认执行位和 LF shebang，Windows 上的 Codex 随附 Git Shell 在补齐工具路径与解释器路径后执行 `./start.sh --help` 正常。首次辅助尝试的失败日志单独保留。
- 审核代码提交为 `f85b0c314c81b0d56a5d0e0df33b675a82683b66`，分支 `review/final-audit-2026-11-19`。相对基线的技术差异为 `.gitattributes`、`start.sh` 模式、`medplatform/lifecycle.py` 与 `tests/test_s07_lifecycle.py`。相对 PR 合并前主线的迁移差异只有新增 `0015`、`0016`；本轮全部迁移文件均与固定基线一致。

## 2. 隔离环境、入口与实际命令

| 项目 | 本次实测 |
| --- | --- |
| 系统 | Windows 11 家庭中文版，构建 22631 |
| Python | x64 CPython 3.14.10，官方 NuGet 便携运行时；独立初始 venv 及 r4 新建 venv |
| Node、npm | Node v24.22.3、npm 11.19.1，便携发行包 |
| 浏览器 | 本机 Microsoft Edge 157.0.4341.60，Playwright 1.62.1，无头实际渲染，`platform=win32` |
| 依赖与结构 | Windows 21 项按原锁安装，`pip check` 通过；实生成 85 张表、154 个注册 API，两份 JSON 与仓库交付清单逐对象相等 |

执行工具策略阻止了已校验签名和 SHA-256 的 Python 安装器静默运行，因此在项目忽略目录解包官方 NuGet 运行时。机器没有 `py` launcher，本次直接调用 `scripts/accept_windows.py`，没有执行要求 `py -3.14` 的最外层双击包装 `WINDOWS_ACCEPTANCE.cmd`。脚本在实机创建新 venv，并实际调用 `start.cmd` 完成应用生命周期和回归。 [CPython Windows 发行](https://www.python.org/downloads/release/python-31410/) · [CPython NuGet 包](https://www.nuget.org/packages/python/3.14.10) · [Node 发行](https://nodejs.org/en/blog/release/v24.22.3/)

主要命令从新克隆目录执行，Node 便携目录在本次进程 PATH 中。启动和补充检查显式使用 `APP_ENV=test`、`AUTH_MODE=demo`、`LLM_MODE=mock`；验收器清除传给子进程的模型和模拟回执凭据变量。

```powershell
git ls-remote https://github.com/kevinlee134679-web/dachaung.git refs/heads/develop
git clone --branch develop --single-branch https://github.com/kevinlee134679-web/dachaung.git dachaung-review-2026-11-19
git rev-parse HEAD
git fsck --full
git switch -c review/final-audit-2026-11-19
git update-index --chmod=+x -- start.sh
git ls-files --eol --stage start.sh

$tool = (Resolve-Path 'test-output/review-tools').Path
$python = Join-Path $tool 'python-nuget/tools/python.exe'
$nodeDir = Join-Path $tool 'node-v24.22.3-win-x64'
$env:Path = $nodeDir + ';' + $env:Path
$env:APP_ENV = 'test'
$env:AUTH_MODE = 'demo'
$env:LLM_MODE = 'mock'
$env:DIALOGUE_PIPELINE = 'single_pass'
& $python -B -X utf8 run.py setup
& (Join-Path $nodeDir 'npm.cmd') install --prefix (Join-Path $tool 'browser-tools') --no-audit --no-fund --ignore-scripts playwright@1.62.1
$db = Join-Path (Resolve-Path 'test-output/review-phases').Path 'starter fixture.sqlite3'
cmd.exe /d /c start.cmd init-demo --database $db
cmd.exe /d /c start.cmd init-demo --database $db
cmd.exe /d /c start.cmd status --database $db
cmd.exe /d /c start.cmd test
cmd.exe /d /c start.cmd inventory --output test-output/review-phases/inventory

& .\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -p test_s07_lifecycle.py -v
& $python -B -X utf8 scripts/accept_windows.py --browser-package (Join-Path $tool 'browser-tools')
& (Join-Path $nodeDir 'node.exe') --test --test-reporter=tap tests/test_s02_ui_async.cjs tests/test_s03_ui_async.cjs
& (Join-Path $nodeDir 'node.exe') --test --test-reporter=tap tests/test_s07_browser_support.cjs
& .\.venv\Scripts\python.exe -B -X utf8 test-output/review-phases/supplementary-review.py
```

新库显式初始化到 `0016`；重复命令返回 2，库 SHA-256 不变。r4 从检查端看到服务 `ready`，启动前后库字节一致；DPAPI 同机同用户保护往返成功；同库重启后原会话有效。两次退出均有应用进程结束、端口释放及完整关闭日志，随后释放 CMD 批处理确认。

## 3. 模块、授权和异常边界

| 运行 | Python 登记 | 执行通过 | 跳过 | 失败／错误 |
| --- | ---: | ---: | ---: | ---: |
| 备份修复前的模块回归 | 276 | 262 | 14 | 0／0 |
| 本地修复后的原生 Windows r4 全量回归 | 277 | 263 | 14 | 0／0 |

新增的第 277 项覆盖备份拒绝跟随目录联接。Node 页面用例 56 项、验收器用例 5 项单独回读均全过，两套用例也由 Python 入口调用，Python 总数中已计入其包装测试。

| 边界 | 本轮结果 |
| --- | --- |
| O 与跨模块授权 | 同源 CSRF、幂等键、患者对象隔离及撤销回归通过；家属只获得显式授权，仅本人可执行的入口保持约束。实际 Edge 补测见下节。 |
| A 与显式执行 | 五类统计、迟到／更正与原快照、预期修订、任务租约及过期隔离等回归通过。未知外部结果保留原任务和尝试，后续周期没有重派发。 |
| B 的 STAR 限制 | 保留 single_pass；STAR 共享最多 8 次尝试、2 个候选和 60 秒时限。明确中途失败从原步骤和剩余预算续跑，预算耗尽及来源变化阻止发布。未知生成拒绝自动重试、降阶及案例重置，原记录保留。Edge 的真实界面产生 6 次 mock 逻辑调用，显式模型探测网络尝试为 0。 |
| C 的权威状态 | 草稿与正式服务分离、权限最小投影、单一服务、接收方与回执、状态和反馈、匿名同辈、不可变积分账本、兑换并发回归通过。未知履约留在原记录，只有确证未交付等适用状态可触发一次退款。 |
| 临床适配 | CAS 及分类保持延期，支持强度保持 `not_configured`／`null`，缺少方法的自动干预拒绝执行，技术规则和虚构管理员没有医学审核权限。 |

对应约束

### Windows 逐项跳过

以下 14 项均从本轮原始 `full-regression.log` 核对，两轮一致。

| 用例 | 日志原因 |
| --- | --- |
| `test_changed_key_does_not_unlock_existing_ciphertext` | Linux-only filesystem protection backend |
| `test_ciphertext_is_randomized_and_bound_to_context` | Linux-only filesystem protection backend |
| `test_key_and_directory_permissions_are_restricted` | Linux-only filesystem protection backend |
| `test_malformed_keys_are_not_replaced` | Linux-only filesystem protection backend |
| `test_missing_key_is_not_replaced_by_reads_or_writes` | Linux-only filesystem protection backend |
| `test_modified_truncated_and_foreign_ciphertexts_are_rejected` | Linux-only filesystem protection backend |
| `test_parallel_process_initialization_and_restart_use_same_key` | Linux-only filesystem protection backend |
| `test_reads_without_original_key_do_not_initialize_storage` | Linux-only filesystem protection backend |
| `test_symlink_and_hardlink_keys_are_rejected` | Linux-only filesystem protection backend |
| `test_symlink_directory_is_rejected` | Linux-only filesystem protection backend |
| `test_unavailable_key_rolls_back_login_without_exposing_paths` | Linux-only filesystem protection backend |
| `test_writable_parent_or_different_owner_is_rejected` | Linux-only filesystem protection backend |
| `test_signal_stops_worker_and_releases_lock` | POSIX subprocess termination; Windows locking covered by implementation boundary |
| `test_backup_rejects_substituted_upload_link_before_migration` | Unprivileged symbolic-link creation not guaranteed on Windows |

Windows 原生 DPAPI、独立进程单库锁及本轮新增的 Windows 目录联接用例均实际执行通过。

## 4. 实际浏览器

- 标准 r4 在 1365px、390px 分别检查首页、用药管理、支持服务、积分权益、我的。五页选中状态正确、主区有内容、无横向溢出。另两组在患者和管理员界面验证 single_pass 单调用、STAR 六调用及模型探测零网络。12 组通过，无页面异常。
- 补充 5 组用独立新库验证：查看资源、存草稿及确认共享前后均无正式服务，明确提交后只有一条；显式模拟派发后同一服务进入处理中、完成；首页近期服务打开同一服务编号并保存三维反馈；家庭绑定不自动授权，仅授 `dialogue:read` 时家人可读而无发送控制；人为延迟切换对象期间导航被禁用且旧对话消失，原家人会话在撤权后读取返回 403。5 组通过，无页面异常。

## 5. Worker、备份升级与恢复

- 显式 `start.cmd ... worker --once` 在验收库运行，识别 3 位虚构患者、准备 6 个节点、无 issues。测试覆盖独立进程单库互斥、重启释放锁、web 与健康检查不触发任务、原 7/28 天节点与 24 小时窗、旧租约令牌拒绝，以及跨周期未知结果不重派发。
- 实际执行 `start.cmd migrate --database <隔离0014库> --stopped --output <私有备份目录>`，先备份再升到 `0016`。独立只读复核验证备份 manifest SHA-256、备份和升级后库的 `integrity_check` 与 `foreign_key_check`、80 张原业务表指纹、原虚构夹具行。0015→0016 检查点保留及注入 DDL 失败回滚的回归也通过。
- 补充恢复使用另一个已停止的 `0016` 夹具库，调用真实 `start.cmd backup --stopped` 后核验数据库与虚构附件两个 manifest 哈希，复制到全新目录，执行 `start.cmd status` 并实际启动。84 张非迁移登记业务表逐表指纹相同，迁移登记另核对为 0016，数据库完整、无外键违规。原 DPAPI 会话在同账户同机器下继续可用，原服务及反馈值一致；原隔离库 SHA-256 保持不变，两次补充服务均正常停机。

### 本轮发现与整改证据

| 发现 | 修复前 | 修复后 |
| --- | --- | --- |
| POSIX 启动入口的 Git 模式和行尾 | 基线 `100644`，本机默认检出 CRLF | 同一脚本 blob，模式 `100755` 且强制 LF，归档可执行、Windows Git Shell 入口复验通过 |
| Windows 备份跟随 `files-demo` 目录联接 | 把隔离夹具中的虚构目标文件复制进备份，迁移返回 0 并推进到 0016 | 备份拒绝 Windows 目录联接及符号链接，迁移返回 2，未复制目标文件、无完成 manifest，隔离 0014 库字节保持；同类嵌套用例纳入全量回归 |

旧夹具及原始日志原地保留。验收和复验使用新目录且只触及虚构数据。目录联接拒绝后留有不完整目录供排查，`manifest.json` 缺失。

## 6. 交付状态及证据边界

- 这次已提交本地修复，并将 R0061/V0061 追加到本地记录提交 `eaa176ba2fad4674a0fa7beaf6b3dde909e1e446`。两份历史文件相对 Git 基线的原字节前缀及 SHA-256 相同。远端 `develop` 仍是固定基线，没有执行推送或合并。原工作区和原运行数据没有变更，旧验收与失败记录保留。
- 远端修复接收、修复分支的 Linux 完整预演、依赖 `py` launcher 的最外层双击路径仍待验证或交付。发布包专用清单在新克隆中不存在，本次源码完整性以 Git 提交、非浅克隆和本地差异为据。
- 演示保持本机回环、虚构身份、mock 模型和模拟履约。真实认证、设备、模型网络、机构及履约、系统推送均未接入，CAS、分型／阈值、强度方法和医学审核资质也未配置。保护凭据仍受原 Windows 用户／机器或原 Linux UID／私有密钥约束。本轮没有调用真实模型、上传运行数据或开展新业务阶段。

证据只留本地。
