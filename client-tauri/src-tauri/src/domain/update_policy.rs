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
