# 搭建与网页使用路径

本指南重建应用 0.7.3、schema 0016。示例使用新目录和虚构数据，在自己的电脑访问 `127.0.0.1`。同版本界面和流程来自归档源码；场景日期按初始化当天计算，编号和时间戳由各自实例生成。

## 1. 备齐文件与工具

把本交付目录完整放在同一个位置。准备程序会先核对 `project-source.tar.gz` 和 `dependencies.zip` 的 SHA-256，再在新目录解包并创建独立 venv。包内含 Windows 21 个、Linux 24 个锁定的 Python wheel，以及 Playwright 1.62.1 和 playwright-core 1.62.1 的离线包。

| 工具 | Windows 11 x64 | Debian 13 x86-64 |
| --- | --- | --- |
| Python | CPython 3.14.10 x64。安装管理器可用 `py install 3.14.10`；离线可运行官方 3.14.10 x64 安装器并安装 launcher。 | 解压锁定的 CPython 3.14.10 Linux 归档，将其 `bin` 目录放到 PATH。 |
| Node 和 npm | Node 24.22.3 x64，附 npm 11.19.1。解压官方 ZIP，将包含 `node.exe` 与 `npm.cmd` 的目录放到 PATH。 | Node 24.22.3 x64，附 npm 11.19.1。解压官方 tar.xz，将其 `bin` 目录放到 PATH。 |
| 浏览器 | 本机 Edge 或 Chrome。验收使用 Edge 157.0.4341.60。 | 本机 Chromium。验收使用 156.0.8078.79。可用 Debian 软件源安装 `chromium` 和 `fonts-noto-cjk`。 |

官方归档下载地址及 SHA-256 在 [runtime-lock.json](runtime-lock.json)。如果收到了另发的 `dachaung-runtime-cache-2026-11-19.zip`，解压即可获得四个对应运行时归档。另发的缓存包只含上游 Python/Node 发布文件。浏览器用目标机器上同版本的已安装程序或从官方渠道获得；记录实际版本，区分相同源码和相同浏览器构建。Node/npm 用于自动验收。普通网页使用由 Python 服务和浏览器完成。

Windows 在终端检查 `py -3.14 --version`、`node --version`、`npm.cmd --version`。Windows PowerShell 可用 `Get-FileHash -Algorithm SHA256 -LiteralPath <下载的文件>`。Linux 在终端检查 `python3.14 --version`、`node --version`、`npm --version`、`chromium --version`，用 `sha256sum <下载的文件>` 校验归档。Linux 的 Python 归档解压后有 `python/bin/python3.14`，Node 归档解压后有 `node-v24.22.3-linux-x64/bin/node`。两者解压到同一个运行时目录时，可用 `export PATH="$runtime/python/bin:$runtime/node-v24.22.3-linux-x64/bin:$PATH"`，其中 `runtime` 是该目录的绝对路径。

## 2. Windows 搭建与启动

在 PowerShell 进入存放本 `USE.md` 的交付目录。下面的 `dachaung-run` 应是一个新的目录，可换成自己电脑上的其他绝对路径。准备时只使用已打包的 Python wheel。

```powershell
$run = Join-Path $env:LOCALAPPDATA 'DachaungDemo/dachaung-run'
py -3.14 -B -X utf8 .\prepare.py --target $run
if ($LASTEXITCODE -ne 0) { throw '项目准备失败，请看上一条输出。' }
Set-Location -LiteralPath (Join-Path $run 'app')

$env:APP_ENV = 'local'
$env:AUTH_MODE = 'demo'
$env:LLM_MODE = 'mock'
$env:DIALOGUE_PIPELINE = 'single_pass'
.\start.cmd init-demo --database 'test-output/repro-demo/main/demo.sqlite3' --port 8131
.\start.cmd status --database 'test-output/repro-demo/main/demo.sqlite3' --port 8131
.\start.cmd serve --database 'test-output/repro-demo/main/demo.sqlite3' --port 8131
```

最后一条命令持续运行，看到本机监听后打开 [主站](http://127.0.0.1:8131/)。另开终端可执行 `Invoke-RestMethod http://127.0.0.1:8131/api/v1/health`，预期 `data.readiness=ready`。选「演示患者甲」和「管理自己的用药」，按[人工操作单](MANUAL-TEST.md)开始。

在同一应用目录的另一终端准备两套辅助场景，各命令执行成功后保留生成器输出。日期窗口和初始余额以其输出为准。

```powershell
& .\.venv\Scripts\python.exe -B -X utf8 -m medplatform.demo_s03 --database 'test-output/repro-demo/analytics/demo.sqlite3'
& .\.venv\Scripts\python.exe -B -X utf8 -m medplatform.demo_points --database 'test-output/repro-demo/points/demo.sqlite3'
```

再分别在两个终端进入应用目录，每个终端执行一行。

```powershell
.\start.cmd serve --database 'test-output/repro-demo/analytics/demo.sqlite3' --port 8132
.\start.cmd serve --database 'test-output/repro-demo/points/demo.sqlite3' --port 8133
```

打开 [统计报告](http://127.0.0.1:8132/)和[积分兑换](http://127.0.0.1:8133/)。分别预期 14 个已到时段中 10 次本人确认，以及通过虚构业务 API 核验产生的 83 分。三个端口使用独立数据库。

## 3. Linux 搭建与启动

在终端进入存放本 `USE.md` 的交付目录。确保 `python3.14`、`node` 与 `npm` 均指向上述版本。浏览器可用 Debian 的软件包管理器安装。

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends chromium fonts-noto-cjk
run="$HOME/dachaung-run"
python3.14 -B -X utf8 ./prepare.py --target "$run" && cd "$run/app"
```

准备成功后，在新建的 `app` 内启动。归档保存了 `start.sh` 的执行权限与 LF 行尾。

```sh
export APP_ENV=local AUTH_MODE=demo LLM_MODE=mock DIALOGUE_PIPELINE=single_pass
./start.sh init-demo --database test-output/repro-demo/main/demo.sqlite3 --port 8131
./start.sh status --database test-output/repro-demo/main/demo.sqlite3 --port 8131
./start.sh serve --database test-output/repro-demo/main/demo.sqlite3 --port 8131
```

使用同一个浏览器地址。要准备报告和兑换辅助场景，在另一个终端进入 `app` 执行以下命令，再在两个独立终端分别执行对应启动命令。

```sh
.venv/bin/python -B -X utf8 -m medplatform.demo_s03 --database test-output/repro-demo/analytics/demo.sqlite3
.venv/bin/python -B -X utf8 -m medplatform.demo_points --database test-output/repro-demo/points/demo.sqlite3

# 每行在不同的终端执行
./start.sh serve --database test-output/repro-demo/analytics/demo.sqlite3 --port 8132
./start.sh serve --database test-output/repro-demo/points/demo.sqlite3 --port 8133
```

## 4. 重跑自动验收

手验库与自动验收生成的库相互隔离。先把下面的 `$run` 或 `run` 设为第 2 或第 3 节建好的目录，再进入其 `app`。

Windows 允许联网安装锁定依赖时，运行仓库外层一键脚本。目录名可含普通空格和中文，应避开 CMD 会解释的符号 `& | < > ^ % ! "`。完成后查看脚本输出所示的新 `RESULT.json`，正常退出码为 0。

```powershell
cmd.exe /d /s /c 'WINDOWS_ACCEPTANCE.cmd <NUL'
```

Windows 保持 Python 和 Playwright 离线安装时，先在同一终端指定 wheel 路径，把锁定的两个 Playwright 包都交给 npm，再运行原生验收器。验收器会创建独立 venv，并使用本机浏览器和 `start.cmd`。

```powershell
$tools = Join-Path $run 'browser-tools'
$tgz = Join-Path $run 'dependencies/playwright'
$wheelDir = (Resolve-Path -LiteralPath (Join-Path $run 'dependencies/windows-x64')).Path
$env:PIP_NO_INDEX = '1'
$env:PIP_FIND_LINKS = ([System.Uri]::new($wheelDir)).AbsoluteUri
npm.cmd install --prefix $tools --offline --ignore-scripts --no-audit --no-fund (Join-Path $tgz 'playwright-1.62.1.tgz') (Join-Path $tgz 'playwright-core-1.62.1.tgz')
if ($LASTEXITCODE -ne 0) { throw 'Playwright 离线安装失败。' }
py -3.14 -B -X utf8 scripts/accept_windows.py --browser-package $tools
```

Linux 使用准备好的 venv 和真实 Chromium。软件模拟的慢速虚拟机可加 `--rehearsal-timeout-multiplier 4`。

```sh
tools="$run/browser-tools"
tgz="$run/dependencies/playwright"
npm install --prefix "$tools" --offline --ignore-scripts --no-audit --no-fund \
  "$tgz/playwright-1.62.1.tgz" "$tgz/playwright-core-1.62.1.tgz" &&
python3.14 -B -X utf8 scripts/accept_windows.py --rehearsal --venv .venv \
  --browser-package "$tools" --browser-executable "$(command -v chromium)"
```

Windows 验证 `status=passed`、`native_windows=true`。Linux 验证 `status=rehearsal_passed_not_windows`、`native_windows=false`。两边须有 12 组真实浏览器。最终实测 Windows Python 登记 277，263 执行通过、14 个平台跳过；Linux 277 执行通过、0 跳过。两边 0 失败、0 错误。14 项逐项原因在 [platform-skip-crosscheck.json](platform-skip-crosscheck.json)。

## 5. 停止、重开、worker 与备份

- 用 `Ctrl+C` 关闭对应服务。再次运行时，对同一个数据库直接执行原来的 `serve` 命令。重复初始化会拒绝覆盖。端口被占用时换一个端口，数据库路径仍使用原来的路径。
- 如需做 worker 检查，在另一终端把系统对应入口接上 `worker --once --database test-output/repro-demo/main/demo.sqlite3 --port 8131`。根据输出核对同库状态；Web 服务需要显式启动独立 worker。
- 备份前停止该库的全部写进程。使用系统对应入口执行 `backup --stopped --database <数据库路径>`。保留私有备份目录与原库。恢复时在一个新的测试目录按备份 `manifest.json` 复制数据库与所列附件，再用新地址执行 `status` 和 `serve`。历史保护凭据需要原 Windows 用户与机器，或原 Linux UID、密钥及初始化标记。详情见归档内 `docs/S07/统一运行与备份.md`。

## 6. 使用 GitHub 克隆和补丁复现

已有仓库的用户仍建议使用新克隆。这条路径用于重建源码，前面交付归档所附的清单和离线依赖仍由本包提供。

```sh
git -c core.autocrlf=false clone --branch develop --single-branch https://github.com/kevinlee134679-web/dachaung.git dachaung-from-github
cd dachaung-from-github
git checkout --detach 2173030cd6c268674a0a475550e1a1af0333c95f
git apply --check --index "<交付目录>/source-fixes.patch"
git apply --index "<交付目录>/source-fixes.patch"
git ls-files --stage start.sh
git write-tree
```

索引显示执行位 `100755`，树哈希为 `49db176ce5d64e74bd42ff39be2a7d4e118e41d0`。文件原字节与权限以该 Git 树为准。要从补丁重建部署文件，用 `git archive --format=tar -o audited-app.tar 49db176ce5d64e74bd42ff39be2a7d4e118e41d0`，再解包到新目录，免受 Windows 检出行尾设置影响。前面交付包的 `project-source.tar.gz` 已执行这一归档步骤，并附逐文件清单；按第 2 或第 3 节可直接部署。现有 venv、运行库、个人配置、浏览器 Cookie、密钥不在复现输入中。
