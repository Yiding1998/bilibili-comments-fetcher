# Progress Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reliable phase-specific terminal progress for collection and export.

**Architecture:** A shared reporter wraps tqdm and non-TTY logs. Existing collectors receive optional callbacks/reporters, keeping terminal concerns out of worker threads.

**Tech Stack:** Python 3.8+, tqdm, unittest.

---

### Task 1: Progress Reporter

**Files:** Create `bili_stats/progress.py`, `tests/test_progress.py`; modify dependencies.

- [ ] Write failing tests for TTY selection, non-TTY logs, initial progress, unknown totals, and close behavior.
- [ ] Implement reporter and add `tqdm>=4.66,<5` to requirements.
- [ ] Run focused tests.

### Task 2: Collection And Export Integration

**Files:** Modify `danmaku.py`, `comments.py`, `exporter.py`, `bilibili_stats.py`; add integration tests.

- [ ] Write failing tests for danmaku segment updates, main-page updates, child-root updates, and workbook updates.
- [ ] Pass one reporter from CLI and update progress only in coordinator threads.
- [ ] Add `--no-progress` and ensure exception-safe closing.
- [ ] Run focused and full tests.

### Task 3: Documentation And Live Verification

**Files:** Modify `README.md`.

- [ ] Document phase bars, non-TTY fallback, dependency, and `--no-progress`.
- [ ] Run full tests and compilation.
- [ ] Run `BV1Q9Vh6CEcC` in a TTY and verify all applicable phase displays.
