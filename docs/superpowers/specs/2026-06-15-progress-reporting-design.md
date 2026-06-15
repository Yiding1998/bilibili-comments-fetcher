# Progress Reporting Design

## Goal

Show phase-specific progress for danmaku segments, main-comment pages, child-comment roots, and Excel workbook export without corrupting concurrent terminal output.

## Behavior

- Use `tqdm>=4.66,<5` in interactive terminals.
- Fall back to start/completion log lines with counts and elapsed time when stderr is not a TTY.
- Support `--no-progress` to disable dynamic bars explicitly.
- Danmaku bars use authoritative segment totals and persisted resume position.
- Main-comment progress has no total; it shows completed pages and collected records.
- Child-comment progress uses the number of pending root comments and updates when one root finishes.
- Excel export uses the exact number of workbooks to be written.
- Only coordinator/main threads update progress objects.
- Exceptions and Ctrl+C close active bars while preserving committed SQLite progress.

## Architecture

`bili_stats/progress.py` defines `ProgressReporter` and task handles. Collectors and exporter accept an optional reporter and remain usable with a no-op default. The CLI owns one reporter and passes it to every phase.

## Testing

Tests use fake streams and clocks to verify known/unknown totals, resume initial values, non-TTY fallback, manual disable, postfix counters, and exception-safe closing.
