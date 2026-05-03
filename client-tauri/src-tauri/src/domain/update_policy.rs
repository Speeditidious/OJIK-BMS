use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct UpdatePolicy {
    pub update_available: bool,
    pub message: Option<String>,
}

impl UpdatePolicy {
    pub fn not_configured(manual: bool) -> Self {
        Self {
            update_available: false,
            message: manual.then(|| {
                "업데이트 API는 signed updater artifact, public key, 서버 metadata endpoint가 준비된 배포 환경에서 연결됩니다.".to_string()
            }),
        }
    }
}
