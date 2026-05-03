use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use tauri::Manager;

const CONFIG_DIR_NAME: &str = "OJIKBMS_Client";
const CONFIG_FILE_NAME: &str = "config.json";

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(default)]
pub struct ClientConfig {
    pub api_url: String,
    pub bms_folders: Vec<String>,
    pub lr2_db_path: Option<String>,
    pub lr2_song_db_path: Option<String>,
    pub beatoraja_db_dir: Option<String>,
    pub beatoraja_songdata_db_path: Option<String>,
    pub beatoraja_songinfo_db_path: Option<String>,
    pub last_synced_at: Option<String>,
    pub client_types: Vec<String>,
    pub refresh_token_expire_days: u32,
    pub last_update_check_at: Option<String>,
    pub dismissed_update_id: Option<String>,
    pub dismissed_update_until: Option<String>,
    pub skipped_update_version: Option<String>,
    pub update_channel: String,
    pub last_update_failure_at: Option<String>,
    pub last_update_failure_version: Option<String>,
    pub last_update_failure_stage: Option<String>,
    pub last_update_failure_message: Option<String>,
}

impl Default for ClientConfig {
    fn default() -> Self {
        Self {
            api_url: default_api_url().to_string(),
            bms_folders: Vec::new(),
            lr2_db_path: None,
            lr2_song_db_path: None,
            beatoraja_db_dir: None,
            beatoraja_songdata_db_path: None,
            beatoraja_songinfo_db_path: None,
            last_synced_at: None,
            client_types: vec!["lr2".to_string(), "beatoraja".to_string()],
            refresh_token_expire_days: 30,
            last_update_check_at: None,
            dismissed_update_id: None,
            dismissed_update_until: None,
            skipped_update_version: None,
            update_channel: "stable".to_string(),
            last_update_failure_at: None,
            last_update_failure_version: None,
            last_update_failure_stage: None,
            last_update_failure_message: None,
        }
    }
}

fn default_api_url() -> &'static str {
    if cfg!(debug_assertions) {
        "http://localhost:8000"
    } else {
        "https://api.ojikbms.kr"
    }
}

pub fn config_file(app: &tauri::AppHandle) -> anyhow::Result<PathBuf> {
    Ok(app
        .path()
        .app_config_dir()?
        .join(CONFIG_DIR_NAME)
        .join(CONFIG_FILE_NAME))
}

pub fn load(app: &tauri::AppHandle) -> anyhow::Result<ClientConfig> {
    let path = config_file(app)?;
    if !path.exists() {
        if let Some(legacy_path) = legacy_config_file() {
            let raw = fs::read_to_string(legacy_path)?;
            let config = serde_json::from_str::<ClientConfig>(&raw)?;
            return save(app, &config);
        }
        return Ok(ClientConfig::default());
    }

    let raw = fs::read_to_string(path)?;
    let config = serde_json::from_str::<ClientConfig>(&raw)?;
    Ok(normalize(config))
}

pub fn save(app: &tauri::AppHandle, config: &ClientConfig) -> anyhow::Result<ClientConfig> {
    let path = config_file(app)?;
    write_atomic(
        &path,
        &serde_json::to_string_pretty(&normalize(config.clone()))?,
    )?;
    load(app)
}

pub fn import_legacy(app: &tauri::AppHandle, path: &Path) -> anyhow::Result<ClientConfig> {
    let raw = fs::read_to_string(path)?;
    let config = serde_json::from_str::<ClientConfig>(&raw)?;
    save(app, &config)
}

pub fn config_dir(app: &tauri::AppHandle) -> anyhow::Result<PathBuf> {
    Ok(config_file(app)?
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from(CONFIG_DIR_NAME)))
}

fn write_atomic(path: &Path, content: &str) -> anyhow::Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }

    let tmp_path = path.with_extension("json.tmp");
    fs::write(&tmp_path, content)?;
    fs::rename(tmp_path, path)?;
    Ok(())
}

fn normalize(mut config: ClientConfig) -> ClientConfig {
    config.api_url = normalize_api_url(&config.api_url);
    config
}

fn legacy_config_file() -> Option<PathBuf> {
    let appdata = std::env::var_os("APPDATA")?;
    let path = PathBuf::from(appdata)
        .join(CONFIG_DIR_NAME)
        .join(CONFIG_FILE_NAME);
    path.exists().then_some(path)
}

fn normalize_api_url(url: &str) -> String {
    let trimmed = url.trim().trim_end_matches('/');
    if let Some(rest) = trimmed.strip_prefix("https://localhost") {
        return format!("http://localhost{rest}");
    }
    if let Some(rest) = trimmed.strip_prefix("https://127.0.0.1") {
        return format!("http://127.0.0.1{rest}");
    }
    trimmed.to_string()
}
