use std::path::Path;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::{Duration, SystemTime};

use serde::Serialize;
use tauri::{AppHandle, Manager};
use time::format_description::well_known::Rfc3339;

use crate::domain::config::{self, ClientConfig};

/// Prefix used for every daily disk log file. Retention scans match by this prefix.
pub const DISK_LOG_PREFIX: &str = "ojikbms-client-";

/// `LevelFilter as usize` for the disk log target. Mutated at runtime when the
/// `verbose_disk_logging` toggle changes, so the filter closure can pick up the
/// new threshold without rebuilding the logger.
static DISK_LOG_LEVEL: AtomicUsize = AtomicUsize::new(log::LevelFilter::Warn as usize);

const DEFAULT_RETAIN_DAYS: u64 = 14;

fn level_filter_to_usize(level: log::LevelFilter) -> usize {
    level as usize
}

fn usize_to_level_filter(value: usize) -> log::LevelFilter {
    match value {
        x if x == log::LevelFilter::Off as usize => log::LevelFilter::Off,
        x if x == log::LevelFilter::Error as usize => log::LevelFilter::Error,
        x if x == log::LevelFilter::Warn as usize => log::LevelFilter::Warn,
        x if x == log::LevelFilter::Info as usize => log::LevelFilter::Info,
        x if x == log::LevelFilter::Debug as usize => log::LevelFilter::Debug,
        _ => log::LevelFilter::Trace,
    }
}

pub fn set_verbose_disk_logging(verbose: bool) {
    let level = if verbose {
        log::LevelFilter::Debug
    } else {
        log::LevelFilter::Warn
    };
    DISK_LOG_LEVEL.store(level_filter_to_usize(level), Ordering::Relaxed);
}

pub fn passes_disk_filter(metadata: &log::Metadata) -> bool {
    let threshold = usize_to_level_filter(DISK_LOG_LEVEL.load(Ordering::Relaxed));
    metadata.level() <= threshold
}

/// Compute today's UTC date in `YYYY-MM-DD` form, used to suffix the active
/// disk log filename. The value is captured once at process start; long-running
/// sessions that cross midnight continue writing to the start-day file (a
/// deliberate trade-off for simplicity).
pub fn today_utc_yyyy_mm_dd() -> String {
    let now = time::OffsetDateTime::now_utc();
    format!(
        "{:04}-{:02}-{:02}",
        now.year(),
        u8::from(now.month()),
        now.day()
    )
}

pub fn current_log_filename() -> String {
    format!("{}{}", DISK_LOG_PREFIX, today_utc_yyyy_mm_dd())
}

/// Read the persisted ClientConfig and align the in-memory disk threshold with
/// it. Called from the main `setup` callback so the disk filter reflects the
/// user's last choice on every launch.
pub fn init_from_config(app: &AppHandle) {
    let verbose = config::load(app)
        .map(|cfg| cfg.verbose_disk_logging)
        .unwrap_or(false);
    set_verbose_disk_logging(verbose);
}

/// Best-effort retention sweep: remove any `ojikbms-client-*.log*` whose
/// mtime is older than `retain_days`. The active file is the only one with a
/// fresh mtime so it is naturally preserved. `sync_error_*.log` files do not
/// match the prefix and are kept regardless of age.
pub fn prune_old_logs(app: &AppHandle, retain_days: u64) {
    let Ok(log_dir) = app.path().app_log_dir() else {
        return;
    };
    let Ok(entries) = std::fs::read_dir(&log_dir) else {
        return;
    };
    let cutoff = match SystemTime::now().checked_sub(Duration::from_secs(retain_days * 86_400)) {
        Some(t) => t,
        None => return,
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let Some(name) = path.file_name().and_then(|s| s.to_str()) else {
            continue;
        };
        if !name.starts_with(DISK_LOG_PREFIX) {
            continue;
        }
        let modified = match entry.metadata().and_then(|m| m.modified()) {
            Ok(t) => t,
            Err(_) => continue,
        };
        if modified < cutoff {
            let _ = std::fs::remove_file(&path);
        }
    }
}

pub fn retain_days_default() -> u64 {
    DEFAULT_RETAIN_DAYS
}

/// Information that helps post-mortem analysis of a sync failure: app version,
/// OS, key path resolutions, and whether verbose logging was on. Secrets and
/// tokens are intentionally excluded.
#[derive(Debug, Clone, Serialize)]
pub struct EnvironmentSnapshot {
    pub captured_at: String,
    pub app_version: String,
    pub os: String,
    pub exe_path: Option<String>,
    pub config_dir: Option<String>,
    pub logs_dir: Option<String>,
    pub api_url: String,
    pub lr2_db_path: Option<String>,
    pub beatoraja_db_dir: Option<String>,
    pub beatoraja_songdata_db_path: Option<String>,
    pub debug_mode: bool,
    pub verbose_disk_logging: bool,
}

impl EnvironmentSnapshot {
    pub fn capture(app: &AppHandle, cfg: &ClientConfig) -> Self {
        let path = app.path();
        let logs_dir = path
            .app_log_dir()
            .ok()
            .map(|p| p.to_string_lossy().to_string());
        let config_dir = config::config_dir(app)
            .ok()
            .map(|p| p.to_string_lossy().to_string());
        let exe_path = std::env::current_exe()
            .ok()
            .map(|p| p.to_string_lossy().to_string());
        let captured_at = time::OffsetDateTime::now_utc()
            .format(&Rfc3339)
            .unwrap_or_else(|_| "1970-01-01T00:00:00Z".to_string());
        let pkg = app.package_info();
        Self {
            captured_at,
            app_version: pkg.version.to_string(),
            os: format!("{} {}", std::env::consts::OS, std::env::consts::ARCH),
            exe_path,
            config_dir,
            logs_dir,
            api_url: cfg.api_url.clone(),
            lr2_db_path: cfg.lr2_db_path.clone(),
            beatoraja_db_dir: cfg.beatoraja_db_dir.clone(),
            beatoraja_songdata_db_path: cfg.beatoraja_songdata_db_path.clone(),
            debug_mode: cfg.debug_mode,
            verbose_disk_logging: cfg.verbose_disk_logging,
        }
    }

    /// Render a human-readable `key : value` block (no secrets, fixed columns).
    pub fn render_text(&self) -> String {
        fn line(buf: &mut String, key: &str, value: &str) {
            buf.push_str(&format!("{key:<24}: {value}\n"));
        }
        let mut out = String::new();
        line(&mut out, "captured_at", &self.captured_at);
        line(&mut out, "app_version", &self.app_version);
        line(&mut out, "os", &self.os);
        line(
            &mut out,
            "exe_path",
            self.exe_path.as_deref().unwrap_or("—"),
        );
        line(
            &mut out,
            "config_dir",
            self.config_dir.as_deref().unwrap_or("—"),
        );
        line(
            &mut out,
            "logs_dir",
            self.logs_dir.as_deref().unwrap_or("—"),
        );
        line(&mut out, "api_url", &self.api_url);
        line(
            &mut out,
            "lr2_db_path",
            self.lr2_db_path.as_deref().unwrap_or("—"),
        );
        line(
            &mut out,
            "beatoraja_db_dir",
            self.beatoraja_db_dir.as_deref().unwrap_or("—"),
        );
        line(
            &mut out,
            "beatoraja_songdata_db_path",
            self.beatoraja_songdata_db_path.as_deref().unwrap_or("—"),
        );
        line(&mut out, "debug_mode", &self.debug_mode.to_string());
        line(
            &mut out,
            "verbose_disk_logging",
            &self.verbose_disk_logging.to_string(),
        );
        out
    }
}

/// Path-existence flags for every configured DB path. Useful in error reports
/// because "the path is set but the file is gone" is a common failure mode.
#[derive(Debug, Clone, Serialize)]
pub struct PathChecks {
    pub lr2_db_exists: Option<bool>,
    pub beatoraja_db_dir_exists: Option<bool>,
    pub beatoraja_score_db_exists: Option<bool>,
    pub beatoraja_scorelog_db_exists: Option<bool>,
    pub beatoraja_songdata_db_exists: Option<bool>,
}

impl PathChecks {
    pub fn capture(cfg: &ClientConfig) -> Self {
        let lr2 = cfg.lr2_db_path.as_deref().map(|p| Path::new(p).exists());
        let bea_dir = cfg
            .beatoraja_db_dir
            .as_deref()
            .map(|p| Path::new(p).exists());
        let bea_score = cfg
            .beatoraja_db_dir
            .as_deref()
            .map(|p| Path::new(p).join("score.db").exists());
        let bea_scorelog = cfg
            .beatoraja_db_dir
            .as_deref()
            .map(|p| Path::new(p).join("scorelog.db").exists());
        let bea_songdata = cfg
            .beatoraja_songdata_db_path
            .as_deref()
            .map(|p| Path::new(p).exists());
        Self {
            lr2_db_exists: lr2,
            beatoraja_db_dir_exists: bea_dir,
            beatoraja_score_db_exists: bea_score,
            beatoraja_scorelog_db_exists: bea_scorelog,
            beatoraja_songdata_db_exists: bea_songdata,
        }
    }

    pub fn render_text(&self) -> String {
        fn fmt_check(value: Option<bool>) -> &'static str {
            match value {
                None => "(not set)",
                Some(true) => "exists",
                Some(false) => "MISSING",
            }
        }
        let mut out = String::new();
        out.push_str(&format!(
            "{:<24}: {}\n",
            "lr2_db_path",
            fmt_check(self.lr2_db_exists)
        ));
        out.push_str(&format!(
            "{:<24}: {}\n",
            "beatoraja_db_dir",
            fmt_check(self.beatoraja_db_dir_exists)
        ));
        out.push_str(&format!(
            "{:<24}: {}\n",
            "beatoraja/score.db",
            fmt_check(self.beatoraja_score_db_exists)
        ));
        out.push_str(&format!(
            "{:<24}: {}\n",
            "beatoraja/scorelog.db",
            fmt_check(self.beatoraja_scorelog_db_exists)
        ));
        out.push_str(&format!(
            "{:<24}: {}\n",
            "beatoraja_songdata_db",
            fmt_check(self.beatoraja_songdata_db_exists)
        ));
        out
    }
}
