# 验证记录

本文件在交付前更新实际结果；计划中的检查不代表已通过。

## Windows 1.1.0

验证日期：2026-10-28（Asia/Taipei）。[Windows 正式构建、安装验收及发布](https://github.com/pppel-lg/DayFrame/actions/runs/40547896070) 全部成功；[PR Windows 检查](https://github.com/pppel-lg/DayFrame/actions/runs/40547900772) 与 [Docker 检查](https://github.com/pppel-lg/DayFrame/actions/runs/40547900840) 通过。[PR #1](https://github.com/pppel-lg/DayFrame/pull/1) 已合并到 main。

- `python -m pytest -q`：本机 **67 passed, 1 skipped**；Windows runner **68 passed**。本机跳过的是未授权创建符号链接；两者均有一个现有的 TestClient/httpx 弃用警告。
- `npm run build --prefix frontend`：TypeScript 与生产构建通过。Playwright 对照用户提供的效果图核查八个页面、1000px 桌面宽度与390px小屏；合成相机、权限拒绝、日记/心情/城市/标签、主图确认、跨午夜、日历跨月/回到今天/年视图筛选、未来信件、备份恢复和导出回归通过。Browser 插件不可用，使用项目已有 Python Playwright。
- `python scripts/sidecar-smoke.py --executable src-tauri/binaries/dayframe-server-x86_64-pc-windows-msvc.exe`：实际冻结后的 Python/前端/FFmpeg 通过中文和空格路径、随机本机端口、原图字节、元数据、校验/重建索引、备份/恢复、HTML/CSV/MP4、关闭重开持久化。
- `python scripts/windows-smoke.py --installer artifacts/desktop/DayFrame-1.1.0-windows-x64-setup.exe --output artifacts/desktop/smoke --default-install`：实际 NSIS 默认安装与真实 WebView2 界面的 **12 组验收通过**。包括原生目录选择、摄像头拒绝提示与合成拍摄、全部页面、原生下载、8765端口占用、关闭/重开、重复实例、原生重启、仅杀主进程后的整棵后端进程树清理、仅杀后端后的错误提示与正常关闭、重装和卸载保留归档。测试应用的 PATH 只保留 Windows System32，使用自身打包运行时。页面脚本错误与外部网络请求均为0。
- 年报生成可打印的自包含 HTML，已用 Chromium 生成 PDF；实际 Windows 系统打印对话框仍属人工验收，不能据此宣称已通过。

正式安装包：[DayFrame-1.1.0-windows-x64-setup.exe](https://github.com/pppel-lg/DayFrame/releases/download/v1.1.0/DayFrame-1.1.0-windows-x64-setup.exe)，**314,429,906 字节**。SHA-256：`6bd6dc92c7458358f299025bd8c61754605e8ac3e1e69fa813f070382c44d91b`；GitHub Release 附件摘要与 CI 校验清单一致。来源提交：`3f4c2d4625851d03560d0656033e5aad5c7ed8d5`。[Release](https://github.com/pppel-lg/DayFrame/releases/tag/v1.1.0) 同时提供 SHA256SUMS 和 build-info.json。原 v1.0.0 Docker 附件未被覆盖。

真实摄像头驱动和硬件授权、物理手机与防火墙、第二台干净电脑、125%/150% 实机缩放、硬件断电及未签名安装器的实际 SmartScreen 体验仍需人工确认。安装步骤见 [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md)，复现命令见 [WINDOWS_BUILD.md](WINDOWS_BUILD.md)。

## Docker 1.0.0 历史验证

## 当前环境

- Windows，Python 3.12，Node 24。
- 本机未安装 Docker Desktop，WSL 未安装 Linux 发行版；Linux 容器构建与烟雾验证交给 GitHub-hosted runner。
- Browser 插件不可用，界面验证使用 Playwright Chromium。
- 不访问用户个人照片，所有自动化测试图片来自合成 fixture 和隔离临时归档。

## 验证项目

- 后端单元和集成测试：33 passed / 1 skipped（Windows 未授权创建符号链接；Linux CI 中运行）。包含实际手机临时监听器的认证、过期、暂存、批准及关闭测试。
- TypeScript 和生产构建：通过；生产依赖 npm audit 和 Python pip-audit 均未发现已知漏洞。一个上游 TestClient/httpx 弃用警告不影响结果。
- 浏览器核心工作流和响应式截图：最终通过，覆盖合成摄像头拍摄、日记保存、原图字节导入、主照片确认、刷新持久化、全部导航、信件、备份、新目录恢复及 390px 适配；另通过拒绝相机权限后文件导入、跨午夜切换日期、跨日期重复图显式确认、CSV 下载入口、原图缺失状态提示回归。页面脚本错误与 5xx 响应均为 0。
- 与 Docker 相同 HTTP 烟雾脚本的本地运行通过，并在强制停止/重启服务后核对原图、日记和备份仍可用。本地模式跳过 FFmpeg（未安装）以及容器挂载路径断言；远程容器模式强制验证这些项目。
- 实际 Docker 构建及容器集成：[GitHub Actions #1](https://github.com/pppel-lg/DayFrame/actions/runs/40451412866) 全部成功。Linux 后端测试 **34 passed**（符号链接测试也通过）；TypeScript/Vite 构建、三个 Compose 配置校验通过。运行实际非 root Linux 容器后验证原图字节、编辑、索引重建、统计、完整性检查、备份、新目录恢复、自包含 HTML/CSV/年报及 FFmpeg MP4；重启同一个容器后，原图、日记、索引和备份仍可读。
- GitHub 镜像及版本发布：已完成。镜像 `ghcr.io/pppel-lg/dayframe:1.0.0`（另有 latest），摘要 `sha256:40f9b7ce4f4aebbff363aea690a4b6d6b4f3b75ff68183d77cd0bd1c69b0ac1f`。源码发行提交 `5f7a69f107e850a2c2d0146009217637a56e1758`。
- [v1.0.0 Release](https://github.com/pppel-lg/DayFrame/releases/tag/v1.0.0) 已发布可 `docker load` 的 Linux amd64 镜像包（248,495,879 字节）、部署配置包、独立 Compose 文件和 SHA256SUMS。

## 10,000 天数据规模

Windows 本地合成 fixture：10,000 条 sidecar、10,000 张独立照片，无用户照片。最终版本索引重建（含启动孤立/缺图检查）17.057 秒；月范围查询 0.011 秒；年度统计 2.992 秒，结果与条数一致且无健康问题。统计会核查当前原图是否存在，耗时依赖文件系统。对比早期实现的重建 199.213 秒、年度统计 11.085 秒，消除了路径验证中的重复文件系统解析。并不把单台机器结果当成所有硬盘的性能保证。

## 设备与平台限制

真实摄像头驱动授权、物理手机同 Wi-Fi、防火墙、另一台物理机器、断电持久性、Windows 登录任务及 macOS 未由自动化确认。首版通过真实文件测试模拟保存中断、索引损坏和归档迁移；这些测试不能替代所有硬件故障场景。

1.0.0 交付范围为 Docker，未提供 Tauri/MSI 安装包；后续 Windows 1.1.0 状态单独记录在上方。HTML 年报可以打印成 PDF；地点回顾采用离线列表。UI 提醒要求应用页面运行；Docker 登录启动通过用户主动执行的 PowerShell 帮助脚本启用。
