use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct UpdateAnnouncement {
    pub id: String,
    pub version: String,
    pub title: String,
    pub body_markdown: String,
    pub release_page_url: Option<String>,
    pub mandatory: bool,
    pub asset_size_bytes: Option<u64>,
    pub published_at: Option<String>,
    #[serde(default)]
    pub supports_auto_install: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct UpdatePolicy {
    pub update_available: bool,
    pub message: Option<String>,
    pub announcement: Option<UpdateAnnouncement>,
}

impl UpdatePolicy {
    pub fn no_update(message: Option<String>) -> Self {
        Self {
            update_available: false,
            message,
            announcement: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::UpdatePolicy;

    #[test]
    fn preserves_supports_auto_install_from_server_response() {
        let raw = r#"{
            "update_available": true,
            "message": null,
            "announcement": {
                "id": "0e524d8e-8cad-4625-a470-df94984a575c",
                "version": "1.0.0-beta.16",
                "title": "OJIK BMS Client v1.0.0-beta.16",
                "body_markdown": "Release notes",
                "release_page_url": "https://github.com/Speeditidious/OJIK-BMS/releases/tag/v1.0.0-beta.16",
                "mandatory": false,
                "asset_size_bytes": 2939648,
                "published_at": "2026-05-07T13:52:28.676132Z",
                "supports_auto_install": true
            }
        }"#;

        let policy: UpdatePolicy = serde_json::from_str(raw).expect("update policy should parse");

        assert!(policy.update_available);
        assert!(
            policy
                .announcement
                .expect("announcement should be present")
                .supports_auto_install
        );
    }

    #[test]
    fn defaults_supports_auto_install_to_false_for_legacy_responses() {
        let raw = r#"{
            "update_available": true,
            "message": null,
            "announcement": {
                "id": "0e524d8e-8cad-4625-a470-df94984a575c",
                "version": "1.0.0-beta.16",
                "title": "OJIK BMS Client v1.0.0-beta.16",
                "body_markdown": "Release notes",
                "release_page_url": null,
                "mandatory": false,
                "asset_size_bytes": null,
                "published_at": null
            }
        }"#;

        let policy: UpdatePolicy = serde_json::from_str(raw).expect("update policy should parse");

        assert!(
            !policy
                .announcement
                .expect("announcement should be present")
                .supports_auto_install
        );
    }
}
