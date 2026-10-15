mod commands;
mod runtime;
use commands::runtime::{restart_runtime_process, runtime_connection};
use runtime::state::RuntimeProcess;
use runtime::supervisor::{launch_runtime, stop_runtime};
use std::sync::Arc;
use tauri::Manager;

pub fn run() {
    let process = Arc::new(RuntimeProcess::default());
    let process_for_setup = Arc::clone(&process);
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_single_instance::init(|_app, _args, _cwd| {}))
        .manage(process)
        .setup(move |app| {
            if let Err(error) = launch_runtime(app.handle(), Arc::clone(&process_for_setup)) {
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
                    process
                        .shutting_down
                        .store(true, std::sync::atomic::Ordering::SeqCst);
                    if let Ok(_lease) = process.lifecycle.lock() {
                        let _ = stop_runtime(process.inner().as_ref());
                    }
                }
            }
        });
}
