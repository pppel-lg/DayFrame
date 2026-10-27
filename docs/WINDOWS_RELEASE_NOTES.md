# DayFrame 1.1.0 — Windows 桌面版

Windows 10/11 x64 的当前用户 NSIS 安装包。Tauri v2 管理窗口与打包的 FastAPI 服务，使用随机本机端口；生产 React、FFmpeg 和 WebView2 离线安装程序随包分发。日常使用无需 Docker、Python、Node.js 或 Rust。

- 下载 `DayFrame-1.1.0-windows-x64-setup.exe`，用 `SHA256SUMS` 核对 SHA-256，双击安装后从开始菜单打开 DayFrame。
- 此版本未做代码签名，可能触发“未知发布者”或 SmartScreen 提示。核对来源和摘要后再决定运行，无需关闭系统防护。
- 默认数据为 `%LOCALAPPDATA%\DayFrame\Archive`，备份、日志和设置在同级 `Backups`、`Logs`、`Settings`。自选路径经验证后保存，重启生效，不自动迁移或合并数据。
- 安装、升级与卸载默认保留个人归档。升级前建议创建并校验独立备份；安装程序和个人数据分开保存。
- 保留归档格式 1、不可变原图和 JSON 权威、可重建 SQLite、校验备份、离线导出及明文未来信件。手机配对仍须主动开启，HTTP 局域网传输未加密。
- 保留全部八个页面；界面采用本地中文字体、暖白与鼠尾草配色，包含空归档状态，不提供虚构照片或记录。
- v1.0.0 Docker 镜像与附件保持独立，不由此发布替换。

发布门禁要求在 Windows runner 上实际构建并静默安装这个安装包，检查真实 WebView2 页面/API、退出和重开、测试数据保留及端口 8765 冲突；摘要和来源提交记录在 `build-info.json`。对应运行的日志与烟雾验证报告位于 GitHub Actions artifacts。真实摄像头驱动、物理手机、第二台干净电脑、系统打印对话框、125%/150% 实机缩放和断电行为仍需人工验收，不能由 CI 结果推定。

安装、数据和卸载说明见 [Windows 安装文档](https://github.com/pppel-lg/DayFrame/blob/v1.1.0/docs/WINDOWS_INSTALL.md)，旧 Docker 数据见 [迁移文档](https://github.com/pppel-lg/DayFrame/blob/v1.1.0/docs/WINDOWS_MIGRATION.md)，源码构建见 [构建文档](https://github.com/pppel-lg/DayFrame/blob/v1.1.0/docs/WINDOWS_BUILD.md)。
