use std::collections::HashSet;
use std::path::Path;

use anyhow::anyhow;
use rusqlite::Row;
use serde_json::json;

use crate::domain::fumen_detail::{FumenDetailItem, SongInfoEntry};
use crate::domain::lr2::{
    clean_hash, get_columns, get_f64, get_i64, get_string, join_text, none_if_zero, open_readonly,
    resolve_col, table_exists, unix_to_rfc3339,
};
use crate::domain::sync_api::{PlayerStats, ScoreItem, SongHash};

#[derive(Debug, Default, Clone)]
pub struct ParseStats {
    pub db_total: usize,
    pub query_result_count: usize,
    pub skipped_hash: usize,
    pub skipped_lr2: usize,
    pub parsed_courses: usize,
    pub parsed: usize,
}

impl ParseStats {
    pub fn skipped_filter(&self) -> usize {
        self.db_total.saturating_sub(self.query_result_count)
    }
}

#[derive(Debug, Default, Clone)]
pub struct ScoreLogStats {
    pub total_queried: usize,
    pub skipped_hash: usize,
    pub skipped_duplicate: usize,
    pub parsed: usize,
    pub parsed_courses: usize,
}

pub fn parse_scores(
    data_dir: &str,
) -> anyhow::Result<(Vec<ScoreItem>, Vec<ScoreItem>, ParseStats)> {
    let score_db = Path::new(data_dir).join("score.db");
    if !score_db.exists() {
        return Err(anyhow!(
            "Beatoraja score.db not found: {}",
            score_db.display()
        ));
    }

    let conn = open_readonly(&score_db)?;
    let available = get_columns(&conn, "score")?;
    if available.is_empty() {
        return Err(anyhow!("Table 'score' not found in {}", score_db.display()));
    }
    if !available.contains("sha256") {
        return Err(anyhow!(
            "Cannot find sha256 column in Beatoraja score table"
        ));
    }

    let cols = BeaCols::new(&available);
    let mut select_cols = vec!["sha256".to_string(), "clear".to_string()];
    if available.contains("mode") {
        select_cols.push("mode".to_string());
    }
    if available.contains("scorehash") {
        select_cols.push("scorehash".to_string());
    }
    for col in cols.iter().flatten() {
        if !select_cols.contains(col) {
            select_cols.push(col.clone());
        }
    }

    let mut where_parts = Vec::new();
    let mut params = Vec::new();
    if available.contains("mode") {
        where_parts.push("(mode = ? OR length(sha256) > 64)".to_string());
        params.push(0_i64);
    }
    if available.contains("player") {
        where_parts.push("player = ?".to_string());
        params.push(0_i64);
    }
    if let Some(playcount) = &cols.playcount {
        where_parts.push(format!("{playcount} > 0"));
    }
    let where_clause = if where_parts.is_empty() {
        String::new()
    } else {
        format!("WHERE {}", where_parts.join(" AND "))
    };

    let db_total =
        conn.query_row("SELECT COUNT(*) FROM score", [], |row| row.get::<_, i64>(0))? as usize;
    let sql = format!(
        "SELECT {} FROM score {}",
        select_cols.join(", "),
        where_clause
    );
    let mut stmt = conn.prepare(&sql)?;
    let mut rows = stmt.query(rusqlite::params_from_iter(params))?;

    let mut scores = Vec::new();
    let mut courses = Vec::new();
    let mut stats = ParseStats {
        db_total,
        ..ParseStats::default()
    };

    while let Some(row) = rows.next()? {
        stats.query_result_count += 1;
        let sha256 = clean_hash(get_string(row, "sha256").unwrap_or_default());
        if sha256.is_empty() {
            stats.skipped_hash += 1;
            continue;
        }

        let raw_scorehash = get_string(row, "scorehash");
        if raw_scorehash
            .as_deref()
            .is_some_and(|value| value.trim().eq_ignore_ascii_case("LR2"))
        {
            stats.skipped_lr2 += 1;
            continue;
        }

        if sha256.len() > 64 {
            let song_sha256s = sha256
                .as_bytes()
                .chunks(64)
                .filter_map(|chunk| {
                    (chunk.len() == 64).then(|| String::from_utf8_lossy(chunk).to_string())
                })
                .collect::<Vec<_>>();
            if song_sha256s.is_empty() {
                stats.skipped_hash += 1;
                continue;
            }
            courses.push(build_item(row, &cols, Some(sha256), None, song_sha256s));
            stats.parsed_courses += 1;
            continue;
        }

        if sha256.len() != 64 {
            stats.skipped_hash += 1;
            continue;
        }

        scores.push(build_item(row, &cols, None, Some(sha256), Vec::new()));
    }

    stats.parsed = scores.len();
    Ok((scores, courses, stats))
}

pub fn parse_player_stats(data_dir: &str) -> Option<PlayerStats> {
    let conn = open_readonly(&Path::new(data_dir).join("score.db")).ok()?;
    let columns = get_columns(&conn, "player").ok()?;
    if columns.is_empty() {
        return None;
    }

    let judgments = [
        ("epg", resolve_col(&columns, &["epg", "ep"])),
        ("lpg", resolve_col(&columns, &["lpg", "lp"])),
        ("egr", resolve_col(&columns, &["egr", "eg"])),
        ("lgr", resolve_col(&columns, &["lgr", "lg"])),
        ("egd", resolve_col(&columns, &["egd"])),
        ("lgd", resolve_col(&columns, &["lgd"])),
        ("ebd", resolve_col(&columns, &["ebd"])),
        ("lbd", resolve_col(&columns, &["lbd"])),
        ("epr", resolve_col(&columns, &["epr"])),
        ("lpr", resolve_col(&columns, &["lpr"])),
        ("ems", resolve_col(&columns, &["ems"])),
        ("lms", resolve_col(&columns, &["lms"])),
    ];
    if judgments.iter().all(|(_, col)| col.is_none()) {
        return None;
    }

    let date_col = resolve_col(&columns, &["date", "timestamp"]);
    let playcount = resolve_col(&columns, &["playcount", "play_count"]);
    let clearcount = resolve_col(&columns, &["clear", "clearcount", "clear_count"]);
    let playtime = resolve_col(&columns, &["playtime", "play_time"]);
    let mut select_cols = Vec::new();
    for col in judgments
        .iter()
        .filter_map(|(_, col)| col.as_ref())
        .chain([&playcount, &clearcount, &playtime].into_iter().flatten())
    {
        if !select_cols.contains(col) {
            select_cols.push(col.clone());
        }
    }

    let mut params = Vec::new();
    let where_clause = if columns.contains("player") {
        params.push(0_i64);
        "WHERE player = ?"
    } else {
        ""
    };
    let order_clause = date_col
        .as_ref()
        .map(|col| format!("ORDER BY {col} DESC LIMIT 1"))
        .unwrap_or_else(|| "LIMIT 1".to_string());
    let sql = format!(
        "SELECT {} FROM player {where_clause} {order_clause}",
        select_cols.join(", ")
    );
    let mut stmt = conn.prepare(&sql).ok()?;

    stmt.query_row(rusqlite::params_from_iter(params), |row| {
        let mut judgment_map = serde_json::Map::new();
        for (key, col) in judgments {
            if let Some(col) = col {
                judgment_map.insert(
                    key.to_string(),
                    json!(get_i64(row, Some(&col)).unwrap_or(0)),
                );
            }
        }
        Ok(PlayerStats {
            client_type: "beatoraja".to_string(),
            playcount: get_i64(row, playcount.as_deref()),
            clearcount: get_i64(row, clearcount.as_deref()),
            playtime: get_i64(row, playtime.as_deref()),
            judgments: Some(serde_json::Value::Object(judgment_map)),
        })
    })
    .ok()
}

pub fn parse_score_log(
    data_dir: &str,
    min_recorded_at: Option<i64>,
) -> (Vec<ScoreItem>, ScoreLogStats) {
    let data_path = Path::new(data_dir);
    let scorelog_db = data_path.join("scorelog.db");
    if !scorelog_db.exists() {
        return (Vec::new(), ScoreLogStats::default());
    }

    let duplicate_pairs = score_db_pairs(data_path);
    let Ok(conn) = open_readonly(&scorelog_db) else {
        return (Vec::new(), ScoreLogStats::default());
    };
    let Ok(available) = get_columns(&conn, "scorelog") else {
        return (Vec::new(), ScoreLogStats::default());
    };
    if available.is_empty() || !available.contains("sha256") {
        return (Vec::new(), ScoreLogStats::default());
    }

    let has_mode = available.contains("mode");
    let has_player = available.contains("player");
    let score_col = if available.contains("score") {
        "score"
    } else {
        "exscore"
    };
    let combo_col = if available.contains("combo") {
        "combo"
    } else {
        "maxcombo"
    };
    let mut params = Vec::new();
    let mut where_parts = Vec::new();
    if has_mode {
        where_parts.push("(mode = ? OR length(sha256) > 64)".to_string());
        params.push(0_i64);
    }
    if has_player {
        where_parts.push("player = ?".to_string());
        params.push(0_i64);
    }
    if let Some(min_recorded_at) = min_recorded_at {
        where_parts.push("date >= ?".to_string());
        params.push(min_recorded_at);
    }
    let where_clause = if where_parts.is_empty() {
        String::new()
    } else {
        format!("WHERE {}", where_parts.join(" AND "))
    };
    let sql = format!(
        "SELECT sha256, clear, {score_col}, {combo_col}, minbp, date FROM scorelog {where_clause} ORDER BY date ASC"
    );

    let mut history = Vec::new();
    let mut stats = ScoreLogStats::default();
    let Ok(mut stmt) = conn.prepare(&sql) else {
        return (history, stats);
    };
    let Ok(mut rows) = stmt.query(rusqlite::params_from_iter(params)) else {
        return (history, stats);
    };

    while let Ok(Some(row)) = rows.next() {
        stats.total_queried += 1;
        let sha256 = clean_hash(get_string(row, "sha256").unwrap_or_default());
        if sha256.len() < 64 {
            stats.skipped_hash += 1;
            continue;
        }
        let date = get_i64(row, Some("date"));
        if date.is_some_and(|date| duplicate_pairs.contains(&(sha256.clone(), date))) {
            stats.skipped_duplicate += 1;
            continue;
        }

        let exscore = get_i64(row, Some(score_col));
        let clear = normalize_max_clear_type(
            beatoraja_clear_type(get_i64(row, Some("clear")).unwrap_or(0)),
            exscore,
            None,
        );
        if sha256.len() > 64 {
            history.push(ScoreItem {
                fumen_hash_others: Some(sha256),
                client_type: "beatoraja".to_string(),
                scorehash: None,
                clear_type: Some(clear),
                exscore,
                max_combo: get_i64(row, Some(combo_col)),
                min_bp: get_i64(row, Some("minbp")),
                recorded_at: date.and_then(unix_to_rfc3339),
                fumen_sha256: None,
                fumen_md5: None,
                notes: None,
                judgments: None,
                options: None,
                play_count: None,
                clear_count: None,
                song_hashes: Vec::new(),
            });
            stats.parsed_courses += 1;
        } else {
            history.push(ScoreItem {
                fumen_sha256: Some(sha256),
                client_type: "beatoraja".to_string(),
                scorehash: None,
                clear_type: Some(clear),
                exscore,
                max_combo: get_i64(row, Some(combo_col)),
                min_bp: get_i64(row, Some("minbp")),
                recorded_at: date.and_then(unix_to_rfc3339),
                fumen_md5: None,
                fumen_hash_others: None,
                notes: None,
                judgments: None,
                options: None,
                play_count: None,
                clear_count: None,
                song_hashes: Vec::new(),
            });
            stats.parsed += 1;
        }
    }

    (history, stats)
}

pub fn parse_songdata(db_path: &str) -> Vec<FumenDetailItem> {
    let Ok(conn) = open_readonly(Path::new(db_path)) else {
        return Vec::new();
    };
    let table = ["song", "musics", "music"]
        .into_iter()
        .find(|table| table_exists(&conn, table).unwrap_or(false));
    let Some(table) = table else {
        return Vec::new();
    };
    let Ok(columns) = get_columns(&conn, table) else {
        return Vec::new();
    };
    if !columns.contains("md5") || !columns.contains("sha256") {
        return Vec::new();
    }
    let wanted = [
        "sha256",
        "md5",
        "title",
        "subtitle",
        "artist",
        "subartist",
        "minbpm",
        "maxbpm",
        "notes",
        "length",
    ];
    let select_cols = wanted
        .into_iter()
        .filter(|col| columns.contains(*col))
        .collect::<Vec<_>>();
    let sql = format!(
        "SELECT {} FROM {table} WHERE sha256 != '' AND sha256 IS NOT NULL AND md5 != '' AND md5 IS NOT NULL",
        select_cols.join(", ")
    );

    let mut items = Vec::new();
    let Ok(mut stmt) = conn.prepare(&sql) else {
        return items;
    };
    let Ok(mut rows) = stmt.query([]) else {
        return items;
    };
    while let Ok(Some(row)) = rows.next() {
        let sha256 = clean_hash(get_string(row, "sha256").unwrap_or_default()).to_lowercase();
        let md5 = clean_hash(get_string(row, "md5").unwrap_or_default()).to_lowercase();
        if sha256.len() != 64 || md5.len() != 32 {
            continue;
        }
        items.push(FumenDetailItem {
            sha256: Some(sha256),
            md5: Some(md5),
            title: join_text(get_string(row, "title"), get_string(row, "subtitle")),
            artist: join_text(get_string(row, "artist"), get_string(row, "subartist")),
            bpm_min: get_f64(row, Some("minbpm")),
            bpm_max: get_f64(row, Some("maxbpm")),
            notes_total: get_i64(row, Some("notes")),
            length: get_i64(row, Some("length")),
            client_type: "beatoraja".to_string(),
            ..FumenDetailItem::default()
        });
    }
    items
}

pub fn parse_songinfo(db_path: &str) -> std::collections::HashMap<String, SongInfoEntry> {
    let mut result = std::collections::HashMap::new();
    let Ok(conn) = open_readonly(Path::new(db_path)) else {
        return result;
    };
    if !table_exists(&conn, "information").unwrap_or(false) {
        return result;
    }
    let Ok(columns) = get_columns(&conn, "information") else {
        return result;
    };
    if !columns.contains("sha256") {
        return result;
    }
    let wanted = ["sha256", "n", "ln", "s", "ls", "total", "mainbpm"];
    let select_cols = wanted
        .into_iter()
        .filter(|col| columns.contains(*col))
        .collect::<Vec<_>>();
    let sql = format!(
        "SELECT {} FROM information WHERE sha256 IS NOT NULL AND sha256 != ''",
        select_cols.join(", ")
    );
    let Ok(mut stmt) = conn.prepare(&sql) else {
        return result;
    };
    let Ok(mut rows) = stmt.query([]) else {
        return result;
    };
    while let Ok(Some(row)) = rows.next() {
        let sha256 = clean_hash(get_string(row, "sha256").unwrap_or_default()).to_lowercase();
        if sha256.len() != 64 {
            continue;
        }
        result.insert(
            sha256,
            SongInfoEntry {
                notes_n: get_i64(row, Some("n")),
                notes_ln: get_i64(row, Some("ln")),
                notes_s: get_i64(row, Some("s")),
                notes_ls: get_i64(row, Some("ls")),
                total: get_i64(row, Some("total")),
                bpm_main: get_f64(row, Some("mainbpm")),
            },
        );
    }
    result
}

#[derive(Debug)]
struct BeaCols {
    ep: Option<String>,
    lp: Option<String>,
    eg: Option<String>,
    lg: Option<String>,
    egd: Option<String>,
    lgd: Option<String>,
    ebd: Option<String>,
    lbd: Option<String>,
    epr: Option<String>,
    lpr: Option<String>,
    ems: Option<String>,
    lms: Option<String>,
    maxcombo: Option<String>,
    minbp: Option<String>,
    playcount: Option<String>,
    exscore: Option<String>,
    date: Option<String>,
    notes: Option<String>,
    clearcount: Option<String>,
    arrangement: Option<String>,
    seed: Option<String>,
    random_raw: Option<String>,
}

impl BeaCols {
    fn new(columns: &HashSet<String>) -> Self {
        Self {
            ep: resolve_col(
                columns,
                &["ep", "epg", "eperfect", "exactperfect", "pgreat"],
            ),
            lp: resolve_col(columns, &["lp", "lpg", "lperfect", "lateperfect"]),
            eg: resolve_col(columns, &["eg", "egr", "egreat", "earlygreat"]),
            lg: resolve_col(columns, &["lg", "lgr", "lgreat", "lategreat"]),
            egd: resolve_col(columns, &["egd", "egood", "earlygood"]),
            lgd: resolve_col(columns, &["lgd", "lgood", "lategood"]),
            ebd: resolve_col(columns, &["ebd", "ebad", "earlybad"]),
            lbd: resolve_col(columns, &["lbd", "lbad", "latebad"]),
            epr: resolve_col(columns, &["epr", "epoor", "earlypoor"]),
            lpr: resolve_col(columns, &["lpr", "lpoor", "latepoor"]),
            ems: resolve_col(columns, &["ems", "emiss", "miss"]),
            lms: resolve_col(columns, &["lms"]),
            maxcombo: resolve_col(columns, &["maxcombo", "max_combo", "combo"]),
            minbp: resolve_col(columns, &["minbp", "min_bp"]),
            playcount: resolve_col(columns, &["playcount", "play_count"]),
            exscore: resolve_col(columns, &["exscore", "ex_score", "score"]),
            date: resolve_col(columns, &["date", "timestamp", "last_play"]),
            notes: resolve_col(columns, &["notes", "total_notes", "totalnotes"]),
            clearcount: resolve_col(columns, &["clearcount", "clear_count"]),
            arrangement: resolve_col(columns, &["option"]),
            seed: resolve_col(columns, &["seed"]),
            random_raw: resolve_col(columns, &["random"]),
        }
    }

    fn iter(&self) -> impl Iterator<Item = &Option<String>> {
        [
            &self.ep,
            &self.lp,
            &self.eg,
            &self.lg,
            &self.egd,
            &self.lgd,
            &self.ebd,
            &self.lbd,
            &self.epr,
            &self.lpr,
            &self.ems,
            &self.lms,
            &self.maxcombo,
            &self.minbp,
            &self.playcount,
            &self.exscore,
            &self.date,
            &self.notes,
            &self.clearcount,
            &self.arrangement,
            &self.seed,
            &self.random_raw,
        ]
        .into_iter()
    }
}

fn build_item(
    row: &Row<'_>,
    cols: &BeaCols,
    fumen_hash_others: Option<String>,
    fumen_sha256: Option<String>,
    song_sha256s: Vec<String>,
) -> ScoreItem {
    let judgments = json!({
        "epg": get_i64(row, cols.ep.as_deref()).unwrap_or(0),
        "lpg": get_i64(row, cols.lp.as_deref()).unwrap_or(0),
        "egr": get_i64(row, cols.eg.as_deref()).unwrap_or(0),
        "lgr": get_i64(row, cols.lg.as_deref()).unwrap_or(0),
        "egd": get_i64(row, cols.egd.as_deref()).unwrap_or(0),
        "lgd": get_i64(row, cols.lgd.as_deref()).unwrap_or(0),
        "ebd": get_i64(row, cols.ebd.as_deref()).unwrap_or(0),
        "lbd": get_i64(row, cols.lbd.as_deref()).unwrap_or(0),
        "epr": get_i64(row, cols.epr.as_deref()).unwrap_or(0),
        "lpr": get_i64(row, cols.lpr.as_deref()).unwrap_or(0),
        "ems": get_i64(row, cols.ems.as_deref()).unwrap_or(0),
        "lms": get_i64(row, cols.lms.as_deref()).unwrap_or(0),
    });
    let notes = none_if_zero(get_i64(row, cols.notes.as_deref()).unwrap_or(0));
    let exscore = beatoraja_exscore(&judgments);
    let clear_type = normalize_max_clear_type(
        beatoraja_clear_type(get_i64(row, Some("clear")).unwrap_or(0)),
        Some(exscore),
        notes,
    );
    let row_mode = get_i64(row, Some("mode")).unwrap_or(0);
    let scorehash = get_string(row, "scorehash")
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty() && !s.eq_ignore_ascii_case("LR2"));

    ScoreItem {
        scorehash,
        fumen_sha256,
        fumen_md5: None,
        fumen_hash_others,
        client_type: "beatoraja".to_string(),
        clear_type: Some(clear_type),
        notes,
        exscore: None,
        max_combo: none_if_zero(get_i64(row, cols.maxcombo.as_deref()).unwrap_or(0)),
        min_bp: get_i64(row, cols.minbp.as_deref()),
        judgments: Some(judgments),
        options: Some(json!({
            "mode": row_mode,
            "option": get_i64(row, cols.arrangement.as_deref()).unwrap_or(0),
            "seed": get_i64(row, cols.seed.as_deref()).unwrap_or(-1),
            "random": get_i64(row, cols.random_raw.as_deref()).unwrap_or(0),
        })),
        play_count: Some(get_i64(row, cols.playcount.as_deref()).unwrap_or(0)),
        clear_count: Some(get_i64(row, cols.clearcount.as_deref()).unwrap_or(0)),
        recorded_at: get_i64(row, cols.date.as_deref()).and_then(unix_to_rfc3339),
        song_hashes: song_sha256s
            .into_iter()
            .map(|sha256| SongHash {
                song_md5: None,
                song_sha256: Some(sha256),
            })
            .collect(),
    }
}

fn score_db_pairs(data_path: &Path) -> HashSet<(String, i64)> {
    let mut pairs = HashSet::new();
    let score_db = data_path.join("score.db");
    let Ok(conn) = open_readonly(&score_db) else {
        return pairs;
    };
    let Ok(columns) = get_columns(&conn, "score") else {
        return pairs;
    };
    if !columns.contains("sha256") || !columns.contains("date") {
        return pairs;
    }
    let mut params = Vec::new();
    let mut where_parts = Vec::new();
    if columns.contains("mode") {
        where_parts.push("(mode = ? OR length(sha256) > 64)".to_string());
        params.push(0_i64);
    }
    if columns.contains("player") {
        where_parts.push("player = ?".to_string());
        params.push(0_i64);
    }
    let where_clause = if where_parts.is_empty() {
        String::new()
    } else {
        format!("WHERE {}", where_parts.join(" AND "))
    };
    let sql = format!("SELECT sha256, date FROM score {where_clause}");
    let Ok(mut stmt) = conn.prepare(&sql) else {
        return pairs;
    };
    let Ok(mut rows) = stmt.query(rusqlite::params_from_iter(params)) else {
        return pairs;
    };
    while let Ok(Some(row)) = rows.next() {
        if let (Some(sha256), Some(date)) = (get_string(row, "sha256"), get_i64(row, Some("date")))
        {
            pairs.insert((sha256.trim().to_string(), date));
        }
    }
    pairs
}

fn beatoraja_clear_type(value: i64) -> i64 {
    match value {
        1 => 1,
        2 => 1,
        3 => 2,
        4 => 3,
        5 => 4,
        6 => 5,
        7 => 6,
        8 => 7,
        9 => 8,
        10 => 9,
        _ => 0,
    }
}

fn beatoraja_exscore(judgments: &serde_json::Value) -> i64 {
    (judgments["epg"].as_i64().unwrap_or(0) + judgments["lpg"].as_i64().unwrap_or(0)) * 2
        + judgments["egr"].as_i64().unwrap_or(0)
        + judgments["lgr"].as_i64().unwrap_or(0)
}

fn normalize_max_clear_type(clear_type: i64, exscore: Option<i64>, notes: Option<i64>) -> i64 {
    if clear_type != 9 {
        return clear_type;
    }
    if exscore == Some(0) {
        return 7;
    }
    if let (Some(exscore), Some(notes)) = (exscore, notes) {
        if exscore == notes * 2 {
            9
        } else {
            8
        }
    } else {
        clear_type
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::Connection;
    use std::fs;
    use std::path::{Path, PathBuf};

    fn temp_dir(name: &str) -> PathBuf {
        let mut path = std::env::temp_dir();
        path.push(format!(
            "ojik_bms_bea_{name}_{}_{}",
            std::process::id(),
            time::OffsetDateTime::now_utc().unix_timestamp_nanos()
        ));
        fs::create_dir_all(&path).expect("create beatoraja temp dir");
        path
    }

    fn create_score_db(dir: &Path) {
        let conn = Connection::open(dir.join("score.db")).expect("create beatoraja score db");
        conn.execute_batch(
            r#"
            CREATE TABLE score (
                sha256 TEXT NOT NULL,
                mode INTEGER NOT NULL,
                player INTEGER NOT NULL,
                clear INTEGER,
                ep INTEGER,
                lp INTEGER,
                eg INTEGER,
                lg INTEGER,
                egd INTEGER,
                lgd INTEGER,
                ebd INTEGER,
                lbd INTEGER,
                epr INTEGER,
                lpr INTEGER,
                ems INTEGER,
                lms INTEGER,
                maxcombo INTEGER,
                minbp INTEGER,
                playcount INTEGER,
                clearcount INTEGER,
                exscore INTEGER,
                option INTEGER,
                seed INTEGER,
                random INTEGER,
                date INTEGER,
                notes INTEGER,
                scorehash TEXT
            );
            "#,
        )
        .expect("create score table");
    }

    #[allow(clippy::too_many_arguments)]
    fn insert_score(
        dir: &Path,
        sha256: &str,
        mode: i64,
        player: i64,
        clear: i64,
        ep: i64,
        lp: i64,
        eg: i64,
        lg: i64,
        maxcombo: i64,
        minbp: i64,
        playcount: i64,
        clearcount: i64,
        date: i64,
        notes: i64,
        scorehash: Option<&str>,
    ) {
        let conn = Connection::open(dir.join("score.db")).expect("open beatoraja score db");
        conn.execute(
            r#"
            INSERT INTO score VALUES (
                ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8,
                50, 50, 10, 10, 5, 5, 2, 1,
                ?9, ?10, ?11, ?12, 1400, 7, 1234, 6,
                ?13, ?14, ?15
            )
            "#,
            (
                sha256, mode, player, clear, ep, lp, eg, lg, maxcombo, minbp, playcount,
                clearcount, date, notes, scorehash,
            ),
        )
        .expect("insert beatoraja score row");
    }

    fn create_scorelog_db(dir: &Path) {
        let conn = Connection::open(dir.join("scorelog.db")).expect("create scorelog db");
        conn.execute_batch(
            r#"
            CREATE TABLE scorelog (
                sha256 TEXT NOT NULL,
                mode INTEGER NOT NULL,
                player INTEGER NOT NULL,
                clear INTEGER,
                oldclear INTEGER,
                score INTEGER,
                oldscore INTEGER,
                combo INTEGER,
                oldcombo INTEGER,
                minbp INTEGER,
                oldminbp INTEGER,
                date INTEGER
            );
            "#,
        )
        .expect("create scorelog table");
    }

    fn insert_scorelog(
        dir: &Path,
        sha256: &str,
        mode: i64,
        player: i64,
        clear: i64,
        score: i64,
        combo: i64,
        minbp: i64,
        date: i64,
    ) {
        let conn = Connection::open(dir.join("scorelog.db")).expect("open scorelog db");
        conn.execute(
            r#"
            INSERT INTO scorelog VALUES (?1, ?2, ?3, ?4, 0, ?5, 0, ?6, 0, ?7, 0, ?8)
            "#,
            (sha256, mode, player, clear, score, combo, minbp, date),
        )
        .expect("insert scorelog row");
    }

    #[test]
    fn parses_basic_score_notes_and_lr2_import_skip() {
        let dir = temp_dir("basic");
        create_score_db(&dir);
        insert_score(
            &dir,
            &("c".repeat(64)),
            0,
            0,
            3,
            500,
            500,
            200,
            200,
            1000,
            3,
            15,
            10,
            1700000000,
            1000,
            None,
        );
        insert_score(
            &dir,
            &("l".repeat(64)),
            0,
            0,
            3,
            1,
            1,
            0,
            0,
            2,
            0,
            1,
            1,
            1700000001,
            2,
            Some("LR2"),
        );
        insert_score(
            &dir,
            &("d".repeat(64)),
            1,
            0,
            3,
            1,
            1,
            0,
            0,
            2,
            0,
            1,
            1,
            1700000002,
            2,
            Some("dp"),
        );

        let (scores, courses, stats) =
            parse_scores(dir.to_str().unwrap()).expect("parse beatoraja scores");

        assert_eq!(scores.len(), 1);
        assert!(courses.is_empty());
        assert_eq!(stats.db_total, 3);
        assert_eq!(stats.query_result_count, 2);
        assert_eq!(stats.skipped_lr2, 1);
        assert_eq!(stats.parsed, 1);
        let score = &scores[0];
        let expected_sha256 = "c".repeat(64);
        assert_eq!(
            score.fumen_sha256.as_deref(),
            Some(expected_sha256.as_str())
        );
        assert_eq!(score.client_type, "beatoraja");
        assert_eq!(score.clear_type, Some(2));
        assert_eq!(score.notes, Some(1000));
        assert_eq!(score.max_combo, Some(1000));
        assert_eq!(score.min_bp, Some(3));
        assert_eq!(score.play_count, Some(15));
        assert_eq!(score.judgments.as_ref().unwrap()["epg"], 500);

        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn includes_nonstandard_mode_course_and_extracts_sha256_chunks() {
        let dir = temp_dir("course");
        create_score_db(&dir);
        insert_score(
            &dir,
            &("c".repeat(64)),
            0,
            0,
            3,
            1,
            1,
            0,
            0,
            2,
            0,
            1,
            1,
            1700000000,
            2,
            None,
        );
        let course_hash = format!(
            "{}{}{}{}",
            "d".repeat(64),
            "e".repeat(64),
            "f".repeat(64),
            "g".repeat(64)
        );
        insert_score(
            &dir,
            &course_hash,
            10000,
            0,
            5,
            10,
            10,
            5,
            5,
            399,
            676,
            17,
            1,
            1755002698,
            12966,
            Some("course-scorehash"),
        );
        insert_score(
            &dir,
            &("h".repeat(64)),
            1,
            0,
            7,
            1,
            1,
            0,
            0,
            2,
            0,
            1,
            1,
            1700000002,
            2,
            Some("dp"),
        );

        let (scores, courses, stats) =
            parse_scores(dir.to_str().unwrap()).expect("parse beatoraja scores");

        assert_eq!(scores.len(), 1);
        assert_eq!(courses.len(), 1);
        assert_eq!(stats.db_total, 3);
        assert_eq!(stats.query_result_count, 2);
        assert_eq!(stats.parsed_courses, 1);
        let course = &courses[0];
        assert_eq!(
            course.fumen_hash_others.as_deref(),
            Some(course_hash.as_str())
        );
        assert_eq!(course.scorehash.as_deref(), Some("course-scorehash"));
        assert_eq!(course.notes, Some(12966));
        assert_eq!(course.min_bp, Some(676));
        assert_eq!(course.play_count, Some(17));
        assert_eq!(course.options.as_ref().unwrap()["mode"], 10000);
        assert_eq!(
            course
                .song_hashes
                .iter()
                .map(|hash| hash.song_sha256.as_deref().unwrap().to_string())
                .collect::<Vec<_>>(),
            vec![
                "d".repeat(64),
                "e".repeat(64),
                "f".repeat(64),
                "g".repeat(64)
            ]
        );

        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn scorelog_includes_courses_and_skips_current_best_duplicates() {
        let dir = temp_dir("scorelog");
        create_score_db(&dir);
        create_scorelog_db(&dir);
        let duplicate_course = format!("{}{}", "o".repeat(64), "p".repeat(64));
        insert_score(
            &dir,
            &duplicate_course,
            10000,
            0,
            5,
            10,
            10,
            5,
            5,
            399,
            676,
            17,
            1,
            1755002698,
            12966,
            Some("duplicate-course"),
        );
        insert_scorelog(
            &dir,
            &duplicate_course,
            10000,
            0,
            5,
            12966,
            399,
            676,
            1755002698,
        );
        let history_course = format!("{}{}", "i".repeat(64), "j".repeat(64));
        insert_scorelog(&dir, &history_course, 10000, 0, 5, 2222, 333, 4, 1755002700);
        insert_scorelog(&dir, &("m".repeat(64)), 0, 0, 4, 1500, 900, 10, 1700000001);
        insert_scorelog(&dir, &("n".repeat(64)), 1, 0, 7, 1800, 1200, 2, 1700000002);

        let (history, stats) = parse_score_log(dir.to_str().unwrap(), None);

        assert_eq!(history.len(), 2);
        assert_eq!(stats.total_queried, 3);
        assert_eq!(stats.skipped_duplicate, 1);
        assert_eq!(stats.parsed, 1);
        assert_eq!(stats.parsed_courses, 1);
        let course = history
            .iter()
            .find(|item| item.fumen_hash_others.is_some())
            .expect("course scorelog item");
        assert_eq!(
            course.fumen_hash_others.as_deref(),
            Some(history_course.as_str())
        );
        assert_eq!(course.exscore, Some(2222));
        assert_eq!(course.max_combo, Some(333));
        assert_eq!(course.min_bp, Some(4));

        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn scorelog_can_filter_old_rows_for_quick_sync() {
        let dir = temp_dir("scorelog_since");
        create_scorelog_db(&dir);
        insert_scorelog(&dir, &("a".repeat(64)), 0, 0, 4, 1500, 900, 10, 1700000001);
        insert_scorelog(&dir, &("b".repeat(64)), 0, 0, 7, 1800, 1200, 2, 1700000002);

        let (history, stats) = parse_score_log(dir.to_str().unwrap(), Some(1700000002));

        assert_eq!(history.len(), 1);
        assert_eq!(stats.total_queried, 1);
        assert_eq!(
            history[0].fumen_sha256.as_deref(),
            Some("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        );

        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn downgrades_impossible_max_records_like_python_client() {
        let dir = temp_dir("max");
        create_score_db(&dir);
        insert_score(
            &dir,
            &("z".repeat(64)),
            0,
            0,
            10,
            0,
            0,
            0,
            0,
            0,
            0,
            1,
            1,
            1700000001,
            1000,
            Some("zero-max"),
        );
        insert_score(
            &dir,
            &("y".repeat(64)),
            0,
            0,
            10,
            999,
            0,
            0,
            0,
            999,
            0,
            1,
            1,
            1700000002,
            1000,
            Some("below-max"),
        );
        insert_score(
            &dir,
            &("x".repeat(64)),
            0,
            0,
            10,
            1000,
            0,
            0,
            0,
            1000,
            0,
            1,
            1,
            1700000003,
            1000,
            Some("true-max"),
        );
        create_scorelog_db(&dir);
        insert_scorelog(&dir, &("a".repeat(64)), 0, 0, 10, 0, 0, 0, 1700000004);
        insert_scorelog(&dir, &("b".repeat(64)), 0, 0, 10, 1500, 900, 1, 1700000005);

        let (scores, _, _) = parse_scores(dir.to_str().unwrap()).expect("parse beatoraja scores");
        let by_hash = scores
            .iter()
            .map(|score| (score.fumen_sha256.as_deref().unwrap(), score.clear_type))
            .collect::<std::collections::HashMap<_, _>>();
        let (history, _) = parse_score_log(dir.to_str().unwrap(), None);
        let history_by_hash = history
            .iter()
            .map(|score| (score.fumen_sha256.as_deref().unwrap(), score.clear_type))
            .collect::<std::collections::HashMap<_, _>>();

        assert_eq!(
            by_hash["zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"],
            Some(7)
        );
        assert_eq!(
            by_hash["yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"],
            Some(8)
        );
        assert_eq!(
            by_hash["xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"],
            Some(9)
        );
        assert_eq!(
            history_by_hash["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
            Some(7)
        );
        assert_eq!(
            history_by_hash["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
            Some(9)
        );

        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn parses_player_stats_songdata_and_songinfo() {
        let dir = temp_dir("detail");
        create_score_db(&dir);
        let score_conn = Connection::open(dir.join("score.db")).expect("open score db");
        score_conn
            .execute_batch(
                r#"
                CREATE TABLE player (
                    player INTEGER,
                    epg INTEGER,
                    lpg INTEGER,
                    egr INTEGER,
                    playcount INTEGER,
                    clearcount INTEGER,
                    playtime INTEGER,
                    date INTEGER
                );
                INSERT INTO player VALUES (0, 10, 20, 30, 99, 88, 777, 1000);
                "#,
            )
            .expect("create player table");

        let songdata = dir.join("songdata.db");
        let song_conn = Connection::open(&songdata).expect("create songdata db");
        song_conn
            .execute_batch(&format!(
                r#"
                CREATE TABLE song (
                    sha256 TEXT,
                    md5 TEXT,
                    title TEXT,
                    subtitle TEXT,
                    artist TEXT,
                    subartist TEXT,
                    minbpm REAL,
                    maxbpm REAL,
                    notes INTEGER,
                    length INTEGER
                );
                INSERT INTO song VALUES ('{}', '{}', 'Title', 'Sub', 'Artist', 'SubArtist', 120.5, 180.0, 1234, 90);
                "#,
                "s".repeat(64),
                "m".repeat(32)
            ))
            .expect("create song table");

        let songinfo = dir.join("songinfo.db");
        let info_conn = Connection::open(&songinfo).expect("create songinfo db");
        info_conn
            .execute_batch(&format!(
                r#"
                CREATE TABLE information (
                    sha256 TEXT,
                    n INTEGER,
                    ln INTEGER,
                    s INTEGER,
                    ls INTEGER,
                    total INTEGER,
                    mainbpm REAL
                );
                INSERT INTO information VALUES ('{}', 1, 2, 3, 4, 10, 150.0);
                "#,
                "s".repeat(64)
            ))
            .expect("create information table");

        let stats = parse_player_stats(dir.to_str().unwrap()).expect("parse player stats");
        let details = parse_songdata(songdata.to_str().unwrap());
        let info = parse_songinfo(songinfo.to_str().unwrap());

        assert_eq!(stats.client_type, "beatoraja");
        assert_eq!(stats.playcount, Some(99));
        assert_eq!(stats.judgments.as_ref().unwrap()["epg"], 10);
        assert_eq!(details.len(), 1);
        let expected_sha256 = "s".repeat(64);
        let expected_md5 = "m".repeat(32);
        assert_eq!(details[0].sha256.as_deref(), Some(expected_sha256.as_str()));
        assert_eq!(details[0].md5.as_deref(), Some(expected_md5.as_str()));
        assert_eq!(details[0].title.as_deref(), Some("Title Sub"));
        assert_eq!(details[0].notes_total, Some(1234));
        let entry = info.get(&"s".repeat(64)).expect("songinfo entry");
        assert_eq!(entry.notes_n, Some(1));
        assert_eq!(entry.bpm_main, Some(150.0));

        let _ = fs::remove_dir_all(dir);
    }
}
