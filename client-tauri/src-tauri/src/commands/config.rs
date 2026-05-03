use std::path::PathBuf;

use serde::Serialize;
use tauri::AppHandle;
use tauri::Manager;
use tauri_plugin_dialog::DialogExt;

use crate::domain::config::{self, ClientConfig};

#[derive(Debug, Clone, Serialize)]
pub struct PathProbe {
    pub path: String,
    pub exists: bool,
    pub kind: Option<String>,
    pub size_bytes: Option<u64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct DiagnosticsInfo {
    pub os: String,
    pub config_dir: Option<String>,
    pub logs_dir: Option<String>,
}

#[tauri::command]
pub fn get_config(app: AppHandle) -> Result<ClientConfig, String> {
    config::load(&app).map_err(|error| error.to_string())
}

#[tauri::command]
pub fn save_config(app: AppHandle, config: ClientConfig) -> Result<ClientConfig, String> {
    config::save(&app, &config).map_err(|error| error.to_string())
}

#[tauri::command]
pub fn import_legacy_config(app: AppHandle, path: String) -> Result<ClientConfig, String> {
    let path = PathBuf::from(path);
    config::import_legacy(&app, &path).map_err(|error| error.to_string())
}

#[tauri::command]
pub fn pick_file(app: AppHandle, kind: String) -> Result<Option<String>, String> {
    let dialog = apply_file_filter(app.dialog().file(), &kind);
    Ok(dialog.blocking_pick_file().map(|path| path.to_string()))
}

#[tauri::command]
pub fn pick_folder(app: AppHandle, _kind: String) -> Result<Option<String>, String> {
    Ok(app
        .dialog()
        .file()
        .blocking_pick_folder()
        .map(|path| path.to_string()))
}

#[tauri::command]
pub fn probe_path(path: String) -> Result<PathProbe, String> {
    let path_buf = PathBuf::from(&path);
    let metadata = std::fs::metadata(&path_buf);
    let (exists, kind, size_bytes) = match metadata {
        Ok(meta) => {
            let kind = if meta.is_file() {
                Some("file".to_string())
            } else if meta.is_dir() {
                Some("dir".to_string())
            } else {
                None
            };
            let size_bytes = meta.is_file().then_some(meta.len());
            (true, kind, size_bytes)
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => (false, None, None),
        Err(error) => return Err(error.to_string()),
    };

    Ok(PathProbe {
        path,
        exists,
        kind,
        size_bytes,
    })
}

#[tauri::command]
pub fn get_diagnostics_info(app: AppHandle) -> Result<DiagnosticsInfo, String> {
    let config_dir = config::config_dir(&app)
        .ok()
        .map(|path| path.to_string_lossy().to_string());
    let logs_dir = app
        .path()
        .app_log_dir()
        .ok()
        .map(|path| path.to_string_lossy().to_string());

    Ok(DiagnosticsInfo {
        os: format!("{} {}", std::env::consts::OS, std::env::consts::ARCH),
        config_dir,
        logs_dir,
    })
}

fn apply_file_filter<R: tauri::Runtime>(
    dialog: tauri_plugin_dialog::FileDialogBuilder<R>,
    kind: &str,
) -> tauri_plugin_dialog::FileDialogBuilder<R> {
    if kind.contains("config") {
        return dialog.add_filter("JSON config", &["json"]);
    }
    dialog.add_filter("SQLite database", &["db", "sqlite", "sqlite3"])
}
