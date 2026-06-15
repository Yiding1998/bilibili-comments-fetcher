# Per-Work Database Design

## Goal

Store each default SQLite database beside its Excel reports at `Results/<work title>/bilibili_stats.sqlite3`, while retaining explicit `--database PATH` overrides.

## Runtime Resolution

For network collection without `--database`, resolve metadata first, sanitize the work title with the same naming function used by export, then open the database in that work directory. For `--export-only`, scan `Results/*/bilibili_stats.sqlite3` and select the database containing the requested `work_key`.

Explicit `--database` always wins and disables automatic path selection and migration.

## Legacy Migration

When `Results/bilibili_stats.sqlite3` exists and no explicit database is supplied, migrate every work into its own database. Copy all related work, episode, danmaku, segment, progress, comment, child-progress, and failure records using idempotent inserts. Verify per-work row counts in source and target. Delete the legacy database plus WAL/SHM sidecars only after every work verifies successfully. Any failure leaves the legacy files intact.

## Errors

Export-only reports no match or multiple matches explicitly. Unsafe/empty titles use the exporter's existing sanitized fallback. Migration can be rerun safely after interruption.

## Testing

Tests cover per-work path generation, export-only discovery, explicit override, multi-work migration, idempotent rerun, count verification, and preservation of the legacy database on failure.
