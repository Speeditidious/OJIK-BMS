use tauri::AppHandle;
use tauri_plugin_opener::OpenerExt;

use crate::domain::update_policy::UpdatePolicy;

const DOWNLOAD_PAGE_URL: &str = "https://www.ojikbms.kr/download";

#[tauri::command]
pub fn check_update_policy(manual: bool) -> Result<UpdatePolicy, String> {
    Ok(UpdatePolicy::not_configured(manual))
}

#[tauri::command]
pub fn install_update(_update_id: String) -> Result<(), String> {
    Err(
        "Tauri updater 설치는 signed updater artifact, public key, 서버 update metadata endpoint가 준비된 배포 환경에서만 실행할 수 있습니다."
            .to_string(),
    )
}

#[tauri::command]
pub fn open_download_page(app: AppHandle) -> Result<String, String> {
    app.opener()
        .open_url(DOWNLOAD_PAGE_URL, None::<&str>)
        .map_err(|error| error.to_string())?;
    Ok(DOWNLOAD_PAGE_URL.to_string())
}
