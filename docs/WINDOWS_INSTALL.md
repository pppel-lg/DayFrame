# Windows 安装和使用

DayFrame 1.1.0 的桌面目标平台为 **Windows 10/11 x64**。安装包是 NSIS `.exe`，使用 Tauri v2、系统 WebView2 和打包的本地归档服务；日常使用不需要 Docker、Python、Node.js 或 Rust。

Windows 安装包须以成功的 [Windows desktop build and release 工作流](https://github.com/pppel-lg/DayFrame/actions/workflows/windows-release.yml)及实际附件为准。本文说明安装流程，不代表已经完成发布或在另一台电脑上验收；实际结果见 [验证记录](VERIFICATION.md)。

## 获取和校验

在 [Releases](https://github.com/pppel-lg/DayFrame/releases) 查找 **v1.1.0** 的 `DayFrame-1.1.0-windows-x64-setup.exe` 和 `SHA256SUMS`。若不存在该版本，Windows 版本尚未正式发布；成功的工作流也可在 Artifacts 中提供同名安装包。v1.0.0 的 Linux Docker 镜像包不能当作 Windows 安装器运行。

下载后在 PowerShell 中核对摘要：

```powershell
Get-FileHash -LiteralPath '.\DayFrame-1.1.0-windows-x64-setup.exe' -Algorithm SHA256
Get-Content -LiteralPath '.\SHA256SUMS'
```

比较完整的 64 位十六进制 SHA-256。此版本没有代码签名，Windows 可能显示“未知发布者”或 SmartScreen 提示。先核对来源和摘要；确认信任该文件后，可使用系统提供的“更多信息 → 仍要运行”。不要关闭系统防护来安装。

## 安装和首次启动

1. 运行安装器，按当前用户安装。应用包内含 WebView2 离线安装程序，供缺少运行时的系统安装；安装后核心归档功能不依赖联网。
2. 从开始菜单启动 DayFrame。首次启动创建空归档，不包含演示照片，也不会自动读取现有照片目录。
3. 在“今日”主动开启摄像头，并在 Windows 提示时允许访问。可选择设备、拍摄或从文件导入。设备和权限有问题时仍可使用文件导入。
4. 保存一条测试记录，再关闭并重新打开应用，确认自己的保存目录可用。正式使用前设置独立备份位置。

应用使用本机随机环回端口，无需预留 8765；不会自动开放防火墙或启动手机监听。真实相机驱动、权限弹窗、物理手机和第二台干净电脑仍需人工验收，自动化不能保证每种设备都可用。

## 数据目录和备份

默认目录在安装目录之外：

| 内容 | 默认位置 |
| --- | --- |
| 原图、日记、信件和归档索引 | `%LOCALAPPDATA%\DayFrame\Archive` |
| 校验备份和恢复副本 | `%LOCALAPPDATA%\DayFrame\Backups` |
| 桌面诊断日志 | `%LOCALAPPDATA%\DayFrame\Logs` |
| 桌面路径设置 | `%LOCALAPPDATA%\DayFrame\Settings` |

设置页可选择其他归档和备份目录。路径必须是可写的独立绝对目录，不能重叠、经过链接/连接点或指向安装/解包、Settings、Logs 等运行目录；非空归档目标必须包含有效的格式 1 `archive.json`。验证失败会显示原因，不会切换。配置保存于 `Settings\desktop.json`，需要重启应用才生效，**不会自动复制、合并或搬移旧数据**。选择一个空目录会打开新的空归档。迁移前按 [Windows 迁移说明](WINDOWS_MIGRATION.md) 复制完整目录。

归档仍使用 [格式 1](ARCHIVE_FORMAT.md)：不可变原图和 JSON 是权威数据，SQLite 可以重建。未来信件是界面时间锁，磁盘 JSON 为明文。把备份放到另一块磁盘，并定期做 [恢复演练](BACKUP_RESTORE.md)。

安装器与卸载器的应用文件不包含上述用户数据目录。升级前仍应完成校验备份；卸载后如需清理归档，应由你单独处理并先确认已有可恢复副本。不要把唯一照片保存在安装目录或临时解包目录。

## 手机上传和提醒

手机上传需要你在设置中明确开启临时配对，并使用可信私有 Wi-Fi。手机只有暂存上传能力，照片须在电脑确认才入库；会话到期或关闭后停止监听。该 HTTP 传输未加密，不能当作端到端加密。防火墙放行由你明确操作，应用不自动修改规则。不要把管理或上传端口映射到公网。

提醒需要界面保持运行；关闭应用后不保证提醒。桌面安装不会自动设置登录启动，现有 `scripts/login-startup.ps1` 是 Docker 启动辅助脚本。

## 常见问题

- 启动失败：检查磁盘空间、目录写入权限及 `Logs`，确认另一个 DayFrame 实例或 Docker 服务没有占用同一归档。应用禁止两个服务同时写同一个归档。
- 选择新目录后看到空白：检查所选路径是否包含 `archive.json`、`photos`、`entries` 等完整内容；改路径不会自动迁移文件。
- 摄像头不可用：在 Windows“隐私和安全性 → 摄像头”检查权限，关闭占用相机的应用，或使用文件导入。首次使用真实设备仍需人工检查。
- 升级或重装：先备份，退出应用，再运行新安装器。核对设置指向的归档与备份目录，执行完整性检查。旧版 Docker 数据按 [迁移说明](WINDOWS_MIGRATION.md) 单独迁移。

源码构建步骤见 [WINDOWS_BUILD.md](WINDOWS_BUILD.md)，本地服务和安全边界见 [DESKTOP_ARCHITECTURE.md](DESKTOP_ARCHITECTURE.md) 与 [SECURITY.md](SECURITY.md)。
