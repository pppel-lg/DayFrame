#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod process_tree;

use process_tree::ProcessTree;
use serde_json::json;
use std::{
    io::{BufRead, BufReader, Read, Write},
    net::{Ipv4Addr, SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, ChildStdin, Command, Stdio},
    sync::{atomic::{AtomicBool, Ordering}, mpsc, Mutex},
    time::{Duration, Instant},
};
use tauri::{Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

struct Backend {
    child: Child,
    input: Option<ChildStdin>,
    tree: Option<ProcessTree>,
}

#[derive(Default)]
struct DesktopState {
    backend: Mutex<Option<Backend>>,
    origin: Mutex<Option<String>>,
    closing: AtomicBool,
    exit_started: AtomicBool,
}

fn trusted(window: &WebviewWindow, state: &DesktopState) -> Result<(), String> {
    let url = window.url().map_err(|_| "无法验证窗口".to_owned())?;
    let origin = format!("{}://{}:{}", url.scheme(), url.host_str().unwrap_or(""), url.port_or_known_default().unwrap_or(0));
    if window.label() != "main" || state.origin.lock().unwrap().as_deref() != Some(&origin)
        || url.path() != "/" {
        return Err("此操作仅可由 DayFrame 主窗口发起".into());
    }
    Ok(())
}

#[tauri::command]
async fn choose_directory(window: WebviewWindow, state: tauri::State<'_, DesktopState>) -> Result<Option<String>, String> {
    trusted(&window, &state)?;
    if state.closing.load(Ordering::SeqCst) { return Err("应用正在关闭".into()); }
    tauri::async_runtime::spawn_blocking(|| rfd::FileDialog::new().set_title("选择 DayFrame 文件夹").pick_folder().map(|p| p.to_string_lossy().into_owned()))
        .await.map_err(|_| "无法打开文件夹选择窗口".into())
}

#[tauri::command]
async fn restart_desktop(window: WebviewWindow, app: tauri::AppHandle, state: tauri::State<'_, DesktopState>) -> Result<(), String> {
    trusted(&window, &state)?;
    if state.exit_started.swap(true, Ordering::SeqCst) { return Err("应用正在关闭".into()); }
    std::thread::spawn(move || {
        std::thread::sleep(Duration::from_millis(200));
        shutdown(&app);
        app.restart();
    });
    Ok(())
}

fn diagnostic(value: serde_json::Value) {
    // Explicit test environment only. Never emit bootstrap credentials.
    if let Some(path) = std::env::var_os("DAYFRAME_SMOKE_STATUS") {
        let _ = std::fs::write(path, value.to_string());
    }
}

fn lifecycle_trace(event: &str) {
    if let Some(path) = std::env::var_os("DAYFRAME_SMOKE_STATUS") {
        let path = PathBuf::from(path).with_file_name("native-events.log");
        if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(file, "{} {}", std::process::id(), event);
        }
    }
}

fn shutdown(app: &tauri::AppHandle) {
    lifecycle_trace("shutdown-enter");
    let state = app.state::<DesktopState>();
    state.closing.store(true, Ordering::SeqCst);
    let backend = state.backend.lock().unwrap().take();
    lifecycle_trace(if backend.is_some() { "shutdown-owned-backend" } else { "shutdown-no-backend" });
    if let Some(mut backend) = backend {
        if let Some(mut pipe) = backend.input.take() { let _ = pipe.write_all(b"\n"); }
        let start = Instant::now();
        loop {
            if matches!(backend.child.try_wait(), Ok(Some(_))) { break; }
            if start.elapsed() > Duration::from_secs(14) {
                let _ = backend.child.kill();
                break;
            }
            std::thread::sleep(Duration::from_millis(50));
        }
        // Closing the job also catches a crashed encoder or extraction child.
        drop(backend.tree.take());
        let _ = backend.child.wait();
    }
    diagnostic(json!({"state":"stopped","pid":std::process::id()}));
    lifecycle_trace("shutdown-finished");
}

fn sidecar_path() -> Result<PathBuf, String> {
    let name = if cfg!(windows) { "dayframe-server.exe" } else { "dayframe-server" };
    let executable = std::env::current_exe().map_err(|_| "无法确定安装位置".to_owned())?;
    let adjacent = executable.parent().unwrap().join(name);
    if adjacent.is_file() { return Ok(adjacent); }
    if cfg!(debug_assertions) {
        let dev = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("binaries/dayframe-server-x86_64-pc-windows-msvc.exe");
        if dev.is_file() { return Ok(dev); }
    }
    Err("安装文件不完整：缺少本地档案组件。请重新安装 DayFrame，个人档案不受影响。".into())
}

fn healthy(port: u16) -> bool {
    let address = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_secs(2)) else { return false; };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = stream.write_all(format!("GET /health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n").as_bytes());
    let mut response = String::new();
    stream.read_to_string(&mut response).is_ok() && response.starts_with("HTTP/1.1 200") && response.contains("\"status\":\"ok\"")
}

fn start_backend(app: &tauri::AppHandle) -> Result<(), String> {
    let mut command = Command::new(sidecar_path()?);
    command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
    // User-supplied shell paths must not override bundled production assets.
    for key in ["FRONTEND_DIST", "DAYFRAME_DATA", "DAYFRAME_BACKUPS", "DAYFRAME_FFMPEG", "PYTHONPATH", "PYTHONHOME"] { command.env_remove(key); }
    #[cfg(windows)] {
        use std::os::windows::process::CommandExt;
        command.creation_flags(windows_sys::Win32::System::Threading::CREATE_NO_WINDOW | windows_sys::Win32::System::Threading::CREATE_SUSPENDED);
    }
    let mut child = command.spawn().map_err(|_| "无法启动本地档案组件。请检查安装文件、杀毒隔离记录与文件夹权限。".to_owned())?;
    let tree = match ProcessTree::attach(&child) {
        Ok(tree) => tree,
        Err(_) => { let _ = child.kill(); let _ = child.wait(); return Err("无法建立安全的子进程管理，请重启应用。".into()); }
    };
    if ProcessTree::resume(&child).is_err() {
        let _ = child.kill(); let _ = child.wait();
        return Err("无法恢复受控的本地档案组件".into());
    }
    let token = format!("{}{}", uuid::Uuid::new_v4().simple(), uuid::Uuid::new_v4().simple());
    let mut input = child.stdin.take().unwrap();
    let output = child.stdout.take().unwrap();
    let message = json!({"token": token});
    let sent = writeln!(input, "{}", message).and_then(|_| input.flush());
    let pid = child.id();
    let state = app.state::<DesktopState>();
    *state.backend.lock().unwrap() = Some(Backend { child, input: Some(input), tree: Some(tree) });
    sent.map_err(|_| "本地档案组件启动中断".to_owned())?;
    let (sender, receiver) = mpsc::channel();
    std::thread::spawn(move || {
        for line in BufReader::new(output).lines().map_while(Result::ok) {
            if let Some(payload) = line.strip_prefix("DAYFRAME_READY ") {
                let port = serde_json::from_str::<serde_json::Value>(payload).ok().and_then(|v| v["port"].as_u64()).filter(|p| *p > 0 && *p <= 65535).map(|p| p as u16);
                let _ = sender.send(port);
                break;
            }
        }
    });
    let port = receiver.recv_timeout(Duration::from_secs(90)).ok().flatten()
        .ok_or_else(|| "打开档案失败。档案可能正由另一个 DayFrame 使用，或目录没有写入权限。请关闭其他实例并检查 %LOCALAPPDATA%\\DayFrame\\Logs\\desktop.log。".to_owned())?;
    if !healthy(port) { return Err("本地档案组件未通过启动检查，请重新打开应用。".into()); }
    if state.closing.load(Ordering::SeqCst) { return Err("应用正在关闭".into()); }
    *state.origin.lock().unwrap() = Some(format!("http://127.0.0.1:{port}"));
    let url = format!("http://127.0.0.1:{port}/desktop/launch?token={token}");
    app.get_webview_window("main").ok_or("主窗口已关闭")?.navigate(url.parse().map_err(|_| "无法打开本地界面")?).map_err(|_| "无法加载本地界面")?;
    diagnostic(json!({"state":"ready","pid":std::process::id(),"sidecar_pid":pid,"port":port}));
    Ok(())
}

fn startup_error(app: &tauri::AppHandle, message: &str) {
    if let Some(window) = app.get_webview_window("main") {
        // The running React page has no launcher callback. Render the terminal
        // error in place: navigating to tauri:// on Windows opens an unsupported
        // external protocol and can block the window's event loop.
        let _ = window.eval(&format!(r#"(() => {{
          const message = {};
          if (typeof window.dayframeStartupError === 'function') {{ window.dayframeStartupError(message); return; }}
          const panel = document.createElement('main');
          panel.setAttribute('role', 'alert');
          Object.assign(panel.style, {{position:'fixed',inset:'0',zIndex:'9999',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',padding:'40px',background:'#f8f7f2',color:'#2c352b',textAlign:'center',gap:'24px'}});
          const heading = document.createElement('h1'); heading.textContent = 'DayFrame';
          const text = document.createElement('p'); text.textContent = message; text.style.maxWidth = '580px';
          const restart = document.createElement('button'); restart.textContent = '重新打开 DayFrame'; restart.className = 'primary';
          restart.onclick = () => window.__TAURI_INTERNALS__.invoke('restart_desktop').catch(() => {{ text.textContent = '请使用窗口右上角关闭 DayFrame，然后重新打开。'; }});
          panel.append(heading, text, restart); document.body.replaceChildren(panel);
        }})()"#, serde_json::to_string(message).unwrap()));
    }
    diagnostic(json!({"state":"failed","pid":std::process::id(),"message":message}));
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") { let _ = window.unminimize(); let _ = window.set_focus(); }
        }))
        .manage(DesktopState::default())
        .invoke_handler(tauri::generate_handler![choose_directory, restart_desktop])
        .setup(|app| {
            let handle = app.handle().clone();
            let mut builder = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("DayFrame").inner_size(1380., 940.).min_inner_size(1000., 600.).prevent_overflow().center()
                .data_directory(std::env::var_os("DAYFRAME_DATA_HOME").map(PathBuf::from).unwrap_or_else(|| std::env::var_os("LOCALAPPDATA").map(PathBuf::from).unwrap_or_default().join("DayFrame")).join("WebView2"))
                .on_navigation({ let app = handle.clone(); move |url| {
                    if url.scheme() == "tauri" || (url.scheme() == "http" && url.host_str() == Some("tauri.localhost")) { return true; }
                    let state = app.state::<DesktopState>();
                    let expected = state.origin.lock().unwrap();
                    let origin = format!("{}://{}:{}", url.scheme(), url.host_str().unwrap_or(""), url.port_or_known_default().unwrap_or(0));
                    expected.as_deref() == Some(&origin) && (url.path() == "/" || url.path() == "/desktop/launch" || url.path().starts_with("/api/exports/") || (url.path().starts_with("/api/photos/") && url.query_pairs().any(|(key, value)| key == "download" && value == "true")))
                }})
                .on_download({ let app = handle.clone(); move |_, event| {
                    if let tauri::webview::DownloadEvent::Requested { url, destination } = event {
                        let state = app.state::<DesktopState>();
                        let origin = format!("{}://{}:{}", url.scheme(), url.host_str().unwrap_or(""), url.port_or_known_default().unwrap_or(0));
                        let valid = state.origin.lock().unwrap().as_deref() == Some(&origin)
                            && (url.path().starts_with("/api/exports/") || url.path().starts_with("/api/photos/"));
                        if !valid { return false; }
                        let filename = destination.file_name().map(|s| s.to_string_lossy().into_owned()).unwrap_or_else(|| "DayFrame-export".into());
                        let selected = if let Some(status) = std::env::var_os("DAYFRAME_SMOKE_STATUS") {
                            let folder = PathBuf::from(status).parent().unwrap_or(std::path::Path::new(".")).join("downloads");
                            if std::fs::create_dir_all(&folder).is_err() { return false; }
                            Some(folder.join(filename))
                        } else {
                            rfd::FileDialog::new().set_title("保存 DayFrame 文件").set_file_name(filename).save_file()
                        };
                        if let Some(path) = selected { *destination = path; } else { return false; }
                    }
                    true
                }});
            if std::env::var_os("DAYFRAME_SMOKE_STATUS").is_some() {
                if let Ok(port) = std::env::var("DAYFRAME_TEST_DEBUG_PORT").unwrap_or_default().parse::<u16>() {
                    builder = builder.additional_browser_args(&format!("--remote-debugging-address=127.0.0.1 --remote-debugging-port={port} --use-fake-ui-for-media-stream --use-fake-device-for-media-stream"));
                }
            }
            let window = builder.build()?;
            window.on_window_event({ let app = handle.clone(); move |event| {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    lifecycle_trace("window-close-request");
                    api.prevent_close();
                    if app.state::<DesktopState>().exit_started.swap(true, Ordering::SeqCst) { lifecycle_trace("window-close-already-owned"); return; }
                    let app = app.clone();
                    std::thread::spawn(move || { shutdown(&app); lifecycle_trace("window-close-exit-call"); app.exit(0); });
                }
            }});
            std::thread::spawn(move || {
                if let Err(error) = start_backend(&handle) {
                    shutdown(&handle);
                    startup_error(&handle, &error);
                } else {
                    loop {
                        std::thread::sleep(Duration::from_secs(1));
                        let state = handle.state::<DesktopState>();
                        if state.closing.load(Ordering::SeqCst) { break; }
                        let exited = state.backend.lock().unwrap().as_mut().map(|b| !matches!(b.child.try_wait(), Ok(None))).unwrap_or(true);
                        if exited {
                            shutdown(&handle);
                            startup_error(&handle, "本地档案组件意外停止。已保存的照片仍在本地，请关闭并重新打开 DayFrame。");
                            break;
                        }
                    }
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!()).expect("DayFrame native window initialization failed");
    app.run(|app, event| { if let tauri::RunEvent::ExitRequested { .. } = event { lifecycle_trace("runtime-exit-request"); shutdown(app); lifecycle_trace("runtime-exit-return"); } });
}
