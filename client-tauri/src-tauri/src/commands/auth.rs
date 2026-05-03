use serde::Serialize;
use tauri::{AppHandle, Emitter};

use crate::domain::{auth, config};

#[derive(Debug, Clone, Serialize)]
pub struct AuthStatus {
    pub logged_in: bool,
    pub refresh_token_expire_days: Option<u32>,
}

/// Emit `auth:changed` so the frontend (use-auth.ts) refreshes its state.
/// Used after login/logout/reauth-required.
pub fn emit_auth_changed(app: &AppHandle, status: &AuthStatus) {
    let _ = app.emit("auth:changed", status.clone());
}

#[tauri::command]
pub fn get_auth_status(app: AppHandle) -> Result<AuthStatus, String> {
    let cfg = config::load(&app).map_err(|error| error.to_string())?;
    let logged_in = auth::load_refresh_token(&app).is_some();
    Ok(AuthStatus {
        logged_in,
        refresh_token_expire_days: auth::refresh_token_expire_days(&app)
            .or(Some(cfg.refresh_token_expire_days)),
    })
}

#[tauri::command]
pub async fn start_login(app: AppHandle) -> Result<AuthStatus, String> {
    let expire_days = auth::run_login_flow(app.clone())
        .await
        .map_err(|error| error.to_string())?;
    let status = AuthStatus {
        logged_in: true,
        refresh_token_expire_days: auth::refresh_token_expire_days(&app).or(Some(expire_days)),
    };
    emit_auth_changed(&app, &status);
    Ok(status)
}

#[tauri::command]
pub fn logout(app: AppHandle) -> Result<AuthStatus, String> {
    auth::clear_tokens(&app);
    let status = AuthStatus {
        logged_in: false,
        refresh_token_expire_days: None,
    };
    emit_auth_changed(&app, &status);
    Ok(status)
}
