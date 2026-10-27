# Dayframe 1.0

每天留下一帧，慢慢看见自己。一个默认离线、由你保管原图的个人自拍与日记档案。

## 运行

安装并启动 Docker Desktop（Windows 使用 Linux containers），下载本仓库后：

```powershell
docker compose up -d
```

打开 **http://localhost:8765**。首次使用会创建空归档，没有演示照片。镜像为 `ghcr.io/pppel-lg/dayframe:1.0.0`。若 GitHub Packages 首次下载要求登录，可以从 [Releases](https://github.com/pppel-lg/DayFrame/releases) 下载 Docker 镜像压缩包后执行 `docker load -i dayframe-1.0.0-linux-amd64.tar.gz`；或运行 `docker compose up -d --build` 从源码构建。

Windows 也可执行 `./scripts/start.ps1`，本地构建用 `./scripts/start.ps1 -Build`。界面和摄像头必须在本机 `localhost` 下打开。普通局域网 HTTP 不提供浏览器实时摄像头安全上下文。

## 数据在哪里

默认使用 Docker 命名卷 `dayframe_archive` 和 `dayframe_backups`，容器内分别为 `/data`、`/backups`。升级、删除或重建容器不会删除卷；**不要执行 `docker compose down -v`**，它会删除卷及其中的数据。

建议日用时将归档挂载到自己可直接访问的目录，备份挂载到另一块磁盘：

1. 复制 `.env.example` 为 `.env`，设置 `DAYFRAME_ARCHIVE` 与 `DAYFRAME_BACKUP_DIR` 为两个独立的绝对目录。
2. Windows 例：`DAYFRAME_ARCHIVE=D:/DayframeArchive`，`DAYFRAME_BACKUP_DIR=E:/DayframeBackups`。
3. 启动：`docker compose -f compose.yaml -f compose.bind.yaml up -d`。
4. Linux 主机先创建目录并授予 UID/GID `10001:10001` 写权限。应用容器以非 root 用户运行。

首次从默认卷改到自选目录，需要先备份并复制现有归档。挂载空目录会打开全新档案，不会自动迁移旧卷。更改路径前阅读 [备份与恢复](docs/BACKUP_RESTORE.md)。

## 能力

- 摄像头预览、选择设备、拍摄、重拍和文件导入；镜像预览与输出分开；叠层仅辅助构图。
- 逻辑记录日期、心情、日记、标签、手动城市；同日多张照片，显式确认切换主图。
- 月历、年度热力图、分页时间轴、筛选和按同一口径计算的记录统计。
- 不可变原图、开放 JSON sidecar、SQLite 可重建索引、完整性检查及回收站。
- 带全量 SHA-256 清单的独立备份，恢复至新目录，导出可离线阅读的日历。
- 往年同日回忆、日期对比、地点回顾、未来信件和年度 HTML 报告。
- 容器中包含 FFmpeg，用每个日期的一张主图制作视频；不覆盖源文件。
- 手机临时配对、上传暂存、电脑确认入库。默认不启动上传监听。

年报选择 HTML 导出，PDF 可用浏览器“打印 → 另存为 PDF”。地图采用离线地点列表，不调用第三方瓦片。未来信件是界面时间锁，磁盘中的 JSON 未加密。

## 手机上传（可选）

```powershell
docker compose -f compose.yaml -f compose.phone.yaml up -d
```

在电脑界面开启本次配对，填入电脑在私有局域网的 IP（如 `http://192.168.1.20:8766`），用同一 Wi-Fi 的手机扫描二维码。上传只进入待确认列表；必须在电脑批准才加入归档。会话 10 分钟后失效，可随时关闭。关闭配对后独立上传服务停止；彻底移除宿主机端口映射需使用默认 Compose 配置重新创建容器。

只在可信私有 Wi-Fi 使用。手机传输为 HTTP，不宣称端到端加密。手机不能浏览私人归档。需要允许 Windows 防火墙上的 8766 私有网络入站。不要将 8765、8766 转发至公网。

## 提醒和登录启动

提醒由打开的界面提供。可在设置中开启并选择时间；浏览器/应用关闭时不保证提醒。

Windows 登录启动是明确选择的宿主机操作，容器不会修改系统：

```powershell
./scripts/login-startup.ps1
# 取消
./scripts/login-startup.ps1 -Remove
```

Docker Desktop 本身也需要开启登录启动。此版本是 Docker 本地应用，不提供 Tauri/Windows MSI 安装包。

## 本地开发

Python 3.12+、Node 22+：

```powershell
python -m pip install -r requirements-dev.txt
npm ci --prefix frontend
npm run build --prefix frontend
$env:DAYFRAME_DATA = 'D:/DayframeArchive'
$env:DAYFRAME_BACKUPS = 'E:/DayframeBackups'
python -m uvicorn backend.dayframe.main:app --host 127.0.0.1 --port 8765 --no-access-log
```

前端热更新另开终端：`npm run dev --prefix frontend`（Vite 代理 `/api` 至 8765）。避免让开发环境指向唯一正式归档。

```powershell
python -m pytest backend/tests -q
npm run build --prefix frontend
docker compose config
docker build -t dayframe:local .
```

CI 会实际构建 Linux 镜像、启动容器、运行导入/编辑/索引重建/校验/备份/导出检查，然后发布到 GHCR，并为首次成功的 1.0.0 发布附上可 `docker load` 的镜像文件和校验清单。

可选浏览器回归：安装 `requirements-e2e.txt` 并执行 `python -m playwright install chromium`，在**专门的空测试归档**上启动服务后运行 `python scripts/browser-smoke.py`、`python scripts/browser-edge-smoke.py`。这些脚本会写入合成测试照片，不要对正式个人归档执行。

## 文档

- [归档协议](docs/ARCHIVE_FORMAT.md)
- [备份、恢复、迁移](docs/BACKUP_RESTORE.md)
- [隐私和安全边界](docs/SECURITY.md)
- [测试记录与已知限制](docs/VERIFICATION.md)
- [API 契约](docs/API.md)
- [版本记录](docs/CHANGELOG.md)
- [原始需求](Dayframe.md)

原始需求中的 Tauri 是建议技术栈。本次用户明确要求 Docker 交付，架构决策记录在 [设计说明](docs/superpowers/specs/2026-10-27-dayframe-design.md) 中；长期数据协议与安全要求保持为产品基线。
