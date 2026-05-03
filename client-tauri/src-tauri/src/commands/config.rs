use std::path::{Path, PathBuf};

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
pub struct DetectedPaths {
    pub lr2_db_path: Option<String>,
    pub lr2_song_db_path: Option<String>,
    pub beatoraja_db_dir: Option<String>,
    pub beatoraja_songdata_db_path: Option<String>,
    pub beatoraja_songinfo_db_path: Option<String>,
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
pub fn detect_client_paths(client: String, hint: String) -> Result<DetectedPaths, String> {
    let hint_path = PathBuf::from(hint);
    match client.as_str() {
        "lr2" => Ok(detect_lr2_paths(&hint_path)),
        "beatoraja" => Ok(detect_beatoraja_paths(&hint_path)),
        other => Err(format!("Unsupported client type: {other}")),
    }
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

fn detect_lr2_paths(path: &Path) -> DetectedPaths {
    let base_dir = if path.is_file() {
        path.parent().unwrap_or(path)
    } else {
        path
    };

    let lr2_db_path = if path.is_file() && !is_filename(path, "song.db") {
        Some(path_to_string(path))
    } else {
        first_existing(&[
            base_dir.join("score.db"),
            base_dir.join("LR2files").join("Database").join("score.db"),
        ])
    };

    let lr2_song_db_path = if is_filename(path, "song.db") {
        Some(path_to_string(path))
    } else {
        first_existing(&[
            base_dir.join("song.db"),
            base_dir.join("LR2files").join("Database").join("song.db"),
        ])
    };

    DetectedPaths {
        lr2_db_path,
        lr2_song_db_path,
        beatoraja_db_dir: None,
        beatoraja_songdata_db_path: None,
        beatoraja_songinfo_db_path: None,
    }
}

fn detect_beatoraja_paths(path: &Path) -> DetectedPaths {
    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();
    if path.is_file() && matches!(file_name.as_str(), "songdata.db" | "songinfo.db") {
        let root_dir = path.parent().unwrap_or(path);
        return DetectedPaths {
            lr2_db_path: None,
            lr2_song_db_path: None,
            beatoraja_db_dir: None,
            beatoraja_songdata_db_path: if file_name == "songdata.db" {
                Some(path_to_string(path))
            } else {
                first_existing(&[root_dir.join("songdata.db")])
            },
            beatoraja_songinfo_db_path: if file_name == "songinfo.db" {
                Some(path_to_string(path))
            } else {
                first_existing(&[root_dir.join("songinfo.db")])
            },
        };
    }

    let score_dir = if path.is_file() && matches!(file_name.as_str(), "score.db" | "scorelog.db") {
        path.parent().unwrap_or(path).to_path_buf()
    } else {
        path.to_path_buf()
    };
    let root_dir = score_dir.parent().unwrap_or(&score_dir);

    DetectedPaths {
        lr2_db_path: None,
        lr2_song_db_path: None,
        beatoraja_db_dir: Some(path_to_string(&score_dir)),
        beatoraja_songdata_db_path: first_existing(&[
            root_dir.join("songdata.db"),
            score_dir.join("songdata.db"),
        ]),
        beatoraja_songinfo_db_path: first_existing(&[
            root_dir.join("songinfo.db"),
            score_dir.join("songinfo.db"),
        ]),
    }
}

fn first_existing(paths: &[PathBuf]) -> Option<String> {
    paths
        .iter()
        .find(|path| path.exists())
        .map(|path| path_to_string(path))
}

fn is_filename(path: &Path, expected: &str) -> bool {
    path.file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| name.eq_ignore_ascii_case(expected))
}

fn path_to_string(path: &Path) -> String {
    path.to_string_lossy().to_string()
}
