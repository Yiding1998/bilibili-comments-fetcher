# Per-Work Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move default SQLite state into each work's report directory and safely migrate the existing shared database.

**Architecture:** Add pure database-path discovery and a transactional/idempotent migration module. Refactor CLI startup so metadata resolution precedes default repository creation, while explicit paths retain current behavior.

**Tech Stack:** Python 3.8+, sqlite3, pathlib, unittest.

---

### Task 1: Path Resolution And Discovery

**Files:** Create `bili_stats/database_paths.py`; create `tests/test_database_paths.py`.

- [ ] Write failing tests for sanitized work paths, unique export-only discovery, missing/duplicate matches, and explicit override.
- [ ] Run focused tests and verify RED.
- [ ] Implement path helpers using `exporter.safe_name` and read-only work-key checks.
- [ ] Run focused tests and verify GREEN.

### Task 2: Legacy Multi-Work Migration

**Files:** Create `bili_stats/migration.py`; create `tests/test_migration.py`.

- [ ] Seed a shared database with two works and related rows; write failing migration tests.
- [ ] Implement idempotent per-work copying, count verification, and delete-after-all-success.
- [ ] Add a forced-failure test proving the legacy database remains.
- [ ] Run focused tests and verify GREEN.

### Task 3: CLI Integration And Documentation

**Files:** Modify `bilibili_stats.py`, `README.md`, and default-path tests.

- [ ] Write failing CLI behavior tests for explicit override and default per-work paths.
- [ ] Refactor default network and export-only flows; invoke migration before automatic selection.
- [ ] Update README directory layout, migration behavior, discovery, and override semantics.
- [ ] Run full tests and compilation.
- [ ] Migrate the real `Results/bilibili_stats.sqlite3`, verify source/target counts, confirm old database removal, and export `BV1Q9Vh6CEcC` from its work-local database.
