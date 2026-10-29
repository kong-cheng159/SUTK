#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::net::TcpStream;
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

use tauri::Manager;

const PORT: u16 = 8765;
const PORT_TRY_MAX: u16 = 8770;
const CREATE_NO_WINDOW: u32 = 0x08000000;

fn active_port_slot() -> &'static Mutex<u16> {
    static SLOT: OnceLock<Mutex<u16>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(PORT))
}

fn set_active_port(port: u16) {
    if let Ok(mut g) = active_port_slot().lock() {
        *g = port;
    }
}

fn active_port() -> u16 {
    active_port_slot().lock().map(|g| *g).unwrap_or(PORT)
}

fn child_slot() -> &'static Mutex<Option<Child>> {
    static SLOT: OnceLock<Mutex<Option<Child>>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(None))
}

fn wide(text: &str) -> Vec<u16> {
    use std::os::windows::ffi::OsStrExt;
    std::ffi::OsStr::new(text)
        .encode_wide()
        .chain(std::iter::once(0))
        .collect()
}

fn alert(text: &str) {
    #[link(name = "user32")]
    extern "system" {
        fn MessageBoxW(
            hwnd: *mut std::ffi::c_void,
            text: *const u16,
            caption: *const u16,
            utype: u32,
        ) -> i32;
    }
    let body = wide(text);
    let title = wide("SUTK 修改器");
    unsafe {
        MessageBoxW(std::ptr::null_mut(), body.as_ptr(), title.as_ptr(), 0x10);
    }
}

fn exe_dir() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from("."))
}

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn app_root() -> PathBuf {
    let beside = exe_dir();
    if beside.join("python").join("python.exe").is_file()
        && beside.join("desktop").join("server.py").is_file()
    {
        return beside;
    }
    repo_root()
}

fn python_exe(root: &Path) -> PathBuf {
    root.join("python").join("python.exe")
}

fn server_script(root: &Path) -> PathBuf {
    root.join("desktop").join("server.py")
}

fn status_ok(port: u16) -> bool {
    status_body(port)
        .map(|body| body.contains("sutk-desktop"))
        .unwrap_or(false)
}

/// 旧进程占着 8765 时仍会返回 200，但缺少新接口；需重启后端。
fn status_has_officials_api(port: u16) -> bool {
    status_body(port)
        .map(|body| body.contains("\"officials\": true") || body.contains("\"officials\":true"))
        .unwrap_or(false)
}

fn status_body(port: u16) -> Option<String> {
    let mut stream = TcpStream::connect_timeout(
        &std::net::SocketAddr::from(([127, 0, 0, 1], port)),
        Duration::from_millis(400),
    )
    .ok()?;
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
    stream
        .write_all(b"GET /api/status HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        .ok()?;
    let mut buf = String::new();
    stream.read_to_string(&mut buf).ok()?;
    Some(buf)
}

fn wait_ready(port: u16) -> bool {
    let deadline = Instant::now() + Duration::from_secs(25);
    while Instant::now() < deadline {
        if status_ok(port) {
            return true;
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    false
}

fn spawn_server(root: &Path, data_dir: &Path, port: u16) -> Result<Child, String> {
    let python = python_exe(root);
    let script = server_script(root);
    if !python.is_file() {
        return Err(format!("找不到 Python：{}", python.display()));
    }
    if !script.is_file() {
        return Err(format!("找不到界面服务：{}", script.display()));
    }
    let log_path = data_dir.join("server.log");
    let log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| format!("无法写日志 {}：{e}", log_path.display()))?;
    Command::new(&python)
        .arg(&script)
        .arg("--no-browser")
        .arg("--port")
        .arg(port.to_string())
        .env("SUTK_APP_DIR", data_dir)
        .current_dir(root)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(log)
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()
        .map_err(|e| format!("启动修改器失败：{e}"))
}

fn stop_server() {
    if let Ok(mut guard) = child_slot().lock() {
        if let Some(child) = guard.as_mut() {
            let _ = child.kill();
            let _ = child.wait();
        }
        *guard = None;
    }
}

fn port_listening(port: u16) -> bool {
    TcpStream::connect_timeout(
        &std::net::SocketAddr::from(([127, 0, 0, 1], port)),
        Duration::from_millis(250),
    )
    .is_ok()
}

/// 8765 上若残留旧 python 服务，exe 会误用旧接口；启动前清掉监听该端口的进程。
#[cfg(windows)]
fn pids_listening_on_port(port: u16) -> Vec<u32> {
    let out = match Command::new("netstat")
        .arg("-ano")
        .creation_flags(CREATE_NO_WINDOW)
        .output()
    {
        Ok(o) if o.status.success() => o,
        _ => return vec![],
    };
    let text = String::from_utf8_lossy(&out.stdout);
    let needle = format!(":{port}");
    let mut pids = Vec::new();
    for line in text.lines() {
        let upper = line.to_uppercase();
        if !upper.contains("LISTENING") {
            continue;
        }
        if !line.contains(&needle) {
            continue;
        }
        let Some(pid_s) = line.split_whitespace().last() else {
            continue;
        };
        if let Ok(pid) = pid_s.parse::<u32>() {
            if pid > 0 {
                pids.push(pid);
            }
        }
    }
    pids.sort_unstable();
    pids.dedup();
    pids
}

#[cfg(windows)]
fn kill_listeners_on_port(port: u16) {
    for pid in pids_listening_on_port(port) {
        let _ = Command::new("taskkill")
            .args(["/F", "/PID", &pid.to_string()])
            .creation_flags(CREATE_NO_WINDOW)
            .status();
    }
    let ps = format!(
        "Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | \
         ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"
    );
    let _ = Command::new("powershell")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            &ps,
        ])
        .creation_flags(CREATE_NO_WINDOW)
        .status();
    std::thread::sleep(Duration::from_millis(350));
}

#[cfg(not(windows))]
fn kill_listeners_on_port(_port: u16) {}

#[cfg(windows)]
fn force_free_port(port: u16) {
    for _ in 0..10 {
        if !port_listening(port) {
            return;
        }
        kill_listeners_on_port(port);
    }
}

#[cfg(not(windows))]
fn force_free_port(port: u16) {
    let _ = port;
}

fn port_ready(port: u16, require_officials: bool) -> bool {
    status_ok(port) && (!require_officials || status_has_officials_api(port))
}

fn try_clear_stale_on_port(port: u16, require_officials: bool) {
    if !port_listening(port) {
        return;
    }
    if port_ready(port, require_officials) {
        return;
    }
    force_free_port(port);
    let deadline = Instant::now() + Duration::from_secs(4);
    while Instant::now() < deadline && port_listening(port) && !port_ready(port, require_officials) {
        std::thread::sleep(Duration::from_millis(200));
    }
}

/// 在指定端口启动或复用服务；端口被无法结束的旧进程占用时返回 Ok(false) 以尝试下一端口。
fn try_ensure_on_port(
    root: &Path,
    data_dir: &Path,
    port: u16,
    require_officials: bool,
) -> Result<bool, String> {
    try_clear_stale_on_port(port, require_officials);

    if port_ready(port, require_officials) {
        set_active_port(port);
        return Ok(true);
    }

    if port_listening(port) {
        return Ok(false);
    }

    let child = spawn_server(root, data_dir, port)?;
    if let Ok(mut guard) = child_slot().lock() {
        *guard = Some(child);
    }
    if !wait_ready(port) {
        stop_server();
        return Ok(false);
    }
    if require_officials && !status_has_officials_api(port) {
        stop_server();
        return Err(
            "界面服务已启动，但仍是旧版（无官职接口）。请确认 desktop\\server.py 与 officials_han_staffing.json 已更新。"
                .into(),
        );
    }
    set_active_port(port);
    Ok(true)
}

fn ensure_api_server(root: &Path, data_dir: &Path, require_officials: bool) -> Result<(), String> {
    let _ = fs::create_dir_all(data_dir);
    stop_server();

    for port in PORT..=PORT_TRY_MAX {
        match try_ensure_on_port(root, data_dir, port, require_officials) {
            Ok(true) => return Ok(()),
            Ok(false) => continue,
            Err(e) => return Err(e),
        }
    }

    Err(
        "无法在 8765–8770 启动新版界面服务。\n\
8765 常被「管理员权限」的旧 pythonw 占用且无法自动结束。\n\
请：① 完全退出修改器 ② 右键「重启后端.bat」→ 以管理员身份运行 ③ 再开修改器。"
            .into(),
    )
}

#[tauri::command]
fn restart_api() -> Result<(), String> {
    let root = app_root();
    let data_dir = exe_dir();
    ensure_api_server(&root, &data_dir, true)
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![restart_api])
        .setup(|app| {
            let root = app_root();
            let data_dir = exe_dir();
            if let Err(err) = ensure_api_server(&root, &data_dir, true) {
                alert(&err);
                return Err(Box::new(std::io::Error::new(
                    std::io::ErrorKind::Other,
                    err,
                )));
            }
            let window = app.get_webview_window("main").ok_or_else(|| {
                std::io::Error::new(std::io::ErrorKind::NotFound, "no window")
            })?;
            let url = format!("http://127.0.0.1:{}/", active_port())
                .parse()
                .map_err(|e| {
                std::io::Error::new(std::io::ErrorKind::InvalidInput, format!("{e}"))
            })?;
            window.navigate(url)?;
            window.show()?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("启动窗口失败")
        .run(|_app, event| {
            if let tauri::RunEvent::Exit = event {
                stop_server();
            }
        });
}
