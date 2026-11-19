# Windows 实机验收包（0.7.3，验收脚本r4）

应用0.7.3，schema0016。此包用于完成剩余Windows验收，**不是“Windows已验收通过”的证明**。GitHub按负责人要求留到S06/S07验收后统一上传，本包不访问GitHub或调用真实模型/机构。

r2修订：原脚本只等待外层CMD进程，不能区分“服务尚未停止”和“服务已停止、批处理仍等待确认”。现在单独核验本次启动的实际应用进程句柄、测试端口释放、本轮正常shutdown日志三项；确认服务已正常退出后才单独释放空闲命令壳。服务本身需要强制清理仍判失败，结果会附shutdown_diagnostic，不把强杀服务改成通过。该修订的Windows实机结果仍需重新运行确认。

r2的后续Windows实机已确认两次正常停止和原会话重启通过；下一步浏览器创建会话时响应等待超时，旧浏览器脚本未处理的Promise导致具体点击/页面错误丢失。r3把点击与响应同时纳入异常处理，按本地API请求完成判断页面就绪，逐步保存进度；最终摘要直接附browser_failure的步骤、具体错误、页面提示和脱敏请求路径。不会绕过页面操作直接调用API，也不会把缺响应、后端错误或超时改判通过。

r3真实Windows已通过前九项，包括12组浏览器、worker、保留80张旧表的升级。完整275项回归有1失败、2错误、14项平台跳过：worker测试父子进程编码不一致、备份数据库连接未关闭造成Windows文件占用、浏览器测试依赖真实毫秒计时。r4分别固定子进程UTF-8、显式关闭备份及测试/验收读取连接、用虚拟时钟检查相同等待语义；新增成功/异常路径都释放连接的回归。失败摘要新增regression_failure诊断。原14项平台跳过未扩张，r4仍需真实Windows复验。

## 运行（无需管理员权限）

1. 把整个ZIP解压到一个**新的目录**，例如 `D:\dachaung-windows-check`。不要放进已有演示工程，也不要只复制cmd文件；路径可含中文和空格，请避免 `& | < > ^ % ! "` 等命令行特殊字符。
2. 确认电脑有 **CPython3.14（验证基线3.14.10）**、**Node.js24 LTS（含npm）**，以及 **Microsoft Edge 或 Chrome**。原项目已有这些工具时直接使用。没有时先用各软件官方安装器安装，再重新打开终端。脚本不会安装系统软件或索取管理员权限。
3. 双击根目录 **WINDOWS_ACCEPTANCE.cmd**，等待完成。它会联网安装项目的锁定Python依赖，以及独立目录中的Playwright1.62.1测试工具；不会下载或替换系统浏览器。
4. 把窗口最后的 **WINDOWS_ACCEPTANCE_RESULT=...** 整行复制回聊天。也可以复制它提示的 `RESULT.json` 内容。成功会显示 `"status":"passed"` 和 `"native_windows":true`；失败也把这行发回，先不删除测试目录，我会按实际失败修复。

如果窗口提示找不到py，在命令提示符运行 `py -0p`，确认已安装3.14；若找不到node/npm，安装Node.js24 LTS并重新打开终端。请勿把旧Linux虚拟环境复制到Windows。

## 自动检查内容

- 校验包内源码SHA256（发布包包含package-manifest.json）。
- 创建独立venv与全新虚构库，实际执行 `start.cmd` 初始化/启动；重复初始化拒绝且原字节不变。
- 直接调用当前Windows用户的原生DPAPI；同库重启后原Cookie/受保护会话仍有效。
- 在实际系统Edge/Chrome中检查桌面与手机宽度的五个导航，实际single_pass、STAR六步与零网络mock探测，共12组。
- 显式worker一次；备份后0014→0016升级，保留80张旧业务表中的虚构夹具。
- 完整Python回归（当前276项，包含原页面Node56项和浏览器验收器Node5项）；Windows不适用的Linux/POSIX用例按实际skipped计数报告，不伪装全部执行。
- 正常停止本次创建的实际服务进程，核对本轮shutdown完成日志并释放测试端口；外层CMD单独处理。停止失败也会记录为失败；不会结束其他Python或浏览器进程。

每次使用新的 `test-output/windows-acceptance/<时间>-<随机号>/` 保存测试库、私有日志、浏览器结果与RESULT.json，不读取、清空或升级原演示库。不打包Linux私钥、运行数据库、.env或Cookie。请只回传结果摘要；原始日志按失败需要再定向排查。

失败时，`server.log` 就在终端 RESULT_FILE 所指的 RESULT.json 的同一个文件夹。用记事本打开即可；需要排查时复制末尾约40行，不要删除旧失败目录，也不要覆盖解压新包到旧目录。

`scripts/accept_windows.py --rehearsal`仅供Linux检查脚本流程，结果固定标记 `rehearsal_passed_not_windows`，不能关闭Windows实机验收。当前准备过程已在Linux预演，真正Windows结果等待这次运行。
