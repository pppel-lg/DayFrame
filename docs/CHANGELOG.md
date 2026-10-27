# 版本记录

## 1.1.0 — 2026-10-28 Windows 桌面

- 新增 Tauri v2 原生窗口、PyInstaller 本地服务和 Windows x64 当前用户 NSIS 安装器，包含 WebView2 离线安装程序与 FFmpeg。
- 随机环回端口、一次性启动认证、同源 React/API、单实例、归档独占和受管进程退出。
- 数据默认保存于 `%LOCALAPPDATA%\DayFrame` 的独立 Archive、Backups、Logs、Settings；自选路径验证并保存，重启生效，不自动迁移数据。
- 按参考图调整全部八个页面，保留拍摄、导入、日记、校验备份、导出及主动手机配对；归档格式仍为 1。
- 独立 Windows CI 构建真实安装器并执行安装后烟雾验证；校验成功才提供发布资产，显式发布门禁拒绝覆盖既有版本。Docker 1.0.0 工作流和附件保持独立。
- 补充安装、源码构建、桌面架构、迁移及安全边界说明。安装包未签名；真实硬件和干净第二台电脑的限制见验证记录。

已完成真实 Windows 安装器构建、12组安装版验收与 [v1.1.0 发布](https://github.com/pppel-lg/DayFrame/releases/tag/v1.1.0)。实际结果、校验摘要与人工验收限制见 [VERIFICATION.md](VERIFICATION.md)。

## 1.0.0 — 2026-10-27

- 首次 Docker 本地应用交付；React/TypeScript 界面和 FastAPI 本地归档服务。
- 每日照片、心情日记、月历、年热力图、时间轴及可迁移文件归档。
- 原图和 sidecar、SQLite 索引重建、健康检查、校验备份和新目录恢复。
- 回忆、地点、未来信件、HTML 年报、延时视频和临时手机上传工作流。
- GitHub Actions 测试、容器烟雾验证、GHCR 镜像及 GitHub Release 镜像包。

实际运行结果与未验证设备能力见 [VERIFICATION.md](VERIFICATION.md)。
