# 大创项目复现交付

应用 0.7.3，数据库结构 0016。本包用于在另一台电脑搭建同版本的本地虚构演示。支持已核验的 Windows 11 x64 和 Debian 13 x86-64 路径。

1. 从[《搭建与网页使用路径》](USE.md)安装或使用固定版本的运行时，执行 `prepare.py` 在新目录离线安装项目的 Python 依赖。
2. 初始化新的本地演示数据库，启动主站及可选的统计、积分场景。
3. 按[《网页人工验收操作单》](MANUAL-TEST.md)操作，按需执行一键验收或 Linux 预演。

| 文件 | 用途 |
| --- | --- |
| [USE.md](USE.md) | Windows、Linux 的搭建、启动、测试、重开和备份路径 |
| [MANUAL-TEST.md](MANUAL-TEST.md) | 本人、家属、管理员及三套网页的手验流程 |
| [AUDIT.md](AUDIT.md)、[audit-evidence.json](audit-evidence.json) | 可共享总审报告与脱敏结构化证据 |
| [platform-skip-crosscheck.json](platform-skip-crosscheck.json) | Windows 的 14 项平台跳过及对应 Linux 实跑结果 |
| `project-source.tar.gz` | 从实测提交导出的 325 个源码文件和新增的逐文件 SHA-256 清单 |
| `source-fixes.patch` | 从 GitHub 固定基线重建实测源码的 Git 补丁 |
| `dependencies.zip`、`prepare.py` | 两个平台的 Python 锁定 wheel、Playwright 离线包和准备脚本 |
| [runtime-lock.json](runtime-lock.json)、[package-checksums.json](package-checksums.json)、[dependency-checksums.json](dependency-checksums.json) | 固定运行时下载地址、浏览器版本及归档和逐个依赖的校验 |

GitHub 基线为 `2173030cd6c268674a0a475550e1a1af0333c95f`，已验收源码为 `b61a4cb74afb29f7a1eea32093980fc4c49f2e6f`。GitHub 基线包含应用和初始化数据，完整跨平台验收需要本包的补丁、发布清单和外部运行时。优先用本包自带源码复现；已有克隆的使用者可按 USE.md 在新检出应用补丁。

应用只监听本机，使用虚构身份、本地 SQLite 和 mock 模型。运行库、Cookie、密钥、真实配置、浏览器配置和私人原始日志由使用者所在环境管理。早期报告中的人员截图与环境情况为历史证据。

## 手动上传到 GitHub

将外层交付 ZIP 解压。目标为 `kevinlee134679-web/dachaung` 的 `develop/handoff-2026-11-19/`。在网页先用 **Add file → Create new file** 创建 `handoff-2026-11-19/README.md`，填入本文件并提交。在该目录用 **Add file → Upload files** 上传同目录的其余文件。提交前查看改动列表，路径应全部位于新的子目录。

另外提供的 `dachaung-runtime-cache-2026-11-19.zip` 保存在本地，GitHub 上的安装者可按 runtime-lock.json 获取同版本官方运行时。 [GitHub 网页上传说明](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)
