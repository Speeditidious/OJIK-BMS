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
use crate::logging::{EnvironmentSnapshot, PathChecks};

const SCORE_BATCH_SIZE: usize = 500;
const REFRESH_TOKEN_PROACTIVE_RENEW_DAYS: u32 = 3;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SyncLanguage {
    Ko,
    En,
    Ja,
}

#[derive(Debug, Clone, Copy)]
struct SyncText {
    language: SyncLanguage,
}

impl SyncText {
    fn new(language: &str) -> Self {
        let language = match language
            .trim()
            .to_ascii_lowercase()
            .split(['-', '_'])
            .next()
        {
            Some("en") => SyncLanguage::En,
            Some("ja") => SyncLanguage::Ja,
            _ => SyncLanguage::Ko,
        };
        Self { language }
    }

    fn record_word(&self, count: impl Into<i64>) -> &'static str {
        match self.language {
            SyncLanguage::En if count.into().abs() == 1 => "record",
            SyncLanguage::En => "records",
            SyncLanguage::Ko | SyncLanguage::Ja => "건",
        }
    }

    fn checking_paths(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[INFO] 설정과 DB 경로를 확인합니다.".to_string(),
            SyncLanguage::En => "[INFO] Checking settings and DB paths.".to_string(),
            SyncLanguage::Ja => "[INFO] 設定とDBパスを確認します。".to_string(),
        }
    }

    fn progress_validating(&self) -> &'static str {
        match self.language {
            SyncLanguage::Ko => "설정 확인 중",
            SyncLanguage::En => "Checking settings",
            SyncLanguage::Ja => "設定を確認中",
        }
    }

    fn progress_local_db(&self) -> &'static str {
        match self.language {
            SyncLanguage::Ko => "로컬 기록 DB 처리 중",
            SyncLanguage::En => "Processing local record DBs",
            SyncLanguage::Ja => "ローカル記録DBを処理中",
        }
    }

    fn progress_lr2_user_db(&self) -> &'static str {
        match self.language {
            SyncLanguage::Ko => "LR2 <username>.db 처리 중",
            SyncLanguage::En => "Processing LR2 <username>.db",
            SyncLanguage::Ja => "LR2 <username>.dbを処理中",
        }
    }

    fn lr2_user_db_log(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[INFO] LR2 <username>.db 처리 중...".to_string(),
            SyncLanguage::En => "[INFO] Processing LR2 <username>.db...".to_string(),
            SyncLanguage::Ja => "[INFO] LR2 <username>.dbを処理中...".to_string(),
        }
    }

    fn lr2_play_record_label(&self) -> &'static str {
        match self.language {
            SyncLanguage::Ko => "LR2 플레이 기록",
            SyncLanguage::En => "LR2 play records",
            SyncLanguage::Ja => "LR2プレイ記録",
        }
    }

    fn progress_beatoraja_scores(&self) -> &'static str {
        match self.language {
            SyncLanguage::Ko => "Beatoraja score.db 및 scorelog.db 처리 중",
            SyncLanguage::En => "Processing Beatoraja score.db and scorelog.db",
            SyncLanguage::Ja => "Beatoraja score.dbとscorelog.dbを処理中",
        }
    }

    fn beatoraja_scores_log(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[INFO] Beatoraja score.db 및 scorelog.db 처리 중...".to_string(),
            SyncLanguage::En => {
                "[INFO] Processing Beatoraja score.db and scorelog.db...".to_string()
            }
            SyncLanguage::Ja => "[INFO] Beatoraja score.dbとscorelog.dbを処理中...".to_string(),
        }
    }

    fn parsing_error_message(&self, client: &str) -> String {
        match self.language {
            SyncLanguage::Ko => format!("{client} 파싱 오류"),
            SyncLanguage::En => format!("{client} parsing error"),
            SyncLanguage::Ja => format!("{client}解析エラー"),
        }
    }

    fn parsing_error_log(&self, client: &str, stage: &str, detail: &str) -> String {
        match self.language {
            SyncLanguage::Ko => format!("[ERROR][stage={stage}] {client} 파싱 오류: {detail}"),
            SyncLanguage::En => format!("[ERROR][stage={stage}] {client} parsing error: {detail}"),
            SyncLanguage::Ja => format!("[ERROR][stage={stage}] {client}解析エラー: {detail}"),
        }
    }

    fn reauth_required(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "로그인 세션이 만료되었습니다. 다시 로그인해주세요.".to_string(),
            SyncLanguage::En => "Your login session has expired. Please log in again.".to_string(),
            SyncLanguage::Ja => {
                "ログインセッションの期限が切れました。再度ログインしてください。".to_string()
            }
        }
    }

    fn scorelog_duplicate_debug(&self, count: usize) -> String {
        let count = format_count_usize(count);
        match self.language {
            SyncLanguage::Ko => format!(
                "[DEBUG] Beatoraja scorelog.db 같은 날 같은 차분 중복 {count}건을 가장 최근 기록으로 통합했습니다."
            ),
            SyncLanguage::En => format!(
                "[DEBUG] Merged {count} same-day duplicate Beatoraja scorelog.db chart records into the latest record."
            ),
            SyncLanguage::Ja => format!(
                "[DEBUG] Beatoraja scorelog.dbの同日同一差分の重複{count}件を最新記録に統合しました。"
            ),
        }
    }

    fn debug_group(&self, index: usize, total: usize, hash: &str, client: &str) -> String {
        match self.language {
            SyncLanguage::Ko => {
                format!("[DEBUG] 통합 그룹 {index}/{total}: hash={hash}, client={client}")
            }
            SyncLanguage::En => {
                format!("[DEBUG] Merge group {index}/{total}: hash={hash}, client={client}")
            }
            SyncLanguage::Ja => {
                format!("[DEBUG] 統合グループ {index}/{total}: hash={hash}, client={client}")
            }
        }
    }

    fn debug_record(
        &self,
        kind: DebugRecordKind,
        clear: String,
        exscore: String,
        recorded_at: &str,
    ) -> String {
        let label = match (self.language, kind) {
            (SyncLanguage::Ko, DebugRecordKind::Kept) => "채택",
            (SyncLanguage::Ko, DebugRecordKind::Dropped) => "제외",
            (SyncLanguage::En, DebugRecordKind::Kept) => "kept",
            (SyncLanguage::En, DebugRecordKind::Dropped) => "dropped",
            (SyncLanguage::Ja, DebugRecordKind::Kept) => "採用",
            (SyncLanguage::Ja, DebugRecordKind::Dropped) => "除外",
        };
        match self.language {
            SyncLanguage::Ko | SyncLanguage::Ja => {
                format!("[DEBUG]   {label}: clear={clear}, exscore={exscore}, recorded_at={recorded_at}")
            }
            SyncLanguage::En => {
                format!("[DEBUG]   {label}: clear={clear}, exscore={exscore}, recorded_at={recorded_at}")
            }
        }
    }

    fn no_data(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[WARN] 동기화할 데이터가 없습니다.".to_string(),
            SyncLanguage::En => "[WARN] No data to sync.".to_string(),
            SyncLanguage::Ja => "[WARN] 同期するデータがありません。".to_string(),
        }
    }

    fn progress_server_upload(&self) -> &'static str {
        match self.language {
            SyncLanguage::Ko => "서버 업로드 중",
            SyncLanguage::En => "Uploading to server",
            SyncLanguage::Ja => "サーバーへアップロード中",
        }
    }

    fn server_syncing(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[INFO] 서버에 동기화 중...".to_string(),
            SyncLanguage::En => "[INFO] Syncing with server...".to_string(),
            SyncLanguage::Ja => "[INFO] サーバーに同期中...".to_string(),
        }
    }

    fn progress_uploading(&self) -> &'static str {
        match self.language {
            SyncLanguage::Ko => "서버에 업로드 중",
            SyncLanguage::En => "Uploading to server",
            SyncLanguage::Ja => "サーバーへアップロード中",
        }
    }

    fn server_response_error(&self, error: &str) -> String {
        match self.language {
            SyncLanguage::Ko => format!("[ERROR][stage=uploading] 서버 응답 오류: {error}"),
            SyncLanguage::En => format!("[ERROR][stage=uploading] Server response error: {error}"),
            SyncLanguage::Ja => format!("[ERROR][stage=uploading] サーバー応答エラー: {error}"),
        }
    }

    fn progress_done(&self) -> &'static str {
        match self.language {
            SyncLanguage::Ko => "동기화 완료",
            SyncLanguage::En => "Sync complete",
            SyncLanguage::Ja => "同期完了",
        }
    }

    fn server_sync_complete(&self, inserted: i64, updated: i64) -> String {
        let inserted_text = format_count_i64(inserted);
        let updated_text = format_count_i64(updated);
        match self.language {
            SyncLanguage::Ko => format!(
                "[INFO] 동기화 완료 - 등록된 기록 {inserted_text}건, 수정된 기록 {updated_text}건"
            ),
            SyncLanguage::En => format!(
                "[INFO] Sync complete - inserted {inserted_text} {}, updated {updated_text} {}",
                self.record_word(inserted),
                self.record_word(updated)
            ),
            SyncLanguage::Ja => {
                format!("[INFO] 同期完了 - 新規記録{inserted_text}件、更新記録{updated_text}件")
            }
        }
    }

    fn unchanged_message(&self) -> String {
        match self.language {
            SyncLanguage::Ko => {
                "서버의 improvement check에서 변경 없음으로 처리된 기록".to_string()
            }
            SyncLanguage::En => {
                "Records treated as unchanged by the server improvement check".to_string()
            }
            SyncLanguage::Ja => "サーバーの改善チェックで変更なしとして処理された記録".to_string(),
        }
    }

    fn aborted_progress(&self) -> &'static str {
        match self.language {
            SyncLanguage::Ko => "오류로 동기화 중단",
            SyncLanguage::En => "Sync stopped due to an error",
            SyncLanguage::Ja => "エラーにより同期中断",
        }
    }

    fn parsing_aborted_log(&self) -> String {
        match self.language {
            SyncLanguage::Ko => {
                "[ERROR] 파싱 오류가 발생해 서버 업로드를 중단했습니다. 경로를 확인한 뒤 다시 시도해주세요.".to_string()
            }
            SyncLanguage::En => {
                "[ERROR] A parsing error occurred, so server upload was stopped. Check the path and try again.".to_string()
            }
            SyncLanguage::Ja => {
                "[ERROR] 解析エラーが発生したため、サーバーへのアップロードを中断しました。パスを確認してから再試行してください。".to_string()
            }
        }
    }

    fn detail_progress(&self) -> &'static str {
        match self.language {
            SyncLanguage::Ko => "차분 상세 정보 준비 중",
            SyncLanguage::En => "Preparing chart detail information",
            SyncLanguage::Ja => "差分詳細情報を準備中",
        }
    }

    fn beatoraja_songdata_processing(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[INFO] Beatoraja songdata.db 처리 중...".to_string(),
            SyncLanguage::En => "[INFO] Processing Beatoraja songdata.db...".to_string(),
            SyncLanguage::Ja => "[INFO] Beatoraja songdata.dbを処理中...".to_string(),
        }
    }

    fn songdata_empty(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[INFO] songdata.db: 유효한 항목 없음 (건너뜀)".to_string(),
            SyncLanguage::En => "[INFO] songdata.db: no valid items (skipped)".to_string(),
            SyncLanguage::Ja => "[INFO] songdata.db: 有効な項目なし (スキップ)".to_string(),
        }
    }

    fn beatoraja_detail_ready(&self, count: usize) -> String {
        let count = format_count_usize(count);
        match self.language {
            SyncLanguage::Ko => {
                format!("[INFO] Beatoraja 차분 상세 정보: {count}개 항목 준비 완료")
            }
            SyncLanguage::En => {
                format!("[INFO] Beatoraja chart detail information: {count} items ready")
            }
            SyncLanguage::Ja => format!("[INFO] Beatoraja差分詳細情報: {count}件の準備完了"),
        }
    }

    fn lr2_detail_ready(&self, count: usize) -> String {
        let count = format_count_usize(count);
        match self.language {
            SyncLanguage::Ko => format!("[INFO] LR2 차분 상세 정보: {count}개 항목 준비 완료"),
            SyncLanguage::En => format!("[INFO] LR2 chart detail information: {count} items ready"),
            SyncLanguage::Ja => format!("[INFO] LR2差分詳細情報: {count}件の準備完了"),
        }
    }

    fn no_detail_items(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[INFO] 차분 상세 정보: 전송할 신규/보강 항목 없음".to_string(),
            SyncLanguage::En => {
                "[INFO] Chart detail information: no new/enrichment items to send".to_string()
            }
            SyncLanguage::Ja => "[INFO] 差分詳細情報: 送信する新規/補完項目なし".to_string(),
        }
    }

    fn fumen_detail_summary(&self, inserted: i64, supplemented: i64, skipped: i64) -> String {
        let inserted = format_count_i64(inserted);
        let supplemented = format_count_i64(supplemented);
        let skipped = format_count_i64(skipped);
        match self.language {
            SyncLanguage::Ko => format!(
                "[INFO] 차분 상세 정보 동기화 완료 - 신규 {inserted}개, 보강 {supplemented}개, 이미 존재한 데이터 {skipped}개"
            ),
            SyncLanguage::En => format!(
                "[INFO] Chart detail sync complete - new {inserted}, enriched {supplemented}, already existing {skipped}"
            ),
            SyncLanguage::Ja => format!(
                "[INFO] 差分詳細情報の同期完了 - 新規{inserted}件、補完{supplemented}件、既存データ{skipped}件"
            ),
        }
    }

    fn fumen_detail_error(&self, error: &str) -> String {
        if let Some(detail) = error.strip_prefix("해시 보강 오류: ") {
            return match self.language {
                SyncLanguage::Ko => error.to_string(),
                SyncLanguage::En => format!("Hash enrichment error: {detail}"),
                SyncLanguage::Ja => format!("ハッシュ補完エラー: {detail}"),
            };
        }
        if let Some(detail) = error.strip_prefix("차분 상세 전송 오류: ") {
            return match self.language {
                SyncLanguage::Ko => error.to_string(),
                SyncLanguage::En => format!("Chart detail upload error: {detail}"),
                SyncLanguage::Ja => format!("差分詳細送信エラー: {detail}"),
            };
        }
        error.to_string()
    }

    fn recognized_lr2(&self, path: &str) -> String {
        match self.language {
            SyncLanguage::Ko => format!("[INFO] LR2 기록 DB 인식됨: {path}"),
            SyncLanguage::En => format!("[INFO] LR2 record DB detected: {path}"),
            SyncLanguage::Ja => format!("[INFO] LR2記録DBを検出: {path}"),
        }
    }

    fn recognized_beatoraja(&self, path: &str) -> String {
        match self.language {
            SyncLanguage::Ko => format!("[INFO] Beatoraja 기록 DB 인식됨: {path}"),
            SyncLanguage::En => format!("[INFO] Beatoraja record DB detected: {path}"),
            SyncLanguage::Ja => format!("[INFO] Beatoraja記録DBを検出: {path}"),
        }
    }

    fn lr2_path_missing(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[WARN] LR2 기록 DB: 경로가 설정되어 있지만 파일/폴더를 찾을 수 없습니다. 경로를 다시 확인해주세요.".to_string(),
            SyncLanguage::En => "[WARN] LR2 record DB: a path is set, but the file/folder could not be found. Please check the path again.".to_string(),
            SyncLanguage::Ja => "[WARN] LR2記録DB: パスは設定されていますが、ファイル/フォルダが見つかりません。パスを再確認してください。".to_string(),
        }
    }

    fn beatoraja_dir_missing(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[WARN] Beatoraja 기록 DB 폴더: 경로가 설정되어 있지만 파일/폴더를 찾을 수 없습니다. 경로를 다시 확인해주세요.".to_string(),
            SyncLanguage::En => "[WARN] Beatoraja record DB folder: a path is set, but the file/folder could not be found. Please check the path again.".to_string(),
            SyncLanguage::Ja => "[WARN] Beatoraja記録DBフォルダ: パスは設定されていますが、ファイル/フォルダが見つかりません。パスを再確認してください。".to_string(),
        }
    }

    fn beatoraja_score_missing(&self) -> String {
        match self.language {
            SyncLanguage::Ko => {
                "[WARN] Beatoraja: score.db를 찾을 수 없습니다. 폴더 경로를 다시 확인해주세요."
                    .to_string()
            }
            SyncLanguage::En => {
                "[WARN] Beatoraja: score.db could not be found. Please check the folder path again."
                    .to_string()
            }
            SyncLanguage::Ja => {
                "[WARN] Beatoraja: score.dbが見つかりません。フォルダパスを再確認してください。"
                    .to_string()
            }
        }
    }

    fn beatoraja_scorelog_missing(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[WARN] Beatoraja: scorelog.db를 찾을 수 없습니다. 폴더 경로를 다시 확인해주세요.".to_string(),
            SyncLanguage::En => "[WARN] Beatoraja: scorelog.db could not be found. Please check the folder path again.".to_string(),
            SyncLanguage::Ja => "[WARN] Beatoraja: scorelog.dbが見つかりません。フォルダパスを再確認してください。".to_string(),
        }
    }

    fn beatoraja_songdata_missing(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[WARN] Beatoraja 전체 동기화: songdata.db 경로가 설정되지 않았거나 파일을 찾을 수 없습니다. 해시 보강을 건너뜁니다.".to_string(),
            SyncLanguage::En => "[WARN] Beatoraja full sync: songdata.db path is not set or the file could not be found. Hash enrichment will be skipped.".to_string(),
            SyncLanguage::Ja => "[WARN] Beatoraja全体同期: songdata.dbのパスが未設定、またはファイルが見つかりません。ハッシュ補完をスキップします。".to_string(),
        }
    }

    fn lr2_no_path(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[INFO] LR2 DB: 경로 없음 (동기화 건너뜀)".to_string(),
            SyncLanguage::En => "[INFO] LR2 DB: no path set (sync skipped)".to_string(),
            SyncLanguage::Ja => "[INFO] LR2 DB: パス未設定 (同期をスキップ)".to_string(),
        }
    }

    fn beatoraja_no_path(&self) -> String {
        match self.language {
            SyncLanguage::Ko => "[INFO] Beatoraja DB: 경로 없음 (동기화 건너뜀)".to_string(),
            SyncLanguage::En => "[INFO] Beatoraja DB: no path set (sync skipped)".to_string(),
            SyncLanguage::Ja => "[INFO] Beatoraja DB: パス未設定 (同期をスキップ)".to_string(),
        }
    }

    fn parse_summary(&self, label: &str, total_processed: usize, effective_total: usize) -> String {
        let total_processed = format_count_usize(total_processed);
        let effective_total = format_count_usize(effective_total);
        match self.language {
            SyncLanguage::Ko => {
                format!("[INFO] {label} 처리 완료 ({total_processed}/{effective_total})")
            }
            SyncLanguage::En => {
                format!("[INFO] {label} processed ({total_processed}/{effective_total})")
            }
            SyncLanguage::Ja => {
                format!("[INFO] {label}の処理完了 ({total_processed}/{effective_total})")
            }
        }
    }

    fn skipped_filter(&self, count: usize) -> String {
        let count = format_count_usize(count);
        match self.language {
            SyncLanguage::Ko => {
                format!("    필터 제외: {count}개 - 정상 동작 (선택한 모드/플레이어 외 기록)")
            }
            SyncLanguage::En => {
                format!("    Filter skipped: {count} records - expected behavior (outside the selected mode/player)")
            }
            SyncLanguage::Ja => {
                format!("    フィルター除外: {count}件 - 正常動作 (選択したモード/プレイヤー以外の記録)")
            }
        }
    }

    fn skipped_lr2_imported(&self, count: usize) -> String {
        let count = format_count_usize(count);
        match self.language {
            SyncLanguage::Ko => {
                format!("    LR2 기록 제외: {count}개 - 정상 동작 (LR2에서 임포트된 기록. Beatoraja 기록 아님)")
            }
            SyncLanguage::En => {
                format!("    LR2 records skipped: {count} records - expected behavior (records imported from LR2, not native Beatoraja records)")
            }
            SyncLanguage::Ja => {
                format!("    LR2記録除外: {count}件 - 正常動作 (LR2からインポートされた記録。Beatoraja本来の記録ではありません)")
            }
        }
    }

    fn skipped_no_play(&self, count: usize) -> String {
        let count = format_count_usize(count);
        match self.language {
            SyncLanguage::Ko => {
                format!("    NO PLAY 제외: {count}개 - 정상 동작 (플레이하지 않은 기록은 업로드하지 않음)")
            }
            SyncLanguage::En => {
                format!("    NO PLAY skipped: {count} records - expected behavior (unplayed records are not uploaded)")
            }
            SyncLanguage::Ja => {
                format!(
                    "    NO PLAY除外: {count}件 - 正常動作 (未プレイ記録はアップロードしません)"
                )
            }
        }
    }

    fn skipped_hash(&self, count: usize, sync_unavailable: bool) -> String {
        let count = format_count_usize(count);
        match (self.language, sync_unavailable) {
            (SyncLanguage::Ko, true) => {
                format!("    ⚠ 해시 오류: {count}개 - 주의: 해시 없음 또는 길이 불일치 (sync 불가, DB 손상 가능성)")
            }
            (SyncLanguage::Ko, false) => {
                format!("    ⚠ 해시 오류: {count}개 - 주의: 해시 없음 또는 길이 불일치")
            }
            (SyncLanguage::En, true) => {
                format!("    ⚠ Hash errors: {count} records - warning: missing hash or length mismatch (cannot sync, possible DB corruption)")
            }
            (SyncLanguage::En, false) => {
                format!(
                    "    ⚠ Hash errors: {count} records - warning: missing hash or length mismatch"
                )
            }
            (SyncLanguage::Ja, true) => {
                format!("    ⚠ ハッシュエラー: {count}件 - 注意: ハッシュなし、または長さ不一致 (同期不可、DB破損の可能性)")
            }
            (SyncLanguage::Ja, false) => {
                format!("    ⚠ ハッシュエラー: {count}件 - 注意: ハッシュなし、または長さ不一致")
            }
        }
    }

    fn scorelog_summary(&self, parsed: usize, total_queried: usize) -> String {
        let parsed = format_count_usize(parsed);
        let total_queried = format_count_usize(total_queried);
        match self.language {
            SyncLanguage::Ko => {
                format!("[INFO] Beatoraja scorelog.db 처리 완료 ({parsed}/{total_queried})")
            }
            SyncLanguage::En => {
                format!("[INFO] Beatoraja scorelog.db processed ({parsed}/{total_queried})")
            }
            SyncLanguage::Ja => {
                format!("[INFO] Beatoraja scorelog.dbの処理完了 ({parsed}/{total_queried})")
            }
        }
    }

    fn skipped_scorelog_duplicate(&self, count: usize) -> String {
        let count = format_count_usize(count);
        match self.language {
            SyncLanguage::Ko => {
                format!(
                    "    score.db 중복 제외: {count}개 - 정상 동작 (현재 최고 기록과 동일한 항목)"
                )
            }
            SyncLanguage::En => {
                format!("    score.db duplicates skipped: {count} records - expected behavior (same as current best records)")
            }
            SyncLanguage::Ja => {
                format!("    score.db重複除外: {count}件 - 正常動作 (現在のベスト記録と同一の項目)")
            }
        }
    }

    fn metadata_update_count(&self, count: usize) -> String {
        let count = format_count_usize(count);
        match self.language {
            SyncLanguage::Ko => format!("[DEBUG] 메타데이터 수정 항목: {count}건"),
            SyncLanguage::En => format!("[DEBUG] Metadata updates: {count} records"),
            SyncLanguage::Ja => format!("[DEBUG] メタデータ更新項目: {count}件"),
        }
    }

    fn metadata_update_entry(
        &self,
        index: usize,
        identifier: &str,
        client_type: &str,
        row_id: &str,
        changed_fields: &str,
    ) -> String {
        match self.language {
            SyncLanguage::Ko => format!(
                "[DEBUG] #{index} 수정: {identifier} ({client_type}, row_id={row_id}), 변경 필드: [{changed_fields}]"
            ),
            SyncLanguage::En => format!(
                "[DEBUG] #{index} updated: {identifier} ({client_type}, row_id={row_id}), changed fields: [{changed_fields}]"
            ),
            SyncLanguage::Ja => format!(
                "[DEBUG] #{index}更新: {identifier} ({client_type}, row_id={row_id}), 変更フィールド: [{changed_fields}]"
            ),
        }
    }

    fn before_json(&self, value: &str) -> String {
        match self.language {
            SyncLanguage::Ko => format!("[DEBUG]   이전: {value}"),
            SyncLanguage::En => format!("[DEBUG]   before: {value}"),
            SyncLanguage::Ja => format!("[DEBUG]   以前: {value}"),
        }
    }

    fn after_json(&self, value: &str) -> String {
        match self.language {
            SyncLanguage::Ko => format!("[DEBUG]   이후: {value}"),
            SyncLanguage::En => format!("[DEBUG]   after: {value}"),
            SyncLanguage::Ja => format!("[DEBUG]   以後: {value}"),
        }
    }
}

#[derive(Debug, Clone, Copy)]
enum DebugRecordKind {
    Kept,
    Dropped,
}

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
    level: String,
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
                let msg = format!("{:#}", error);
                let text = config::load(&app_for_task)
                    .map(|cfg| SyncText::new(&cfg.language))
                    .unwrap_or_else(|_| SyncText::new("ko"));
                write_error_log(&app_for_task, &run_id_for_task, None, Some(&msg));
                if msg.contains(auth_domain::REAUTH_REQUIRED_TAG) {
                    // Notify the auth store so the header switches to logged-out
                    // and broadcast a dedicated event so the UI can show a
                    // re-login banner instead of a generic sync error.
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
                            message: text.reauth_required(),
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
    let text = SyncText::new(&cfg.language);
    ensure_session_for_sync(&app, &cfg.api_url).await?;
    let api = ApiClient::new(cfg.api_url.clone(), app.clone(), cfg.debug_mode)?;
    let include_lr2 = matches!(request.client_filter.as_str(), "all" | "lr2");
    let include_bea = matches!(request.client_filter.as_str(), "all" | "beatoraja");
    let mut errors: Vec<SyncErrorEntry> = Vec::new();

    log(&app, &sync_run_id, "info", &text.checking_paths());
    progress(
        &app,
        &sync_run_id,
        None,
        "validating",
        None,
        None,
        text.progress_validating(),
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
        text,
    );

    if include_lr2 && cfg.lr2_db_path.is_some() && !lr2_path_ok {
        log(&app, &sync_run_id, "warn", &text.lr2_path_missing());
    }
    if include_bea && cfg.beatoraja_db_dir.is_some() && !bea_dir_ok {
        log(&app, &sync_run_id, "warn", &text.beatoraja_dir_missing());
    }
    if include_bea && bea_dir_ok && !bea_score_db_ok {
        log(&app, &sync_run_id, "warn", &text.beatoraja_score_missing());
    }
    if include_bea && bea_dir_ok && !bea_scorelog_ok {
        log(
            &app,
            &sync_run_id,
            "warn",
            &text.beatoraja_scorelog_missing(),
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
            &text.beatoraja_songdata_missing(),
        );
    }

    check_cancel(&cancel_flag)?;

    if request.full_sync {
        errors.extend(
            run_full_detail_sync(
                &app,
                &sync_run_id,
                &api,
                &cfg,
                include_lr2,
                include_bea,
                text,
            )
            .await,
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
        text.progress_local_db(),
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
                text.progress_lr2_user_db(),
            );
            log(&app, &sync_run_id, "info", &text.lr2_user_db_log());
            match lr2::parse_scores(path) {
                Ok((scores, courses, stats)) => {
                    log_parse_summary(
                        &app,
                        &sync_run_id,
                        text.lr2_play_record_label(),
                        stats.parsed + stats.parsed_courses,
                        stats.db_total,
                        stats.skipped_filter(),
                        0,
                        stats.skipped_no_play,
                        stats.skipped_hash,
                        text,
                    );
                    all_scores.extend(scores);
                    all_scores.extend(courses);
                    if let Some(stats) = lr2::parse_player_stats(path) {
                        all_player_stats.push(stats);
                    }
                }
                Err(error) => {
                    let detail = format!("path={path} | {error:#}");
                    errors.push(SyncErrorEntry {
                        client: Some("lr2".to_string()),
                        message: text.parsing_error_message("LR2"),
                        detail: Some(detail.clone()),
                        level: "error".to_string(),
                    });
                    log(
                        &app,
                        &sync_run_id,
                        "error",
                        &text.parsing_error_log("LR2", "parsing/lr2", &detail),
                    );
                    finish_sync_aborted_by_error(&app, sync_run_id, request, errors, text);
                    return Ok(());
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
                text.progress_beatoraja_scores(),
            );
            log(&app, &sync_run_id, "info", &text.beatoraja_scores_log());
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
                        stats.skipped_no_play,
                        stats.skipped_hash,
                        text,
                    );
                    all_scores.extend(scores);
                    all_scores.extend(courses);
                }
                Err(error) => {
                    let detail = format!("path={path} | error={error:#}");
                    errors.push(SyncErrorEntry {
                        client: Some("beatoraja".to_string()),
                        message: text.parsing_error_message("Beatoraja"),
                        detail: Some(detail.clone()),
                        level: "error".to_string(),
                    });
                    log(
                        &app,
                        &sync_run_id,
                        "error",
                        &text.parsing_error_log("Beatoraja", "parsing/beatoraja", &detail),
                    );
                    finish_sync_aborted_by_error(&app, sync_run_id, request, errors, text);
                    return Ok(());
                }
            }

            let (scorelog, stats) = beatoraja::parse_score_log(path, None);
            log_scorelog_summary(
                &app,
                &sync_run_id,
                stats.parsed + stats.parsed_courses,
                stats.total_queried,
                stats.skipped_duplicate,
                stats.skipped_no_play,
                stats.skipped_hash,
                text,
            );
            all_scores.extend(scorelog);

            if let Some(stats) = beatoraja::parse_player_stats(path) {
                all_player_stats.push(stats);
            }
        }
    }

    check_cancel(&cancel_flag)?;

    let sync_now_utc_date = time::OffsetDateTime::now_utc().date();
    let (deduped, dedup_groups) =
        dedup_same_day_records(std::mem::take(&mut all_scores), sync_now_utc_date);
    all_scores = deduped;
    if !dedup_groups.is_empty() {
        let total_dropped: usize = dedup_groups.iter().map(|g| g.dropped.len()).sum();
        log(
            &app,
            &sync_run_id,
            "debug",
            &text.scorelog_duplicate_debug(total_dropped),
        );
        let group_count = dedup_groups.len();
        for (i, group) in dedup_groups.iter().enumerate() {
            let hash = group
                .kept
                .fumen_sha256
                .as_deref()
                .or(group.kept.fumen_md5.as_deref())
                .or(group.kept.fumen_hash_others.as_deref())
                .unwrap_or("unknown");
            log(
                &app,
                &sync_run_id,
                "debug",
                &text.debug_group(i + 1, group_count, hash, &group.kept.client_type),
            );
            log(
                &app,
                &sync_run_id,
                "debug",
                &text.debug_record(
                    DebugRecordKind::Kept,
                    group
                        .kept
                        .clear_type
                        .map_or("-".to_string(), |v| v.to_string()),
                    group
                        .kept
                        .exscore
                        .map_or("-".to_string(), |v| v.to_string()),
                    group.kept.recorded_at.as_deref().unwrap_or("-"),
                ),
            );
            for dropped in &group.dropped {
                log(
                    &app,
                    &sync_run_id,
                    "debug",
                    &text.debug_record(
                        DebugRecordKind::Dropped,
                        dropped
                            .clear_type
                            .map_or("-".to_string(), |v| v.to_string()),
                        dropped.exscore.map_or("-".to_string(), |v| v.to_string()),
                        dropped.recorded_at.as_deref().unwrap_or("-"),
                    ),
                );
            }
        }
    }

    if all_scores.is_empty() && all_player_stats.is_empty() {
        log(&app, &sync_run_id, "warn", &text.no_data());
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
        text.progress_server_upload(),
    );
    log(&app, &sync_run_id, "info", &text.server_syncing());

    let mut inserted = 0;
    let mut synced = 0;
    let mut skipped = 0;
    let mut metadata_updated = 0;
    let mut server_errors = Vec::new();
    let mut has_score_changes = false;
    let chunks = if all_scores.is_empty() {
        1
    } else {
        all_scores.chunks(SCORE_BATCH_SIZE).len()
    };

    if all_scores.is_empty() {
        let response = api
            .sync_scores(&[], &all_player_stats, true, has_score_changes)
            .await?;
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
            let response = api
                .sync_scores(batch, stats_batch, idx + 1 == chunks, has_score_changes)
                .await?;
            inserted += response.inserted_scores;
            synced += response.synced_scores;
            skipped += response.skipped_scores;
            metadata_updated += response.metadata_updated;
            if response.synced_scores > 0 || response.inserted_scores > 0 {
                has_score_changes = true;
            }
            server_errors.extend(response.errors);
            if cfg.debug_mode {
                log_debug_updates(&app, &sync_run_id, &response.debug_updates, text);
            }
            progress(
                &app,
                &sync_run_id,
                None,
                "uploading",
                Some(idx + 1),
                Some(chunks),
                text.progress_uploading(),
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
        log(
            &app,
            &sync_run_id,
            "error",
            &text.server_response_error(&error),
        );
        errors.push(SyncErrorEntry {
            client: None,
            message: error,
            detail: Some("stage=uploading".to_string()),
            level: "error".to_string(),
        });
    }

    progress(
        &app,
        &sync_run_id,
        None,
        "done",
        None,
        None,
        text.progress_done(),
    );
    log(
        &app,
        &sync_run_id,
        "info",
        &text.server_sync_complete(inserted, metadata_updated),
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
                    message: Some(text.unchanged_message()),
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

fn finish_sync_aborted_by_error(
    app: &AppHandle,
    sync_run_id: String,
    request: SyncRequest,
    errors: Vec<SyncErrorEntry>,
    text: SyncText,
) {
    progress(
        app,
        &sync_run_id,
        None,
        "done",
        None,
        None,
        text.aborted_progress(),
    );
    log(app, &sync_run_id, "error", &text.parsing_aborted_log());
    emit_finished(
        app,
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
}

async fn ensure_session_for_sync(app: &AppHandle, api_url: &str) -> anyhow::Result<()> {
    if !auth_domain::ensure_refresh_token_fresh(app, api_url, REFRESH_TOKEN_PROACTIVE_RENEW_DAYS)
        .await?
    {
        return Err(auth_domain::reauth_required_error());
    }

    auth_cmd::emit_auth_changed(
        app,
        &AuthStatus {
            logged_in: true,
            refresh_token_expire_days: auth_domain::refresh_token_expire_days(app),
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
    text: SyncText,
) -> Vec<SyncErrorEntry> {
    let mut errors = Vec::new();
    progress(
        app,
        sync_run_id,
        None,
        "supplementing",
        None,
        None,
        text.detail_progress(),
    );
    let mut bea_items = Vec::new();
    if include_bea {
        if let Some(songdata_path) = cfg.beatoraja_songdata_db_path.as_deref() {
            if Path::new(songdata_path).exists() {
                log(
                    app,
                    sync_run_id,
                    "info",
                    &text.beatoraja_songdata_processing(),
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
                    log(app, sync_run_id, "info", &text.songdata_empty());
                } else {
                    log(
                        app,
                        sync_run_id,
                        "info",
                        &text.beatoraja_detail_ready(bea_items.len()),
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
            &text.lr2_detail_ready(lr2_items.len()),
        );
    }

    if bea_items.is_empty() && lr2_items.is_empty() {
        log(app, sync_run_id, "info", &text.no_detail_items());
        return errors;
    }

    let summary = fumen_detail::run_detail_sync(api, bea_items, lr2_items).await;
    log(
        app,
        sync_run_id,
        "info",
        &text.fumen_detail_summary(
            summary.inserted,
            summary.supplemented + summary.updated,
            summary.skipped,
        ),
    );
    for error in summary.errors.into_iter().take(5) {
        let message = text.fumen_detail_error(&error);
        log(
            app,
            sync_run_id,
            "warn",
            &format!("[WARN][stage=supplementing] {message}"),
        );
        errors.push(SyncErrorEntry {
            client: None,
            message,
            detail: Some("stage=supplementing".to_string()),
            level: "warn".to_string(),
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
    text: SyncText,
) {
    if client_filter != "all" {
        return;
    }

    if lr2_ok {
        if let Some(path) = cfg.lr2_db_path.as_deref() {
            log(app, sync_run_id, "info", &text.recognized_lr2(path));
        }
    } else if cfg.lr2_db_path.is_none() {
        log(app, sync_run_id, "info", &text.lr2_no_path());
    }

    if bea_ok {
        if let Some(path) = cfg.beatoraja_db_dir.as_deref() {
            log(app, sync_run_id, "info", &text.recognized_beatoraja(path));
        }
    } else if cfg.beatoraja_db_dir.is_none() {
        log(app, sync_run_id, "info", &text.beatoraja_no_path());
    }

    if full_sync && bea_ok && !bea_songdata_ok {
        log(app, sync_run_id, "warn", &text.beatoraja_songdata_missing());
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
    skipped_no_play: usize,
    skipped_hash: usize,
    text: SyncText,
) {
    log(
        app,
        sync_run_id,
        "info",
        &text.parse_summary(label, total_processed, effective_total),
    );
    if skipped_filter > 0 {
        log(
            app,
            sync_run_id,
            "info",
            &text.skipped_filter(skipped_filter),
        );
    }
    if skipped_lr2 > 0 {
        log(
            app,
            sync_run_id,
            "info",
            &text.skipped_lr2_imported(skipped_lr2),
        );
    }
    if skipped_no_play > 0 {
        log(
            app,
            sync_run_id,
            "info",
            &text.skipped_no_play(skipped_no_play),
        );
    }
    if skipped_hash > 0 {
        log(
            app,
            sync_run_id,
            "warn",
            &text.skipped_hash(skipped_hash, true),
        );
    }
}

fn log_scorelog_summary(
    app: &AppHandle,
    sync_run_id: &str,
    parsed: usize,
    total_queried: usize,
    skipped_duplicate: usize,
    skipped_no_play: usize,
    skipped_hash: usize,
    text: SyncText,
) {
    log(
        app,
        sync_run_id,
        "info",
        &text.scorelog_summary(parsed, total_queried),
    );
    if skipped_duplicate > 0 {
        log(
            app,
            sync_run_id,
            "info",
            &text.skipped_scorelog_duplicate(skipped_duplicate),
        );
    }
    if skipped_no_play > 0 {
        log(
            app,
            sync_run_id,
            "info",
            &text.skipped_no_play(skipped_no_play),
        );
    }
    if skipped_hash > 0 {
        log(
            app,
            sync_run_id,
            "warn",
            &text.skipped_hash(skipped_hash, false),
        );
    }
}

fn log_debug_updates(
    app: &AppHandle,
    sync_run_id: &str,
    updates: &[serde_json::Value],
    text: SyncText,
) {
    if updates.is_empty() {
        return;
    }
    log(
        app,
        sync_run_id,
        "debug",
        &text.metadata_update_count(updates.len()),
    );
    for (i, entry) in updates.iter().enumerate() {
        let identifier = entry
            .get("identifier")
            .and_then(|v| v.as_str())
            .unwrap_or("?");
        let client_type = entry
            .get("client_type")
            .and_then(|v| v.as_str())
            .unwrap_or("?");
        let row_id = entry.get("row_id").and_then(|v| v.as_str()).unwrap_or("?");
        let changed_fields = entry
            .get("changed_fields")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str())
                    .collect::<Vec<_>>()
                    .join(", ")
            })
            .unwrap_or_default();
        log(
            app,
            sync_run_id,
            "debug",
            &text.metadata_update_entry(i + 1, identifier, client_type, row_id, &changed_fields),
        );
        if let Some(before) = entry.get("before") {
            let before_str = serde_json::to_string(before).unwrap_or_else(|_| "?".to_string());
            log(app, sync_run_id, "debug", &text.before_json(&before_str));
        }
        if let Some(after) = entry.get("after") {
            let after_str = serde_json::to_string(after).unwrap_or_else(|_| "?".to_string());
            log(app, sync_run_id, "debug", &text.after_json(&after_str));
        }
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

    // Mirror the line into the `log` crate so the disk target captures it.
    // The disk target's filter (in `crate::logging`) drops INFO/DEBUG by
    // default and lets WARN/ERROR through, which is exactly the signal we
    // want preserved for after-the-fact troubleshooting.
    let short_id = &sync_run_id[..8.min(sync_run_id.len())];
    match level {
        "error" => log::error!(target: "sync", "[{short_id}] {message}"),
        "warn" => log::warn!(target: "sync", "[{short_id}] {message}"),
        "debug" => log::debug!(target: "sync", "[{short_id}] {message}"),
        _ => log::info!(target: "sync", "[{short_id}] {message}"),
    }
}

fn emit_finished(app: &AppHandle, result: SyncResult) {
    write_error_log(app, &result.sync_run_id, Some(&result), None);
    let _ = app.emit("sync:finished", result);
}

#[derive(Debug, Clone, Serialize)]
struct StageCounts {
    client_filter: String,
    full_sync: bool,
    inserted: i64,
    improved: i64,
    metadata_updated: i64,
    unchanged: i64,
    errors_total: usize,
    errors_error: usize,
    errors_warn: usize,
}

impl StageCounts {
    fn from_result(result: &SyncResult) -> Self {
        let errors_warn = result.errors.iter().filter(|e| e.level == "warn").count();
        let errors_error = result.errors.len() - errors_warn;
        Self {
            client_filter: result.client_filter.clone(),
            full_sync: result.full_sync,
            inserted: result.inserted,
            improved: result.improved,
            metadata_updated: result.metadata_updated,
            unchanged: result.unchanged,
            errors_total: result.errors.len(),
            errors_error,
            errors_warn,
        }
    }

    fn render_text(&self) -> String {
        let mut out = String::new();
        let mut line = |k: &str, v: String| out.push_str(&format!("{:<24}: {}\n", k, v));
        line("client_filter", self.client_filter.clone());
        line("full_sync", self.full_sync.to_string());
        line("inserted", self.inserted.to_string());
        line("improved", self.improved.to_string());
        line("metadata_updated", self.metadata_updated.to_string());
        line("unchanged", self.unchanged.to_string());
        line("errors_total", self.errors_total.to_string());
        line("errors_error", self.errors_error.to_string());
        line("errors_warn", self.errors_warn.to_string());
        out
    }
}

#[derive(Debug, Serialize)]
struct ErrorReport<'a> {
    sync_run_id: &'a str,
    generated_at: String,
    environment: EnvironmentSnapshot,
    path_checks: PathChecks,
    stage_counts: Option<StageCounts>,
    fatal: Option<&'a str>,
    errors: &'a [SyncErrorEntry],
}

fn write_error_log(
    app: &AppHandle,
    sync_run_id: &str,
    result: Option<&SyncResult>,
    fatal: Option<&str>,
) {
    let errors: &[SyncErrorEntry] = result.map(|r| r.errors.as_slice()).unwrap_or(&[]);
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

    let cfg = config::load(app).unwrap_or_default();
    let environment = EnvironmentSnapshot::capture(app, &cfg);
    let path_checks = PathChecks::capture(&cfg);
    let stage_counts = result.map(StageCounts::from_result);
    let generated_at = now_rfc3339();

    let mut content = String::new();
    content.push_str("OJIK BMS Client - Sync Error Report\n");
    content.push_str("====================================\n");
    content.push_str(&format!("sync_run_id             : {}\n", sync_run_id));
    content.push_str(&format!("generated_at            : {}\n\n", generated_at));

    content.push_str("[ENVIRONMENT]\n");
    content.push_str(&environment.render_text());
    content.push('\n');

    content.push_str("[PATH CHECKS]\n");
    content.push_str(&path_checks.render_text());
    content.push('\n');

    if let Some(counts) = &stage_counts {
        content.push_str("[STAGE COUNTS]\n");
        content.push_str(&counts.render_text());
        content.push('\n');
    }

    if let Some(msg) = fatal {
        content.push_str("[FATAL]\n");
        content.push_str(msg);
        content.push_str("\n\n");
    }

    if !errors.is_empty() {
        content.push_str("[ERRORS]\n");
        for err in errors {
            let tag = if err.level == "warn" { "WARN" } else { "ERROR" };
            match &err.client {
                Some(c) => content.push_str(&format!("[{}][{}] {}\n", tag, c, err.message)),
                None => content.push_str(&format!("[{}] {}\n", tag, err.message)),
            }
            if let Some(detail) = &err.detail {
                content.push_str(&format!("  Detail: {}\n", detail));
            }
        }
        content.push('\n');
    }

    let report = ErrorReport {
        sync_run_id,
        generated_at,
        environment,
        path_checks,
        stage_counts,
        fatal,
        errors,
    };
    if let Ok(json) = serde_json::to_string_pretty(&report) {
        content.push_str("[JSON]\n");
        content.push_str(&json);
        content.push('\n');
    }

    let _ = std::fs::write(path, content);
}

fn now_rfc3339() -> String {
    time::OffsetDateTime::now_utc()
        .format(&time::format_description::well_known::Rfc3339)
        .unwrap_or_else(|_| "1970-01-01T00:00:00Z".to_string())
}

fn recorded_at_date_utc(recorded_at: &Option<String>) -> Option<time::Date> {
    recorded_at.as_deref().and_then(|s| {
        time::OffsetDateTime::parse(s, &time::format_description::well_known::Rfc3339)
            .ok()
            .map(|dt| dt.to_offset(time::UtcOffset::UTC).date())
    })
}

fn recorded_at_unix_timestamp(recorded_at: &Option<String>) -> Option<i64> {
    recorded_at.as_deref().and_then(|s| {
        time::OffsetDateTime::parse(s, &time::format_description::well_known::Rfc3339)
            .ok()
            .map(|dt| dt.unix_timestamp())
    })
}

/// Returns true if `a` should be replaced by `b` (b is "better" by the dedup ordering).
/// Order: recorded_at desc → clear_type desc → exscore desc → input order (first wins).
fn score_ordering_lt(a: &ScoreItem, b: &ScoreItem) -> bool {
    let a_ts = recorded_at_unix_timestamp(&a.recorded_at);
    let b_ts = recorded_at_unix_timestamp(&b.recorded_at);
    match (a_ts, b_ts) {
        (Some(ax), Some(bx)) if ax != bx => return ax < bx,
        (None, Some(_)) => return true,
        (Some(_), None) => return false,
        _ => {}
    }
    match (a.clear_type, b.clear_type) {
        (Some(ax), Some(bx)) if ax != bx => return ax < bx,
        (None, Some(_)) => return true,
        _ => {}
    }
    match (a.exscore, b.exscore) {
        (Some(ax), Some(bx)) if ax != bx => return ax < bx,
        (None, Some(_)) => return true,
        _ => {}
    }
    false
}

struct DedupGroup {
    kept: ScoreItem,
    dropped: Vec<ScoreItem>,
}

/// Dedup scores so that each (fumen_identifier, client_type, UTC date) key keeps only
/// the best entry (latest recorded_at, then highest clear_type, then highest exscore).
/// The returned vector is **sorted ascending by recorded_at** so that the server's
/// cumulative-best improvement check processes oldest records first — without this,
/// historical scorelog entries are silently dropped when they arrive in non-chronological
/// order (HashMap iteration is randomized).
///
/// Items without any fumen identifier pass through unchanged.
/// Items with recorded_at=None use `sync_now_utc_date` as the date key, matching the
/// synced_at UTC date the server will assign (project convention for LR2 rows).
fn dedup_same_day_records(
    items: Vec<ScoreItem>,
    sync_now_utc_date: time::Date,
) -> (Vec<ScoreItem>, Vec<DedupGroup>) {
    let mut keep: HashMap<(String, String, time::Date), ScoreItem> = HashMap::new();
    let mut dropped_by_key: HashMap<(String, String, time::Date), Vec<ScoreItem>> = HashMap::new();
    let mut passthrough: Vec<ScoreItem> = Vec::new();

    for item in items {
        let id = item
            .fumen_sha256
            .clone()
            .or_else(|| item.fumen_md5.clone())
            .or_else(|| item.fumen_hash_others.clone());
        let Some(id) = id else {
            passthrough.push(item);
            continue;
        };
        let date = recorded_at_date_utc(&item.recorded_at).unwrap_or(sync_now_utc_date);
        let key = (id, item.client_type.clone(), date);
        let should_replace = match keep.get(&key) {
            None => true,
            Some(existing) => score_ordering_lt(existing, &item),
        };
        if should_replace {
            if let Some(evicted) = keep.insert(key.clone(), item) {
                dropped_by_key.entry(key).or_default().push(evicted);
            }
        } else {
            dropped_by_key.entry(key).or_default().push(item);
        }
    }

    let mut groups: Vec<DedupGroup> = Vec::new();
    let mut out: Vec<ScoreItem> = Vec::new();
    for (key, kept) in keep {
        if let Some(dropped) = dropped_by_key.remove(&key) {
            groups.push(DedupGroup {
                kept: kept.clone(),
                dropped,
            });
            out.push(kept);
        } else {
            out.push(kept);
        }
    }
    out.extend(passthrough);

    // Sort ascending by recorded_at so that the server's cumulative-best
    // improvement check (api/app/routers/sync.py::_is_improvement) processes
    // historical records oldest-first. Without this, a HashMap-randomized order
    // makes any record older than the first-processed one be skipped as
    // "no improvement", which silently drops the bulk of scorelog history.
    // Items without recorded_at sort first (i64::MIN) — they hit the same-day
    // merge path on the server regardless of position.
    out.sort_by_key(|item| recorded_at_unix_timestamp(&item.recorded_at).unwrap_or(i64::MIN));

    (out, groups)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_item(
        fumen_sha256: Option<&str>,
        fumen_md5: Option<&str>,
        fumen_hash_others: Option<&str>,
        client_type: &str,
        recorded_at: Option<&str>,
        clear_type: Option<i64>,
        exscore: Option<i64>,
    ) -> ScoreItem {
        ScoreItem {
            scorehash: None,
            fumen_sha256: fumen_sha256.map(str::to_string),
            fumen_md5: fumen_md5.map(str::to_string),
            fumen_hash_others: fumen_hash_others.map(str::to_string),
            client_type: client_type.to_string(),
            clear_type,
            notes: None,
            exscore,
            max_combo: None,
            min_bp: None,
            judgments: None,
            options: None,
            play_count: None,
            clear_count: None,
            recorded_at: recorded_at.map(str::to_string),
            song_hashes: vec![],
        }
    }

    fn march19() -> time::Date {
        time::Date::from_calendar_date(2025, time::Month::March, 19).unwrap()
    }

    #[test]
    fn dedup_keeps_latest_recorded_at_for_same_day_course() {
        let hash = "a".repeat(256);
        let earlier = make_item(
            None,
            None,
            Some(&hash),
            "beatoraja",
            Some("2025-03-19T11:20:14Z"),
            Some(1),
            Some(100),
        );
        let later = make_item(
            None,
            None,
            Some(&hash),
            "beatoraja",
            Some("2025-03-19T11:33:12Z"),
            Some(4),
            Some(200),
        );
        let (out, dropped) = dedup_same_day_records(vec![earlier, later], march19());
        assert_eq!(dropped.len(), 1);
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].exscore, Some(200));
    }

    #[test]
    fn dedup_uses_sync_now_date_when_recorded_at_is_none() {
        let md5 = "b".repeat(32);
        let item1 = make_item(None, Some(&md5), None, "lr2", None, Some(2), Some(500));
        let item2 = make_item(None, Some(&md5), None, "lr2", None, Some(2), Some(500));
        let (out, dropped) = dedup_same_day_records(vec![item1, item2], march19());
        assert_eq!(dropped.len(), 1);
        assert_eq!(out.len(), 1);
    }

    #[test]
    fn dedup_keeps_recorded_at_some_over_none_on_collision() {
        let md5 = "c".repeat(32);
        let with_ts = make_item(
            None,
            Some(&md5),
            None,
            "beatoraja",
            Some("2025-03-19T12:00:00Z"),
            Some(2),
            Some(300),
        );
        let without_ts = make_item(
            None,
            Some(&md5),
            None,
            "beatoraja",
            None,
            Some(1),
            Some(100),
        );
        // sync_now_utc_date == march19 so without_ts date key matches with_ts date key
        let (out, dropped) = dedup_same_day_records(vec![without_ts, with_ts], march19());
        assert_eq!(dropped.len(), 1);
        assert_eq!(out.len(), 1);
        assert!(out[0].recorded_at.is_some());
    }

    #[test]
    fn dedup_treats_different_dates_as_separate() {
        let sha256 = "d".repeat(64);
        let day1 = make_item(
            Some(&sha256),
            None,
            None,
            "beatoraja",
            Some("2025-03-19T12:00:00Z"),
            Some(2),
            Some(500),
        );
        let day2 = make_item(
            Some(&sha256),
            None,
            None,
            "beatoraja",
            Some("2025-03-20T12:00:00Z"),
            Some(2),
            Some(500),
        );
        let (out, dropped) = dedup_same_day_records(vec![day1, day2], march19());
        assert_eq!(dropped.len(), 0);
        assert_eq!(out.len(), 2);
    }

    #[test]
    fn dedup_falls_back_to_clear_type_then_exscore_on_tie() {
        let sha256 = "e".repeat(64);
        let same_ts = "2025-03-19T12:00:00Z";
        let low_clear = make_item(
            Some(&sha256),
            None,
            None,
            "beatoraja",
            Some(same_ts),
            Some(1),
            Some(500),
        );
        let high_clear = make_item(
            Some(&sha256),
            None,
            None,
            "beatoraja",
            Some(same_ts),
            Some(4),
            Some(300),
        );
        let (out, dropped) = dedup_same_day_records(vec![low_clear, high_clear], march19());
        assert_eq!(dropped.len(), 1);
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].clear_type, Some(4));
    }

    #[test]
    fn dedup_handles_md5_only_records() {
        let md5 = "f".repeat(32);
        let item1 = make_item(
            None,
            Some(&md5),
            None,
            "lr2",
            Some("2025-03-19T10:00:00Z"),
            Some(2),
            Some(400),
        );
        let item2 = make_item(
            None,
            Some(&md5),
            None,
            "lr2",
            Some("2025-03-19T11:00:00Z"),
            Some(2),
            Some(450),
        );
        let (out, dropped) = dedup_same_day_records(vec![item1, item2], march19());
        assert_eq!(dropped.len(), 1);
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].exscore, Some(450));
    }

    #[test]
    fn dedup_returns_items_sorted_ascending_by_recorded_at() {
        // Three different fumens, recorded_at out of order on input.
        // After dedup, output must be sorted ascending so the server's improvement
        // check processes oldest-first.
        let h_old = "1".repeat(64);
        let h_mid = "2".repeat(64);
        let h_new = "3".repeat(64);

        let item_new = make_item(
            Some(&h_new),
            None,
            None,
            "beatoraja",
            Some("2025-03-19T12:00:00Z"),
            Some(2),
            Some(400),
        );
        let item_old = make_item(
            Some(&h_old),
            None,
            None,
            "beatoraja",
            Some("2025-01-01T12:00:00Z"),
            Some(2),
            Some(300),
        );
        let item_mid = make_item(
            Some(&h_mid),
            None,
            None,
            "beatoraja",
            Some("2025-02-15T12:00:00Z"),
            Some(2),
            Some(350),
        );

        // Intentionally pass items in non-chronological order to mimic the
        // HashMap-scrambled order that triggered the original bug.
        let (out, _) = dedup_same_day_records(vec![item_new, item_old, item_mid], march19());
        assert_eq!(out.len(), 3);
        let ts: Vec<&str> = out
            .iter()
            .map(|s| s.recorded_at.as_deref().unwrap_or(""))
            .collect();
        assert_eq!(
            ts,
            vec![
                "2025-01-01T12:00:00Z",
                "2025-02-15T12:00:00Z",
                "2025-03-19T12:00:00Z",
            ]
        );
    }

    #[test]
    fn dedup_places_recorded_at_none_before_dated_items() {
        // recorded_at=None falls back to i64::MIN in the sort key, so it must
        // appear before any dated item.
        let md5 = "a".repeat(32);
        let sha = "b".repeat(64);
        let dated = make_item(
            Some(&sha),
            None,
            None,
            "beatoraja",
            Some("2025-03-19T12:00:00Z"),
            Some(2),
            Some(500),
        );
        let undated = make_item(None, Some(&md5), None, "lr2", None, Some(2), Some(400));

        let (out, _) = dedup_same_day_records(vec![dated, undated], march19());
        assert_eq!(out.len(), 2);
        assert!(out[0].recorded_at.is_none());
        assert!(out[1].recorded_at.is_some());
    }

    #[test]
    fn sync_text_renders_japanese_runtime_logs() {
        let text = SyncText::new("ja");

        assert_eq!(text.checking_paths(), "[INFO] 設定とDBパスを確認します。");
        assert_eq!(
            text.fumen_detail_summary(0, 2, 47_140),
            "[INFO] 差分詳細情報の同期完了 - 新規0件、補完2件、既存データ47,140件"
        );
        assert_eq!(
            text.parse_summary("LR2プレイ記録", 5_636, 5_648),
            "[INFO] LR2プレイ記録の処理完了 (5,636/5,648)"
        );
        assert_eq!(
            text.skipped_no_play(12),
            "    NO PLAY除外: 12件 - 正常動作 (未プレイ記録はアップロードしません)"
        );
        assert_eq!(
            text.scorelog_duplicate_debug(3),
            "[DEBUG] Beatoraja scorelog.dbの同日同一差分の重複3件を最新記録に統合しました。"
        );
        assert_eq!(
            text.fumen_detail_error("차분 상세 전송 오류: timeout"),
            "差分詳細送信エラー: timeout"
        );
    }

    #[test]
    fn sync_text_renders_english_runtime_logs() {
        let text = SyncText::new("en-US");

        assert_eq!(
            text.checking_paths(),
            "[INFO] Checking settings and DB paths."
        );
        assert_eq!(
            text.server_sync_complete(1, 2),
            "[INFO] Sync complete - inserted 1 record, updated 2 records"
        );
        assert_eq!(
            text.skipped_lr2_imported(2_843),
            "    LR2 records skipped: 2,843 records - expected behavior (records imported from LR2, not native Beatoraja records)"
        );
        assert_eq!(
            text.metadata_update_entry(2, "abc", "beatoraja", "row-1", "title, artist"),
            "[DEBUG] #2 updated: abc (beatoraja, row_id=row-1), changed fields: [title, artist]"
        );
        assert_eq!(
            text.reauth_required(),
            "Your login session has expired. Please log in again."
        );
    }
}
