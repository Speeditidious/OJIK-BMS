mod commands;
mod domain;

use tauri::Manager;

pub fn run() {
    tauri::Builder::default()
        .manage(commands::sync::SyncRegistry::default())
        .plugin(
            tauri_plugin_log::Builder::new()
                .targets([tauri_plugin_log::Target::new(
                    tauri_plugin_log::TargetKind::Stdout,
                )])
                .build(),
        )
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            commands::config::get_config,
            commands::config::save_config,
            commands::config::import_legacy_config,
            commands::config::pick_file,
            commands::config::pick_folder,
            commands::config::probe_path,
            commands::config::detect_client_paths,
            commands::config::get_diagnostics_info,
            commands::auth::get_auth_status,
            commands::auth::start_login,
            commands::auth::logout,
            commands::sync::start_sync,
            commands::sync::cancel_sync,
            commands::update::check_update_policy,
            commands::update::install_update,
            commands::update::open_download_page
        ])
        .run(tauri::generate_context!())
        .expect("failed to run OJIK BMS Client");
}
