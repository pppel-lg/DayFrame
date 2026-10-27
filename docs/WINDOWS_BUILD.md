# Windows 源码构建

以下步骤面向构建者；最终安装器的使用者不需要安装开发工具。目标版本为 1.1.0、Windows x64。源码中存在构建配置不等于已产出可用安装包，实际构建、烟雾验证与下载结果见 [VERIFICATION.md](VERIFICATION.md)。

## 工具和依赖

在 Windows 10/11 x64 上准备 Git、Node.js 22、Python 3.12、Rust stable 的 `x86_64-pc-windows-msvc` 工具链，以及 Visual Studio Build Tools 的“使用 C++ 的桌面开发”和 Windows SDK。开发时需要 WebView2；发布的 NSIS 配置包含 WebView2 离线安装程序。

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt -r requirements-desktop.txt -r requirements-e2e.txt
python -m playwright install chromium
npm ci --no-audit --no-fund
npm ci --prefix frontend --no-audit --no-fund
rustup target add x86_64-pc-windows-msvc
```

Python 和 npm 依赖分别以 requirements 文件及根目录、frontend 的 lockfile 为准；Rust 依赖以 `src-tauri/Cargo.lock` 为准。初次安装依赖、获取 WebView2 安装程序及构建工具需要联网。

## 开发和打包

使用专用空目录隔离测试数据，避免开发服务接触唯一正式归档：

```powershell
$env:DAYFRAME_DATA_HOME = Join-Path $PWD 'artifacts\desktop-dev-data'
npm run desktop:dev
```

原有浏览器/Docker 开发方式仍可使用，见 [README](../README.md)。桌面运行由 Tauri 管理本地服务，不需要另起固定 8765 端口的 Uvicorn。

打包前运行检查，再构建 x64 NSIS：

```powershell
python -m pytest backend/tests -q
npm run typecheck --prefix frontend
npm run desktop:build -- --target x86_64-pc-windows-msvc
python scripts/sidecar-smoke.py --executable 'src-tauri/binaries/dayframe-server-x86_64-pc-windows-msvc.exe' --output 'artifacts/desktop/sidecar-smoke'
```

Tauri 的 `beforeBuildCommand` 负责生产前端和 PyInstaller sidecar；无需在 `desktop:build` 前重复打包。`npm run sidecar:build` 可单独调试 sidecar 构建，它调用 `python scripts/build-sidecar.py`。构建将真实 React 资源、FFmpeg 和分发说明嵌入独立 sidecar，再通过 Tauri `externalBin` 随安装器分发。

使用显式 target 时，安装器输出位于 `src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/`。安装包由当前构建生成，不能把源码、网页快照或空占位文件改名为安装器。Windows CI 会将唯一的非空输出复制为 `artifacts/desktop/DayFrame-1.1.0-windows-x64-setup.exe`。

## 验证真实安装包

```powershell
python scripts/windows-smoke.py --installer 'artifacts/desktop/DayFrame-1.1.0-windows-x64-setup.exe' --output 'artifacts/desktop/smoke'
Get-FileHash -LiteralPath 'artifacts/desktop/DayFrame-1.1.0-windows-x64-setup.exe' -Algorithm SHA256
```

本地手动构建时先将实际 NSIS 输出复制到上述文件名，或把 `--installer` 改成真实输出路径。脚本会静默安装到隔离位置，启动安装后的应用，以专用 `DAYFRAME_DATA_HOME` 隔离归档，并检查真实 WebView2 页面/API、关闭、重新启动、数据保留和固定 8765 已被占用的情况。日志及测试生成数据保留在输出目录。它会启用仅测试使用的生命周期诊断和 WebView2 调试接口；普通启动不启用这些接口。

自动化使用合成图片与测试归档。真实摄像头、物理手机、防火墙交互、第二台干净电脑及硬件断电仍是人工验收范围；不能把流水线通过写成这些项目已验证。

## CI 和发布边界

`.github/workflows/windows-release.yml` 在 PR、`main`、`codex/windows-desktop`、`v1.1.0` 标签和手动运行时构建。它安装依赖，执行后端测试、类型检查、真实打包、打包后端/FFmpeg 验证和安装后烟雾验证，成功后提供安装器、`SHA256SUMS` 和 `build-info.json`；验证日志作为独立 artifact 保留。原有 `.github/workflows/release.yml` 继续负责 Docker 1.0.0。

普通 PR 或分支构建不会创建 Windows Release。只有手动运行并明确选择 `publish=true`，或推送匹配的 `v1.1.0` 标签，才会在安装验证成功后进入单独发布 job。发布前再次核对摘要；已存在的 v1.1.0 会使发布失败，不替换附件，也不接触 v1.0.0 的 Docker 资产。未签名安装器的限制见 [安装说明](WINDOWS_INSTALL.md)。
