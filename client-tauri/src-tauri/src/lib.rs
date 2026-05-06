mod commands;
mod domain;
mod logging;

use tauri::Manager;
use tauri_plugin_log::{RotationStrategy, Target, TargetKind, TimezoneStrategy};

const DISK_LOG_MAX_FILE_SIZE: u128 = 5_000_000;
const DISK_LOG_KEEP_ROTATIONS: usize = 10;

fn log_targets(file_name: String) -> Vec<Target> {
    let log_dir_target = Target::new(TargetKind::LogDir {
        file_name: Some(file_name),
    })
    .filter(logging::passes_disk_filter);

    #[cfg(debug_assertions)]
    {
        vec![log_dir_target, Target::new(TargetKind::Stdout)]
    }
    #[cfg(not(debug_assertions))]
    {
        vec![log_dir_target]
    }
}

pub fn run() {
    let log_filename = logging::current_log_filename();

    tauri::Builder::default()
        .manage(commands::sync::SyncRegistry::default())
        .plugin(
            tauri_plugin_log::Builder::new()
                .clear_targets()
                // Let everything through to the dispatch layer; the disk target
                // applies its own dynamic threshold via `passes_disk_filter`,
                // and stdout (debug builds only) keeps full verbosity.
                .level(log::LevelFilter::Debug)
                .level_for("keyring", log::LevelFilter::Warn)
                .level_for("reqwest", log::LevelFilter::Warn)
                .level_for("reqwest::retry", log::LevelFilter::Warn)
                .level_for("tao", log::LevelFilter::Warn)
                .level_for("tauri::manager", log::LevelFilter::Info)
                .max_file_size(DISK_LOG_MAX_FILE_SIZE)
                .rotation_strategy(RotationStrategy::KeepSome(DISK_LOG_KEEP_ROTATIONS))
                .timezone_strategy(TimezoneStrategy::UseUtc)
                .targets(log_targets(log_filename))
                .build(),
        )
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            commands::config::get_config,
            commands::config::save_config,
            commands::config::import_legacy_config,
            commands::config::pick_file,
            commands::config::pick_folder,
            commands::config::probe_path,
            commands::config::get_diagnostics_info,
            commands::auth::get_auth_status,
            commands::auth::start_login,
            commands::auth::logout,
            commands::sync::start_sync,
            commands::sync::cancel_sync,
            commands::update::check_update_policy,
            commands::update::open_download_page
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            logging::init_from_config(&handle);

            let prune_handle = handle.clone();
            tauri::async_runtime::spawn(async move {
                logging::prune_old_logs(&prune_handle, logging::retain_days_default());
            });

            let pkg = handle.package_info();
            log::info!(
                target: "startup",
                "OJIK BMS Client started (version={}, os={} {}, verbose_disk_logging={})",
                pkg.version,
                std::env::consts::OS,
                std::env::consts::ARCH,
                domain::config::load(&handle)
                    .map(|c| c.verbose_disk_logging)
                    .unwrap_or(false)
            );
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("failed to run OJIK BMS Client");
}
