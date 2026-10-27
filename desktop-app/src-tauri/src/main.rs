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
const CREATE_NO_WINDOW: u32 = 0x08000000;

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
    let mut stream = match TcpStream::connect_timeout(
        &std::net::SocketAddr::from(([127, 0, 0, 1], port)),
        Duration::from_millis(400),
    ) {
        Ok(s) => s,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
    if stream
        .write_all(b"GET /api/status HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        .is_err()
    {
        return false;
    }
    let mut buf = String::new();
    let _ = stream.read_to_string(&mut buf);
    buf.contains("sutk-desktop")
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

fn spawn_server(root: &Path, data_dir: &Path) -> Result<Child, String> {
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
        .arg(PORT.to_string())
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

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let root = app_root();
            let data_dir = exe_dir();
            let _ = fs::create_dir_all(&data_dir);
            if !status_ok(PORT) {
                match spawn_server(&root, &data_dir) {
                    Ok(child) => {
                        if let Ok(mut guard) = child_slot().lock() {
                            *guard = Some(child);
                        }
                    }
                    Err(err) => {
                        alert(&err);
                        return Err(Box::new(std::io::Error::new(std::io::ErrorKind::Other, err)));
                    }
                }
                if !wait_ready(PORT) {
                    let log = data_dir.join("server.log");
                    let extra = fs::read_to_string(&log).unwrap_or_default();
                    let tail: String = extra
                        .chars()
                        .rev()
                        .take(600)
                        .collect::<String>()
                        .chars()
                        .rev()
                        .collect();
                    alert(&format!(
                        "界面服务没有在 25 秒内启动。\n{}\n{}",
                        log.display(),
                        tail
                    ));
                    stop_server();
                    return Err(Box::new(std::io::Error::new(
                        std::io::ErrorKind::TimedOut,
                        "server timeout",
                    )));
                }
            }
            let window = app.get_webview_window("main").ok_or_else(|| {
                std::io::Error::new(std::io::ErrorKind::NotFound, "no window")
            })?;
            let url = format!("http://127.0.0.1:{PORT}/").parse().map_err(|e| {
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
