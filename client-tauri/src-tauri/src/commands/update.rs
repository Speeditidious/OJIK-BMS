use tauri::AppHandle;
use tauri_plugin_opener::OpenerExt;

use crate::domain::{config, update_policy::UpdatePolicy};

const DOWNLOAD_PAGE_URL: &str = "https://www.ojikbms.kr/download";

#[tauri::command]
pub async fn check_update_policy(app: AppHandle, manual: bool) -> Result<UpdatePolicy, String> {
    let cfg = config::load(&app).map_err(|error| error.to_string())?;
    let url = format!("{}/client/update-policy", cfg.api_url);
    let client = reqwest::Client::builder()
        .danger_accept_invalid_certs(is_local_url(&cfg.api_url))
        .build()
        .map_err(|error| error.to_string())?;

    let response = match client
        .get(url)
        .query(&[
            ("version", env!("CARGO_PKG_VERSION")),
            ("target", std::env::consts::OS),
            ("arch", std::env::consts::ARCH),
            ("channel", cfg.update_channel.as_str()),
            ("installer_kind", "nsis"),
        ])
        .send()
        .await
    {
        Ok(response) => response,
        Err(error) => {
            return Ok(UpdatePolicy::no_update(
                manual.then(|| format!("업데이트 서버에 연결할 수 없습니다: {error}")),
            ));
        }
    };

    if !response.status().is_success() {
        return Ok(UpdatePolicy::no_update(manual.then(|| {
            format!(
                "업데이트 서버 응답이 올바르지 않습니다: {}",
                response.status()
            )
        })));
    }

    let policy = response
        .json::<UpdatePolicy>()
        .await
        .map_err(|error| error.to_string())?;
    Ok(apply_local_dismissals(policy, &cfg))
}

#[tauri::command]
pub fn install_update(app: AppHandle, _update_id: String) -> Result<(), String> {
    app.opener()
        .open_url(DOWNLOAD_PAGE_URL, None::<&str>)
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub fn open_download_page(app: AppHandle) -> Result<String, String> {
    app.opener()
        .open_url(DOWNLOAD_PAGE_URL, None::<&str>)
        .map_err(|error| error.to_string())?;
    Ok(DOWNLOAD_PAGE_URL.to_string())
}

fn apply_local_dismissals(mut policy: UpdatePolicy, cfg: &config::ClientConfig) -> UpdatePolicy {
    let Some(announcement) = policy.announcement.as_ref() else {
        return policy;
    };

    if !announcement.mandatory
        && cfg.skipped_update_version.as_deref() == Some(announcement.version.as_str())
    {
        return UpdatePolicy::no_update(None);
    }

    if !announcement.mandatory
        && cfg.dismissed_update_id.as_deref() == Some(announcement.id.as_str())
        && cfg
            .dismissed_update_until
            .as_deref()
            .is_some_and(|until| until > current_utc_marker().as_str())
    {
        return UpdatePolicy::no_update(None);
    }

    if !policy.update_available {
        policy.announcement = None;
    }
    policy
}

fn current_utc_marker() -> String {
    use time::format_description::well_known::Rfc3339;
    time::OffsetDateTime::now_utc()
        .format(&Rfc3339)
        .unwrap_or_default()
}

fn is_local_url(url: &str) -> bool {
    url.contains("://localhost") || url.contains("://127.0.0.1")
}
