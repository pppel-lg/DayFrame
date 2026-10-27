# Docker 与 Windows 桌面迁移

Docker 1.0.0 与 Windows 桌面 1.1.0 均使用 [归档格式 1](ARCHIVE_FORMAT.md)。迁移复制完整归档；不要只复制 `index/dayframe.sqlite3`。JSON、原图、信件和归档配置都应保留，SQLite 索引可以重建。

**先完成校验备份，再停止旧应用，最后复制。** 不要让 Docker 与桌面程序同时打开同一个归档；更改桌面路径不会自动搬移数据。保留旧副本，核对完成前不删除 Docker 容器、卷或原目录。

## 从 Docker 默认命名卷迁移

先在旧界面执行“立即备份”，确认成功并记录归档条数、日期和需要核对的记录。然后在原 Compose 所在目录停止服务，保留容器与卷：

```powershell
docker compose stop dayframe
$taskContainerId = docker compose ps --all --quiet dayframe
if (-not $taskContainerId) { throw '没有找到 DayFrame 容器；不要创建新容器覆盖原配置。' }

$taskArchivePath = 'D:\DayFrameMigration\Archive'
$taskBackupPath = 'D:\DayFrameMigration\Backups'
if ((Test-Path -LiteralPath $taskArchivePath) -or (Test-Path -LiteralPath $taskBackupPath)) {
    throw '请选择两个尚不存在的迁移目标目录，避免混入或覆盖旧文件。'
}
New-Item -ItemType Directory -Path $taskArchivePath, $taskBackupPath | Out-Null
docker cp "${taskContainerId}:/data/." $taskArchivePath
if ($LASTEXITCODE -ne 0) { throw '归档复制失败；保留原容器和卷。' }
docker cp "${taskContainerId}:/backups/." $taskBackupPath
if ($LASTEXITCODE -ne 0) { throw '备份复制失败；保留原容器和卷。' }
```

路径只是示例，按磁盘空间选择独立目录。`docker cp` 从停止但仍存在的容器复制完整挂载内容。不要执行 `docker compose down -v`、`docker volume rm` 或清理卷；它们会删除数据。若旧容器已不存在，先使用 Docker Desktop 的 Volumes 导出原 `dayframe_archive` 与 `dayframe_backups`，不要把空新卷误认为旧归档。

安装并打开桌面应用，在设置中选择复制后的 Archive 和 Backups，保存后重启。首次默认空归档不影响复制的目录。执行完整性检查，核对原图、日记、信件、主照片、日期和备份列表；有问题时保留日志与原副本，不以重建索引代替缺失原图。

## 已使用 Docker 自选目录

停止原 Docker 服务，将原宿主机归档目录和备份目录复制到新的独立位置，再通过桌面设置选择新位置并重启。确认文件完整、目录可写。选择原目录直接使用时也必须先停止 Docker，并保留完整备份；两个程序不得并行写入。

## 跨电脑和恢复

关闭 DayFrame 后，把完整归档与独立备份复制到新电脑。在新电脑安装桌面版，设置归档和备份目录，重启并运行完整性检查。绝对路径只保存在该电脑的桌面设置中，归档内照片引用保持相对路径。

从校验备份恢复时，沿用 [备份与恢复](BACKUP_RESTORE.md) 流程恢复到新的空目标。当前恢复副本位于 `Backups\restored\<名称>`；它仍在备份目录内部，不能直接作为桌面归档路径。先关闭应用，将该完整恢复副本复制到备份目录之外的独立空目录，再在设置选择复制后的目录、保存并重启。路径验证会拒绝归档与备份的嵌套或重叠。应用不自动合并两个档案，也不覆盖旧目录。

## 回退

退出桌面应用后，可重新启动旧 Docker 容器访问仍保留的旧卷。复制迁移后两个目录各自独立，桌面新增记录不会自动出现在旧 Docker 卷；回退前先备份桌面新增数据，再决定使用哪一份完整归档。不要盲目用旧副本覆盖新记录。桌面卸载不承担归档迁移，数据是否正确必须由完整性检查和实际抽查确认。
