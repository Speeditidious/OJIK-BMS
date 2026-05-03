use std::collections::HashMap;
use std::fs;
use std::io::{Read, Write};
use std::net::TcpListener;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

use anyhow::{anyhow, Context};
use base64::Engine;
use keyring::Entry;
use reqwest::StatusCode;
use serde::Deserialize;
use tauri::AppHandle;
use tauri_plugin_opener::OpenerExt;

use crate::domain::config;

const KEYRING_SERVICE: &str = "ojikbms-client";
const ACCESS_TOKEN_KEY: &str = "access_token";
const REFRESH_TOKEN_KEY: &str = "refresh_token";
const SECRETS_DIR_NAME: &str = ".secrets";

/// Marker error returned when the user must manually re-authenticate.
/// Callers (commands/sync.rs, commands/auth.rs) detect this string prefix to
/// emit `auth:reauth-required` instead of a generic sync error.
pub const REAUTH_REQUIRED_TAG: &str = "AUTH_REAUTH_REQUIRED";

#[derive(Debug, Deserialize)]
struct RefreshResponse {
    access_token: String,
    refresh_token: String,
}

pub fn load_access_token(app: &AppHandle) -> Option<String> {
    load_secret(app, ACCESS_TOKEN_KEY)
}

pub fn load_refresh_token(app: &AppHandle) -> Option<String> {
    load_secret(app, REFRESH_TOKEN_KEY)
}

pub fn refresh_token_expire_days(app: &AppHandle) -> Option<u32> {
    load_refresh_token(app).and_then(|token| decode_refresh_expire_days(&token))
}

pub fn save_tokens(app: &AppHandle, access_token: &str, refresh_token: &str) -> anyhow::Result<()> {
    save_secret(app, ACCESS_TOKEN_KEY, access_token)?;
    save_secret(app, REFRESH_TOKEN_KEY, refresh_token)?;

    if let Some(days) = decode_refresh_expire_days(refresh_token) {
        let mut cfg = config::load(app)?;
        cfg.refresh_token_expire_days = days;
        config::save(app, &cfg)?;
    }

    Ok(())
}

pub fn clear_tokens(app: &AppHandle) {
    let _ = delete_secret(app, ACCESS_TOKEN_KEY);
    let _ = delete_secret(app, REFRESH_TOKEN_KEY);
}

/// Refresh the access token using the stored refresh token.
///
/// Returns `Ok(true)` on success, `Ok(false)` when refresh is not possible
/// (no refresh token, or server says the refresh token is no longer valid).
/// On `Ok(false)` the caller should treat this as "re-authentication required"
/// — but tokens are NOT auto-cleared so the user can retry without losing
/// state to transient network errors.
pub async fn refresh_access_token(app: &AppHandle, api_url: &str) -> anyhow::Result<bool> {
    let Some(refresh_token) = load_refresh_token(app) else {
        log::warn!("refresh_access_token: no refresh_token in storage");
        return Ok(false);
    };

    let client = reqwest::Client::builder()
        .danger_accept_invalid_certs(is_local_url(api_url))
        .build()?;

    let response = client
        .post(format!("{api_url}/auth/refresh"))
        .json(&serde_json::json!({ "refresh_token": refresh_token }))
        .send()
        .await?;

    let status = response.status();
    if status == StatusCode::OK {
        let body = response.json::<RefreshResponse>().await?;
        save_secret(app, ACCESS_TOKEN_KEY, &body.access_token)?;
        save_secret(app, REFRESH_TOKEN_KEY, &body.refresh_token)?;
        log::info!("refresh_access_token: success (new tokens persisted)");
        return Ok(true);
    }

    let body_preview = response
        .text()
        .await
        .map(|text| trim_for_log(&text, 200))
        .unwrap_or_default();
    log::warn!(
        "refresh_access_token: server rejected refresh (status={status}, body={body_preview})"
    );

    // NOTE: Do NOT clear tokens on 401/403. Tokens are only cleared on explicit
    // logout. This avoids losing the session due to transient errors and lets
    // the user retry. The frontend banner / re-login flow handles UX.
    Ok(false)
}

pub async fn run_login_flow(app: AppHandle) -> anyhow::Result<u32> {
    let cfg = config::load(&app)?;
    let listener = TcpListener::bind(("127.0.0.1", 0)).context("failed to bind OAuth callback")?;
    listener.set_nonblocking(true)?;
    let port = listener.local_addr()?.port();
    let login_url = format!("{}/auth/discord/login?state=agent:{port}", cfg.api_url);

    println!("\nDiscord login URL:\n  {login_url}\n");
    open_login_url(&app, &login_url)?;

    let tokens = tauri::async_runtime::spawn_blocking(move || wait_for_callback(listener))
        .await
        .map_err(|error| anyhow!(error.to_string()))??;

    save_tokens(&app, &tokens.access_token, &tokens.refresh_token)?;
    Ok(decode_refresh_expire_days(&tokens.refresh_token).unwrap_or(cfg.refresh_token_expire_days))
}

fn open_login_url(app: &AppHandle, login_url: &str) -> anyhow::Result<()> {
    if is_wsl() && open_with_windows_browser(login_url) {
        return Ok(());
    }

    app.opener()
        .open_url(login_url.to_string(), None::<&str>)
        .map_err(|error| anyhow!(error.to_string()))
}

fn is_wsl() -> bool {
    if std::env::var_os("WSL_DISTRO_NAME").is_some() {
        return true;
    }
    std::fs::read_to_string("/proc/sys/kernel/osrelease")
        .map(|release| release.to_ascii_lowercase().contains("microsoft"))
        .unwrap_or(false)
}

fn open_with_windows_browser(login_url: &str) -> bool {
    Command::new("powershell.exe")
        .env("OJIKBMS_LOGIN_URL", login_url)
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Start-Process -FilePath $env:OJIKBMS_LOGIN_URL",
        ])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

#[derive(Debug)]
struct CallbackTokens {
    access_token: String,
    refresh_token: String,
}

fn wait_for_callback(listener: TcpListener) -> anyhow::Result<CallbackTokens> {
    let deadline = Instant::now() + Duration::from_secs(120);

    loop {
        match listener.accept() {
            Ok((mut stream, _addr)) => {
                let mut buf = [0_u8; 8192];
                let read = stream.read(&mut buf)?;
                let request = String::from_utf8_lossy(&buf[..read]);
                let first_line = request.lines().next().unwrap_or_default();
                let path = first_line.split_whitespace().nth(1).unwrap_or_default();
                let params = parse_query(path);

                if let (Some(access_token), Some(refresh_token)) =
                    (params.get("access_token"), params.get("refresh_token"))
                {
                    let body = concat!(
                        "<html><body><h2>OJIK BMS: 로그인 성공!</h2>",
                        "<p>이 창을 닫고 OJIK BMS Client로 돌아가세요.</p></body></html>"
                    );
                    write_http_response(&mut stream, 200, body)?;
                    return Ok(CallbackTokens {
                        access_token: access_token.clone(),
                        refresh_token: refresh_token.clone(),
                    });
                }

                let error = params
                    .get("error")
                    .cloned()
                    .unwrap_or_else(|| "OAuth callback did not include tokens".to_string());
                write_http_response(
                    &mut stream,
                    400,
                    "<html><body><h2>OJIK BMS: 로그인 실패</h2></body></html>",
                )?;
                return Err(anyhow!(error));
            }
            Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                if Instant::now() >= deadline {
                    return Err(anyhow!("로그인 시간 초과 또는 취소됨"));
                }
                std::thread::sleep(Duration::from_millis(100));
            }
            Err(error) => return Err(error.into()),
        }
    }
}

fn write_http_response(stream: &mut impl Write, status: u16, body: &str) -> std::io::Result<()> {
    let status_text = if status == 200 { "OK" } else { "Bad Request" };
    write!(
        stream,
        "HTTP/1.1 {status} {status_text}\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.as_bytes().len()
    )
}

fn parse_query(path: &str) -> HashMap<String, String> {
    let query = path
        .split_once('?')
        .map(|(_, query)| query)
        .unwrap_or_default();
    query
        .split('&')
        .filter_map(|pair| {
            let (key, value) = pair.split_once('=')?;
            Some((url_decode(key), url_decode(value)))
        })
        .collect()
}

fn url_decode(input: &str) -> String {
    let mut bytes = Vec::with_capacity(input.len());
    let mut chars = input.as_bytes().iter().copied();
    while let Some(byte) = chars.next() {
        match byte {
            b'+' => bytes.push(b' '),
            b'%' => {
                let hi = chars.next();
                let lo = chars.next();
                if let (Some(hi), Some(lo)) = (hi, lo) {
                    let hex = [hi, lo];
                    if let Ok(hex) = std::str::from_utf8(&hex) {
                        let Ok(value) = u8::from_str_radix(hex, 16) else {
                            continue;
                        };
                        bytes.push(value);
                    }
                }
            }
            _ => bytes.push(byte),
        }
    }
    String::from_utf8_lossy(&bytes).to_string()
}

fn decode_refresh_expire_days(token: &str) -> Option<u32> {
    let payload = token.split('.').nth(1)?;
    let decoded = base64::engine::general_purpose::URL_SAFE_NO_PAD
        .decode(payload)
        .ok()?;
    let value: serde_json::Value = serde_json::from_slice(&decoded).ok()?;
    let exp = value.get("exp")?.as_i64()?;
    let now = time::OffsetDateTime::now_utc().unix_timestamp();
    (exp > now).then_some(((exp - now) / 86_400) as u32)
}

fn secrets_dir(app: &AppHandle) -> anyhow::Result<PathBuf> {
    Ok(config::config_dir(app)?.join(SECRETS_DIR_NAME))
}

fn secret_file_path(app: &AppHandle, key: &str) -> anyhow::Result<PathBuf> {
    Ok(secrets_dir(app)?.join(key))
}

fn load_secret(app: &AppHandle, key: &str) -> Option<String> {
    match Entry::new(KEYRING_SERVICE, key).and_then(|entry| entry.get_password()) {
        Ok(value) => {
            log::debug!("load_secret: keyring hit (key={key})");
            return Some(value);
        }
        Err(error) => {
            log::debug!("load_secret: keyring miss (key={key}, error={error})");
        }
    }

    match secret_file_path(app, key).and_then(|path| {
        if path.exists() {
            Ok(Some(fs::read_to_string(&path)?))
        } else {
            Ok(None)
        }
    }) {
        Ok(Some(value)) => {
            log::debug!("load_secret: file fallback hit (key={key})");
            Some(value.trim().to_string()).filter(|s| !s.is_empty())
        }
        Ok(None) => {
            log::debug!("load_secret: not found in keyring or file (key={key})");
            None
        }
        Err(error) => {
            log::warn!("load_secret: file fallback read failed (key={key}, error={error})");
            None
        }
    }
}

fn save_secret(app: &AppHandle, key: &str, value: &str) -> anyhow::Result<()> {
    let keyring_result =
        Entry::new(KEYRING_SERVICE, key).and_then(|entry| entry.set_password(value));

    match keyring_result {
        Ok(()) => {
            log::info!("save_secret: stored via keyring (key={key})");
            // Clean up any stale file fallback so reads don't return outdated tokens.
            if let Ok(path) = secret_file_path(app, key) {
                let _ = fs::remove_file(&path);
            }
            Ok(())
        }
        Err(keyring_err) => {
            log::warn!(
                "save_secret: keyring unavailable, falling back to file storage (key={key}, error={keyring_err})"
            );
            write_secret_file(app, key, value).with_context(|| {
                format!(
                    "failed to persist secret '{key}' to keyring or file (keyring error: {keyring_err})"
                )
            })
        }
    }
}

fn delete_secret(app: &AppHandle, key: &str) -> anyhow::Result<()> {
    // Try keyring delete; ignore "not found" / backend errors so file fallback
    // still gets cleaned up.
    if let Ok(entry) = Entry::new(KEYRING_SERVICE, key) {
        let _ = entry.delete_credential();
    }
    if let Ok(path) = secret_file_path(app, key) {
        if path.exists() {
            fs::remove_file(&path)?;
        }
    }
    Ok(())
}

fn write_secret_file(app: &AppHandle, key: &str, value: &str) -> anyhow::Result<()> {
    let dir = secrets_dir(app)?;
    fs::create_dir_all(&dir)?;
    let path = dir.join(key);
    fs::write(&path, value)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(&path, fs::Permissions::from_mode(0o600));
        let _ = fs::set_permissions(&dir, fs::Permissions::from_mode(0o700));
    }
    Ok(())
}

fn trim_for_log(text: &str, cap: usize) -> String {
    if text.len() > cap {
        format!("{}...", &text[..cap])
    } else {
        text.to_string()
    }
}

fn is_local_url(url: &str) -> bool {
    url.contains("://localhost") || url.contains("://127.0.0.1") || url.contains("://[::1]")
}
