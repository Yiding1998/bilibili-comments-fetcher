# Bilibili Complete Statistics Design

## Goal

Turn the existing single-file prototype into a reliable command-line application that collects and reports Bilibili danmaku and comments for normal videos, multi-part videos, collections, and bangumi seasons or episodes.

The application must preserve progress, resume interrupted work, accurately parse protobuf danmaku, fetch every accessible child-comment page, and generate both per-episode reports and global summaries.

## Supported Inputs

The CLI automatically recognizes:

- A bare `BV` identifier.
- A normal Bilibili video URL.
- A multi-part video URL.
- A collection or series URL.
- A bangumi `ep` URL or identifier.
- A bangumi `ss` URL or identifier.

Every input is resolved into one normalized work containing one or more episodes. An episode is the smallest independently collectible unit and carries identifiers such as `bvid`, `aid`, `cid`, and, where applicable, `ep_id`.

## Architecture

The implementation is split into a small Python package. The existing `bilibili_stats.py` remains as a compatibility launcher.

### `bili_stats/cli.py`

Owns argument parsing, validation, task orchestration, progress output, and process exit codes. It does not contain Bilibili API or report-generation logic.

Supported operational options include:

- `--cookie` and `--cookie-file` for authentication.
- `--database` to select the SQLite state file.
- `--restart` to remove progress for the resolved work before collecting it again.
- `--export-only` to generate reports from existing database content without network requests.
- Configurable request and retry limits where operationally useful.

Cookie values are never printed. Cookie files and local state files are excluded from version control.

### `bili_stats/models.py`

Defines normalized data structures for works, episodes, danmaku, comments, collection status, and API failures. These structures form explicit interfaces between modules.

### `bili_stats/resolver.py`

Recognizes the input type and resolves it into a normalized work:

- Normal and multi-part videos resolve through video metadata and page lists.
- Collections resolve to their member videos and pages.
- Bangumi episode and season inputs resolve to the season and its accessible episode list.

Resolution preserves source ordering and stable platform identifiers so rerunning the same input maps to the same database records.

### `bili_stats/client.py`

Owns the HTTP session, request headers, WBI key acquisition and signing, timeouts, retry policy, rate limiting, and API response validation.

Transient failures use bounded exponential backoff with jitter. HTTP 412 and rate-limit responses receive longer backoff. A shared adaptive limiter starts with bounded concurrency, reduces both request rate and concurrency after 412, 429, or repeated 5xx responses, and gradually restores throughput after sustained success. Authentication failures are reported explicitly. The client does not claim that inaccessible content was collected.

### `bili_stats/danmaku.py`

Downloads protobuf danmaku segments for each episode and parses the protobuf wire format using generated message classes backed by the `protobuf` package. It records the platform danmaku ID, text, timestamp, progress, mode, color, sender hash, and other available fields.

Records are deduplicated by stable platform identity rather than by text. Identical messages sent multiple times therefore remain distinct records and contribute correctly to text-frequency statistics.

Segment downloads use bounded concurrency while database commits advance only the contiguous completed segment frontier. A later segment may finish first, but the persisted resume cursor never skips an unfinished earlier segment.

### `bili_stats/comments.py`

Fetches all accessible top-level comment pages using the current signed cursor API. For every top-level comment with child replies, it follows the child-comment endpoint until all accessible pages are exhausted.

Comments are deduplicated by `rpid`. Stored fields include parent/root relationships, user identifiers, user names, content, creation time, like count, and episode/work ownership.

The main-comment cursor and each root comment.s child-page position are persisted independently. Interrupted child pagination resumes without restarting the main page. Main-comment cursor pages remain sequential, while child-reply streams for different root comments may run concurrently under the shared adaptive limiter; pages within one root remain ordered.

### `bili_stats/checkpoint.py`

Uses SQLite as both the collection store and resume mechanism. It owns schema creation, migrations, transactions, uniqueness constraints, cursor state, status transitions, and restart deletion.

Core records include:

- Works and episodes.
- Danmaku records and per-episode segment progress.
- Comment records, main-comment cursor progress, and child-comment progress.
- Collection attempts, completion flags, errors, and timestamps.

Writes for one fetched page or segment are transactional. Replaying a request after interruption is safe because stable identifiers have uniqueness constraints.

### `bili_stats/exporter.py`

Reads only from SQLite and creates Excel workbooks with `pandas` and `openpyxl`. It cleans unsupported control characters without altering stored source data.

Each episode gets:

- `弹幕明细.xlsx`
- `弹幕统计.xlsx`
- `完整评论.xlsx`
- `评论用户统计.xlsx`

Each work additionally gets:

- `全局弹幕统计.xlsx`
- `全局评论统计.xlsx`
- `分集概览.xlsx`

Reports state whether each source is complete, partially complete, or failed. Global reports retain episode identity where needed and aggregate frequencies across all collected episodes.

## Data Flow

1. Parse CLI options without exposing credentials.
2. Resolve the supplied identifier or URL into a normalized work and ordered episode list.
3. Upsert the work and episode metadata in SQLite.
4. For each unfinished episode, resume danmaku segment collection from its committed cursor.
5. Resume top-level comment collection from its committed cursor.
6. Resume child-comment pagination for every unfinished root comment.
7. Record source-specific completion or failure status without preventing other episodes from running.
8. Generate per-episode reports and global summaries from the database.
9. Return a nonzero exit status when required sources remain failed or partial, while preserving all usable output.

Comments belong to the Bilibili object identified by `aid`. For multi-part videos, comments are collected once at work/video scope rather than duplicated for every `cid`; exports make that ownership explicit. Danmaku remains episode/page-specific because it is identified by `cid`.

## Resume And Restart Semantics

The default behavior is automatic resume. A repeated invocation resolves the same stable identifiers and continues incomplete work.

`--restart` deletes collected records and cursors only for the resolved work, then starts it again. It does not delete unrelated works stored in the same database.

`--export-only` requires the work to exist in the selected database. It performs no HTTP calls and exports the current complete or partial state.

## Error Handling

- Connection errors, timeouts, server failures, and rate limits use bounded retries and feed the shared adaptive limiter.
- An exhausted request records a structured failure containing operation, endpoint category, status or API code, and a sanitized message.
- One failed episode does not stop remaining episodes.
- Keyboard interruption leaves the last committed page or segment recoverable.
- Invalid or expired authentication is surfaced distinctly from temporary network failure.
- Missing access, deleted content, regional restrictions, and platform limitations are reported rather than treated as empty successful results.
- Excel export failures do not destroy collected database state.

The program aims to collect all content exposed to the authenticated user through supported endpoints. It does not attempt to bypass access controls or guarantee access to content withheld by Bilibili.

## Accuracy Rules

- Protobuf is parsed structurally; binary data is never scanned with text regular expressions.
- Danmaku records are deduplicated by platform ID, not message text.
- Comment records are deduplicated by `rpid`.
- All accessible child-comment pages are requested.
- API empty results are considered completion only when the associated cursor or pagination metadata confirms the end.
- Counts in reports are derived from stored detail rows, making summaries reproducible.

## Testing

Tests run offline using fixed response fixtures and temporary SQLite databases.

Coverage includes:

- Recognition of BV identifiers, video URLs, collection URLs, `ep` inputs, and `ss` inputs.
- Resolution of normal videos, multi-part videos, collections, and bangumi seasons.
- WBI signing with a fixed clock and immutable input parameters.
- Protobuf parsing of Chinese, English, emoji, and repeated identical messages with different IDs.
- Top-level comment cursor pagination.
- Complete child-comment pagination and parent/root relationships.
- SQLite uniqueness, atomic cursor updates, interruption, replay, and automatic resume.
- Work-scoped restart without deleting unrelated tasks.
- Per-episode reports, global summaries, and completeness labels.
- Sanitized logging that never includes Cookie content.

Network integration checks may be run manually with user credentials, but automated correctness must not depend on live Bilibili behavior.

## Compatibility And Dependencies

The supported runtime is documented as a modern maintained Python 3 release. Required packages are declared in a dependency file and include:

- `requests`
- `pandas`
- `openpyxl`
- `protobuf`

The old command form remains valid through `bilibili_stats.py`, which delegates to the package CLI. Existing generated spreadsheets are left untouched.

## Out Of Scope

- Circumventing login, membership, regional, moderation, or anti-abuse controls.
- Downloading video or audio media.
- Sentiment analysis, keyword classification, or visualization beyond statistical Excel reports.
- A graphical user interface or hosted service.
