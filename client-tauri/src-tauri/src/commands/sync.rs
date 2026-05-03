use std::collections::HashMap;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager, State};
use uuid::Uuid;

use crate::commands::auth::{self as auth_cmd, AuthStatus};
use crate::domain::auth as auth_domain;
use crate::domain::sync_api::{ApiClient, PlayerStats, ScoreItem};
use crate::domain::{beatoraja, config, fumen_detail, lr2};

const SCORE_BATCH_SIZE: usize = 500;
const QUICK_SYNC_SCORELOG_OVERLAP_DAYS: i64 = 3;

#[derive(Default)]
pub struct SyncRegistry {
    runs: Mutex<HashMap<String, Arc<AtomicBool>>>,
}

impl SyncRegistry {
    fn insert(&self, id: &str) -> Arc<AtomicBool> {
        let cancel = Arc::new(AtomicBool::new(false));
        self.runs
            .lock()
            .expect("sync registry poisoned")
            .insert(id.to_string(), cancel.clone());
        cancel
    }

    fn cancel(&self, id: &str) {
        if let Some(flag) = self
            .runs
            .lock()
            .expect("sync registry poisoned")
            .get(id)
            .cloned()
        {
            flag.store(true, Ordering::SeqCst);
        }
    }

    fn remove(&self, id: &str) {
        self.runs.lock().expect("sync registry poisoned").remove(id);
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct SyncRequest {
    pub client_filter: String,
    pub full_sync: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct SyncRunId {
    pub id: String,
}

#[derive(Debug, Clone, Serialize)]
struct SyncStartedEvent {
    sync_run_id: String,
    client_filter: String,
    full_sync: bool,
}

#[derive(Debug, Clone, Serialize)]
struct SyncProgressEvent {
    sync_run_id: String,
    client: Option<String>,
    stage: String,
    current: Option<usize>,
    total: Option<usize>,
    message: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
struct LogEvent {
    sync_run_id: String,
    level: String,
    message: String,
    ts: String,
}

#[derive(Debug, Clone, Serialize)]
struct SyncErrorEvent {
    message: String,
}

#[derive(Debug, Clone, Serialize)]
struct ReauthRequiredEvent {
    sync_run_id: String,
    message: String,
}

#[derive(Debug, Clone, Serialize)]
struct SyncCancelledEvent {
    sync_run_id: String,
}

#[derive(Debug, Clone, Serialize)]
struct SyncResult {
    sync_run_id: String,
    finished_at: String,
    client_filter: String,
    full_sync: bool,
    inserted: i64,
    improved: i64,
    metadata_updated: i64,
    unchanged: i64,
    skipped_reasons: Vec<SyncSkipReason>,
    errors: Vec<SyncErrorEntry>,
    per_client: HashMap<String, ClientResult>,
    result_url: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
struct SyncSkipReason {
    code: String,
    count: i64,
    message: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
struct SyncErrorEntry {
    client: Option<String>,
    message: String,
    detail: Option<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
struct ClientResult {
    inserted: i64,
    improved: i64,
}

#[tauri::command]
pub fn start_sync(
    app: AppHandle,
    registry: State<'_, SyncRegistry>,
    request: SyncRequest,
) -> Result<SyncRunId, String> {
    let sync_run_id = Uuid::new_v4().to_string();
    let cancel_flag = registry.insert(&sync_run_id);

    app.emit(
        "sync:started",
        SyncStartedEvent {
            sync_run_id: sync_run_id.clone(),
            client_filter: request.client_filter.clone(),
            full_sync: request.full_sync,
        },
    )
    .map_err(|error| error.to_string())?;

    let run_id_for_task = sync_run_id.clone();
    let app_for_task = app.clone();
    tauri::async_runtime::spawn(async move {
        let result = run_sync(
            app_for_task.clone(),
            run_id_for_task.clone(),
            request,
            cancel_flag.clone(),
        )
        .await;
        app_for_task
            .state::<SyncRegistry>()
            .remove(&run_id_for_task);
        if let Err(error) = result {
            if cancel_flag.load(Ordering::SeqCst) {
                let _ = app_for_task.emit(
                    "sync:cancelled",
                    SyncCancelledEvent {
                        sync_run_id: run_id_for_task,
                    },
                );
            } else {
                let msg = error.to_string();
                write_error_log(&app_for_task, &run_id_for_task, &[], Some(&msg));
                if msg.contains(auth_domain::REAUTH_REQUIRED_TAG) {
                    // Notify the auth store so the header switches to logged-out
                    // and broadcast a dedicated event so the UI can show a
                    // "다시 로그인" banner instead of a generic sync error.
                    let status = AuthStatus {
                        logged_in: false,
                        refresh_token_expire_days: auth_domain::refresh_token_expire_days(
                            &app_for_task,
                        ),
                    };
                    auth_cmd::emit_auth_changed(&app_for_task, &status);
                    let _ = app_for_task.emit(
                        "auth:reauth-required",
                        ReauthRequiredEvent {
                            sync_run_id: run_id_for_task.clone(),
                            message: "로그인 세션이 만료되었습니다. 다시 로그인해주세요."
                                .to_string(),
                        },
                    );
                } else {
                    let _ = app_for_task.emit("sync:error", SyncErrorEvent { message: msg });
                }
            }
        }
    });

    Ok(SyncRunId { id: sync_run_id })
}

#[tauri::command]
pub fn cancel_sync(registry: State<'_, SyncRegistry>, sync_run_id: String) -> Result<(), String> {
    registry.cancel(&sync_run_id);
    Ok(())
}

async fn run_sync(
    app: AppHandle,
    sync_run_id: String,
    request: SyncRequest,
    cancel_flag: Arc<AtomicBool>,
) -> anyhow::Result<()> {
    let cfg = config::load(&app)?;
    let api = ApiClient::new(cfg.api_url.clone(), app.clone())?;
    let include_lr2 = matches!(request.client_filter.as_str(), "all" | "lr2");
    let include_bea = matches!(request.client_filter.as_str(), "all" | "beatoraja");
    let mut errors: Vec<SyncErrorEntry> = Vec::new();

    log(
        &app,
        &sync_run_id,
        "info",
        "[INFO] 설정과 DB 경로를 확인합니다.",
    );
    progress(
        &app,
        &sync_run_id,
        None,
        "validating",
        None,
        None,
        "설정 확인 중",
    );

    let lr2_path_ok = cfg
        .lr2_db_path
        .as_deref()
        .is_some_and(|path| Path::new(path).exists());
    let bea_dir_ok = cfg
        .beatoraja_db_dir
        .as_deref()
        .is_some_and(|path| Path::new(path).exists());
    let bea_score_db_ok = cfg
        .beatoraja_db_dir
        .as_deref()
        .is_some_and(|path| Path::new(path).join("score.db").exists());
    let bea_scorelog_ok = cfg
        .beatoraja_db_dir
        .as_deref()
        .is_some_and(|path| Path::new(path).join("scorelog.db").exists());
    let bea_songdata_ok = request.full_sync
        && cfg
            .beatoraja_songdata_db_path
            .as_deref()
            .is_some_and(|path| Path::new(path).exists());
    let lr2_ok = include_lr2 && lr2_path_ok;
    let bea_ok = include_bea && bea_score_db_ok;

    log_recognition_summary(
        &app,
        &sync_run_id,
        &cfg,
        request.client_filter.as_str(),
        request.full_sync,
        lr2_path_ok,
        bea_score_db_ok,
        bea_songdata_ok,
    );

    if include_lr2 && cfg.lr2_db_path.is_some() && !lr2_path_ok {
        log(
            &app,
            &sync_run_id,
            "warn",
            "[WARN] LR2 기록 DB: 경로가 설정되어 있지만 파일/폴더를 찾을 수 없습니다. 경로를 다시 확인해주세요.",
        );
    }
    if include_bea && cfg.beatoraja_db_dir.is_some() && !bea_dir_ok {
        log(
            &app,
            &sync_run_id,
            "warn",
            "[WARN] Beatoraja 기록 DB 폴더: 경로가 설정되어 있지만 파일/폴더를 찾을 수 없습니다. 경로를 다시 확인해주세요.",
        );
    }
    if include_bea && bea_dir_ok && !bea_score_db_ok {
        log(
            &app,
            &sync_run_id,
            "warn",
            "[WARN] Beatoraja: score.db를 찾을 수 없습니다. 폴더 경로를 다시 확인해주세요.",
        );
    }
    if include_bea && bea_dir_ok && !bea_scorelog_ok {
        log(
            &app,
            &sync_run_id,
            "warn",
            "[WARN] Beatoraja: scorelog.db를 찾을 수 없습니다. 폴더 경로를 다시 확인해주세요.",
        );
    }
    if request.full_sync
        && include_bea
        && bea_score_db_ok
        && !bea_songdata_ok
        && request.client_filter != "all"
    {
        log(
            &app,
            &sync_run_id,
            "warn",
            "[WARN] Beatoraja 전체 동기화: songdata.db 경로가 설정되지 않았거나 파일을 찾을 수 없습니다. 해시 보강을 건너뜁니다.",
        );
    }

    check_cancel(&cancel_flag)?;

    if request.full_sync {
        errors.extend(
            run_full_detail_sync(&app, &sync_run_id, &api, &cfg, include_lr2, include_bea).await,
        );
        check_cancel(&cancel_flag)?;
    }

    progress(
        &app,
        &sync_run_id,
        None,
        "parsing",
        None,
        None,
        "로컬 기록 DB 처리 중",
    );
    let mut all_scores: Vec<ScoreItem> = Vec::new();
    let mut all_player_stats: Vec<PlayerStats> = Vec::new();

    if lr2_ok {
        if let Some(path) = cfg.lr2_db_path.as_deref() {
            progress(
                &app,
                &sync_run_id,
                Some("lr2"),
                "parsing",
                None,
                None,
                "LR2 <username>.db 처리 중",
            );
            log(
                &app,
                &sync_run_id,
                "info",
                "[INFO] LR2 <username>.db 처리 중...",
            );
            match lr2::parse_scores(path) {
                Ok((scores, courses, stats)) => {
                    log_parse_summary(
                        &app,
                        &sync_run_id,
                        "LR2 플레이 기록",
                        stats.parsed + stats.parsed_courses,
                        stats.db_total,
                        stats.skipped_filter(),
                        0,
                        stats.skipped_hash,
                    );
                    all_scores.extend(scores);
                    all_scores.extend(courses);
                    if let Some(stats) = lr2::parse_player_stats(path) {
                        all_player_stats.push(stats);
                    }
                }
                Err(error) => {
                    errors.push(SyncErrorEntry {
                        client: Some("lr2".to_string()),
                        message: "LR2 파싱 오류".to_string(),
                        detail: Some(error.to_string()),
                    });
                    log(
                        &app,
                        &sync_run_id,
                        "error",
                        &format!("[ERROR] LR2 파싱 오류: {error}"),
                    );
                }
            }
        }
    }

    check_cancel(&cancel_flag)?;

    if bea_ok {
        if let Some(path) = cfg.beatoraja_db_dir.as_deref() {
            progress(
                &app,
                &sync_run_id,
                Some("beatoraja"),
                "parsing",
                None,
                None,
                "Beatoraja score.db 및 scorelog.db 처리 중",
            );
            log(
                &app,
                &sync_run_id,
                "info",
                "[INFO] Beatoraja score.db 및 scorelog.db 처리 중...",
            );
            match beatoraja::parse_scores(path) {
                Ok((scores, courses, stats)) => {
                    log_parse_summary(
                        &app,
                        &sync_run_id,
                        "Beatoraja score.db",
                        stats.parsed + stats.parsed_courses,
                        stats.db_total.saturating_sub(stats.skipped_lr2),
                        stats.skipped_filter(),
                        stats.skipped_lr2,
                        stats.skipped_hash,
                    );
                    all_scores.extend(scores);
                    all_scores.extend(courses);
                }
                Err(error) => {
                    errors.push(SyncErrorEntry {
                        client: Some("beatoraja".to_string()),
                        message: "Beatoraja 파싱 오류".to_string(),
                        detail: Some(error.to_string()),
                    });
                    log(
                        &app,
                        &sync_run_id,
                        "error",
                        &format!("[ERROR] Beatoraja 파싱 오류: {error}"),
                    );
                }
            }

            let scorelog_since =
                quick_sync_scorelog_since(cfg.last_synced_at.as_deref(), request.full_sync);
            if let Some(since) = scorelog_since {
                log(
                    &app,
                    &sync_run_id,
                    "info",
                    &format!(
                        "[INFO] Beatoraja scorelog.db: 최근 동기화 기준 {}일 overlap 이후 기록만 확인합니다 (since={since}).",
                        QUICK_SYNC_SCORELOG_OVERLAP_DAYS
                    ),
                );
            }
            let (scorelog, stats) = beatoraja::parse_score_log(path, scorelog_since);
            log_scorelog_summary(
                &app,
                &sync_run_id,
                stats.parsed + stats.parsed_courses,
                stats.total_queried,
                stats.skipped_duplicate,
                stats.skipped_hash,
            );
            all_scores.extend(scorelog);

            if let Some(stats) = beatoraja::parse_player_stats(path) {
                all_player_stats.push(stats);
            }
        }
    }

    check_cancel(&cancel_flag)?;

    if all_scores.is_empty() && all_player_stats.is_empty() {
        log(
            &app,
            &sync_run_id,
            "warn",
            "[WARN] 동기화할 데이터가 없습니다.",
        );
        emit_finished(
            &app,
            SyncResult {
                sync_run_id,
                finished_at: now_rfc3339(),
                client_filter: request.client_filter,
                full_sync: request.full_sync,
                inserted: 0,
                improved: 0,
                metadata_updated: 0,
                unchanged: 0,
                skipped_reasons: Vec::new(),
                errors,
                per_client: HashMap::new(),
                result_url: None,
            },
        );
        return Ok(());
    }

    progress(
        &app,
        &sync_run_id,
        None,
        "uploading",
        Some(0),
        Some(all_scores.len()),
        "서버 업로드 중",
    );
    log(&app, &sync_run_id, "info", "[INFO] 서버에 동기화 중...");

    let mut inserted = 0;
    let mut synced = 0;
    let mut skipped = 0;
    let mut metadata_updated = 0;
    let mut server_errors = Vec::new();
    let chunks = if all_scores.is_empty() {
        1
    } else {
        all_scores.chunks(SCORE_BATCH_SIZE).len()
    };

    if all_scores.is_empty() {
        let response = api.sync_scores(&[], &all_player_stats).await?;
        inserted += response.inserted_scores;
        synced += response.synced_scores;
        skipped += response.skipped_scores;
        metadata_updated += response.metadata_updated;
        server_errors.extend(response.errors);
    } else {
        for (idx, batch) in all_scores.chunks(SCORE_BATCH_SIZE).enumerate() {
            check_cancel(&cancel_flag)?;
            let stats_batch = if idx == 0 {
                all_player_stats.as_slice()
            } else {
                &[]
            };
            let response = api.sync_scores(batch, stats_batch).await?;
            inserted += response.inserted_scores;
            synced += response.synced_scores;
            skipped += response.skipped_scores;
            metadata_updated += response.metadata_updated;
            server_errors.extend(response.errors);
            progress(
                &app,
                &sync_run_id,
                None,
                "uploading",
                Some(idx + 1),
                Some(chunks),
                "서버에 업로드 중",
            );
        }
    }

    if inserted > 0 || synced > 0 || !all_player_stats.is_empty() {
        let mut updated = cfg.clone();
        updated.last_synced_at = Some(now_rfc3339());
        let _ = config::save(&app, &updated);
    }

    let improvement_count = api.fetch_today_improvement_count().await.ok().flatten();
    let improved = improvement_count.unwrap_or(synced);
    let per_client = HashMap::new();
    for error in server_errors {
        errors.push(SyncErrorEntry {
            client: None,
            message: error,
            detail: None,
        });
    }

    progress(&app, &sync_run_id, None, "done", None, None, "동기화 완료");
    log(
        &app,
        &sync_run_id,
        "info",
        &format!(
            "[INFO] 동기화 완료 - 등록된 기록 {}건, 수정된 기록 {}건",
            format_count_i64(inserted),
            format_count_i64(metadata_updated)
        ),
    );

    emit_finished(
        &app,
        SyncResult {
            sync_run_id,
            finished_at: now_rfc3339(),
            client_filter: request.client_filter,
            full_sync: request.full_sync,
            inserted,
            improved,
            metadata_updated,
            unchanged: skipped,
            skipped_reasons: (skipped > 0)
                .then(|| SyncSkipReason {
                    code: "unchanged".to_string(),
                    count: skipped,
                    message: Some(
                        "서버의 improvement check에서 변경 없음으로 처리된 기록".to_string(),
                    ),
                })
                .into_iter()
                .collect(),
            errors,
            per_client,
            result_url: None,
        },
    );

    Ok(())
}

async fn run_full_detail_sync(
    app: &AppHandle,
    sync_run_id: &str,
    api: &ApiClient,
    cfg: &config::ClientConfig,
    include_lr2: bool,
    include_bea: bool,
) -> Vec<SyncErrorEntry> {
    let mut errors = Vec::new();
    progress(
        app,
        sync_run_id,
        None,
        "supplementing",
        None,
        None,
        "차분 상세 정보 준비 중",
    );
    let mut bea_items = Vec::new();
    if include_bea {
        if let Some(songdata_path) = cfg.beatoraja_songdata_db_path.as_deref() {
            if Path::new(songdata_path).exists() {
                log(
                    app,
                    sync_run_id,
                    "info",
                    "[INFO] Beatoraja songdata.db 처리 중...",
                );
                bea_items = beatoraja::parse_songdata(songdata_path);
                if let Some(songinfo_path) = cfg.beatoraja_songinfo_db_path.as_deref() {
                    if Path::new(songinfo_path).exists() {
                        let songinfo = beatoraja::parse_songinfo(songinfo_path);
                        for item in &mut bea_items {
                            if let Some(info) =
                                item.sha256.as_ref().and_then(|sha256| songinfo.get(sha256))
                            {
                                item.bpm_main = info.bpm_main;
                                item.notes_n = info.notes_n;
                                item.notes_ln = info.notes_ln;
                                item.notes_s = info.notes_s;
                                item.notes_ls = info.notes_ls;
                                item.total = info.total;
                            }
                        }
                    }
                }
                if bea_items.is_empty() {
                    log(
                        app,
                        sync_run_id,
                        "info",
                        "[INFO] songdata.db: 유효한 항목 없음 (건너뜀)",
                    );
                } else {
                    log(
                        app,
                        sync_run_id,
                        "info",
                        &format!(
                            "[INFO] Beatoraja 차분 상세 정보: {}개 항목 준비 완료",
                            format_count_usize(bea_items.len())
                        ),
                    );
                }
            }
        }
    }

    let lr2_items = if include_lr2 {
        cfg.lr2_song_db_path
            .as_deref()
            .filter(|path| Path::new(path).exists())
            .map(lr2::parse_songdata)
            .unwrap_or_default()
    } else {
        Vec::new()
    };
    if !lr2_items.is_empty() {
        log(
            app,
            sync_run_id,
            "info",
            &format!(
                "[INFO] LR2 차분 상세 정보: {}개 항목 준비 완료",
                format_count_usize(lr2_items.len())
            ),
        );
    }

    if bea_items.is_empty() && lr2_items.is_empty() {
        log(
            app,
            sync_run_id,
            "info",
            "[INFO] 차분 상세 정보: 전송할 신규/보강 항목 없음",
        );
        return errors;
    }

    let summary = fumen_detail::run_detail_sync(api, bea_items, lr2_items).await;
    log(
        app,
        sync_run_id,
        "info",
        &format!(
            "[INFO] 차분 상세 정보 동기화 완료 - 신규 {}개, 보강 {}개, 이미 존재한 데이터 {}개",
            format_count_i64(summary.inserted),
            format_count_i64(summary.supplemented + summary.updated),
            format_count_i64(summary.skipped)
        ),
    );
    for error in summary.errors.into_iter().take(5) {
        log(app, sync_run_id, "warn", &format!("[WARN] {error}"));
        errors.push(SyncErrorEntry {
            client: None,
            message: error,
            detail: Some("full detail sync".to_string()),
        });
    }
    errors
}

fn log_recognition_summary(
    app: &AppHandle,
    sync_run_id: &str,
    cfg: &config::ClientConfig,
    client_filter: &str,
    full_sync: bool,
    lr2_ok: bool,
    bea_ok: bool,
    bea_songdata_ok: bool,
) {
    if client_filter != "all" {
        return;
    }

    if lr2_ok {
        if let Some(path) = cfg.lr2_db_path.as_deref() {
            log(
                app,
                sync_run_id,
                "info",
                &format!("[INFO] LR2 기록 DB 인식됨: {path}"),
            );
        }
    } else if cfg.lr2_db_path.is_none() {
        log(
            app,
            sync_run_id,
            "info",
            "[INFO] LR2 DB: 경로 없음 (동기화 건너뜀)",
        );
    }

    if bea_ok {
        if let Some(path) = cfg.beatoraja_db_dir.as_deref() {
            log(
                app,
                sync_run_id,
                "info",
                &format!("[INFO] Beatoraja 기록 DB 인식됨: {path}"),
            );
        }
    } else if cfg.beatoraja_db_dir.is_none() {
        log(
            app,
            sync_run_id,
            "info",
            "[INFO] Beatoraja DB: 경로 없음 (동기화 건너뜀)",
        );
    }

    if full_sync && bea_ok && !bea_songdata_ok {
        log(
            app,
            sync_run_id,
            "warn",
            "[WARN] Beatoraja 전체 동기화: songdata.db 경로가 설정되지 않았거나 파일을 찾을 수 없습니다. 해시 보강을 건너뜁니다.",
        );
    }
}

fn log_parse_summary(
    app: &AppHandle,
    sync_run_id: &str,
    label: &str,
    total_processed: usize,
    effective_total: usize,
    skipped_filter: usize,
    skipped_lr2: usize,
    skipped_hash: usize,
) {
    log(
        app,
        sync_run_id,
        "info",
        &format!(
            "[INFO] {label} 처리 완료 ({}/{})",
            format_count_usize(total_processed),
            format_count_usize(effective_total)
        ),
    );
    if skipped_filter > 0 {
        log(
            app,
            sync_run_id,
            "info",
            &format!(
                "    미플레이/필터 제외: {}개 - 정상 동작 (플레이 기록 없는 차분 포함)",
                format_count_usize(skipped_filter)
            ),
        );
    }
    if skipped_lr2 > 0 {
        log(
            app,
            sync_run_id,
            "info",
            &format!(
                "    LR2 기록 제외: {}개 - 정상 동작 (LR2에서 임포트된 기록. Beatoraja 기록 아님)",
                format_count_usize(skipped_lr2)
            ),
        );
    }
    if skipped_hash > 0 {
        log(
            app,
            sync_run_id,
            "warn",
            &format!(
                "    ⚠ 해시 오류: {}개 - 주의: 해시 없음 또는 길이 불일치 (sync 불가, DB 손상 가능성)",
                format_count_usize(skipped_hash)
            ),
        );
    }
}

fn log_scorelog_summary(
    app: &AppHandle,
    sync_run_id: &str,
    parsed: usize,
    total_queried: usize,
    skipped_duplicate: usize,
    skipped_hash: usize,
) {
    log(
        app,
        sync_run_id,
        "info",
        &format!(
            "[INFO] Beatoraja scorelog.db 처리 완료 ({}/{})",
            format_count_usize(parsed),
            format_count_usize(total_queried)
        ),
    );
    if skipped_duplicate > 0 {
        log(
            app,
            sync_run_id,
            "info",
            &format!(
                "    score.db 중복 제외: {}개 - 정상 동작 (현재 최고 기록과 동일한 항목)",
                format_count_usize(skipped_duplicate)
            ),
        );
    }
    if skipped_hash > 0 {
        log(
            app,
            sync_run_id,
            "warn",
            &format!(
                "    ⚠ 해시 오류: {}개 - 주의: 해시 없음 또는 길이 불일치",
                format_count_usize(skipped_hash)
            ),
        );
    }
}

fn format_count_usize(value: usize) -> String {
    group_digits(&value.to_string())
}

fn format_count_i64(value: i64) -> String {
    if value < 0 {
        format!("-{}", group_digits(&value.abs().to_string()))
    } else {
        group_digits(&value.to_string())
    }
}

fn group_digits(value: &str) -> String {
    let mut grouped = String::new();
    for (idx, ch) in value.chars().rev().enumerate() {
        if idx > 0 && idx % 3 == 0 {
            grouped.push(',');
        }
        grouped.push(ch);
    }
    grouped.chars().rev().collect()
}

fn check_cancel(cancel_flag: &AtomicBool) -> anyhow::Result<()> {
    if cancel_flag.load(Ordering::SeqCst) {
        anyhow::bail!("sync cancelled");
    }
    Ok(())
}

fn quick_sync_scorelog_since(last_synced_at: Option<&str>, full_sync: bool) -> Option<i64> {
    if full_sync {
        return None;
    }
    let synced_at = last_synced_at.and_then(|value| {
        time::OffsetDateTime::parse(value, &time::format_description::well_known::Rfc3339).ok()
    })?;
    Some(
        (synced_at - time::Duration::days(QUICK_SYNC_SCORELOG_OVERLAP_DAYS))
            .unix_timestamp()
            .max(0),
    )
}

fn progress(
    app: &AppHandle,
    sync_run_id: &str,
    client: Option<&str>,
    stage: &str,
    current: Option<usize>,
    total: Option<usize>,
    message: &str,
) {
    let _ = app.emit(
        "sync:progress",
        SyncProgressEvent {
            sync_run_id: sync_run_id.to_string(),
            client: client.map(str::to_string),
            stage: stage.to_string(),
            current,
            total,
            message: Some(message.to_string()),
        },
    );
}

fn log(app: &AppHandle, sync_run_id: &str, level: &str, message: &str) {
    let _ = app.emit(
        "sync:log",
        LogEvent {
            sync_run_id: sync_run_id.to_string(),
            level: level.to_string(),
            message: message.to_string(),
            ts: now_rfc3339(),
        },
    );
}

fn emit_finished(app: &AppHandle, result: SyncResult) {
    write_error_log(app, &result.sync_run_id, &result.errors, None);
    let _ = app.emit("sync:finished", result);
}

fn write_error_log(
    app: &AppHandle,
    sync_run_id: &str,
    errors: &[SyncErrorEntry],
    fatal: Option<&str>,
) {
    if errors.is_empty() && fatal.is_none() {
        return;
    }
    let log_dir = match app.path().app_log_dir() {
        Ok(dir) => dir,
        Err(_) => return,
    };
    if std::fs::create_dir_all(&log_dir).is_err() {
        return;
    }
    let short_id = &sync_run_id[..8.min(sync_run_id.len())];
    let path = log_dir.join(format!("sync_error_{}.log", short_id));
    let mut content = format!(
        "OJIK BMS Client - Sync Error Log\nSync Run ID: {}\nGenerated: {}\n\n",
        sync_run_id,
        now_rfc3339()
    );
    if let Some(msg) = fatal {
        content.push_str(&format!("[FATAL] {}\n", msg));
    }
    for err in errors {
        match &err.client {
            Some(c) => content.push_str(&format!("[ERROR][{}] {}\n", c, err.message)),
            None => content.push_str(&format!("[ERROR] {}\n", err.message)),
        }
        if let Some(detail) = &err.detail {
            content.push_str(&format!("  Detail: {}\n", detail));
        }
    }
    let _ = std::fs::write(path, content);
}

fn now_rfc3339() -> String {
    time::OffsetDateTime::now_utc()
        .format(&time::format_description::well_known::Rfc3339)
        .unwrap_or_else(|_| "1970-01-01T00:00:00Z".to_string())
}
