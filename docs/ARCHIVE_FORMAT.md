# 归档格式 1

原图字节与 JSON sidecar 是权威来源，SQLite 仅是可重建查询索引。所有持久引用相对归档根目录，不依赖 Windows 盘符或容器路径。

```text
archive.json                 格式、版本、归档 ID、开始日期
photos/YYYY/MM/              不可变原图
entries/YYYY/MM/date.json    当日元数据和照片清单
letters/                     开放未来信件 JSON
index/dayframe.sqlite3       派生查询索引
thumbnails/                  派生缩略图
cache/                       派生临时资源
exports/                     日历、年报、视频
trash/                       待恢复照片
recovery/                    故障或冲突记录
```

`schema_version`、`format_version` 为 1。程序遇到更新的格式版本拒绝写入。实际字段与接口见 [API.md](API.md)，验证模型见 `backend/dayframe/models.py`。

`record_date` 是用户选择的逻辑日期，拍摄 UTC 时刻、时区、导入时刻分开保存。导入未知拍摄时刻不会伪造成记录日期的午夜。重复原图按 SHA-256 提示，不能静默覆盖。同日后续图片默认保留旧主图。

写入先保存完整原件，再原子替换 sidecar，最后更新 SQLite。启动时重建索引可消除 sidecar 比索引新的中断状态；未被引用的原图作为孤立文件报告，不删除。磁盘及文件系统的原子替换保障存在平台边界，应配合独立备份。

回收站属于归档数据管理，不等于永久删除。不要使用磁盘清理工具删除照片、entries 或 letters；缓存和缩略图可以重建。直接编辑 JSON 前请备份，并运行完整性检查和索引重建。
