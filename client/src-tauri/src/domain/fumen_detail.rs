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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub keymode: Option<i64>,
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
    pub enriched: i64,
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
    enriched: i64,
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
                    summary.errors.push(format!("해시 보강 오류: {error:#}"));
                    break;
                }
            }
        }
    }

    let known = api.fetch_known_hashes().await.ok();
    let complete_sha256: HashSet<String> = known
        .as_ref()
        .map(|k| k.complete_sha256.iter().map(|v| v.to_lowercase()).collect())
        .unwrap_or_default();
    let complete_md5: HashSet<String> = known
        .as_ref()
        .map(|k| k.complete_md5.iter().map(|v| v.to_lowercase()).collect())
        .unwrap_or_default();
    let known_sha256: HashSet<String> = known
        .as_ref()
        .map(|k| {
            k.complete_sha256
                .iter()
                .chain(k.partial_sha256.iter())
                .map(|v| v.to_lowercase())
                .collect()
        })
        .unwrap_or_default();
    let known_md5: HashSet<String> = known
        .as_ref()
        .map(|k| {
            k.complete_md5
                .iter()
                .chain(k.partial_md5.iter())
                .map(|v| v.to_lowercase())
                .collect()
        })
        .unwrap_or_default();
    let keymode_missing_md5: HashSet<String> = known
        .as_ref()
        .map(|k| {
            k.keymode_missing_md5
                .iter()
                .map(|v| v.to_lowercase())
                .collect()
        })
        .unwrap_or_default();

    // Beatoraja: exclude complete-and-keymode-ok items to reduce bandwidth
    beatoraja_items.retain(|item| {
        beatoraja_item_should_send(item, &complete_sha256, &complete_md5, &keymode_missing_md5)
    });

    let mut all_items = Vec::new();
    all_items.append(&mut beatoraja_items);
    all_items.extend(
        lr2_items
            .into_iter()
            .filter(|item| lr2_item_should_send(item, &known_md5, &known_sha256, &keymode_missing_md5)),
    );

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
                summary.enriched += response.enriched;
                summary.skipped += response.skipped;
                if response.overlap_count > 0 {
                    summary.enriched -= response.overlap_count;
                }
            }
            Err(error) => {
                summary
                    .errors
                    .push(format!("차분 상세 전송 오류: {error:#}"));
                break;
            }
        }
    }

    summary
}

/// Returns true if a Beatoraja detail item should be uploaded.
/// Complete items (server already has full data) are skipped unless they need keymode.
fn beatoraja_item_should_send(
    item: &FumenDetailItem,
    complete_sha256: &HashSet<String>,
    complete_md5: &HashSet<String>,
    keymode_missing_md5: &HashSet<String>,
) -> bool {
    let complete = item
        .sha256
        .as_ref()
        .is_some_and(|h| complete_sha256.contains(h))
        || item
            .md5
            .as_ref()
            .is_some_and(|h| complete_md5.contains(h));
    let needs_keymode = item
        .md5
        .as_ref()
        .is_some_and(|h| keymode_missing_md5.contains(h));
    !complete || needs_keymode
}

/// Returns true if an LR2 detail item should be uploaded.
/// Known items (complete or partial) are skipped unless they need keymode.
fn lr2_item_should_send(
    item: &FumenDetailItem,
    known_md5: &HashSet<String>,
    known_sha256: &HashSet<String>,
    keymode_missing_md5: &HashSet<String>,
) -> bool {
    let known_by_md5 = item
        .md5
        .as_ref()
        .is_some_and(|md5| known_md5.contains(&md5.to_lowercase()));
    let known_by_sha256 = item
        .sha256
        .as_ref()
        .is_some_and(|sha256| known_sha256.contains(&sha256.to_lowercase()));
    let needs_keymode = item
        .md5
        .as_ref()
        .is_some_and(|md5| keymode_missing_md5.contains(&md5.to_lowercase()));
    (!known_by_md5 && !known_by_sha256) || needs_keymode
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lr2_item(md5: &str) -> FumenDetailItem {
        FumenDetailItem {
            md5: Some(md5.to_string()),
            client_type: "lr2".to_string(),
            ..FumenDetailItem::default()
        }
    }

    fn bea_item(md5: &str, sha256: &str) -> FumenDetailItem {
        FumenDetailItem {
            md5: Some(md5.to_string()),
            sha256: Some(sha256.to_string()),
            client_type: "beatoraja".to_string(),
            ..FumenDetailItem::default()
        }
    }

    fn hashset(items: &[&str]) -> HashSet<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn lr2_items_resent_when_in_keymode_missing_md5() {
        let md5_a = "a".repeat(32);
        let item = lr2_item(&md5_a);

        // md5_a is complete (would normally be skipped) but also in keymode_missing_md5
        let known_md5 = hashset(&[&md5_a]);
        let known_sha256 = hashset(&[]);
        let keymode_missing_md5 = hashset(&[&md5_a]);

        assert!(
            lr2_item_should_send(&item, &known_md5, &known_sha256, &keymode_missing_md5),
            "item in keymode_missing_md5 should be resent even if known"
        );
    }

    #[test]
    fn lr2_items_skipped_when_not_in_keymode_missing_md5() {
        let md5_b = "b".repeat(32);
        let item = lr2_item(&md5_b);

        // md5_b is in complete_md5 and NOT in keymode_missing_md5
        let known_md5 = hashset(&[&md5_b]);
        let known_sha256 = hashset(&[]);
        let keymode_missing_md5 = hashset(&[]);

        assert!(
            !lr2_item_should_send(&item, &known_md5, &known_sha256, &keymode_missing_md5),
            "known item not in keymode_missing_md5 should be filtered out"
        );
    }

    #[test]
    fn lr2_unknown_items_always_sent() {
        let md5_c = "c".repeat(32);
        let item = lr2_item(&md5_c);

        let known_md5 = hashset(&[]);
        let known_sha256 = hashset(&[]);
        let keymode_missing_md5 = hashset(&[]);

        assert!(
            lr2_item_should_send(&item, &known_md5, &known_sha256, &keymode_missing_md5),
            "unknown item should always be sent"
        );
    }

    #[test]
    fn beatoraja_items_excluded_when_complete_and_no_keymode_need() {
        let sha256_a = "a".repeat(64);
        let md5_a = "a".repeat(32);
        let item = bea_item(&md5_a, &sha256_a);

        let complete_sha256 = hashset(&[&sha256_a]);
        let complete_md5 = hashset(&[]);
        let keymode_missing_md5 = hashset(&[]);

        assert!(
            !beatoraja_item_should_send(&item, &complete_sha256, &complete_md5, &keymode_missing_md5),
            "complete beatoraja item not needing keymode should be excluded"
        );
    }

    #[test]
    fn beatoraja_items_retained_when_complete_but_keymode_needed() {
        let sha256_a = "a".repeat(64);
        let md5_a = "a".repeat(32);
        let item = bea_item(&md5_a, &sha256_a);

        // sha256_a is complete but md5_a needs keymode
        let complete_sha256 = hashset(&[&sha256_a]);
        let complete_md5 = hashset(&[]);
        let keymode_missing_md5 = hashset(&[&md5_a]);

        assert!(
            beatoraja_item_should_send(&item, &complete_sha256, &complete_md5, &keymode_missing_md5),
            "complete beatoraja item whose md5 is in keymode_missing_md5 should be retained"
        );
    }

    #[test]
    fn beatoraja_incomplete_items_always_sent() {
        let sha256_b = "b".repeat(64);
        let md5_b = "b".repeat(32);
        let item = bea_item(&md5_b, &sha256_b);

        let complete_sha256 = hashset(&[]);
        let complete_md5 = hashset(&[]);
        let keymode_missing_md5 = hashset(&[]);

        assert!(
            beatoraja_item_should_send(&item, &complete_sha256, &complete_md5, &keymode_missing_md5),
            "incomplete beatoraja item should always be sent"
        );
    }

    #[test]
    fn detail_sync_summary_enriched_does_not_affect_inserted() {
        // Verify that DetailSyncSummary.enriched and .inserted are independent fields
        let mut summary = DetailSyncSummary::default();
        summary.inserted += 5;
        summary.enriched += 3;
        summary.enriched -= 1; // overlap_count deduction

        assert_eq!(summary.inserted, 5, "inserted should be unaffected by enriched changes");
        assert_eq!(summary.enriched, 2, "enriched after overlap deduction");
    }
}
