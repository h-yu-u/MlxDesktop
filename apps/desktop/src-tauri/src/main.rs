#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use serde_json::Value;
use std::sync::{
    atomic::{AtomicU64, Ordering},
    Arc, Mutex,
};
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};
use tokio::sync::Notify;

const PROTOCOL_VERSION: u32 = 1;

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimeConnection {
    base_url: String,
    token: String,
    protocol_version: u32,
    generation: u64,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimeStatusEvent {
    status: String,
    generation: u64,
    message: Option<String>,
}

struct RuntimeProcess {
    connection: Mutex<Option<RuntimeConnection>>,
    error: Mutex<Option<String>>,
    child: Mutex<Option<CommandChild>>,
    ready: Notify,
    generation: AtomicU64,
}

impl Default for RuntimeProcess {
    fn default() -> Self {
        Self {
            connection: Mutex::new(None),
            error: Mutex::new(None),
            child: Mutex::new(None),
            ready: Notify::new(),
            generation: AtomicU64::new(0),
        }
    }
}

#[tauri::command]
async fn runtime_connection(
    state: State<'_, Arc<RuntimeProcess>>,
) -> Result<RuntimeConnection, String> {
    let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs(20);
    loop {
        if let Some(result) = current_runtime_result(state.inner().as_ref())? {
            return result;
        }
        let notified = state.ready.notified();
        if let Some(result) = current_runtime_result(state.inner().as_ref())? {
            return result;
        }
        tokio::time::timeout_at(deadline, notified)
            .await
            .map_err(|_| "Runtime startup timed out".to_string())?;
    }
}

#[tauri::command]
fn restart_runtime_process(
    app: AppHandle,
    state: State<'_, Arc<RuntimeProcess>>,
) -> Result<(), String> {
    stop_runtime(state.inner().as_ref())?;
    launch_runtime(&app, Arc::clone(state.inner()))
}

fn current_runtime_result(
    state: &RuntimeProcess,
) -> Result<Option<Result<RuntimeConnection, String>>, String> {
    if let Some(connection) = state
        .connection
        .lock()
        .map_err(|_| "Runtime connection lock failed")?
        .clone()
    {
        return Ok(Some(Ok(connection)));
    }
    let error = state
        .error
        .lock()
        .map_err(|_| "Runtime error lock failed")?
        .clone();
    Ok(error.map(Err))
}

fn launch_runtime(app: &AppHandle, process: Arc<RuntimeProcess>) -> Result<(), String> {
    let generation = process.generation.fetch_add(1, Ordering::SeqCst) + 1;
    *process
        .connection
        .lock()
        .map_err(|_| "Runtime connection lock failed")? = None;
    *process
        .error
        .lock()
        .map_err(|_| "Runtime error lock failed")? = None;
    emit_status(app, "starting", generation, None);

    let token = format!("{}{}", uuid::Uuid::new_v4(), uuid::Uuid::new_v4());
    let data_directory = app.path().app_data_dir().map_err(|error| error.to_string())?;
    std::fs::create_dir_all(&data_directory).map_err(|error| error.to_string())?;

    #[cfg(debug_assertions)]
    let command = {
        let runtime_project = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../../services/runtime")
            .canonicalize()
            .map_err(|error| error.to_string())?;
        let python_path = runtime_project.join("src");
        app.shell()
            .command("uv")
            .args(["run", "--project"])
            .args([runtime_project.to_str().ok_or("Invalid Runtime project path")?])
            .args([
                "--python",
                "3.12",
                "python",
                "-m",
                "mlx_studio_runtime.entrypoints.http.main",
            ])
            .env("PYTHONPATH", python_path)
            .env("MLX_STUDIO_DATA_DIR", &data_directory)
            .env("MLX_STUDIO_SESSION_TOKEN", &token)
    };
    #[cfg(not(debug_assertions))]
    let command = app
        .shell()
        .sidecar("mlx-studio-runtime")
        .map_err(|error| format!("Runtime sidecar unavailable: {error}"))?
        .env("MLX_STUDIO_DATA_DIR", &data_directory)
        .env("MLX_STUDIO_SESSION_TOKEN", &token);

    let (mut receiver, child) = match command.spawn() {
        Ok(spawned) => spawned,
        Err(error) => {
            let message = format!("Runtime sidecar failed to start: {error}");
            set_failed(app, &process, generation, message.clone());
            return Err(message);
        }
    };
    *process
        .child
        .lock()
        .map_err(|_| "Runtime child lock failed")? = Some(child);

    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        let mut stdout_buffer = Vec::<u8>::new();
        while let Some(event) = receiver.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    stdout_buffer.extend(bytes);
                    consume_handshakes(
                        &mut stdout_buffer,
                        &app_handle,
                        &process,
                        &token,
                        generation,
                    );
                }
                CommandEvent::Stderr(bytes) => {
                    let text = String::from_utf8_lossy(&bytes).trim().to_string();
                    if !text.is_empty() {
                        eprintln!("[runtime] {text}");
                    }
                }
                CommandEvent::Terminated(_) => {
                    clear_child_if_current(&process, generation);
                    set_failed(
                        &app_handle,
                        &process,
                        generation,
                        "Runtime process exited".to_string(),
                    );
                    break;
                }
                CommandEvent::Error(error) => {
                    set_failed(
                        &app_handle,
                        &process,
                        generation,
                        format!("Runtime process error: {error}"),
                    );
                    break;
                }
                _ => {}
            }
        }
    });
    Ok(())
}

fn consume_handshakes(
    buffer: &mut Vec<u8>,
    app: &AppHandle,
    process: &RuntimeProcess,
    token: &str,
    generation: u64,
) {
    while let Some(position) = buffer.iter().position(|byte| *byte == b'\n') {
        let frame: Vec<u8> = buffer.drain(..=position).collect();
        let Ok(value) = serde_json::from_slice::<Value>(&frame) else {
            continue;
        };
        if value["type"] != "runtime.ready" {
            continue;
        }
        let port = value["port"].as_u64().unwrap_or(0);
        let protocol_version = value["protocol_version"].as_u64().unwrap_or(0) as u32;
        if port == 0 || protocol_version != PROTOCOL_VERSION {
            set_failed(
                app,
                process,
                generation,
                "Runtime handshake is incompatible".to_string(),
            );
            continue;
        }
        if process.generation.load(Ordering::SeqCst) != generation {
            continue;
        }
        let connection = RuntimeConnection {
            base_url: format!("http://127.0.0.1:{port}"),
            token: token.to_string(),
            protocol_version,
            generation,
        };
        if let Ok(mut slot) = process.connection.lock() {
            *slot = Some(connection);
        }
        if let Ok(mut slot) = process.error.lock() {
            *slot = None;
        }
        process.ready.notify_waiters();
        emit_status(app, "ready", generation, None);
    }
}

fn set_failed(
    app: &AppHandle,
    process: &RuntimeProcess,
    generation: u64,
    message: String,
) {
    if process.generation.load(Ordering::SeqCst) != generation {
        return;
    }
    if let Ok(mut slot) = process.connection.lock() {
        *slot = None;
    }
    if let Ok(mut slot) = process.error.lock() {
        *slot = Some(message.clone());
    }
    process.ready.notify_waiters();
    emit_status(app, "failed", generation, Some(message));
}

fn emit_status(
    app: &AppHandle,
    status: &str,
    generation: u64,
    message: Option<String>,
) {
    let _ = app.emit(
        "runtime-status",
        RuntimeStatusEvent {
            status: status.to_string(),
            generation,
            message,
        },
    );
}

fn clear_child_if_current(process: &RuntimeProcess, generation: u64) {
    if process.generation.load(Ordering::SeqCst) == generation {
        if let Ok(mut child) = process.child.lock() {
            child.take();
        }
    }
}

fn stop_runtime(process: &RuntimeProcess) -> Result<(), String> {
    let child = process
        .child
        .lock()
        .map_err(|_| "Runtime child lock failed")?
        .take();
    if let Some(child) = child {
        child.kill().map_err(|error| error.to_string())?;
    }
    Ok(())
}

fn main() {
    let process = Arc::new(RuntimeProcess::default());
    let process_for_setup = Arc::clone(&process);
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_single_instance::init(|_app, _args, _cwd| {}))
        .manage(process)
        .setup(move |app| {
            if let Err(error) = launch_runtime(&app.handle(), Arc::clone(&process_for_setup)) {
                eprintln!("Runtime launch failed: {error}");
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            runtime_connection,
            restart_runtime_process,
        ])
        .build(tauri::generate_context!())
        .expect("failed to build MLX Studio")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                if let Some(process) = app.try_state::<Arc<RuntimeProcess>>() {
                    let _ = stop_runtime(process.inner().as_ref());
                }
            }
        });
}
