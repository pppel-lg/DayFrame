# 第三方依赖

直接依赖版本记录在 `requirements.txt`、`requirements-dev.txt`、`requirements-desktop.txt`、`requirements-e2e.txt`，npm 依赖锁定在根目录和 `frontend/package-lock.json`，Rust 依赖锁定在 `src-tauri/Cargo.lock`。运行时依赖不包含云端图像处理或分析服务。构建时应保留上游版权、许可证及所需分发说明；此清单不是法律意见或全量软件物料清单。

- React、Vite、TypeScript、Lucide、QRCode：各自包内许可证，随安装包保留。
- FastAPI、Pydantic、Uvicorn、Starlette、python-multipart：包内许可证，Python 依赖随镜像安装。
- Pillow、pillow-heif：图像验证与派生预览；不重写导入原图。HEIF 使用平台提供的编解码依赖，不能据此宣称支持所有 HEIF 扩展。
- Noto Sans SC、Noto Serif SC：SIL Open Font License 1.1；字体随构建资源自托管，许可证保留在字体包与应用分发材料中，不请求 Google Fonts。
- FFmpeg：来自 Debian 软件仓库的独立可执行程序，镜像中保留 `/usr/share/doc/ffmpeg/` 及其系统依赖许可证。视频编码器可能涉及 GPL/LGPL 以及当地专利许可；程序不会自动把原图上传至编码服务。
- SQLite：Python 标准库绑定，独立数据库索引可重建。

## Windows 桌面分发

- Tauri v2、其插件与 Rust 依赖：具体版本和许可证见 `src-tauri/Cargo.lock` 及各 crate 的分发说明；JavaScript CLI/API 的解析版本见根目录和前端 lockfile。
- PyInstaller：用于生成独立 Python sidecar；其许可证包含打包应用的分发例外。不要把这一例外解释为免除应用内其他依赖的许可条件。
- imageio-ffmpeg 0.6.0：构建时提供 Windows FFmpeg 可执行程序；Python 包与 FFmpeg 二进制本身的许可分别核对。当前打包程序记录该 FFmpeg 的 GPL 组件（包括 libx264），不宣称它是纯 LGPL 二进制。桌面 sidecar 嵌入 `licenses/FFmpeg-build.txt`、`FFmpeg-license.txt`、`FFmpeg-source.txt`，保留实际 `-version`、`-L` 输出及分发/源码线索。需要对应源码、构建脚本或其他材料时应按实际二进制的许可履行，不能只依据 Python 包许可证判断。
- Microsoft Edge WebView2 Runtime：NSIS 包包含其离线安装程序，运行时按 Microsoft 的适用分发条款提供。它是 WebView2 运行依赖，不是 Node.js 或开发用浏览器。
- NSIS：用于生成当前用户 Windows 安装器；其运行和生成的安装器涉及不同组件的分发条件，保留相应上游说明。
- Playwright 与 Chromium：仅用于开发和 CI 的浏览器验收，不作为 DayFrame 安装器的应用运行时分发。

Windows 发布不等同于完成许可证法律审查。发布者应以打包 sidecar 内实际 `licenses/`、具体 FFmpeg 构建和依赖版本核对分发义务；发现缺失时先补齐，不能把在线包说明当作离线分发材料已存在的证据。

容器基础镜像使用官方 Node 和 Python 镜像。复现依赖审计：`python -m pip_audit -r requirements.txt`，`npm audit`，`npm audit --prefix frontend`；Rust 可使用安装后的 `cargo audit`。审计工具需另行安装，结果是特定日期的漏洞数据库快照，应在后续升级时重新执行。
