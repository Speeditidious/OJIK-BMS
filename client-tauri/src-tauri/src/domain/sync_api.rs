use std::time::Duration;

use anyhow::anyhow;
use reqwest::{header::RETRY_AFTER, Client, Method, Response, StatusCode};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use serde_json::Value;
use tauri::AppHandle;
use tokio::time::sleep;

use crate::domain::auth;

const API_REQUEST_TIMEOUT_SECS: u64 = 300;
const API_REQUEST_MAX_ATTEMPTS: usize = 3;

#[derive(Debug, Clone, Serialize)]
pub struct ScoreItem {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scorehash: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fumen_sha256: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fumen_md5: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fumen_hash_others: Option<String>,
    pub client_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub clear_type: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub notes: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub exscore: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_combo: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_bp: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub judgments: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub play_count: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub clear_count: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recorded_at: Option<String>,
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub song_hashes: Vec<SongHash>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SongHash {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub song_md5: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub song_sha256: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PlayerStats {
    pub client_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub playcount: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub clearcount: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub playtime: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub judgments: Option<Value>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SyncResponse {
    pub synced_scores: i64,
    pub inserted_scores: i64,
    #[serde(default)]
    pub skipped_scores: i64,
    #[serde(default)]
    pub metadata_updated: i64,
    #[serde(default)]
    pub errors: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct KnownHashes {
    #[serde(default)]
    pub complete_sha256: Vec<String>,
    #[serde(default)]
    pub complete_md5: Vec<String>,
    #[serde(default)]
    pub partial_sha256: Vec<String>,
    #[serde(default)]
    pub partial_md5: Vec<String>,
}

#[derive(Clone)]
pub struct ApiClient {
    client: Client,
    api_url: String,
    app: AppHandle,
}

impl ApiClient {
    pub fn new(api_url: String, app: AppHandle) -> anyhow::Result<Self> {
        let client = Client::builder()
            .danger_accept_invalid_certs(is_local_url(&api_url))
            .connect_timeout(Duration::from_secs(15))
            .timeout(Duration::from_secs(API_REQUEST_TIMEOUT_SECS))
            .build()?;
        Ok(Self {
            client,
            api_url,
            app,
        })
    }

    pub async fn sync_scores(
        &self,
        scores: &[ScoreItem],
        player_stats: &[PlayerStats],
        is_final_batch: bool,
        has_previous_score_changes: bool,
    ) -> anyhow::Result<SyncResponse> {
        self.request_json_decoded(
            Method::POST,
            "/sync/",
            &serde_json::json!({
                "scores": scores,
                "player_stats": player_stats,
                "is_final_batch": is_final_batch,
                "has_previous_score_changes": has_previous_score_changes,
            }),
        )
        .await
    }

    pub async fn fetch_today_improvement_count(&self) -> anyhow::Result<Option<i64>> {
        let today = time::OffsetDateTime::now_utc().date().to_string();
        let body = self
            .request_decoded::<Value>(
                Method::GET,
                &format!("/analysis/recent-updates?date={today}&limit=1"),
            )
            .await?;
        Ok(body
            .get("day_summary")
            .and_then(|summary| summary.get("total_updates"))
            .and_then(Value::as_i64))
    }

    pub async fn fetch_known_hashes(&self) -> anyhow::Result<KnownHashes> {
        self.request_decoded(Method::GET, "/fumens/known-hashes")
            .await
    }

    pub async fn post_json<T>(&self, path: &str, payload: &Value) -> anyhow::Result<T>
    where
        T: DeserializeOwned,
    {
        self.request_json_decoded(Method::POST, path, payload).await
    }

    async fn request_decoded<T>(&self, method: Method, path: &str) -> anyhow::Result<T>
    where
        T: DeserializeOwned,
    {
        self.request_decoded_with_payload(method, path, None).await
    }

    async fn request_json_decoded<T>(
        &self,
        method: Method,
        path: &str,
        payload: &Value,
    ) -> anyhow::Result<T>
    where
        T: DeserializeOwned,
    {
        self.request_decoded_with_payload(method, path, Some(payload))
            .await
    }

    async fn request_decoded_with_payload<T>(
        &self,
        method: Method,
        path: &str,
        payload: Option<&Value>,
    ) -> anyhow::Result<T>
    where
        T: DeserializeOwned,
    {
        let url = format!("{}{}", self.api_url, path);
        let mut last_error: Option<anyhow::Error> = None;

        for attempt in 1..=API_REQUEST_MAX_ATTEMPTS {
            match self
                .send_authorized_request(method.clone(), &url, payload)
                .await
            {
                Ok(response) => {
                    let status = response.status();
                    if is_retryable_status(status) {
                        let delay =
                            retry_after_delay(&response).unwrap_or_else(|| retry_delay(attempt));
                        let text = response.text().await.unwrap_or_default();
                        let error = anyhow!("HTTP {status}: {}", trim_for_log(&text))
                            .context("server request failed");
                        if attempt < API_REQUEST_MAX_ATTEMPTS {
                            log_retry(&method, path, attempt, &error);
                            sleep(delay).await;
                            last_error = Some(error);
                            continue;
                        }
                        return Err(error);
                    }

                    let response = ensure_success(response).await?;
                    match response.json::<T>().await {
                        Ok(body) => return Ok(body),
                        Err(error) => {
                            let retryable = is_retryable_reqwest_error(&error);
                            let error = anyhow!(error).context("server response read failed");
                            if retryable && attempt < API_REQUEST_MAX_ATTEMPTS {
                                log_retry(&method, path, attempt, &error);
                                sleep(retry_delay(attempt)).await;
                                last_error = Some(error);
                                continue;
                            }
                            return Err(error);
                        }
                    }
                }
                Err(error) => {
                    if is_retryable_anyhow_error(&error) && attempt < API_REQUEST_MAX_ATTEMPTS {
                        log_retry(&method, path, attempt, &error);
                        sleep(retry_delay(attempt)).await;
                        last_error = Some(error);
                        continue;
                    }
                    return Err(error);
                }
            }
        }

        Err(last_error.unwrap_or_else(|| anyhow!("server request failed")))
    }

    async fn send_authorized_request(
        &self,
        method: Method,
        url: &str,
        payload: Option<&Value>,
    ) -> anyhow::Result<Response> {
        let response = self
            .send_request(method.clone(), url, payload, true)
            .await?;
        if response.status() != StatusCode::UNAUTHORIZED {
            return Ok(response);
        }

        log::info!("send_authorized_request: 401 received, attempting token refresh");
        if !auth::refresh_access_token(&self.app, &self.api_url).await? {
            // Tagged error so commands/sync.rs can distinguish "user must
            // re-login" from generic sync failures and emit auth:reauth-required.
            return Err(anyhow!(
                "{}: 로그인 세션이 만료되었습니다. 다시 로그인해주세요.",
                auth::REAUTH_REQUIRED_TAG
            ));
        }

        self.send_request(method, url, payload, true).await
    }

    async fn send_request(
        &self,
        method: Method,
        url: &str,
        payload: Option<&Value>,
        authenticated: bool,
    ) -> anyhow::Result<Response> {
        let mut request = self.client.request(method, url);
        if let Some(payload) = payload {
            request = request.json(payload);
        }
        if authenticated {
            if let Some(token) = auth::load_access_token(&self.app) {
                request = request.bearer_auth(token);
            } else {
                log::warn!("send_request: no access_token in storage; sending unauthenticated");
            }
        }
        Ok(request.send().await?)
    }
}

async fn ensure_success(response: Response) -> anyhow::Result<Response> {
    if response.status().is_success() {
        return Ok(response);
    }
    let status = response.status();
    let text = response.text().await.unwrap_or_default();
    Err(anyhow!("HTTP {status}: {}", trim_for_log(&text)).context("server request failed"))
}

fn trim_for_log(text: &str) -> String {
    const CAP: usize = 300;
    if text.len() > CAP {
        format!("{}...", &text[..CAP])
    } else {
        text.to_string()
    }
}

fn is_retryable_status(status: StatusCode) -> bool {
    matches!(
        status,
        StatusCode::REQUEST_TIMEOUT
            | StatusCode::TOO_MANY_REQUESTS
            | StatusCode::INTERNAL_SERVER_ERROR
            | StatusCode::BAD_GATEWAY
            | StatusCode::SERVICE_UNAVAILABLE
            | StatusCode::GATEWAY_TIMEOUT
    )
}

fn is_retryable_reqwest_error(error: &reqwest::Error) -> bool {
    error.is_timeout() || error.is_connect() || error.is_request()
}

fn is_retryable_anyhow_error(error: &anyhow::Error) -> bool {
    error.chain().any(|cause| {
        cause
            .downcast_ref::<reqwest::Error>()
            .is_some_and(is_retryable_reqwest_error)
    })
}

fn retry_after_delay(response: &Response) -> Option<Duration> {
    let seconds = response
        .headers()
        .get(RETRY_AFTER)?
        .to_str()
        .ok()?
        .parse::<u64>()
        .ok()?;
    Some(Duration::from_secs(seconds.min(30)))
}

fn retry_delay(attempt: usize) -> Duration {
    match attempt {
        1 => Duration::from_secs(2),
        2 => Duration::from_secs(5),
        _ => Duration::from_secs(10),
    }
}

fn log_retry(method: &Method, path: &str, attempt: usize, error: &anyhow::Error) {
    log::warn!(
        "api request failed transiently; retrying {method} {path} (attempt {}/{}) after: {error}",
        attempt + 1,
        API_REQUEST_MAX_ATTEMPTS
    );
}

fn is_local_url(url: &str) -> bool {
    url.contains("://localhost") || url.contains("://127.0.0.1") || url.contains("://[::1]")
}
