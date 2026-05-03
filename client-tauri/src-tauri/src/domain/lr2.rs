use std::collections::HashSet;
use std::path::Path;

use anyhow::{anyhow, Context};
use rusqlite::types::ValueRef;
use rusqlite::{Connection, OpenFlags, Row};
use serde_json::json;
use time::format_description::well_known::Rfc3339;

use crate::domain::fumen_detail::FumenDetailItem;
use crate::domain::sync_api::{PlayerStats, ScoreItem, SongHash};

#[derive(Debug, Default, Clone)]
pub struct ParseStats {
    pub db_total: usize,
    pub query_result_count: usize,
    pub skipped_hash: usize,
    pub parsed_courses: usize,
    pub parsed: usize,
}

impl ParseStats {
    pub fn skipped_filter(&self) -> usize {
        self.db_total.saturating_sub(self.query_result_count)
    }
}

const HASH_CANDIDATES: &[&str] = &["sha256", "hash", "SHA256", "Hash"];

pub fn parse_scores(
    score_db_path: &str,
) -> anyhow::Result<(Vec<ScoreItem>, Vec<ScoreItem>, ParseStats)> {
    let path = Path::new(score_db_path);
    if !path.exists() {
        return Err(anyhow!("LR2 score DB not found: {}", path.display()));
    }

    let conn = open_readonly(path)?;
    let available = get_columns(&conn, "score")?;
    if available.is_empty() {
        return Err(anyhow!("Table 'score' not found in {}", path.display()));
    }
    let hash_col = resolve_col(&available, HASH_CANDIDATES)
        .ok_or_else(|| anyhow!("Cannot find hash column in LR2 score table"))?;

    let cols = Lr2Cols {
        pg: resolve_col(&available, &["pg", "pgreat", "p_great", "perfect"]),
        gr: resolve_col(&available, &["gr", "great"]),
        gd: resolve_col(&available, &["gd", "good"]),
        bd: resolve_col(&available, &["bd", "bad"]),
        pr: resolve_col(&available, &["pr", "poor"]),
        maxcombo: resolve_col(&available, &["maxcombo", "max_combo", "combo"]),
        minbp: resolve_col(&available, &["minbp", "min_bp"]),
        playtime: resolve_col(&available, &["playtime", "play_time", "date", "last_play"]),
        playcount: resolve_col(&available, &["playcount", "play_count"]),
        clear: resolve_col(&available, &["clear", "clear_type"]),
        op_best: resolve_col(&available, &["op_best", "opbest"]),
        op_history: resolve_col(&available, &["op_history", "ophistory"]),
        rseed: resolve_col(&available, &["rseed", "random_seed", "seed"]),
        clearcount: resolve_col(&available, &["clearcount", "clear_count"]),
        scorehash: resolve_col(&available, &["scorehash"]),
        totalnotes: resolve_col(&available, &["totalnotes", "total_notes", "notes"]),
    };

    let mut select_cols = vec![hash_col.clone()];
    for col in cols.iter().flatten() {
        if !select_cols.contains(col) {
            select_cols.push(col.clone());
        }
    }
    let where_clause = cols
        .playcount
        .as_ref()
        .map(|col| format!("WHERE {col} > 0"))
        .unwrap_or_default();

    let db_total =
        conn.query_row("SELECT COUNT(*) FROM score", [], |row| row.get::<_, i64>(0))? as usize;
    let sql = format!(
        "SELECT {} FROM score {}",
        select_cols.join(", "),
        where_clause
    );
    let mut stmt = conn.prepare(&sql)?;
    let mut rows = stmt.query([])?;

    let mut scores = Vec::new();
    let mut courses = Vec::new();
    let mut stats = ParseStats {
        db_total,
        ..ParseStats::default()
    };

    while let Some(row) = rows.next()? {
        stats.query_result_count += 1;
        let raw_hash = clean_hash(get_string(row, &hash_col).unwrap_or_default());
        if raw_hash.is_empty() {
            stats.skipped_hash += 1;
            continue;
        }

        if raw_hash.len() > 64 {
            let song_md5s = raw_hash[32..]
                .as_bytes()
                .chunks(32)
                .filter_map(|chunk| {
                    (chunk.len() == 32).then(|| String::from_utf8_lossy(chunk).to_string())
                })
                .collect::<Vec<_>>();
            if song_md5s.is_empty() {
                stats.skipped_hash += 1;
                continue;
            }
            courses.push(build_item(
                row,
                &cols,
                Some(raw_hash),
                None,
                None,
                song_md5s,
                Vec::new(),
            ));
            stats.parsed_courses += 1;
            continue;
        }

        if !matches!(raw_hash.len(), 32 | 64) {
            stats.skipped_hash += 1;
            continue;
        }

        let (md5, sha256) = if raw_hash.len() == 32 {
            (Some(raw_hash), None)
        } else {
            (None, Some(raw_hash))
        };
        scores.push(build_item(
            row,
            &cols,
            None,
            md5,
            sha256,
            Vec::new(),
            Vec::new(),
        ));
    }

    stats.parsed = scores.len();
    Ok((scores, courses, stats))
}

pub fn parse_player_stats(score_db_path: &str) -> Option<PlayerStats> {
    let conn = open_readonly(Path::new(score_db_path)).ok()?;
    let columns = get_columns(&conn, "player").ok()?;
    if columns.is_empty() {
        return None;
    }

    let pg = resolve_col(&columns, &["perfect", "pg", "pgreat", "p_great"]);
    let gr = resolve_col(&columns, &["great", "gr"]);
    let gd = resolve_col(&columns, &["good", "gd"]);
    let bd = resolve_col(&columns, &["bad", "bd"]);
    let pr = resolve_col(&columns, &["poor", "pr"]);
    let playcount = resolve_col(&columns, &["playcount", "play_count"]);
    let clearcount = resolve_col(&columns, &["clear", "clearcount", "clear_count"]);
    let playtime = resolve_col(&columns, &["playtime", "play_time"]);

    let mut select_cols = vec![];
    for col in [&pg, &gr, &gd, &bd, &pr, &playcount, &clearcount, &playtime]
        .into_iter()
        .flatten()
    {
        if !select_cols.contains(col) {
            select_cols.push(col.clone());
        }
    }
    if select_cols.is_empty() {
        return None;
    }

    let sql = format!("SELECT {} FROM player LIMIT 1", select_cols.join(", "));
    let mut stmt = conn.prepare(&sql).ok()?;
    stmt.query_row([], |row| {
        Ok(PlayerStats {
            client_type: "lr2".to_string(),
            playcount: get_i64(row, playcount.as_deref()),
            clearcount: get_i64(row, clearcount.as_deref()),
            playtime: get_i64(row, playtime.as_deref()),
            judgments: Some(json!({
                "perfect": get_i64(row, pg.as_deref()).unwrap_or(0),
                "great": get_i64(row, gr.as_deref()).unwrap_or(0),
                "good": get_i64(row, gd.as_deref()).unwrap_or(0),
                "bad": get_i64(row, bd.as_deref()).unwrap_or(0),
                "poor": get_i64(row, pr.as_deref()).unwrap_or(0),
            })),
        })
    })
    .ok()
}

pub fn parse_songdata(db_path: &str) -> Vec<FumenDetailItem> {
    let Ok(conn) = open_readonly(Path::new(db_path)) else {
        return Vec::new();
    };
    if !table_exists(&conn, "song").unwrap_or(false) {
        return Vec::new();
    }
    let Ok(columns) = get_columns(&conn, "song") else {
        return Vec::new();
    };
    let Some(hash_col) = resolve_col(&columns, &["hash", "sha256", "Hash"]) else {
        return Vec::new();
    };

    let title_col = columns.contains("title").then_some("title".to_string());
    let subtitle_col = columns
        .contains("subtitle")
        .then_some("subtitle".to_string());
    let artist_col = columns.contains("artist").then_some("artist".to_string());
    let subartist_col = columns
        .contains("subartist")
        .then_some("subartist".to_string());
    let minbpm_col = columns.contains("minbpm").then_some("minbpm".to_string());
    let maxbpm_col = columns.contains("maxbpm").then_some("maxbpm".to_string());

    let mut select_cols = vec![hash_col.clone()];
    for col in [
        &title_col,
        &subtitle_col,
        &artist_col,
        &subartist_col,
        &minbpm_col,
        &maxbpm_col,
    ]
    .into_iter()
    .flatten()
    {
        select_cols.push(col.clone());
    }
    let sql = format!(
        "SELECT {} FROM song WHERE {hash_col} IS NOT NULL AND {hash_col} != ''",
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
        let md5 = clean_hash(get_string(row, &hash_col).unwrap_or_default()).to_lowercase();
        if md5.len() != 32 {
            continue;
        }
        let title = join_text(
            get_string(row, title_col.as_deref().unwrap_or_default()),
            get_string(row, subtitle_col.as_deref().unwrap_or_default()),
        );
        let artist = join_text(
            get_string(row, artist_col.as_deref().unwrap_or_default()),
            get_string(row, subartist_col.as_deref().unwrap_or_default()),
        );
        items.push(FumenDetailItem {
            md5: Some(md5),
            sha256: None,
            title,
            artist,
            bpm_min: get_f64(row, minbpm_col.as_deref()),
            bpm_max: get_f64(row, maxbpm_col.as_deref()),
            client_type: "lr2".to_string(),
            ..FumenDetailItem::default()
        });
    }
    items
}

#[derive(Debug)]
struct Lr2Cols {
    pg: Option<String>,
    gr: Option<String>,
    gd: Option<String>,
    bd: Option<String>,
    pr: Option<String>,
    maxcombo: Option<String>,
    minbp: Option<String>,
    playtime: Option<String>,
    playcount: Option<String>,
    clear: Option<String>,
    op_best: Option<String>,
    op_history: Option<String>,
    rseed: Option<String>,
    clearcount: Option<String>,
    scorehash: Option<String>,
    totalnotes: Option<String>,
}

impl Lr2Cols {
    fn iter(&self) -> impl Iterator<Item = &Option<String>> {
        [
            &self.pg,
            &self.gr,
            &self.gd,
            &self.bd,
            &self.pr,
            &self.maxcombo,
            &self.minbp,
            &self.playtime,
            &self.playcount,
            &self.clear,
            &self.op_best,
            &self.op_history,
            &self.rseed,
            &self.clearcount,
            &self.scorehash,
            &self.totalnotes,
        ]
        .into_iter()
    }
}

fn build_item(
    row: &Row<'_>,
    cols: &Lr2Cols,
    fumen_hash_others: Option<String>,
    fumen_md5: Option<String>,
    fumen_sha256: Option<String>,
    song_md5s: Vec<String>,
    song_sha256s: Vec<String>,
) -> ScoreItem {
    let judgments = json!({
        "perfect": get_i64(row, cols.pg.as_deref()).unwrap_or(0),
        "great": get_i64(row, cols.gr.as_deref()).unwrap_or(0),
        "good": get_i64(row, cols.gd.as_deref()).unwrap_or(0),
        "bad": get_i64(row, cols.bd.as_deref()).unwrap_or(0),
        "poor": get_i64(row, cols.pr.as_deref()).unwrap_or(0),
    });
    let notes = none_if_zero(get_i64(row, cols.totalnotes.as_deref()).unwrap_or(0));
    let clear_val = get_i64(row, cols.clear.as_deref()).unwrap_or(0);
    let mut clear_type = lr2_clear_type(clear_val);
    if fumen_hash_others.is_none() && clear_type == 7 {
        let good = judgments["good"].as_i64().unwrap_or(0);
        let bad = judgments["bad"].as_i64().unwrap_or(0);
        let great = judgments["great"].as_i64().unwrap_or(0);
        let perfect = judgments["perfect"].as_i64().unwrap_or(0);
        let exscore = perfect * 2 + great;
        if good == 0 && bad == 0 {
            clear_type = 8;
            if great == 0 {
                if exscore == 0 {
                    clear_type = 7;
                } else if notes.is_some_and(|n| exscore == n * 2) {
                    clear_type = 9;
                }
            }
        }
    }

    ScoreItem {
        scorehash: get_string(row, cols.scorehash.as_deref().unwrap_or_default())
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty()),
        fumen_sha256,
        fumen_md5,
        fumen_hash_others,
        client_type: "lr2".to_string(),
        clear_type: Some(clear_type),
        notes,
        exscore: None,
        max_combo: none_if_zero(get_i64(row, cols.maxcombo.as_deref()).unwrap_or(0)),
        min_bp: get_i64(row, cols.minbp.as_deref()),
        judgments: Some(judgments),
        options: Some(json!({
            "op_best": get_i64(row, cols.op_best.as_deref()).unwrap_or(0),
            "op_history": get_i64(row, cols.op_history.as_deref()).unwrap_or(0),
            "rseed": get_i64(row, cols.rseed.as_deref()),
        })),
        play_count: Some(get_i64(row, cols.playcount.as_deref()).unwrap_or(0)),
        clear_count: Some(get_i64(row, cols.clearcount.as_deref()).unwrap_or(0)),
        recorded_at: get_i64(row, cols.playtime.as_deref()).and_then(unix_to_rfc3339),
        song_hashes: song_md5s
            .into_iter()
            .map(|md5| SongHash {
                song_md5: Some(md5),
                song_sha256: None,
            })
            .chain(song_sha256s.into_iter().map(|sha256| SongHash {
                song_md5: None,
                song_sha256: Some(sha256),
            }))
            .collect(),
    }
}

fn lr2_clear_type(value: i64) -> i64 {
    match value {
        1 => 1,
        2 => 3,
        3 => 4,
        4 => 5,
        5 => 7,
        _ => 0,
    }
}

pub(crate) fn open_readonly(path: &Path) -> anyhow::Result<Connection> {
    Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .with_context(|| format!("failed to open SQLite DB: {}", path.display()))
}

pub(crate) fn get_columns(conn: &Connection, table: &str) -> anyhow::Result<HashSet<String>> {
    let mut stmt = conn.prepare(&format!("PRAGMA table_info({table})"))?;
    let rows = stmt.query_map([], |row| row.get::<_, String>(1))?;
    Ok(rows.filter_map(Result::ok).collect())
}

pub(crate) fn table_exists(conn: &Connection, table: &str) -> anyhow::Result<bool> {
    let count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?1",
        [table],
        |row| row.get(0),
    )?;
    Ok(count > 0)
}

pub(crate) fn resolve_col(columns: &HashSet<String>, candidates: &[&str]) -> Option<String> {
    candidates
        .iter()
        .find(|candidate| columns.contains(**candidate))
        .map(|candidate| (*candidate).to_string())
}

pub(crate) fn get_i64(row: &Row<'_>, col: Option<&str>) -> Option<i64> {
    let col = col?;
    match row.get_ref(col).ok()? {
        ValueRef::Integer(v) => Some(v),
        ValueRef::Real(v) => Some(v as i64),
        ValueRef::Text(v) => std::str::from_utf8(v).ok()?.parse().ok(),
        _ => None,
    }
}

pub(crate) fn get_f64(row: &Row<'_>, col: Option<&str>) -> Option<f64> {
    let col = col?;
    match row.get_ref(col).ok()? {
        ValueRef::Integer(v) => Some(v as f64),
        ValueRef::Real(v) => Some(v),
        ValueRef::Text(v) => std::str::from_utf8(v).ok()?.parse().ok(),
        _ => None,
    }
}

pub(crate) fn get_string(row: &Row<'_>, col: &str) -> Option<String> {
    if col.is_empty() {
        return None;
    }
    match row.get_ref(col).ok()? {
        ValueRef::Text(v) => Some(String::from_utf8_lossy(v).to_string()),
        ValueRef::Integer(v) => Some(v.to_string()),
        ValueRef::Real(v) => Some(v.to_string()),
        _ => None,
    }
}

pub(crate) fn unix_to_rfc3339(ts: i64) -> Option<String> {
    (ts > 0)
        .then_some(ts)
        .and_then(|ts| time::OffsetDateTime::from_unix_timestamp(ts).ok())
        .and_then(|dt| dt.format(&Rfc3339).ok())
}

pub(crate) fn clean_hash(value: String) -> String {
    value.trim().replace('\0', "")
}

pub(crate) fn none_if_zero(value: i64) -> Option<i64> {
    (value != 0).then_some(value)
}

pub(crate) fn join_text(a: Option<String>, b: Option<String>) -> Option<String> {
    let joined = format!("{} {}", a.unwrap_or_default(), b.unwrap_or_default())
        .trim()
        .to_string();
    (!joined.is_empty()).then_some(joined)
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::Connection;
    use std::fs;
    use std::path::PathBuf;

    fn temp_db(name: &str) -> PathBuf {
        let mut path = std::env::temp_dir();
        path.push(format!(
            "ojik_bms_lr2_{name}_{}_{}.db",
            std::process::id(),
            time::OffsetDateTime::now_utc().unix_timestamp_nanos()
        ));
        path
    }

    fn create_score_db(path: &Path) {
        let conn = Connection::open(path).expect("create lr2 test db");
        conn.execute_batch(
            r#"
            CREATE TABLE score (
                sha256 TEXT PRIMARY KEY,
                clear INTEGER,
                pg INTEGER,
                gr INTEGER,
                gd INTEGER,
                bd INTEGER,
                pr INTEGER,
                maxcombo INTEGER,
                minbp INTEGER,
                playtime INTEGER,
                playcount INTEGER,
                op_best INTEGER,
                op_history INTEGER,
                rseed INTEGER,
                scorehash TEXT,
                clearcount INTEGER,
                totalnotes INTEGER
            );
            "#,
        )
        .expect("create score table");
    }

    #[allow(clippy::too_many_arguments)]
    fn insert_score(
        path: &Path,
        hash: &str,
        clear: i64,
        pg: i64,
        gr: i64,
        gd: i64,
        bd: i64,
        pr: i64,
        maxcombo: i64,
        minbp: i64,
        playcount: i64,
        scorehash: Option<&str>,
        totalnotes: i64,
    ) {
        let conn = Connection::open(path).expect("open lr2 test db");
        conn.execute(
            r#"
            INSERT INTO score VALUES (
                ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9,
                1700000000, ?10, 12, 34, 56, ?11, 2, ?12
            )
            "#,
            (
                hash, clear, pg, gr, gd, bd, pr, maxcombo, minbp, playcount, scorehash, totalnotes,
            ),
        )
        .expect("insert lr2 score row");
    }

    #[test]
    fn parses_basic_score_and_preserves_notes_and_min_bp_zero() {
        let db = temp_db("basic");
        create_score_db(&db);
        insert_score(
            &db,
            &("a".repeat(64)),
            3,
            1000,
            500,
            100,
            50,
            20,
            1200,
            0,
            10,
            Some("abc123"),
            800,
        );
        insert_score(
            &db,
            &("b".repeat(64)),
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            Some("skip"),
            0,
        );

        let (scores, courses, stats) =
            parse_scores(db.to_str().unwrap()).expect("parse lr2 scores");

        assert_eq!(scores.len(), 1);
        assert!(courses.is_empty());
        assert_eq!(stats.db_total, 2);
        assert_eq!(stats.query_result_count, 1);
        assert_eq!(stats.parsed, 1);
        let score = &scores[0];
        let expected_sha256 = "a".repeat(64);
        assert_eq!(
            score.fumen_sha256.as_deref(),
            Some(expected_sha256.as_str())
        );
        assert_eq!(score.fumen_md5, None);
        assert_eq!(score.client_type, "lr2");
        assert_eq!(score.clear_type, Some(4));
        assert_eq!(score.notes, Some(800));
        assert_eq!(score.max_combo, Some(1200));
        assert_eq!(score.min_bp, Some(0));
        assert_eq!(score.play_count, Some(10));
        assert_eq!(score.scorehash.as_deref(), Some("abc123"));

        let _ = fs::remove_file(db);
    }

    #[test]
    fn separates_md5_sha256_and_preserves_course_raw_hash() {
        let db = temp_db("hashes");
        create_score_db(&db);
        let md5 = "m".repeat(32);
        let sha256 = "s".repeat(64);
        let course = format!("{}{}{}", "h".repeat(32), "c".repeat(32), "d".repeat(32));
        insert_score(&db, &md5, 2, 1, 1, 0, 0, 0, 1, 1, 1, None, 2);
        insert_score(&db, &sha256, 2, 1, 1, 0, 0, 0, 1, 1, 1, None, 2);
        insert_score(
            &db,
            &course,
            5,
            10,
            0,
            0,
            0,
            0,
            10,
            0,
            1,
            Some("course-scorehash"),
            10,
        );

        let (scores, courses, stats) =
            parse_scores(db.to_str().unwrap()).expect("parse lr2 scores");

        assert_eq!(scores.len(), 2);
        assert_eq!(courses.len(), 1);
        assert_eq!(stats.parsed_courses, 1);
        assert!(scores
            .iter()
            .any(|score| score.fumen_md5.as_deref() == Some(md5.as_str())));
        assert!(scores
            .iter()
            .any(|score| score.fumen_sha256.as_deref() == Some(sha256.as_str())));
        let course_item = &courses[0];
        assert_eq!(
            course_item.fumen_hash_others.as_deref(),
            Some(course.as_str())
        );
        assert_eq!(course_item.scorehash.as_deref(), Some("course-scorehash"));
        assert_eq!(
            course_item
                .song_hashes
                .iter()
                .map(|hash| hash.song_md5.as_deref().unwrap())
                .collect::<Vec<_>>(),
            vec!["c".repeat(32), "d".repeat(32)]
        );

        let _ = fs::remove_file(db);
    }

    #[test]
    fn normalizes_lr2_fc_perfect_and_max_only_for_single_scores() {
        let db = temp_db("clear");
        create_score_db(&db);
        insert_score(
            &db,
            &("z".repeat(64)),
            5,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            1,
            Some("zero-fc"),
            1000,
        );
        insert_score(
            &db,
            &("y".repeat(64)),
            5,
            999,
            0,
            0,
            0,
            0,
            999,
            0,
            1,
            Some("perfect"),
            1000,
        );
        insert_score(
            &db,
            &("x".repeat(64)),
            5,
            1000,
            0,
            0,
            0,
            0,
            1000,
            0,
            1,
            Some("max"),
            1000,
        );
        let course = format!("{}{}{}", "h".repeat(32), "i".repeat(32), "j".repeat(32));
        insert_score(
            &db,
            &course,
            5,
            1000,
            0,
            0,
            0,
            0,
            1000,
            0,
            1,
            Some("course"),
            1000,
        );

        let (scores, courses, _) = parse_scores(db.to_str().unwrap()).expect("parse lr2 scores");
        let by_hash = scores
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
        assert_eq!(courses[0].clear_type, Some(7));

        let _ = fs::remove_file(db);
    }

    #[test]
    fn parses_player_stats() {
        let db = temp_db("player");
        create_score_db(&db);
        let conn = Connection::open(&db).expect("open lr2 test db");
        conn.execute_batch(
            r#"
            CREATE TABLE player (
                pg INTEGER,
                gr INTEGER,
                gd INTEGER,
                bd INTEGER,
                pr INTEGER,
                playcount INTEGER,
                clearcount INTEGER,
                playtime INTEGER
            );
            INSERT INTO player VALUES (10, 20, 3, 4, 5, 99, 88, 777);
            "#,
        )
        .expect("create player table");

        let stats = parse_player_stats(db.to_str().unwrap()).expect("parse lr2 player stats");

        assert_eq!(stats.client_type, "lr2");
        assert_eq!(stats.playcount, Some(99));
        assert_eq!(stats.clearcount, Some(88));
        assert_eq!(stats.playtime, Some(777));
        assert_eq!(stats.judgments.unwrap()["perfect"], 10);

        let _ = fs::remove_file(db);
    }
}
