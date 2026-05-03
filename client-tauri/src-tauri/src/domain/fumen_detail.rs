use std::collections::HashSet;

use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::domain::sync_api::ApiClient;

#[derive(Debug, Default, Clone, Serialize)]
pub struct FumenDetailItem {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub md5: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sha256: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub artist: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bpm_min: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bpm_max: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bpm_main: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub notes_total: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub notes_n: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub notes_ln: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub notes_s: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub notes_ls: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub length: Option<i64>,
    pub client_type: String,
}

#[derive(Debug, Default, Clone)]
pub struct SongInfoEntry {
    pub notes_n: Option<i64>,
    pub notes_ln: Option<i64>,
    pub notes_s: Option<i64>,
    pub notes_ls: Option<i64>,
    pub total: Option<i64>,
    pub bpm_main: Option<f64>,
}

#[derive(Debug, Default, Clone)]
pub struct DetailSyncSummary {
    pub supplemented: i64,
    pub inserted: i64,
    pub updated: i64,
    pub skipped: i64,
    pub errors: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct SupplementResponse {
    #[serde(default)]
    supplemented: i64,
    #[serde(default)]
    supplemented_md5s: Vec<String>,
    #[serde(default)]
    supplemented_sha256s: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct DetailResponse {
    #[serde(default)]
    inserted: i64,
    #[serde(default)]
    updated: i64,
    #[serde(default)]
    skipped: i64,
    #[serde(default)]
    overlap_count: i64,
}

pub async fn run_detail_sync(
    api: &ApiClient,
    mut beatoraja_items: Vec<FumenDetailItem>,
    lr2_items: Vec<FumenDetailItem>,
) -> DetailSyncSummary {
    let mut summary = DetailSyncSummary::default();
    let mut supplemented_md5s = Vec::new();
    let mut supplemented_sha256s = Vec::new();

    if !beatoraja_items.is_empty() {
        let pairs = beatoraja_items
            .iter()
            .filter_map(|item| {
                Some(json!({ "md5": item.md5.as_ref()?, "sha256": item.sha256.as_ref()? }))
            })
            .collect::<Vec<_>>();

        for batch in pairs.chunks(5000) {
            let payload = json!({
                "client_type": "beatoraja",
                "items": batch,
            });
            match api
                .post_json::<SupplementResponse>("/fumens/supplement", &payload)
                .await
            {
                Ok(response) => {
                    summary.supplemented += response.supplemented;
                    supplemented_md5s.extend(response.supplemented_md5s);
                    supplemented_sha256s.extend(response.supplemented_sha256s);
                }
                Err(error) => {
                    summary.errors.push(format!("해시 보강 오류: {error}"));
                    break;
                }
            }
        }
    }

    let known = api.fetch_known_hashes().await.ok();
    let known_md5 = known
        .as_ref()
        .map(|known| {
            known
                .complete_md5
                .iter()
                .chain(known.partial_md5.iter())
                .map(|value| value.to_lowercase())
                .collect::<HashSet<_>>()
        })
        .unwrap_or_default();
    let known_sha256 = known
        .as_ref()
        .map(|known| {
            known
                .complete_sha256
                .iter()
                .chain(known.partial_sha256.iter())
                .map(|value| value.to_lowercase())
                .collect::<HashSet<_>>()
        })
        .unwrap_or_default();

    let mut all_items = Vec::new();
    all_items.append(&mut beatoraja_items);
    all_items.extend(lr2_items.into_iter().filter(|item| {
        let known_by_md5 = item
            .md5
            .as_ref()
            .is_some_and(|md5| known_md5.contains(&md5.to_lowercase()));
        let known_by_sha256 = item
            .sha256
            .as_ref()
            .is_some_and(|sha256| known_sha256.contains(&sha256.to_lowercase()));
        !known_by_md5 && !known_by_sha256
    }));

    let mut seen_sha256 = HashSet::new();
    let mut seen_md5 = HashSet::new();
    all_items.retain(|item| {
        let sha256_seen = item
            .sha256
            .as_ref()
            .is_some_and(|sha256| seen_sha256.contains(sha256));
        let md5_seen = item.md5.as_ref().is_some_and(|md5| seen_md5.contains(md5));
        if sha256_seen || md5_seen {
            return false;
        }
        if let Some(sha256) = &item.sha256 {
            seen_sha256.insert(sha256.clone());
        }
        if let Some(md5) = &item.md5 {
            seen_md5.insert(md5.clone());
        }
        true
    });

    for batch in all_items.chunks(1024) {
        let payload = json!({
            "items": batch,
            "supplemented_md5s": supplemented_md5s,
            "supplemented_sha256s": supplemented_sha256s,
        });
        match api
            .post_json::<DetailResponse>("/fumens/sync-details", &payload)
            .await
        {
            Ok(response) => {
                summary.inserted += response.inserted;
                summary.updated += response.updated;
                summary.skipped += response.skipped;
                if response.overlap_count > 0 {
                    summary.updated -= response.overlap_count;
                }
            }
            Err(error) => {
                summary.errors.push(format!("차분 상세 전송 오류: {error}"));
                break;
            }
        }
    }

    summary
}
