# Server DB Schema

```
users            : id(UUID PK), username(UNIQUE), bio(String 500, nullable),
                   is_active, is_admin,
                   avatar_url, first_synced_at(JSONB), preferences(JSONB),
                   created_at, updated_at
                   [is_public 제거됨 — migration 0010]
oauth_accounts   : (user_id, provider) composite PK, provider_account_id,
                   provider_username, discord_avatar_hash, discord_avatar_url

difficulty_tables: id(UUID PK), name, symbol, slug, source_url(UNIQUE),
                   level_order(JSONB), display_level_order(JSONB nullable),
                   non_regular_level_order(JSONB nullable),
                   is_default, created_at, updated_at
                   -- display_level_order: optional admin-managed dashboard display order.
                   -- non_regular_level_order: admin-managed levels shown after the main group;
                      stale values missing from level_order are ignored.
fumens           : fumen_id(UUID PK), md5, sha256
                   [md5/sha256 partial unique indexes remain for client hash lookup],
                   title(Text), artist(Text),
                   bpm_min, bpm_max, bpm_main,
                   notes_total, notes_n, notes_ln, notes_s, notes_ls,
                   total, length, keymode(Integer nullable),
                   youtube_url, file_url, file_url_diff,
                   added_by_user_id(FK→users, nullable),
                   created_at, updated_at
fumen_table_entries: (fumen_id, table_id) composite PK,
                   fumen_id(FK→fumens ON DELETE CASCADE),
                   table_id(FK→difficulty_tables ON DELETE CASCADE),
                   level, created_at, updated_at
user_favorite_difficulty_tables: (user_id, table_id) UNIQUE, display_order
user_fumen_tags  : id(UUID PK), user_id, fumen_id(FK→fumens), tag, display_order
                   [unique(user_id, fumen_id, tag)]

announcement_tags: id(UUID PK), name(UNIQUE), color,
                   send_notification, display_order, created_at, updated_at
announcements    : id(UUID PK), tag_id(FK→announcement_tags),
                   title, body, body_en, body_ja,
                   is_published, published_at, created_at, updated_at
announcement_templates: id(UUID PK), tag_id(FK→announcement_tags nullable),
                   title_template, title_en_template, title_ja_template,
                   body_template, body_en_template, body_ja_template,
                   created_at, updated_at
                   [uq_announcement_templates_tag_id: UNIQUE on tag_id WHERE tag_id IS NOT NULL]
                   [uq_announcement_templates_global: UNIQUE on (1) WHERE tag_id IS NULL]
                   -- tag_id=NULL means global default template; one row per tag + at most one global.
notifications    : id(UUID PK), type, target_user_id(FK→users nullable),
                   announcement_id(FK→announcements nullable), dedupe_key(UNIQUE),
                   title, body, link_url, metadata(JSONB), is_published, created_at
notification_reads: (user_id, notification_id) composite PK,
                   read_at, deleted_at
notification_user_states: user_id(FK→users PK), read_cutoff_at, created_at, updated_at
table_import_log : id(UUID PK), user_id(FK→users), source_url,
                   outcome(created/duplicate/failed), error_detail, created_at
table_source_aliases: id(UUID PK), alias_url(UNIQUE),
                   table_id(FK→difficulty_tables), created_at

user_player_stats: id(UUID PK), user_id, client_type,
                   synced_at  [UNIQUE per (user_id, client_type, UTC day)],
                   playcount, clearcount, playtime, judgments(JSONB)
user_scores      : id(UUID PK), user_id, client_type, scorehash,
                   fumen_id(nullable FK→fumens), fumen_sha256, fumen_md5, fumen_hash_others,
                   clear_type, exscore, rate, rank, max_combo, min_bp,
                   play_count, clear_count, judgments(JSONB), options(JSONB),
                   recorded_at, synced_at
                   [no FK to users — intentional]
user_rankings    : (user_id, table_id) composite PK,
                   exp, exp_level, rating, rating_norm,
                   rating_contributions(JSONB), exp_top_contributions(JSONB),
                   dan_title, calculated_at
user_table_rating_checkpoints: (user_id, table_id, effective_date) composite PK,
                   exp, rating
                   [sparse checkpoint rows only when exp or rating changes]
user_table_rating_update_daily: (user_id, table_id, effective_date) composite PK,
                   update_count
                   [only non-zero dates; per-table rating update counts]
user_rating_update_daily: (user_id, effective_date) composite PK,
                   update_count
                   [only non-zero dates; cross-table deduped rating update counts]

courses          : id(UUID PK), name, source_table_id(FK→difficulty_tables),
                   md5_list(JSONB), sha256_list(JSONB), constraint(JSONB),
                   is_active, dan_title, synced_at
admin_action_logs: id(UUID PK), parent_log_id(self FK nullable),
                   action_name, target_kind, target_id, target_label,
                   status, triggered_by(FK→users nullable), celery_task_id,
                   payload(JSONB), last_message, error_message,
                   started_at, completed_at
admin_action_log_lines: id(UUID PK), log_id(FK→admin_action_logs ON DELETE CASCADE),
                   level, message, created_at
custom_difficulty_tables: id(UUID PK), owner_id(FK→users), name, is_public, levels(JSONB)
custom_courses   : id(UUID PK), owner_id(FK→users), name,
                   song_list(JSONB), course_file_config(JSONB)
schedules        : id(UUID PK), user_id(FK→users), title, description,
                   scheduled_date, scheduled_time, is_completed
```

**`fumens` 식별 규칙**: 서버 내부 참조는 `fumen_id`를 사용한다. 클라이언트 동기화 입력과 course member list는 여전히 sha256/md5 hash를 사용하며, 서버가 hash → `fumen_id`를 해석한다. `user_scores.fumen_id`는 nullable이다. 서버에 등록되지 않은 차분 또는 `fumen_hash_others` course 기록은 `fumen_id = NULL`로 보존한다.

**`fumen_table_entries` 정규화 정책**: 한 차분이 어느 난이도표의 어느 level에 속하는지는 `fumen_table_entries`가 source of truth다. 과거 `fumens.table_entries` JSONB는 제거되었다. API 응답의 `table_entries` 배열은 하위 호환용으로 이 테이블에서 재구성한다.

**`fumens.title` / `fumens.artist` 타입**: 난이도표 remote metadata는 길이 제한이 일정하지 않으므로 두 컬럼은 `TEXT`다. import 단계에서 제목/아티스트를 임의로 자르지 않는다.

**`user_scores` 누적 모델**: 기록 개선 시 새 행 INSERT → 누적 히스토리 역할 수행. 동일 UTC 날짜 내 같은 차분 기록은 per-field best 머지 후 단일 행 유지.

**`user_scores` NO PLAY 정책**: `clear_type = 0`(NO PLAY) 기록은 저장하지 않는다. 로컬 DB에 playcount 0 기록이 있더라도 NO PLAY이면 동기화 payload와 서버 저장 대상에서 제외한다.

**`user_scores` LR2 오분류 방어 정책**: 구버전 클라이언트가 Beatoraja `score.db`를 LR2 경로로 읽어 보낸 것으로 보이는 기록은 저장하지 않는다. 서버 `/sync`는 `client_type = 'lr2'`, `recorded_at IS NOT NULL`, LR2 판정 키(`perfect`, `great`, `good`, `bad`, `poor`)가 모두 0 또는 누락인 score item을 정상 스킵 처리한다.

**`user_scores.scorehash` 중복 방지**: `scorehash IS NOT NULL`인 행은 `(scorehash, user_id, client_type, COALESCE(fumen_sha256,''), COALESCE(fumen_md5,''), COALESCE(fumen_hash_others,''))` partial unique index로 dedup한다. `scorehash`가 같아도 차분 식별자(`fumen_sha256`/`fumen_md5`/`fumen_hash_others`)가 다르면 별도 기록이다.

**`user_scores.fumen_id` backfill 정책**: table import, fumen supplement, sync resolution이 등록된 fumen hash와 score hash를 매칭하면 `fumen_id`를 채운다. 성능값은 변경하지 않는다. hash 컬럼은 서버에 없는 차분 기록을 보존하기 위해 계속 유지한다.

**`user_rankings.exp_level` caveat**: 저장되는 레벨은 `api/ranking_tables/config.toml`의 application-level `max_level` cap이 적용된 값이다. 반면 `exp` 원본 누적값은 cap 없이 계속 증가한다.

**`user_rankings` coverage caveat**: 활성 유저가 `user_scores` 또는 `user_player_stats`를 하나라도 보유하면 모든 ranking-enabled 난이도표에 row를 가진다. 해당 표에 점수가 없으면 `exp=0`, `rating=0`, `rating_norm=0` row를 생성해 표별 랭킹 유저 수를 맞춘다.

**Discord avatar policy**: `oauth_accounts.discord_avatar_hash` stores the canonical Discord avatar hash returned by OAuth `identify`; response URLs are derived from `(provider_account_id, discord_avatar_hash)`. `discord_avatar_url` remains for compatibility/backfill only. If the hash is absent, the user has no Discord avatar or has not reauthenticated since the column was introduced.

**레이팅 파생 테이블 caveat**: `user_table_rating_checkpoints`, `user_table_rating_update_daily`, `user_rating_update_daily`는 모두 `user_scores`에서 재생산되는 derived data다. overview 응답 최적화용 저장소이며, 상세 곡 단위 기여도 source of truth는 여전히 `user_scores`다. `user_table_rating_update_daily`와 `user_rating_update_daily`는 `update_count > 0`인 날짜만 저장하므로, row 부재는 "0건" 또는 "아직 재계산 전"을 모두 의미할 수 있다. 이 구분은 request path에서 `user_rankings.calculated_at` freshness와 fallback으로 해소한다.

**`courses.constraint` 정책**: 난이도표 header의 course/grade `constraint` 토큰을 정규화된 문자열 배열로 보존한다. 같은 곡 구성(`md5_list` 우선, 없으면 `sha256_list`)의 코스 variant가 여러 개 있으면 import 단계에서 constraint 우선순위로 단 하나만 `is_active=true`가 된다. 비활성 variant는 삭제하지 않고 운영 추적용으로 남긴다.

**알림 모델 정책**: `notifications.target_user_id IS NULL`은 전체 대상 broadcast 알림이고, 값이 있으면 해당 유저 전용 알림이다. 전체 읽음 처리는 `notification_user_states.read_cutoff_at` 갱신으로 처리해 과거 알림 수만큼 `notification_reads` row를 만들지 않는다. 개별 읽음/삭제만 `notification_reads`에 lazy insert한다.

**공지사항 본문 다국어 정책**: `announcements.body`는 기본/한국어 본문이고, `body_en`, `body_ja`가 있으면 프론트에서 UI 언어에 맞게 우선 표시한다. 비어 있으면 `body`로 fallback한다.

**난이도표 import 로그 정책**: `table_import_log.outcome = duplicate`는 외부 fetch를 유발하지 않으며 quota에 포함하지 않는다. 신규 import 성공(`created`)은 24시간 5회, 실패(`failed`)는 1시간 5회 제한의 집계 근거다. `table_source_aliases`는 관리자가 미러 URL을 기존 정본 표로 연결할 때 사용한다.

**`admin_action_logs` 정책**: sqladmin에서 오래 걸리는 작업을 큐잉할 때 parent row를 만들고 진행 메시지는 `admin_action_log_lines`에 append-only INSERT로 저장한다. batch 작업은 `parent_log_id`로 child logs를 묶으며, parent status는 child들의 pending/running/success/failed 상태에서 집계된다.

## `fumens` — 상세 정보 컬럼

### BPM

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `bpm_min` | Float? | 최솟값 BPM (songdata.db `minbpm` / LR2song.db `minbpm`) |
| `bpm_max` | Float? | 최댓값 BPM (songdata.db `maxbpm` / LR2song.db `maxbpm`) |
| `bpm_main` | Float? | 주 BPM (songinfo.db `mainbpm` — Beatoraja 전용) |

과거 단일 `bpm` 컬럼은 migration 0005에서 삭제됨. 세 컬럼으로 분리하여 BPM 변속 정보를 보존한다.

### 노트 수

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `notes_total` | Integer? | 총 노트 수. 롱노트 1개로 계산 (songdata.db `notes`). 구 `total_notes`에서 개명. |
| `notes_n` | Integer? | 단노트 수 (songinfo.db `n`) |
| `notes_ln` | Integer? | 롱노트 수 (songinfo.db `ln`) |
| `notes_s` | Integer? | 스크래치 수 (songinfo.db `s`) |
| `notes_ls` | Integer? | 롱스크래치 수 (songinfo.db `ls`) |

**LR2 제한**: LR2 `karinotes`는 롱노트를 2개로 계산하므로 서버 convention과 불일치 → `notes_*` 필드는 LR2에서 채울 수 없음. NULL로 남김.

### 기타

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `total` | Integer? | 토탈값 (songinfo.db `total`) |
| `length` | Integer? | 차분 길이 밀리초 (songdata.db `length`) |
| `keymode` | Integer? | 키 수 (5, 7, 10, 14 등). LR2 소스: `score.db` `song.mode`, Beatoraja 소스: `songdata.db` `song.mode`. 클라이언트 full sync 시 채워짐. NULL은 아직 동기화되지 않은 레코드를 의미함. |
| `added_by_user_id` | UUID? | 최초로 서버에 해당 차분을 추가한 유저. `POST /fumens/sync-details` INSERT 시 기록. |

### 데이터 소스 및 우선순위

1. **Beatoraja 먼저** — `songdata.db` (bpm_min/max, notes_total, length) + `songinfo.db` (bpm_main, notes_n/ln/s/ls, total) 합산. 데이터가 더 풍부.
2. **LR2 나중** — 서버에 존재하지 않는 차분만 INSERT (bpm_min/max, title, artist 한정). 이미 Beatoraja에서 추가된 차분은 SKIP.
3. 기존에 값이 있는 필드는 덮어쓰지 않음 (NULL인 필드만 채움).

### 클라이언트 FULL sync 흐름

```
GET /fumens/known-hashes
  → complete set (모든 detail 필드 비어있지 않음): 클라이언트에서 완전 제외
  → partial set (일부 NULL): Beatoraja 항목만 전송 (LR2 SKIP)
  → unknown: Beatoraja + LR2 모두 전송 (신규 INSERT)

POST /fumens/sync-details
  → Beatoraja: 빈 필드 채우기 (UPDATE) 또는 신규 INSERT
  → LR2: 존재하지 않는 경우만 INSERT, 존재하면 SKIP
```

---

## `user_scores` — best 조회 방식

`user_scores`는 **append-only** 누적 기록 테이블이다. 한 fumen에 여러 행이 쌓이므로,
조회 시 "현재 best"를 계산하는 방법이 필요하다.

### 방식: 구동기별 최근 행 + 항목별 비교

`is_best_*` 컬럼은 존재하지 않는다. 대신 조회 시 **각 `client_type`별로 가장 최근 행
1개**를 선택한 뒤, 항목별로 비교해 최선값을 반환한다.

```
(fumen_sha256, fumen_md5, fumen_hash_others) 기준으로 그룹핑
  └─ client_type별 가장 최근 행 (ORDER BY COALESCE(recorded_at, synced_at) DESC)
       └─ 각 필드의 best값 집계:
            clear_type  → MAX
            exscore     → MAX
            min_bp      → MIN  (낮을수록 좋음)
            max_combo   → MAX
```

여러 구동기(LR2 + Beatoraja)가 있으면 각각 최근 행을 구한 뒤 항목별로 비교한다.
이때 서로 다른 구동기가 다른 필드에서 best를 차지하면 `source_client = "MIX"`로
표시된다 (기존 MIX 동작 유지).

### 개선 체크 (sync 시)

새 행을 INSERT할지 판단할 때는 **해당 (fumen, client_type)의 모든 기존 행을 조회해
Python에서 MAX/MIN 집계**한 뒤 비교한다(`_fetch_current_bests()`).

- `clear_type`: new ≥ existing best → insert
- `exscore`: new ≥ existing best → insert
- `min_bp`: new ≤ existing best (lower is better) → insert
- `max_combo`: new ≥ existing best → insert
- `play_count`: new > existing best (strict) → insert

동점(≥/≤)도 insert 조건에 포함된다 (같은 값을 여러 번 달성하면 최신 기록 유지).

### Same-day merge

같은 UTC 날짜에 이미 (fumen, client_type) 행이 있으면:
- 새 행을 INSERT하지 않고, 기존 행을 per-field best 값으로 UPDATE한다.
- 하루 안에 여러 번 플레이해도 행이 늘어나지 않는다.

### 기록 갱신 집계 — 단일 소스 정의

"기록 갱신 수"는 아래 규칙을 따르며, **캘린더, 활동 바차트, 상세 통계 카드, 차분 탭
아이템 수가 모두 동일한 소스**를 사용한다.

#### 집계 단위 및 기준

- **집계 단위**: 차분(fumen) 단위. 같은 날짜·같은 차분에 여러 구동기 기록이 있어도 **1개**로 집계.
- **갱신 판단**: `clear_type`, `exscore`, `max_combo`, `min_bp` 중 하나라도 **개선**되면 갱신. `play_count`만 변화한 경우는 갱신에 포함하지 않는다.
- **첫 플레이** (해당 fumen의 첫 기록): 항상 갱신으로 처리.
- **개선 방향**: `clear_type > prev`, `exscore > prev`, `max_combo > prev`, `min_bp < prev`.

#### SQL 구현 (`_build_activity_subquery` + `_improvement_filter`)

```sql
-- 파티션: (user_id, hash_col) — client_type 없음 (LR2/Beatoraja 통합 타임라인)
-- hash_col = COALESCE(fumen_sha256, fumen_md5, fumen_hash_others)
LAG(clear_type)  OVER (PARTITION BY user_id, hash_col ORDER BY effective_ts)  → prev_ct
LAG(exscore)     OVER (...)                                                    → prev_ex
LAG(min_bp)      OVER (...)                                                    → prev_bp
LAG(max_combo)   OVER (...)                                                    → prev_mc
ROW_NUMBER()     OVER (PARTITION BY user_id, hash_col ORDER BY effective_ts)   → rn
ROW_NUMBER()     OVER (PARTITION BY user_id, hash_col, day ORDER BY effective_ts DESC) → rn_in_day

-- 개선 조건 (_improvement_filter):
rn = 1  -- 첫 플레이
OR clear_type > COALESCE(prev_ct, 0)
OR exscore    > COALESCE(prev_ex, 0)
OR (min_bp IS NOT NULL AND (prev_bp IS NULL OR min_bp < prev_bp))
OR max_combo  > COALESCE(prev_mc, 0)

-- 일별 집계:
COUNT(*) FILTER (WHERE is_improvement AND rn_in_day = 1)
```

`rn_in_day = 1`은 같은 날 같은 차분의 여러 구동기 기록 중 최신 1개만 선택한다.

#### 초기 동기화 행 제외

LR2는 `first_synced_at["lr2"] + 3시간` 이내에 `synced_at`이 찍힌 행을 집계에서 제외한다
(최초 벌크 임포트분은 "갱신"이 아님). Outer filter로 적용하므로 LAG 타임라인 자체에는
포함되어 이전 값 참조에 사용된다.

#### 사용 엔드포인트별 적용

| 엔드포인트 | 적용 방식 |
|------------|-----------|
| `/analysis/heatmap` | `_build_activity_subquery` + `_improvement_filter`, 연간 집계 |
| `/analysis/activity` | 동일, 최근 N일 집계 |
| `/analysis/recent-updates?date=` → `day_summary.total_updates` | 동일 로직으로 해당 날짜 1일 집계 |
| `/analysis/score-updates?date=` (차분 탭) | per-client ROW_NUMBER로 최신 행 선택 후 개선 방향(`>/<`) 비교. date 지정 시 limit=500 (전체 처리). `buildMergedFumens`에서 sha256/md5 기준 dedup → 결과 아이템 수 = `total_updates`와 일치 |

---

### 일별 플레이 횟수 집계

#### 히트맵 / 활동 그래프 (`plays` 필드)

`/analysis/heatmap`, `/analysis/activity`의 `plays`는 **`UserPlayerStats.playcount`
LAG 델타 합산**이다.

```
delta = GREATEST(0, playcount - LAG(playcount) OVER (PARTITION BY user_id, client_type ORDER BY synced_at))
```

- **날짜 기준**: `synced_at` 날짜 (실제 플레이 날짜 ≠ 동기화 날짜일 수 있음)
- **첫 동기화**: `LAG=NULL` → `delta = 0` (자동 처리됨)

#### 상세 페이지 차분별 play_count 표시 (`/analysis/recent-updates`, `/analysis/score-updates`)

상세 페이지에서 각 차분(fumen)별 플레이 횟수 변화는 **`UserScore.play_count` 델타**로 계산.

| 경우 | 델타 | UI 표시 |
|------|------|---------|
| `rn > 1` (이전 기록 존재) | `GREATEST(0, play_count - prev_play_count)` | `prev → new` |
| `rn == 1`, 진짜 첫 플레이 (case 2-1) | `play_count` 전체 | `new` 또는 `0 → new` |
| `rn == 1`, LR2 첫 동기화 (case 2-2) | outer query에서 행 자체 제외 | 표시 안 됨 |
| `rn == 1`, Beatoraja 첫 동기화 (case 2-2) | `is_initial_sync=True` | `- → new` (툴팁: "첫 동기화") |

Beatoraja 첫 동기화 판단: `synced_at <= first_synced_at["beatoraja"] + 3시간`.
`is_initial_sync` 플래그로 프론트엔드에 전달됨.

---

## 날짜 상세 페이지 집계 (`/analysis/recent-updates?date=YYYY-MM-DD`)

날짜를 선택하면 `day_summary` 오브젝트가 함께 반환된다. 각 항목의 집계 방식과
프론트엔드 표시 규칙은 아래와 같다.

### 갱신 수 (`total_updates`)

히트맵·활동 그래프와 동일한 `_build_activity_subquery` + `_improvement_filter` 로직으로
계산한다. "기록 갱신 집계 — 단일 소스 정의" 섹션 참고.

### 플레이 수 (`total_play_count` / `play_count_uncertain`)

`UserScore.play_count` 델타를 fumen별 대표 행에서 합산한다 (상세는 "일별 플레이 횟수
집계" 섹션 참고).

`play_count_uncertain=True` 조건: 해당 날짜의 어느 fumen이든 `_is_initial_sync_record`
판정을 받으면 전체 플레이 수가 불확실로 처리된다.

### 플레이 시간 / 격파 노트 수 (`total_playtime` / `total_notes_hit`)

`UserPlayerStats` LAG 델타로 계산한다 (`_get_day_stats` 헬퍼).

```
playtime_delta  = GREATEST(0, playtime - COALESCE(LAG(playtime), playtime))
notes_hit_delta = Σ GREATEST(0, judgment_key - prev_judgment_key)
                  (LR2: perfect+great+good+bad / Beatoraja: epg+lpg+egr+lgr+egd+lgd+ebd+lbd)
```

LAG는 `(user_id, client_type)` 파티션 내 `synced_at` 순서로 계산.

#### 불확실(`-`) 표시 조건

`_get_day_stats`는 `has_rows` (해당 날짜에 PlayerStats 행 존재 여부) 플래그를 함께
반환한다. `day_summary` 빌드 시 두 조건을 OR로 합산한다:

| 조건 | 의미 | 결과 |
|------|------|------|
| `has_rows=True` AND `delta=0` | 첫 동기화 행(LAG=NULL)이거나 클라이언트가 해당 항목 미제공(LR2 playtime 없음 등) | `uncertain=True` → `-` |
| `has_rows=False` AND `len(entries) > 0` | 날짜가 PlayerStats 추적 시작 이전 (Beatoraja `recorded_at`이 첫 동기화보다 과거) | `uncertain=True` → `-` |
| `has_rows=False` AND `len(entries) = 0` | 해당 날짜에 플레이 자체 없음 | `uncertain=False` → `0` |
| `has_rows=True` AND `delta > 0` | 정상 집계 | `uncertain=False` → 실제 값 |

#### `uncertain` 표시 기준이 `play_count_uncertain`과 다른 이유

`play_count_uncertain`은 UserScore 레코드 기반(동기화 시간 기준)이고,
`playtime_uncertain` / `notes_hit_uncertain`은 UserPlayerStats 레코드 기반이다.
PlayerStats는 첫 동기화 시점부터 쌓이지만 UserScore는 Beatoraja `recorded_at` 덕분에
첫 동기화보다 훨씬 과거 날짜에도 데이터가 존재할 수 있다. 따라서 두 불확실 조건은
독립적으로 계산해야 한다.

---

## 클라이언트 업데이트 공지 (`client_update_announcements`)

관리자가 sqladmin에서 데스크톱 클라이언트 업데이트 알림을 작성하고 공개하는 테이블이다.
설치된 Tauri 클라이언트는 `/client/update-policy`를 주기적으로 확인하며, 공개된 최신
버전이 현재 앱 버전보다 높으면 업데이트 팝업을 표시한다.

| 필드 | 설명 |
|------|------|
| `version` | 알림 대상 클라이언트 버전. 선행 `v`는 API 비교에서 정규화한다. |
| `channel` | 업데이트 채널. 기본값은 `stable`. |
| `target_os` / `arch` / `installer_kind` | Tauri target 조합. 동일 `version`/`channel`이라도 Windows NSIS와 Linux AppImage는 별도 row로 저장한다. 현재 기본값은 `windows` / `x86_64` / `nsis`. |
| `title` / `body_markdown` | 클라이언트 업데이트 팝업과 Tauri updater notes에 표시할 관리자 작성 기본 문구. 현재 기본 문구는 한국어로 사용한다. |
| `body_markdown_en` / `body_markdown_ja` | 클라이언트 업데이트 팝업용 영어/일본어 본문. 비어 있으면 클라이언트는 `body_markdown`으로 fallback한다. |
| `release_page_url` | 릴리즈 페이지 링크. 선택값. |
| `update_url` | 다운로드 페이지와 updater metadata가 사용할 설치 파일 URL. |
| `tauri_signature` | Tauri 자동 설치용 서명. 알림만 보낼 때는 비워둘 수 있으며, 비어 있으면 `/client/tauri-update/*`는 204를 반환한다. |
| `mandatory` | 필수 업데이트 여부. 필수이면 클라이언트의 “나중에/건너뛰기” suppress를 무시한다. |
| `min_supported_version` | 이 업데이트를 받을 수 있는 최소 클라이언트 버전. 비어 있으면 제한 없음. |
| `is_published` | `true`일 때만 클라이언트 업데이트 API와 다운로드 페이지에 노출된다. |
| `publish_after` | 예약 공개 시각. `NULL`이면 `is_published=true` 즉시 공개. |
| `published_at` | 최초 공개 시각. sqladmin publish action 또는 `is_published=true` 저장 시 자동 기록된다. |

**릴리즈 target 관리 정책**: Git tag로 클라이언트를 배포하면 CI가 artifact별 metadata를 읽어 `target_os`/`arch`/`installer_kind` 조합마다 draft row를 생성한다. 예를 들어 `v1.2.3`이 Windows NSIS와 Linux AppImage를 모두 포함하면 같은 `version='1.2.3'`, `channel='stable'` 아래에 `windows/x86_64/nsis` row와 `linux/x86_64/appimage` row가 각각 생긴다. sqladmin에서는 개별 row publish도 가능하고, 같은 `version`/`channel` 전체 target row를 한 번에 publish하는 batch action도 제공한다.

주의: GitHub Release 최신값을 직접 신뢰하지 말고, 다운로드 페이지와 앱 업데이트 알림은 항상
이 테이블의 `is_published` / `publish_after` gate를 거쳐야 한다.


---

## 이슈 도메인 (`issue_tags`, `issues`, `issue_comments`, `issue_user_mentions`, `issue_issue_references`)

유저–어드민 소통 창구인 GitHub Issues 스타일 이슈 시스템. Migration 0033에서 추가.

### `issue_tags`

어드민이 sqladmin에서 직접 관리하는 이슈 태그 테이블.

| 필드 | 설명 |
|------|------|
| `slug` | 안정적인 프로그래밍 식별자. `bug`, `suggestion`, `question`, `other`. **슬러그를 변경하면 프론트엔드 필터 로직이 깨지므로 절대 변경 금지.** |
| `name` / `name_en` / `name_ja` | 다국어 표시명. 프론트엔드는 로케일에 맞게 fallback 표시한다. |
| `content_hint` | 이슈 작성 폼의 body textarea placeholder. 어드민이 sqladmin에서 직접 편집. `bug` 슬러그에만 기본값이 설정되어 있다. |
| `is_active` | `false`이면 이슈 작성 폼에서 숨겨지지만, 기존 이슈의 태그 이력은 보존된다. |
| `display_order` | 필터·태그 셀렉터 표시 순서. |

### `issues`

유저가 작성하는 공개 이슈 스레드. `id`는 자동증가 정수로 GitHub Issues의 `#123` 참조와 동일하게 사용한다.

| 필드 | 설명 |
|------|------|
| `id` | 정수 PK. 이슈 참조 시 `#123` 형태로 사용. |
| `author_id` | `ondelete=RESTRICT` — 이슈가 있는 유저는 계정 삭제 불가. |
| `tag_id` | `ondelete=RESTRICT` — 이슈가 있는 태그는 삭제 불가. |
| `status` | `open` / `completed` / `not_planned`. 기본값 `open`. |
| `comment_count` | 비정규화된 댓글 수. 댓글 생성과 같은 트랜잭션에서 `UPDATE issues SET comment_count = comment_count + 1`로 유지. **댓글을 수동 삭제할 경우 이 값도 반드시 동기화해야 한다.** |
| `last_activity_at` | 이슈 생성 및 댓글 추가 시 갱신. 목록 기본 정렬 기준. |
| `closed_at` / `closed_by_id` | `open`이 아닌 상태로 변경 시 채워진다. `open`으로 Reopen 시 `NULL`로 초기화. |
| `is_pinned` | 관리자에 의해 논의중인 이슈로 고정되었는지 여부. 목록 정렬에서 필터 통과 후 최상단 우선순위로 사용된다. |
| `pinned_at` | 마지막으로 고정된 시각. 고정 해제 시 `NULL`. |
| `pinned_by_id` | 마지막으로 고정한 관리자 사용자 ID. 사용자가 삭제되면 `NULL` (`ondelete=SET NULL`). |

**주의**: `completed` / `not_planned` 상태의 이슈는 API에서 댓글을 `409 Conflict`로 거부한다. 어드민이 Reopen 하면 다시 댓글 가능.

GIN 전문검색 인덱스: `ix_issues_search_all` (title+body), `ix_issues_search_title`, `ix_issues_search_body`. 검색 시 `plainto_tsquery('simple', ...)` 사용.

### `issue_comments`

`issue_id`는 `ondelete=CASCADE` — 이슈 삭제 시 댓글도 삭제된다 (단, sqladmin에서 이슈 삭제는 `can_delete=False`로 막혀 있다).

### `issue_user_mentions` / `issue_issue_references`

이슈 body 또는 댓글 작성 시 `@username` / `#123` 토큰을 파싱해 저장하는 참조 테이블.
실패한 참조(존재하지 않는 유저/이슈)는 무시되고 raw 텍스트는 그대로 표시된다.

### `notifications` — `type = "issue_mention"` 사용 패턴

`@username` 멘션이 포함된 이슈/댓글 저장 시, 언급된 유저(작성자 본인 제외)에게 대상 유저 전용 알림 생성.

- `target_user_id`: 언급된 유저 ID (해당 유저만 알림 수신)
- `link_url`: `/issues/{issue_id}`
- `dedupe_key`:
  - 이슈 body: `issue_mention:issue:{issue_id}:user:{mentioned_user_id}`
  - 댓글: `issue_mention:comment:{comment_id}:user:{mentioned_user_id}`
