# User Activity Reports Design

## Goal

Add stable user-activity rankings to the existing Excel export and standardize all future runtime artifacts under `Results/`. Real integration verification uses `BV1Q9Vh6CEcC`.

## Identity And Grouping

- Danmaku users are grouped by Bilibili's available `sender_hash`; no username reverse lookup is attempted.
- Comment users are grouped by `user_mid`. The displayed username is the most recent non-empty username by comment time, with deterministic fallback when times match.
- Empty identity values remain reportable under an explicit unknown label rather than being silently dropped.

## Reports

Each episode directory adds `弹幕用户排行.xlsx` with columns: `排名`, `发送者哈希`, `弹幕次数`, `弹幕内容`.

The work directory adds:

- `全局弹幕用户排行.xlsx` with the same columns across all episodes.
- `评论用户排行.xlsx` with columns: `排名`, `用户MID`, `用户名`, `评论次数`, `评论内容`.

Rows sort by count descending and identity ascending for deterministic ties. Content remains in collection order, includes repeated sends/comments, and is joined by newlines in one cell per user. Values exceeding Excel's 32,767-character cell limit are truncated with an explicit marker.

## Paths

- Default Excel output root: `Results/`.
- Default SQLite database: `Results/bilibili_stats.sqlite3`.
- Explicit `--output-dir` and `--database` continue to override defaults.

## Architecture

Pure aggregation helpers transform stored detail rows into report rows. The exporter calls these helpers for per-episode and global reports. Collection and database schemas do not change, so an existing database can generate the new reports with `--export-only`.

## Testing

Offline tests cover count ordering, deterministic ties, duplicate content retention, comment grouping by MID, latest-name selection, unknown identities, newline joining, Excel length truncation, file creation, and the new CLI defaults.

The live smoke command is:

```bash
python3 bilibili_stats.py BV1Q9Vh6CEcC --cookie-file cookie.txt
```

All resulting database and report files must be under `Results/`.
