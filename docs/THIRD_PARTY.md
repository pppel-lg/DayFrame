# 第三方依赖

直接依赖版本锁定在 `requirements.txt`、`requirements-dev.txt`、`frontend/package-lock.json`。运行时依赖不包含云端图像处理或分析服务。

- React、Vite、TypeScript、Lucide、QRCode：各自包内许可证，随安装包保留。
- FastAPI、Pydantic、Uvicorn、Starlette、python-multipart：包内许可证，Python 依赖随镜像安装。
- Pillow、pillow-heif：图像验证与派生预览；不重写导入原图。HEIF 使用平台提供的编解码依赖，不能据此宣称支持所有 HEIF 扩展。
- Noto Sans SC：SIL Open Font License；字体随构建资源自托管，许可证见应用 `/fonts/OFL.txt`，不请求 Google Fonts。
- FFmpeg：来自 Debian 软件仓库的独立可执行程序，镜像中保留 `/usr/share/doc/ffmpeg/` 及其系统依赖许可证。视频编码器可能涉及 GPL/LGPL 以及当地专利许可；程序不会自动把原图上传至编码服务。
- SQLite：Python 标准库绑定，独立数据库索引可重建。

容器基础镜像使用官方 Node 和 Python 镜像。复现依赖审计：`python -m pip_audit -r requirements.txt`，`npm audit --prefix frontend`。审计结果是特定日期的漏洞数据库快照，应在后续升级时重新执行。
