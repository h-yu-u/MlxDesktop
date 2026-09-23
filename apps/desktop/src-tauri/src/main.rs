#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use serde_json::Value;
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};
use tokio::sync::Notify;

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimeConnection {
    base_url: String,
    token: String,
    protocol_version: u32,
}

#[derive(Default)]
struct RuntimeProcess {
    connection: Mutex<Option<RuntimeConnection>>,
    token: Mutex<Option<String>>,
    child: Mutex<Option<CommandChild>>,
    ready: Notify,
}

#[tauri::command]
async fn runtime_connection(state: State<'_, Arc<RuntimeProcess>>) -> Result<RuntimeConnection, String> {
    if let Some(connection) = state.connection.lock().map_err(|_| "Runtime lock failed")?.clone() {
        return Ok(connection);
    }
    tokio::time::timeout(std::time::Duration::from_secs(20), state.ready.notified())
        .await
        .map_err(|_| "Runtime startup timed out")?;
    state.connection.lock().map_err(|_| "Runtime lock failed")?.clone()
        .ok_or_else(|| "Runtime handshake failed".to_string())
}

fn launch_runtime(app: &AppHandle, process: Arc<RuntimeProcess>) -> Result<(), String> {
    let token = uuid::Uuid::new_v4().to_string() + &uuid::Uuid::new_v4().to_string();
    *process.token.lock().map_err(|_| "Runtime token lock failed")? = Some(token.clone());
    let data_directory = app.path().app_data_dir().map_err(|error| error.to_string())?;
    std::fs::create_dir_all(&data_directory).map_err(|error| error.to_string())?;
    #[cfg(debug_assertions)]
    let command = {
        let runtime_project = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../../services/runtime")
            .canonicalize()
            .map_err(|error| error.to_string())?;
        let python_path = runtime_project.join("src");
        app.shell().command("uv")
            .args(["run", "--project"])
            .args([runtime_project.to_str().ok_or("Invalid Runtime project path")?])
            .args(["--python", "3.12", "python", "-m", "mlx_studio_runtime.entrypoints.http.main"])
            .env("PYTHONPATH", python_path)
            .env("MLX_STUDIO_DATA_DIR", &data_directory)
            .env("MLX_STUDIO_SESSION_TOKEN", &token)
    };
    #[cfg(not(debug_assertions))]
    let command = app.shell().sidecar("mlx-studio-runtime")
        .map_err(|error| format!("Runtime sidecar unavailable: {error}"))?
        .env("MLX_STUDIO_DATA_DIR", &data_directory)
        .env("MLX_STUDIO_SESSION_TOKEN", &token);
    let (mut receiver, child) = command.spawn()
        .map_err(|error| format!("Runtime sidecar failed to start: {error}"))?;
    *process.child.lock().map_err(|_| "Runtime child lock failed")? = Some(child);
    let app_handle = app.clone();
    let process_for_events = Arc::clone(&process);
    tauri::async_runtime::spawn(async move {
        let mut stdout_buffer = Vec::<u8>::new();
        while let Some(event) = receiver.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    stdout_buffer.extend(bytes);
                    while let Some(position) = stdout_buffer.iter().position(|byte| *byte == b'\n') {
                        let frame: Vec<u8> = stdout_buffer.drain(..=position).collect();
                        if let Ok(value) = serde_json::from_slice::<Value>(&frame) {
                            if value["type"] == "runtime.ready" {
                                let port = value["port"].as_u64().unwrap_or(0);
                                let protocol_version = value["protocol_version"].as_u64().unwrap_or(0) as u32;
                                if port > 0 && protocol_version == 1 {
                                    let connection = RuntimeConnection {
                                        base_url: format!("http://127.0.0.1:{port}"),
                                        token: token.clone(),
                                        protocol_version,
                                    };
                                    if let Ok(mut slot) = process_for_events.connection.lock() {
                                        *slot = Some(connection);
                                    }
                                    process_for_events.ready.notify_one();
                                    let _ = app_handle.emit("runtime-status", "ready");
                                }
                            }
                        }
                    }
                }
                CommandEvent::Terminated(_) => {
                    if let Ok(mut slot) = process_for_events.connection.lock() {
                        *slot = None;
                    }
                    let _ = app_handle.emit("runtime-status", "failed");
                }
                CommandEvent::Error(error) => {
                    let _ = app_handle.emit("runtime-status", format!("error:{error}"));
                }
                CommandEvent::Stderr(_) => {}
                _ => {}
            }
        }
    });
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
        .invoke_handler(tauri::generate_handler![runtime_connection])
        .build(tauri::generate_context!())
        .expect("failed to build MLX Studio")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                if let Some(process) = app.try_state::<Arc<RuntimeProcess>>() {
                    if let Ok(mut child) = process.child.lock() {
                        if let Some(child) = child.take() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        });
}
